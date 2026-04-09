"""Cross-crawl comparison summary service."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.models import CrawlIssue, CrawlJob, CrawlPage, JobStatus
from app.schemas import (
    CrawlComparisonSummary,
    CrawlSnapshotAggregates,
    IndexabilityDistribution,
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


def _build_aggregates(db: Session, job: CrawlJob) -> CrawlSnapshotAggregates:
    avg_rt = db.execute(
        select(func.avg(CrawlPage.response_time)).where(
            and_(CrawlPage.job_id == job.id, CrawlPage.response_time.isnot(None))
        )
    ).scalar_one()

    issues_count = db.execute(select(func.count(CrawlIssue.id)).where(CrawlIssue.job_id == job.id)).scalar_one()

    return CrawlSnapshotAggregates(
        job_id=str(job.id),
        target_url=job.target_url,
        completed_at=job.completed_at,
        urls_crawled=job.urls_crawled,
        avg_response_time_ms=round(avg_rt, 1) if avg_rt is not None else None,
        issues_count=issues_count,
        status_codes=_status_code_distribution(db, job.id),
        indexability=_indexability_distribution(db, job.id),
        sitemap_coverage=_sitemap_coverage(db, job.id),
    )


def _issue_type_counts(db: Session, job_id: UUID) -> dict[str, int]:
    rows = db.execute(
        select(CrawlIssue.issue_type, func.count().label("cnt"))
        .where(CrawlIssue.job_id == job_id)
        .group_by(CrawlIssue.issue_type)
    ).all()
    return {r.issue_type: r.cnt for r in rows}


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

    cur_issues = _issue_type_counts(db, job.id)
    prev_issues = _issue_type_counts(db, prev_job.id)

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
