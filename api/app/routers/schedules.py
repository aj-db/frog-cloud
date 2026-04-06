"""Recurring crawl schedules (tenant-scoped)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from croniter import croniter
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.auth import TenantDep
from app.db import get_db
from app.models import CrawlProfile, ScheduledCrawl
from app.schemas import ScheduledCrawlCreate, ScheduledCrawlResponse, ScheduledCrawlUpdate

router = APIRouter(prefix="/schedules", tags=["schedules"])


def _validate_cron(expr: str) -> None:
    from datetime import datetime, timezone

    try:
        croniter(expr.strip(), datetime.now(timezone.utc))
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid cron expression: {e}") from e


def _validate_timezone(tz: str) -> None:
    try:
        from zoneinfo import ZoneInfo

        ZoneInfo(tz)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid timezone: {tz}") from e


@router.get("", response_model=list[ScheduledCrawlResponse])
def list_schedules(
    tenant: TenantDep,
    db: Annotated[Session, Depends(get_db)],
) -> list[ScheduledCrawl]:
    rows = db.execute(
        select(ScheduledCrawl)
        .where(ScheduledCrawl.tenant_id == tenant.id)
        .order_by(ScheduledCrawl.created_at.desc())
    ).scalars().all()
    return list(rows)


@router.post("", response_model=ScheduledCrawlResponse, status_code=status.HTTP_201_CREATED)
def create_schedule(
    body: ScheduledCrawlCreate,
    tenant: TenantDep,
    db: Annotated[Session, Depends(get_db)],
) -> ScheduledCrawl:
    _validate_cron(body.cron_expression)
    _validate_timezone(body.timezone)
    try:
        profile_uuid = UUID(body.profile_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid profile_id") from e
    profile = db.execute(
        select(CrawlProfile).where(
            and_(CrawlProfile.id == profile_uuid, CrawlProfile.tenant_id == tenant.id)
        )
    ).scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")

    row = ScheduledCrawl(
        tenant_id=tenant.id,
        profile_id=profile.id,
        target_url=body.target_url.strip(),
        cron_expression=body.cron_expression.strip(),
        timezone=body.timezone.strip(),
        is_active=body.is_active,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/{schedule_id}", response_model=ScheduledCrawlResponse)
def get_schedule(
    schedule_id: UUID,
    tenant: TenantDep,
    db: Annotated[Session, Depends(get_db)],
) -> ScheduledCrawl:
    row = db.execute(
        select(ScheduledCrawl).where(
            and_(ScheduledCrawl.id == schedule_id, ScheduledCrawl.tenant_id == tenant.id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return row


@router.patch("/{schedule_id}", response_model=ScheduledCrawlResponse)
def update_schedule(
    schedule_id: UUID,
    body: ScheduledCrawlUpdate,
    tenant: TenantDep,
    db: Annotated[Session, Depends(get_db)],
) -> ScheduledCrawl:
    row = db.execute(
        select(ScheduledCrawl).where(
            and_(ScheduledCrawl.id == schedule_id, ScheduledCrawl.tenant_id == tenant.id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    if body.cron_expression is not None:
        _validate_cron(body.cron_expression)
        row.cron_expression = body.cron_expression.strip()
    if body.timezone is not None:
        _validate_timezone(body.timezone)
        row.timezone = body.timezone.strip()
    if body.target_url is not None:
        row.target_url = body.target_url.strip()
    if body.is_active is not None:
        row.is_active = body.is_active
    if body.profile_id is not None:
        try:
            profile_uuid = UUID(body.profile_id)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid profile_id") from e
        profile = db.execute(
            select(CrawlProfile).where(
                and_(CrawlProfile.id == profile_uuid, CrawlProfile.tenant_id == tenant.id)
            )
        ).scalar_one_or_none()
        if profile is None:
            raise HTTPException(status_code=404, detail="Profile not found")
        row.profile_id = profile.id
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: UUID,
    tenant: TenantDep,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    row = db.execute(
        select(ScheduledCrawl).where(
            and_(ScheduledCrawl.id == schedule_id, ScheduledCrawl.tenant_id == tenant.id)
        )
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(row)
    db.commit()
