"""Tenant info and Clerk organization sync webhooks."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import TenantDep
from app.config import get_settings
from app.db import get_db
from app.models import Tenant
from app.schemas import TenantResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/me", response_model=TenantResponse)
def get_current_tenant_profile(tenant: TenantDep) -> Tenant:
    return tenant


def _svix_signing_secret_bytes(raw: str) -> bytes:
    if raw.startswith("whsec_"):
        return base64.b64decode(raw[6:])
    return raw.encode("utf-8")


def _verify_svix_payload(
    body: bytes,
    svix_id: str,
    svix_timestamp: str,
    svix_signature: str,
    secret: str,
) -> bool:
    """Verify Clerk/Svix webhook signature (v1)."""
    try:
        ts_int = int(svix_timestamp)
    except ValueError:
        return False
    # Reject very old timestamps (5 minute skew window handled loosely)
    import time

    if abs(time.time() - ts_int) > 300:
        return False

    secret_bytes = _svix_signing_secret_bytes(secret)
    to_sign = f"{svix_id}.{svix_timestamp}.{body.decode('utf-8')}".encode("utf-8")
    expected = hmac.new(secret_bytes, to_sign, hashlib.sha256).digest()
    expected_b64 = base64.b64encode(expected).decode("utf-8")

    for part in svix_signature.split():
        if part.startswith("v1,"):
            sig = part[3:]
            if hmac.compare_digest(sig, expected_b64):
                return True
    return False


def _upsert_tenant_from_clerk_org(db: Session, data: dict[str, Any]) -> Tenant:
    org_id = str(data.get("id", ""))
    if not org_id:
        raise HTTPException(status_code=400, detail="Missing organization id")
    name = str(data.get("name") or data.get("slug") or "Organization")
    existing = db.execute(select(Tenant).where(Tenant.clerk_org_id == org_id)).scalar_one_or_none()
    if existing:
        existing.name = name
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing
    tenant = Tenant(clerk_org_id=org_id, name=name, plan="free", settings={})
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return tenant


webhook_router = APIRouter(tags=["webhooks"])


@webhook_router.post("/webhooks/clerk", status_code=status.HTTP_204_NO_CONTENT)
async def clerk_org_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    svix_id: Annotated[str | None, Header(alias="svix-id")] = None,
    svix_timestamp: Annotated[str | None, Header(alias="svix-timestamp")] = None,
    svix_signature: Annotated[str | None, Header(alias="svix-signature")] = None,
) -> None:
    settings = get_settings()
    secret = settings.clerk_webhook_secret
    if not secret:
        logger.error("CLERK_WEBHOOK_SECRET not configured")
        raise HTTPException(status_code=503, detail="Webhooks not configured")

    body = await request.body()
    if not svix_id or not svix_timestamp or not svix_signature:
        raise HTTPException(status_code=400, detail="Missing Svix headers")

    if not _verify_svix_payload(body, svix_id, svix_timestamp, svix_signature, secret):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="Invalid JSON") from e

    event_type = payload.get("type")
    data = payload.get("data") or {}

    if event_type in (
        "organization.created",
        "organization.updated",
        "organizationMembership.created",
    ):
        org = data.get("organization") or data
        if isinstance(org, dict) and org.get("id"):
            _upsert_tenant_from_clerk_org(db, org)
        elif event_type == "organizationMembership.created":
            nested = data.get("organization")
            if isinstance(nested, dict) and nested.get("id"):
                _upsert_tenant_from_clerk_org(db, nested)

    elif event_type == "organization.deleted":
        org_id = str(data.get("id", ""))
        if org_id:
            row = db.execute(select(Tenant).where(Tenant.clerk_org_id == org_id)).scalar_one_or_none()
            if row:
                db.delete(row)
                db.commit()

    return None
