"""Paginated crawl results, exports, issues, and links."""

from __future__ import annotations

import csv
import io
import json
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import Integer, and_, exists, func, or_, select
from sqlalchemy.orm import Session

from app.auth import TenantDep
from app.db import get_db
from app.models import CrawlIssue, CrawlJob, CrawlLink, CrawlPage
from app.schemas import (
    CrawlComparisonSummary,
    CrawlIssueResponse,
    CrawlLinkResponse,
    CrawlPageResponse,
    PageFilterRule,
    PaginatedResponse,
)
from app.services.crawl_summary import build_comparison_summary

router = APIRouter(tags=["results"])

SORT_FIELDS = frozenset({"address", "status_code", "word_count", "response_time", "crawl_depth"})

# ---------------------------------------------------------------------------
# Dynamic filter engine
# ---------------------------------------------------------------------------

FILTERABLE_FIELDS: dict[str, tuple[str, str]] = {
    # field_key -> (CrawlPage attribute, type)
    "address":                ("address", "string"),
    "title":                  ("title", "string"),
    "meta_description":       ("meta_description", "string"),
    "h1":                     ("h1", "string"),
    "canonical":              ("canonical", "string"),
    "canonical_link_element": ("canonical_link_element", "string"),
    "meta_robots":            ("meta_robots", "string"),
    "x_robots_tag":           ("x_robots_tag", "string"),
    "pagination_status":      ("pagination_status", "string"),
    "content_type":           ("content_type", "string"),
    "http_version":           ("http_version", "string"),
    "redirect_url":           ("redirect_url", "string"),
    "indexability":           ("indexability", "string"),
    "status_code":            ("status_code", "number"),
    "word_count":             ("word_count", "number"),
    "crawl_depth":            ("crawl_depth", "number"),
    "response_time":          ("response_time", "number"),
    "size_bytes":             ("size_bytes", "number"),
    "inlinks":                ("inlinks", "number"),
    "outlinks":               ("outlinks", "number"),
    "link_score":             ("link_score", "number"),
    "in_sitemap":             ("in_sitemap", "boolean"),
}

STRING_OPS = frozenset({
    "contains", "not_contains", "equals", "not_equals",
    "starts_with", "ends_with", "is_empty", "is_not_empty", "regex",
})
NUMBER_OPS = frozenset({
    "eq", "neq", "gt", "gte", "lt", "lte", "is_empty", "is_not_empty",
})
BOOLEAN_OPS = frozenset({"is_true", "is_false", "is_empty"})

PSEUDO_FIELDS = frozenset({"has_issues", "issue_type"})


def _rule_to_clause(rule: PageFilterRule, job_id: UUID):
    """Convert a single filter rule into a SQLAlchemy expression."""

    if rule.field in PSEUDO_FIELDS:
        return _pseudo_field_clause(rule, job_id)

    spec = FILTERABLE_FIELDS.get(rule.field)
    if spec is None:
        raise HTTPException(status_code=400, detail=f"Unknown filter field: {rule.field}")

    attr_name, ftype = spec
    col = getattr(CrawlPage, attr_name)

    if ftype == "string":
        return _string_clause(col, rule.op, rule.value)
    if ftype == "number":
        return _number_clause(col, rule.op, rule.value)
    if ftype == "boolean":
        return _boolean_clause(col, rule.op)

    raise HTTPException(status_code=400, detail=f"Unknown field type for {rule.field}")


def _string_clause(col, op: str, value: str):
    if op not in STRING_OPS:
        raise HTTPException(status_code=400, detail=f"Invalid string operator: {op}")
    if op == "contains":
        return col.ilike(f"%{value}%")
    if op == "not_contains":
        return ~col.ilike(f"%{value}%") | col.is_(None)
    if op == "equals":
        return col == value
    if op == "not_equals":
        return (col != value) | col.is_(None)
    if op == "starts_with":
        return col.ilike(f"{value}%")
    if op == "ends_with":
        return col.ilike(f"%{value}")
    if op == "is_empty":
        return col.is_(None) | (col == "")
    if op == "is_not_empty":
        return col.isnot(None) & (col != "")
    if op == "regex":
        return col.op("~*")(value)
    raise HTTPException(status_code=400, detail=f"Unhandled string operator: {op}")


def _number_clause(col, op: str, value: str):
    if op not in NUMBER_OPS:
        raise HTTPException(status_code=400, detail=f"Invalid number operator: {op}")
    if op == "is_empty":
        return col.is_(None)
    if op == "is_not_empty":
        return col.isnot(None)
    try:
        v = float(value)
        if v == int(v):
            v = int(v)
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid number value: {value}") from e
    if op == "eq":
        return col == v
    if op == "neq":
        return (col != v) | col.is_(None)
    if op == "gt":
        return col > v
    if op == "gte":
        return col >= v
    if op == "lt":
        return col < v
    if op == "lte":
        return col <= v
    raise HTTPException(status_code=400, detail=f"Unhandled number operator: {op}")


def _boolean_clause(col, op: str):
    if op not in BOOLEAN_OPS:
        raise HTTPException(status_code=400, detail=f"Invalid boolean operator: {op}")
    if op == "is_true":
        return col.is_(True)
    if op == "is_false":
        return col.is_(False)
    if op == "is_empty":
        return col.is_(None)
    raise HTTPException(status_code=400, detail=f"Unhandled boolean operator: {op}")


def _pseudo_field_clause(rule: PageFilterRule, job_id: UUID):
    if rule.field == "has_issues":
        sub = exists().where(
            and_(CrawlIssue.job_id == job_id, CrawlIssue.page_id == CrawlPage.id)
        )
        if rule.op == "is_true":
            return sub
        return ~sub

    if rule.field == "issue_type":
        sub = exists().where(
            and_(
                CrawlIssue.job_id == job_id,
                CrawlIssue.page_id == CrawlPage.id,
                CrawlIssue.issue_type == rule.value,
            )
        )
        if rule.op == "not_equals":
            return ~sub
        return sub

    raise HTTPException(status_code=400, detail=f"Unknown pseudo-field: {rule.field}")


def _parse_filter_rules(raw: str | None) -> list[PageFilterRule]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail="Invalid filters JSON") from e
    if not isinstance(data, list):
        raise HTTPException(status_code=400, detail="filters must be a JSON array")
    rules: list[PageFilterRule] = []
    for item in data:
        try:
            rules.append(PageFilterRule.model_validate(item))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid filter rule: {e}") from e
    return rules


def _apply_dynamic_filters(
    stmt,
    job_id: UUID,
    rules: list[PageFilterRule],
    logic: str = "and",
):
    stmt = stmt.where(CrawlPage.job_id == job_id)
    if not rules:
        return stmt
    clauses = [_rule_to_clause(r, job_id) for r in rules]
    if logic == "or":
        stmt = stmt.where(or_(*clauses))
    else:
        stmt = stmt.where(and_(*clauses))
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
    filters: Annotated[str | None, Query()] = None,
    filter_logic: Annotated[Literal["and", "or"], Query()] = "and",
) -> PaginatedResponse[CrawlPageResponse]:
    _job_for_tenant(db, tenant.id, job_id)
    if sort not in SORT_FIELDS:
        raise HTTPException(status_code=400, detail="Invalid sort field")

    rules = _parse_filter_rules(filters)

    count_stmt = select(func.count(CrawlPage.id))
    count_stmt = _apply_dynamic_filters(count_stmt, job_id, rules, filter_logic)
    total = int(db.execute(count_stmt).scalar_one())

    k1, kcol, idcol = _sort_columns(sort)
    if dir == "asc":
        order = (k1.asc(), kcol.asc().nulls_last(), idcol.asc())
    else:
        order = (k1.desc(), kcol.desc().nulls_last(), idcol.desc())

    q = select(CrawlPage)
    q = _apply_dynamic_filters(q, job_id, rules, filter_logic)
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


_DEPTH_SENTINEL = 2_147_483_647


def _fmt_depth(v: int | None) -> str:
    if v is None or v >= _DEPTH_SENTINEL:
        return ""
    return str(v)


def _csv_row(page: CrawlPage) -> dict[str, str]:
    return {
        "address": page.address,
        "status_code": "" if page.status_code is None else str(page.status_code),
        "title": page.title or "",
        "indexability": page.indexability or "",
        "meta_description": page.meta_description or "",
        "h1": page.h1 or "",
        "canonical": page.canonical or "",
        "canonical_link_element": page.canonical_link_element or "",
        "meta_robots": page.meta_robots or "",
        "x_robots_tag": page.x_robots_tag or "",
        "pagination_status": page.pagination_status or "",
        "content_type": page.content_type or "",
        "http_version": page.http_version or "",
        "redirect_url": page.redirect_url or "",
        "in_sitemap": "" if page.in_sitemap is None else ("Yes" if page.in_sitemap else "No"),
        "word_count": "" if page.word_count is None else str(page.word_count),
        "crawl_depth": _fmt_depth(page.crawl_depth),
        "response_time": "" if page.response_time is None else str(page.response_time),
        "size_bytes": "" if page.size_bytes is None else str(page.size_bytes),
        "inlinks": "" if page.inlinks is None else str(page.inlinks),
        "outlinks": "" if page.outlinks is None else str(page.outlinks),
        "link_score": "" if page.link_score is None else str(page.link_score),
    }


@router.get("/{job_id}/pages/export")
def export_pages_csv(
    job_id: UUID,
    tenant: TenantDep,
    db: Annotated[Session, Depends(get_db)],
    format: Annotated[str, Query()] = "csv",
    filters: Annotated[str | None, Query()] = None,
    filter_logic: Annotated[Literal["and", "or"], Query()] = "and",
) -> StreamingResponse:
    if format.lower() != "csv":
        raise HTTPException(status_code=400, detail="Only format=csv is supported")

    _job_for_tenant(db, tenant.id, job_id)
    rules = _parse_filter_rules(filters)
    q = select(CrawlPage)
    q = _apply_dynamic_filters(q, job_id, rules, filter_logic)
    q = q.order_by(CrawlPage.address.asc(), CrawlPage.id.asc())

    fieldnames = [
        "address",
        "status_code",
        "title",
        "indexability",
        "meta_description",
        "h1",
        "canonical",
        "canonical_link_element",
        "meta_robots",
        "x_robots_tag",
        "pagination_status",
        "content_type",
        "http_version",
        "redirect_url",
        "in_sitemap",
        "word_count",
        "crawl_depth",
        "response_time",
        "size_bytes",
        "inlinks",
        "outlinks",
        "link_score",
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


@router.get("/{job_id}/summary", response_model=CrawlComparisonSummary)
def get_crawl_summary(
    job_id: UUID,
    tenant: TenantDep,
    db: Annotated[Session, Depends(get_db)],
    previous_job_id: Annotated[UUID | None, Query()] = None,
) -> CrawlComparisonSummary:
    job = _job_for_tenant(db, tenant.id, job_id)
    if job.status not in ("complete", "loading"):
        raise HTTPException(
            status_code=409,
            detail="Summary is only available for completed crawls",
        )
    return build_comparison_summary(db, job, previous_job_id=previous_job_id)
