"""Crawl job lifecycle API."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session

from app.auth import TenantDep
from app.config import get_settings
from app.db import get_db
from app.models import CrawlJob, CrawlProfile, JobExecutor, JobStatus
from app.request_urls import externalize_url
from app.schemas import (
    CrawlJobCreate,
    CrawlJobCreateAccepted,
    CrawlJobListEnvelope,
    CrawlJobListResponse,
    CrawlJobResponse,
    IssueTrendResponse,
)
from app.services.crawl_summary import build_issues_trend
from crawler.executor import enqueue_job_execution
from crawler.ssrf import UnsafeUrlError, validate_public_http_url

router = APIRouter(prefix="/crawls", tags=["crawls"])


def _executor_for_request() -> JobExecutor:
    settings = get_settings()
    return JobExecutor(settings.executor_backend)


def _dispatch_job(job_id: UUID, executor: JobExecutor, request: Request) -> None:
    try:
        enqueue_job_execution(
            job_id,
            executor,
            launch_url=(
                externalize_url(request.url_for("internal_launch_worker"), request.headers)
                if executor == JobExecutor.gce
                else None
            ),
        )
    except (RuntimeError, ValueError) as e:
        raise HTTPException(status_code=503, detail=str(e)) from e


@router.post("", response_model=CrawlJobCreateAccepted, status_code=status.HTTP_202_ACCEPTED)
def create_crawl(
    body: CrawlJobCreate,
    request: Request,
    tenant: TenantDep,
    db: Annotated[Session, Depends(get_db)],
) -> CrawlJobCreateAccepted:
    try:
        validate_public_http_url(body.target_url)
    except UnsafeUrlError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        profile_uuid = UUID(body.profile_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid profile_id") from e

    profile = db.execute(
        select(CrawlProfile).where(and_(CrawlProfile.id == profile_uuid, CrawlProfile.tenant_id == tenant.id))
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    executor = _executor_for_request()
    job = CrawlJob(
        tenant_id=tenant.id,
        profile_id=profile.id,
        target_url=body.target_url.strip(),
        max_urls=body.max_urls,
        status=JobStatus.queued,
        executor=executor,
        artifact_prefix=f"tenants/{tenant.id}/jobs/",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    _dispatch_job(job.id, executor, request)

    return CrawlJobCreateAccepted(job_id=str(job.id), status="queued")


@router.get("", response_model=CrawlJobListEnvelope)
def list_crawls(
    tenant: TenantDep,
    db: Annotated[Session, Depends(get_db)],
    cursor: Annotated[str | None, Query(description="Opaque pagination cursor (job id)")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    target_url: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
) -> CrawlJobListEnvelope:
    q = select(CrawlJob).where(CrawlJob.tenant_id == tenant.id).order_by(CrawlJob.created_at.desc(), CrawlJob.id.desc())
    if target_url:
        q = q.where(CrawlJob.target_url == target_url)
    if status:
        q = q.where(CrawlJob.status == status)

    if cursor:
        try:
            cur_uuid = UUID(cursor)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid cursor") from None
        ref = db.get(CrawlJob, cur_uuid)
        if ref is None or ref.tenant_id != tenant.id:
            raise HTTPException(status_code=400, detail="Invalid cursor")
        q = q.where(
            or_(
                CrawlJob.created_at < ref.created_at,
                and_(CrawlJob.created_at == ref.created_at, CrawlJob.id < ref.id),
            )
        )
    rows = list(db.execute(q.limit(limit + 1)).scalars().all())
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]
    next_cursor: str | None = str(rows[-1].id) if has_more and rows else None
    return CrawlJobListEnvelope(
        items=[CrawlJobListResponse.model_validate(r) for r in rows],
        next_cursor=next_cursor,
    )


@router.get("/issues-trend", response_model=IssueTrendResponse)
def get_issues_trend(
    tenant: TenantDep,
    db: Annotated[Session, Depends(get_db)],
) -> IssueTrendResponse:
    return build_issues_trend(db, tenant.id)


@router.get("/{job_id}", response_model=CrawlJobResponse)
def get_crawl(
    job_id: UUID,
    tenant: TenantDep,
    db: Annotated[Session, Depends(get_db)],
) -> CrawlJob:
    job = db.execute(
        select(CrawlJob).where(and_(CrawlJob.id == job_id, CrawlJob.tenant_id == tenant.id))
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post(
    "/{job_id}/retry",
    response_model=CrawlJobCreateAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_crawl(
    job_id: UUID,
    request: Request,
    tenant: TenantDep,
    db: Annotated[Session, Depends(get_db)],
) -> CrawlJobCreateAccepted:
    old = db.execute(
        select(CrawlJob).where(and_(CrawlJob.id == job_id, CrawlJob.tenant_id == tenant.id))
    ).scalar_one_or_none()
    if old is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if old.status != JobStatus.failed:
        raise HTTPException(status_code=409, detail="Only failed jobs can be retried")

    executor = old.executor
    new_job = CrawlJob(
        tenant_id=tenant.id,
        profile_id=old.profile_id,
        target_url=old.target_url,
        max_urls=old.max_urls,
        status=JobStatus.queued,
        executor=executor,
        artifact_prefix=f"tenants/{tenant.id}/jobs/",
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    _dispatch_job(new_job.id, executor, request)

    return CrawlJobCreateAccepted(job_id=str(new_job.id), status="queued")


_TERMINAL_STATUSES = frozenset({JobStatus.complete, JobStatus.failed, JobStatus.cancelled})


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_crawl(
    job_id: UUID,
    tenant: TenantDep,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    job = db.execute(
        select(CrawlJob).where(and_(CrawlJob.id == job_id, CrawlJob.tenant_id == tenant.id))
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status not in _TERMINAL_STATUSES:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete a job in '{job.status.value}' state",
        )
    db.execute(delete(CrawlJob).where(CrawlJob.id == job_id))
    db.commit()


@router.post(
    "/{job_id}/duplicate",
    response_model=CrawlJobCreateAccepted,
    status_code=status.HTTP_202_ACCEPTED,
)
def duplicate_crawl(
    job_id: UUID,
    request: Request,
    tenant: TenantDep,
    db: Annotated[Session, Depends(get_db)],
) -> CrawlJobCreateAccepted:
    old = db.execute(
        select(CrawlJob).where(and_(CrawlJob.id == job_id, CrawlJob.tenant_id == tenant.id))
    ).scalar_one_or_none()
    if old is None:
        raise HTTPException(status_code=404, detail="Job not found")

    executor = _executor_for_request()
    new_job = CrawlJob(
        tenant_id=tenant.id,
        profile_id=old.profile_id,
        target_url=old.target_url,
        max_urls=old.max_urls,
        status=JobStatus.queued,
        executor=executor,
        artifact_prefix=f"tenants/{tenant.id}/jobs/",
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    _dispatch_job(new_job.id, executor, request)

    return CrawlJobCreateAccepted(job_id=str(new_job.id), status="queued")
