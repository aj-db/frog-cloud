"""Clerk JWT verification and tenant resolution."""

from __future__ import annotations

import logging
import time
from typing import Annotated, Any
from urllib.parse import urlparse

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwk, jwt
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import Tenant

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)

# JWKS cache: url -> (fetched_at_epoch, keys_by_kid)
_jwks_cache: dict[str, tuple[float, dict[str, dict[str, Any]]]] = {}
_JWKS_TTL_SEC = 300


def _jwks_url_for_issuer(iss: str) -> str:
    base = iss.rstrip("/")
    return f"{base}/.well-known/jwks.json"


async def _fetch_jwks(url: str) -> dict[str, dict[str, Any]]:
    now = time.time()
    cached = _jwks_cache.get(url)
    if cached and now - cached[0] < _JWKS_TTL_SEC:
        return cached[1]

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        body = resp.json()

    keys: dict[str, dict[str, Any]] = {}
    for key in body.get("keys", []):
        kid = key.get("kid")
        if kid:
            keys[kid] = key
    _jwks_cache[url] = (now, keys)
    return keys


def _verify_sync(token: str, jwks_keys: dict[str, dict[str, Any]], issuer: str) -> dict[str, Any]:
    headers = jwt.get_unverified_header(token)
    kid = headers.get("kid")
    alg = headers.get("alg") or "RS256"
    if not kid or kid not in jwks_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token signing key",
        )
    key = jwk.construct(jwks_keys[kid], algorithm=alg)
    try:
        return jwt.decode(
            token,
            key,
            algorithms=[alg],
            issuer=issuer,
            options={"verify_aud": False},
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        ) from e


def extract_org_id(claims: dict[str, Any]) -> str | None:
    """Resolve active Clerk organization id from JWT claims."""
    if org := claims.get("org_id"):
        return str(org)
    if org := claims.get("organization_id"):
        return str(org)
    nested_o = claims.get("o")
    if isinstance(nested_o, dict) and nested_o.get("id"):
        return str(nested_o["id"])
    # Some Clerk templates use orgs_role / org_slug without id in JWT — not supported here
    return None


async def verify_clerk_jwt(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        unverified = jwt.get_unverified_claims(token)
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        ) from e

    issuer = unverified.get("iss")
    if not issuer or not isinstance(issuer, str):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing issuer",
        )

    parsed = urlparse(issuer)
    if parsed.scheme not in ("https", "http"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid issuer scheme",
        )

    if settings.clerk_jwks_url:
        jwks_url = settings.clerk_jwks_url
    else:
        jwks_url = _jwks_url_for_issuer(issuer)

    try:
        keys = await _fetch_jwks(jwks_url)
        return _verify_sync(token, keys, issuer)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("JWKS fetch or verify failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service unavailable",
        ) from e


async def get_claims_optional(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> dict[str, Any] | None:
    if creds is None or creds.scheme.lower() != "bearer":
        return None
    return await verify_clerk_jwt(creds.credentials)


async def get_claims_required(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> dict[str, Any]:
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    return await verify_clerk_jwt(creds.credentials)


async def get_current_tenant(
    claims: Annotated[dict[str, Any], Depends(get_claims_required)],
    db: Annotated[Session, Depends(get_db)],
) -> Tenant:
    org_id = extract_org_id(claims)
    if not org_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No active organization in token; select an organization in Clerk.",
        )
    row = db.execute(select(Tenant).where(Tenant.clerk_org_id == org_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found for this organization; complete onboarding or webhook sync.",
        )
    return row


TenantDep = Annotated[Tenant, Depends(get_current_tenant)]
