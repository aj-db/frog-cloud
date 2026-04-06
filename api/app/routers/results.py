"""Paginated crawl results, exports, issues, and links."""

from __future__ import annotations

import csv
import io
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import Integer, and_, exists, func, or_, select
from sqlalchemy.orm import Session

from app.auth import TenantDep
from app.db import get_db
from app.models import CrawlIssue, CrawlJob, CrawlLink, CrawlPage
from app.schemas import CrawlIssueResponse, CrawlLinkResponse, CrawlPageResponse, PaginatedResponse

router = APIRouter(tags=["results"])

SORT_FIELDS = frozenset({"address", "status_code", "word_count", "response_time", "crawl_depth"})


def _job_for_tenant(db: Session, tenant_id: UUID, job_id: UUID) -> CrawlJob:
    job = db.execute(
        select(CrawlJob).where(and_(CrawlJob.id == job_id, CrawlJob.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


def _parse_status_filter(raw: str | None) -> tuple[int | None, int | None]:
    if raw is None or raw == "":
        return None, None
    r = raw.strip().lower()
    if r == "4xx":
        return 400, 499
    if r == "5xx":
        return 500, 599
    if r == "3xx":
        return 300, 399
    if r == "2xx":
        return 200, 299
    try:
        v = int(r)
        return v, v
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid status_code filter") from e


def _apply_page_filters(
    stmt,
    job_id: UUID,
    *,
    status_lo: int | None,
    status_hi: int | None,
    indexability: str | None,
    content_type: str | None,
    has_issues: bool | None,
    search: str | None,
):
    stmt = stmt.where(CrawlPage.job_id == job_id)
    if status_lo is not None and status_hi is not None:
        stmt = stmt.where(
            CrawlPage.status_code.isnot(None),
            CrawlPage.status_code >= status_lo,
            CrawlPage.status_code <= status_hi,
        )
    if indexability:
        stmt = stmt.where(CrawlPage.indexability == indexability)
    if content_type:
        stmt = stmt.where(CrawlPage.content_type.ilike(f"%{content_type}%"))
    if has_issues is True:
        sub = exists().where(
            and_(CrawlIssue.job_id == job_id, CrawlIssue.page_id == CrawlPage.id)
        )
        stmt = stmt.where(sub)
    elif has_issues is False:
        sub = exists().where(
            and_(CrawlIssue.job_id == job_id, CrawlIssue.page_id == CrawlPage.id)
        )
        stmt = stmt.where(~sub)
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(or_(CrawlPage.address.ilike(term), CrawlPage.title.ilike(term)))
    return stmt


def _sort_columns(sort: str):
    col = getattr(CrawlPage, sort)
    if sort == "status_code":
        return func.coalesce(col, -1).cast(Integer), col, CrawlPage.id
    if sort in ("word_count", "crawl_depth"):
        return func.coalesce(col, -1).cast(Integer), col, CrawlPage.id
    if sort == "response_time":
        return func.coalesce(col, -1.0), col, CrawlPage.id
    # address text
    return func.coalesce(col, ""), col, CrawlPage.id


def _keyset_filter(ref: CrawlPage, sort: str, dir: str):
    """Keyset (`sort_key`, `id`) relative to ref row."""
    if sort == "address":
        ra = ref.address or ""
        if dir == "asc":
            return or_(CrawlPage.address > ra, and_(CrawlPage.address == ra, CrawlPage.id > ref.id))
        return or_(CrawlPage.address < ra, and_(CrawlPage.address == ra, CrawlPage.id < ref.id))

    if sort in ("status_code", "word_count", "crawl_depth"):
        k1 = func.coalesce(getattr(CrawlPage, sort), -1).cast(Integer)
        rv = getattr(ref, sort)
        refk = -1 if rv is None else int(rv)
        if dir == "asc":
            return or_(k1 > refk, and_(k1 == refk, CrawlPage.id > ref.id))
        return or_(k1 < refk, and_(k1 == refk, CrawlPage.id < ref.id))

    if sort == "response_time":
        k1 = func.coalesce(CrawlPage.response_time, -1.0)
        rv = ref.response_time
        refk = -1.0 if rv is None else float(rv)
        if dir == "asc":
            return or_(k1 > refk, and_(k1 == refk, CrawlPage.id > ref.id))
        return or_(k1 < refk, and_(k1 == refk, CrawlPage.id < ref.id))

    raise HTTPException(status_code=400, detail="Unsupported sort")


@router.get("/{job_id}/pages", response_model=PaginatedResponse[CrawlPageResponse])
def list_pages(
    job_id: UUID,
    tenant: TenantDep,
    db: Annotated[Session, Depends(get_db)],
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    sort: Annotated[str, Query()] = "address",
    dir: Annotated[Literal["asc", "desc"], Query(alias="dir")] = "asc",
    status_code: Annotated[str | None, Query()] = None,
    indexability: Annotated[str | None, Query()] = None,
    content_type: Annotated[str | None, Query()] = None,
    has_issues: Annotated[bool | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
) -> PaginatedResponse[CrawlPageResponse]:
    _job_for_tenant(db, tenant.id, job_id)
    if sort not in SORT_FIELDS:
        raise HTTPException(status_code=400, detail="Invalid sort field")

    lo, hi = _parse_status_filter(status_code)

    count_stmt = select(func.count(CrawlPage.id))
    count_stmt = _apply_page_filters(
        count_stmt,
        job_id,
        status_lo=lo,
        status_hi=hi,
        indexability=indexability,
        content_type=content_type,
        has_issues=has_issues,
        search=search,
    )
    total = int(db.execute(count_stmt).scalar_one())

    k1, kcol, idcol = _sort_columns(sort)
    if dir == "asc":
        order = (k1.asc(), kcol.asc().nulls_last(), idcol.asc())
    else:
        order = (k1.desc(), kcol.desc().nulls_last(), idcol.desc())

    q = select(CrawlPage)
    q = _apply_page_filters(
        q,
        job_id,
        status_lo=lo,
        status_hi=hi,
        indexability=indexability,
        content_type=content_type,
        has_issues=has_issues,
        search=search,
    )
    q = q.order_by(*order)

    if cursor:
        try:
            cur_uuid = UUID(cursor)
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid cursor") from e
        ref = db.execute(select(CrawlPage).where(CrawlPage.id == cur_uuid)).scalar_one_or_none()
        if ref is None or ref.job_id != job_id:
            raise HTTPException(status_code=400, detail="Invalid cursor")
        q = q.where(_keyset_filter(ref, sort, dir))

    rows = list(db.execute(q.limit(limit + 1)).scalars().all())
    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]
    next_cursor = str(rows[-1].id) if has_more and rows else None

    return PaginatedResponse(
        items=[CrawlPageResponse.model_validate(r) for r in rows],
        next_cursor=next_cursor,
        total_count=total,
    )


def _csv_row(page: CrawlPage) -> dict[str, str]:
    return {
        "id": str(page.id),
        "address": page.address,
        "status_code": "" if page.status_code is None else str(page.status_code),
        "title": page.title or "",
        "indexability": page.indexability or "",
        "content_type": page.content_type or "",
        "word_count": "" if page.word_count is None else str(page.word_count),
        "crawl_depth": "" if page.crawl_depth is None else str(page.crawl_depth),
        "response_time": "" if page.response_time is None else str(page.response_time),
    }


@router.get("/{job_id}/pages/export")
def export_pages_csv(
    job_id: UUID,
    tenant: TenantDep,
    db: Annotated[Session, Depends(get_db)],
    format: Annotated[str, Query()] = "csv",
    status_code: Annotated[str | None, Query()] = None,
    indexability: Annotated[str | None, Query()] = None,
    content_type: Annotated[str | None, Query()] = None,
    has_issues: Annotated[bool | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
) -> StreamingResponse:
    if format.lower() != "csv":
        raise HTTPException(status_code=400, detail="Only format=csv is supported")

    _job_for_tenant(db, tenant.id, job_id)
    lo, hi = _parse_status_filter(status_code)
    q = select(CrawlPage)
    q = _apply_page_filters(
        q,
        job_id,
        status_lo=lo,
        status_hi=hi,
        indexability=indexability,
        content_type=content_type,
        has_issues=has_issues,
        search=search,
    )
    q = q.order_by(CrawlPage.address.asc(), CrawlPage.id.asc())

    fieldnames = [
        "id",
        "address",
        "status_code",
        "title",
        "indexability",
        "content_type",
        "word_count",
        "crawl_depth",
        "response_time",
    ]

    def gen():
        buf = io.StringIO()
        writer = csv.DictWriter(buf, fieldnames=fieldnames)
        writer.writeheader()
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        res = db.execute(q)
        for page in res.scalars().yield_per(500):
            writer.writerow(_csv_row(page))
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    return StreamingResponse(
        gen(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="crawl-{job_id}-pages.csv"'},
    )


@router.get("/{job_id}/issues", response_model=list[CrawlIssueResponse])
def list_issues(
    job_id: UUID,
    tenant: TenantDep,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=2000)] = 500,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CrawlIssue]:
    _job_for_tenant(db, tenant.id, job_id)
    rows = db.execute(
        select(CrawlIssue)
        .where(CrawlIssue.job_id == job_id)
        .order_by(CrawlIssue.severity.asc(), CrawlIssue.created_at.asc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()
    return list(rows)


@router.get("/{job_id}/links", response_model=list[CrawlLinkResponse])
def list_links(
    job_id: UUID,
    tenant: TenantDep,
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=5000)] = 1000,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CrawlLink]:
    _job_for_tenant(db, tenant.id, job_id)
    rows = db.execute(
        select(CrawlLink)
        .where(CrawlLink.job_id == job_id)
        .order_by(CrawlLink.source_url.asc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()
    return list(rows)
