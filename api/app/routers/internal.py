"""Authenticated internal routes for Cloud Tasks / Cloud Scheduler."""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import CrawlJob, JobExecutor, JobStatus, ScheduledCrawl
from app.request_urls import externalize_url, request_url
from app.schemas import LaunchWorkerPayload, ScheduleTriggerPayload
from crawler.executor import enqueue_job_execution
from crawler.launcher import launch_worker_vm
from crawler.ssrf import UnsafeUrlError, validate_public_http_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])


def verify_google_oidc(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    settings = get_settings()
    audience = settings.internal_oidc_audience or request_url(request)
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = id_token.verify_oauth2_token(
            token,
            google_requests.Request(),
            audience=audience,
        )
    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid OIDC token: {e}") from e
    return claims


@router.post("/launch-worker")
def internal_launch_worker(
    body: LaunchWorkerPayload,
    db: Annotated[Session, Depends(get_db)],
    _claims: Annotated[dict, Depends(verify_google_oidc)],
) -> dict[str, str]:
    try:
        jid = UUID(body.job_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid job_id") from e

    try:
        op = launch_worker_vm(db, jid)
        return {"status": "ok", "operation": op}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.post("/schedule-trigger")
def internal_schedule_trigger(
    body: ScheduleTriggerPayload,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    _claims: Annotated[dict, Depends(verify_google_oidc)],
) -> dict[str, str]:
    try:
        sid = UUID(body.schedule_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid schedule_id") from e

    sched = db.execute(select(ScheduledCrawl).where(ScheduledCrawl.id == sid)).scalar_one_or_none()
    if sched is None or not sched.is_active:
        raise HTTPException(status_code=404, detail="Schedule not found or inactive")

    try:
        validate_public_http_url(sched.target_url)
    except UnsafeUrlError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    settings = get_settings()
    executor = JobExecutor(settings.executor_backend)

    job = CrawlJob(
        tenant_id=sched.tenant_id,
        profile_id=sched.profile_id,
        target_url=sched.target_url,
        status=JobStatus.queued,
        executor=executor,
        artifact_prefix=f"tenants/{sched.tenant_id}/jobs/",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    try:
        enqueue_job_execution(
            job.id,
            executor,
            launch_url=(
                externalize_url(request.url_for("internal_launch_worker"), request.headers)
                if executor == JobExecutor.gce
                else None
            ),
        )
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    return {"status": "ok", "job_id": str(job.id)}
