"""Crawl job status transitions and heartbeat updates."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import CrawlJob, JobStatus

ALLOWED_TRANSITIONS: dict[JobStatus, frozenset[JobStatus]] = {
    JobStatus.queued: frozenset(
        {
            JobStatus.running,
            JobStatus.provisioning,
            JobStatus.failed,
            JobStatus.cancelled,
        }
    ),
    JobStatus.provisioning: frozenset({JobStatus.running, JobStatus.failed, JobStatus.cancelled}),
    JobStatus.running: frozenset({JobStatus.extracting, JobStatus.failed, JobStatus.cancelled}),
    JobStatus.extracting: frozenset({JobStatus.loading, JobStatus.failed, JobStatus.cancelled}),
    JobStatus.loading: frozenset({JobStatus.complete, JobStatus.failed, JobStatus.cancelled}),
    JobStatus.complete: frozenset(),
    JobStatus.failed: frozenset({JobStatus.queued}),
    JobStatus.cancelled: frozenset(),
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def transition_allowed(current: JobStatus, new: JobStatus) -> bool:
    return new in ALLOWED_TRANSITIONS.get(current, frozenset())


def transition_job_status(
    db: Session,
    job_id: UUID,
    *,
    from_statuses: Iterable[JobStatus] | None,
    to_status: JobStatus,
    error: str | None = None,
    progress_pct: float | None = None,
) -> bool:
    """
    Move job to `to_status` if current status is allowed and matches `from_statuses`
    (when provided). Uses row lock (PostgreSQL). Returns True if updated.
    """
    job = db.execute(select(CrawlJob).where(CrawlJob.id == job_id).with_for_update()).scalar_one_or_none()
    if job is None:
        return False
    if from_statuses is not None and job.status not in list(from_statuses):
        return False
    if not transition_allowed(job.status, to_status):
        return False

    job.status = to_status
    job.updated_at = utcnow()
    job.last_heartbeat_at = utcnow()
    if error is not None:
        job.error = error[:8000]
    if progress_pct is not None:
        job.progress_pct = progress_pct
    if to_status == JobStatus.running and job.started_at is None:
        job.started_at = utcnow()
    if to_status in (JobStatus.complete, JobStatus.failed, JobStatus.cancelled):
        job.completed_at = utcnow()

    db.add(job)
    db.commit()
    return True


def update_heartbeat(
    db: Session,
    job_id: UUID,
    progress_pct: float | None = None,
    urls_crawled: int | None = None,
    status_message: str | None = None,
) -> None:
    values: dict = {"last_heartbeat_at": utcnow(), "updated_at": utcnow()}
    if progress_pct is not None:
        values["progress_pct"] = progress_pct
    if urls_crawled is not None:
        values["urls_crawled"] = urls_crawled
    if status_message is not None:
        values["status_message"] = status_message[:512]
    db.execute(update(CrawlJob).where(CrawlJob.id == job_id).values(**values))
    db.commit()


def set_job_error(db: Session, job_id: UUID, message: str) -> None:
    db.execute(
        update(CrawlJob)
        .where(CrawlJob.id == job_id)
        .values(
            status=JobStatus.failed,
            error=message[:8000],
            completed_at=utcnow(),
            updated_at=utcnow(),
            last_heartbeat_at=utcnow(),
        )
    )
    db.commit()
