"""Cross-crawl comparison summary service."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.models import CrawlIssue, CrawlJob, CrawlPage, JobStatus
from app.schemas import (
    CrawlComparisonSummary,
    CrawlSnapshotAggregates,
    ExactStatusCodeCount,
    IndexabilityDistribution,
    IssueTrendPoint,
    IssueTrendResponse,
    IssueTypeCount,
    IssueTypeDelta,
    SitemapCoverage,
    StatusCodeDistribution,
)


def _find_previous_job(db: Session, job: CrawlJob) -> CrawlJob | None:
    stmt = (
        select(CrawlJob)
        .where(
            and_(
                CrawlJob.tenant_id == job.tenant_id,
                CrawlJob.profile_id == job.profile_id,
                CrawlJob.target_url == job.target_url,
                CrawlJob.status == JobStatus.complete,
                CrawlJob.id != job.id,
                CrawlJob.created_at < job.created_at,
            )
        )
        .order_by(CrawlJob.created_at.desc(), CrawlJob.id.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def _status_code_distribution(db: Session, job_id: UUID) -> StatusCodeDistribution:
    bucket = case(
        (and_(CrawlPage.status_code >= 200, CrawlPage.status_code < 300), "s2"),
        (and_(CrawlPage.status_code >= 300, CrawlPage.status_code < 400), "s3"),
        (and_(CrawlPage.status_code >= 400, CrawlPage.status_code < 500), "s4"),
        (and_(CrawlPage.status_code >= 500, CrawlPage.status_code < 600), "s5"),
        else_="other",
    )
    rows = db.execute(
        select(bucket.label("bucket"), func.count().label("cnt")).where(CrawlPage.job_id == job_id).group_by("bucket")
    ).all()
    dist = StatusCodeDistribution()
    for row in rows:
        b, c = row.bucket, row.cnt
        if b == "s2":
            dist.status_2xx = c
        elif b == "s3":
            dist.status_3xx = c
        elif b == "s4":
            dist.status_4xx = c
        elif b == "s5":
            dist.status_5xx = c
        else:
            dist.other = c
    return dist


def _status_code_counts(db: Session, job_id: UUID) -> list[ExactStatusCodeCount]:
    null_rank = case((CrawlPage.status_code.is_(None), 1), else_=0)
    rows = db.execute(
        select(CrawlPage.status_code, func.count().label("cnt"))
        .where(CrawlPage.job_id == job_id)
        .group_by(CrawlPage.status_code)
        .order_by(null_rank.asc(), CrawlPage.status_code.asc())
    ).all()
    return [
        ExactStatusCodeCount(status_code=row.status_code, count=row.cnt)
        for row in rows
    ]


def _indexability_distribution(db: Session, job_id: UUID) -> IndexabilityDistribution:
    rows = db.execute(
        select(CrawlPage.indexability, func.count().label("cnt"))
        .where(CrawlPage.job_id == job_id)
        .group_by(CrawlPage.indexability)
    ).all()
    dist = IndexabilityDistribution()
    for row in rows:
        val = (row.indexability or "").lower()
        if val == "indexable":
            dist.indexable = row.cnt
        else:
            dist.non_indexable += row.cnt
    return dist


def _sitemap_coverage(db: Session, job_id: UUID) -> SitemapCoverage:
    bucket = case(
        (CrawlPage.in_sitemap.is_(True), "yes"),
        (CrawlPage.in_sitemap.is_(False), "no"),
        else_="unknown",
    )
    rows = db.execute(
        select(bucket.label("bucket"), func.count().label("cnt")).where(CrawlPage.job_id == job_id).group_by("bucket")
    ).all()
    cov = SitemapCoverage()
    for row in rows:
        if row.bucket == "yes":
            cov.in_sitemap = row.cnt
        elif row.bucket == "no":
            cov.not_in_sitemap = row.cnt
        else:
            cov.unknown = row.cnt
    return cov


def _issue_type_count_rows(db: Session, job_id: UUID) -> list[IssueTypeCount]:
    rows = db.execute(
        select(CrawlIssue.issue_type, func.count().label("cnt"))
        .where(CrawlIssue.job_id == job_id)
        .group_by(CrawlIssue.issue_type)
        .order_by(func.count().desc(), CrawlIssue.issue_type.asc())
    ).all()
    return [IssueTypeCount(issue_type=row.issue_type, count=row.cnt) for row in rows]


def _build_aggregates(db: Session, job: CrawlJob) -> CrawlSnapshotAggregates:
    avg_rt = db.execute(
        select(func.avg(CrawlPage.response_time)).where(
            and_(CrawlPage.job_id == job.id, CrawlPage.response_time.isnot(None))
        )
    ).scalar_one()

    issue_type_counts = _issue_type_count_rows(db, job.id)
    issues_count = sum(item.count for item in issue_type_counts)

    return CrawlSnapshotAggregates(
        job_id=str(job.id),
        target_url=job.target_url,
        completed_at=job.completed_at,
        urls_crawled=job.urls_crawled,
        avg_response_time_ms=round(avg_rt, 1) if avg_rt is not None else None,
        issues_count=issues_count,
        issue_type_counts=issue_type_counts,
        status_codes=_status_code_distribution(db, job.id),
        status_code_counts=_status_code_counts(db, job.id),
        indexability=_indexability_distribution(db, job.id),
        sitemap_coverage=_sitemap_coverage(db, job.id),
    )


def _issue_type_counts(items: list[IssueTypeCount]) -> dict[str, int]:
    return {item.issue_type: item.count for item in items}


def build_issues_trend(db: Session, tenant_id: UUID) -> IssueTrendResponse:
    rows = db.execute(
        select(
            CrawlJob.id.label("job_id"),
            CrawlJob.completed_at,
            CrawlJob.target_url,
            CrawlIssue.issue_type,
            func.count(func.distinct(CrawlIssue.page_id)).label("url_count"),
        )
        .join(CrawlIssue, CrawlIssue.job_id == CrawlJob.id)
        .where(
            and_(
                CrawlJob.tenant_id == tenant_id,
                CrawlJob.status == JobStatus.complete,
            )
        )
        .group_by(
            CrawlJob.id,
            CrawlJob.completed_at,
            CrawlJob.target_url,
            CrawlIssue.issue_type,
        )
        .order_by(
            CrawlJob.completed_at.asc(),
            CrawlJob.id.asc(),
            CrawlIssue.issue_type.asc(),
        )
    ).all()

    points = [
        IssueTrendPoint(
            job_id=str(row.job_id),
            completed_at=row.completed_at,
            target_url=row.target_url,
            issue_type=row.issue_type,
            url_count=row.url_count,
        )
        for row in rows
    ]

    return IssueTrendResponse(
        points=points,
        issue_types=sorted({point.issue_type for point in points}),
    )


def build_comparison_summary(
    db: Session,
    job: CrawlJob,
    previous_job_id: UUID | None = None,
) -> CrawlComparisonSummary:
    current_agg = _build_aggregates(db, job)

    prev_job: CrawlJob | None = None
    if previous_job_id:
        prev_job = db.execute(
            select(CrawlJob).where(
                and_(
                    CrawlJob.id == previous_job_id,
                    CrawlJob.tenant_id == job.tenant_id,
                )
            )
        ).scalar_one_or_none()
    else:
        prev_job = _find_previous_job(db, job)

    if prev_job is None:
        return CrawlComparisonSummary(current=current_agg)

    prev_agg = _build_aggregates(db, prev_job)

    cur_issues = _issue_type_counts(current_agg.issue_type_counts)
    prev_issues = _issue_type_counts(prev_agg.issue_type_counts)

    all_types = sorted(set(cur_issues) | set(prev_issues))
    new_types = [t for t in all_types if t in cur_issues and t not in prev_issues]
    resolved_types = [t for t in all_types if t not in cur_issues and t in prev_issues]

    deltas = []
    for t in all_types:
        pc = prev_issues.get(t, 0)
        cc = cur_issues.get(t, 0)
        if cc != pc:
            deltas.append(IssueTypeDelta(issue_type=t, previous_count=pc, current_count=cc, delta=cc - pc))

    return CrawlComparisonSummary(
        current=current_agg,
        previous=prev_agg,
        new_issue_types=new_types,
        resolved_issue_types=resolved_types,
        issue_type_deltas=deltas,
    )
