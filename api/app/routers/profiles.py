"""Tenant-scoped crawl profile CRUD."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.auth import TenantDep
from app.db import get_db
from app.models import CrawlProfile
from app.schemas import CrawlProfileCreate, CrawlProfileResponse, CrawlProfileUpdate

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get("", response_model=list[CrawlProfileResponse])
def list_profiles(
    tenant: TenantDep,
    db: Annotated[Session, Depends(get_db)],
) -> list[CrawlProfile]:
    rows = (
        db.execute(select(CrawlProfile).where(CrawlProfile.tenant_id == tenant.id).order_by(CrawlProfile.name.asc()))
        .scalars()
        .all()
    )
    return list(rows)


@router.post("", response_model=CrawlProfileResponse, status_code=status.HTTP_201_CREATED)
def create_profile(
    body: CrawlProfileCreate,
    tenant: TenantDep,
    db: Annotated[Session, Depends(get_db)],
) -> CrawlProfile:
    existing = db.execute(
        select(CrawlProfile).where(and_(CrawlProfile.tenant_id == tenant.id, CrawlProfile.name == body.name))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Profile name already exists")
    row = CrawlProfile(
        tenant_id=tenant.id,
        name=body.name.strip(),
        description=body.description,
        config_path=body.config_path.strip(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/{profile_id}", response_model=CrawlProfileResponse)
def get_profile(
    profile_id: UUID,
    tenant: TenantDep,
    db: Annotated[Session, Depends(get_db)],
) -> CrawlProfile:
    row = db.execute(
        select(CrawlProfile).where(and_(CrawlProfile.id == profile_id, CrawlProfile.tenant_id == tenant.id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return row


@router.patch("/{profile_id}", response_model=CrawlProfileResponse)
def update_profile(
    profile_id: UUID,
    body: CrawlProfileUpdate,
    tenant: TenantDep,
    db: Annotated[Session, Depends(get_db)],
) -> CrawlProfile:
    row = db.execute(
        select(CrawlProfile).where(and_(CrawlProfile.id == profile_id, CrawlProfile.tenant_id == tenant.id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    if body.name is not None:
        dup = db.execute(
            select(CrawlProfile).where(
                and_(
                    CrawlProfile.tenant_id == tenant.id,
                    CrawlProfile.name == body.name,
                    CrawlProfile.id != profile_id,
                )
            )
        ).scalar_one_or_none()
        if dup:
            raise HTTPException(status_code=409, detail="Profile name already exists")
        row.name = body.name.strip()
    if body.description is not None:
        row.description = body.description
    if body.config_path is not None:
        row.config_path = body.config_path.strip()
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_profile(
    profile_id: UUID,
    tenant: TenantDep,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    row = db.execute(
        select(CrawlProfile).where(and_(CrawlProfile.id == profile_id, CrawlProfile.tenant_id == tenant.id))
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    db.delete(row)
    db.commit()
