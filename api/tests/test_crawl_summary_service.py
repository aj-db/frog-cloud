"""Unit tests for the crawl comparison summary service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


from app.models import CrawlJob, JobExecutor, JobStatus
from app.schemas import ExactStatusCodeCount, IssueTypeCount
from app.services.crawl_summary import (
    _find_previous_job,
    _issue_type_count_rows,
    _status_code_counts,
    build_comparison_summary,
)


def _make_job(
    *,
    tenant_id: uuid.UUID | None = None,
    profile_id: uuid.UUID | None = None,
    target_url: str = "https://example.com",
    status: JobStatus = JobStatus.complete,
    urls_crawled: int = 50,
    created_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> CrawlJob:
    job = MagicMock(spec=CrawlJob)
    job.id = uuid.uuid4()
    job.tenant_id = tenant_id or uuid.uuid4()
    job.profile_id = profile_id or uuid.uuid4()
    job.target_url = target_url
    job.status = status
    job.urls_crawled = urls_crawled
    job.executor = JobExecutor.gce
    job.progress_pct = 100.0
    job.error = None
    job.artifact_prefix = None
    job.started_at = None
    job.completed_at = completed_at or datetime.now(timezone.utc)
    job.created_at = created_at or datetime.now(timezone.utc)
    job.updated_at = datetime.now(timezone.utc)
    job.last_heartbeat_at = None
    job.max_urls = None
    job.status_message = None
    return job


def test_no_previous_crawl_returns_none_previous():
    db = MagicMock()
    job = _make_job()

    db.execute.return_value.scalar_one_or_none.return_value = None
    db.execute.return_value.scalar_one.side_effect = [
        42.5,  # avg response time
        3,  # issues count
    ]
    db.execute.return_value.all.return_value = []

    with patch("app.services.crawl_summary._find_previous_job", return_value=None):
        with patch("app.services.crawl_summary._build_aggregates") as mock_agg:
            from app.schemas import (
                CrawlSnapshotAggregates,
                IndexabilityDistribution,
                SitemapCoverage,
                StatusCodeDistribution,
            )

            mock_agg.return_value = CrawlSnapshotAggregates(
                job_id=str(job.id),
                target_url=job.target_url,
                completed_at=job.completed_at,
                urls_crawled=job.urls_crawled,
                avg_response_time_ms=42.5,
                issues_count=3,
                issue_type_counts=[IssueTypeCount(issue_type="status_200", count=2)],
                status_codes=StatusCodeDistribution(),
                status_code_counts=[ExactStatusCodeCount(status_code=200, count=2)],
                indexability=IndexabilityDistribution(),
                sitemap_coverage=SitemapCoverage(),
            )
            summary = build_comparison_summary(db, job)

    assert summary.current.job_id == str(job.id)
    assert summary.previous is None
    assert summary.new_issue_types == []
    assert summary.resolved_issue_types == []
    assert summary.issue_type_deltas == []
    assert summary.current.issue_type_counts[0].issue_type == "status_200"
    assert summary.current.status_code_counts[0].status_code == 200


def test_with_previous_crawl_computes_deltas():
    from app.schemas import (
        CrawlSnapshotAggregates,
        IndexabilityDistribution,
        SitemapCoverage,
        StatusCodeDistribution,
    )

    tenant_id = uuid.uuid4()
    profile_id = uuid.uuid4()

    current_job = _make_job(
        tenant_id=tenant_id,
        profile_id=profile_id,
        urls_crawled=100,
        created_at=datetime(2026, 4, 8, tzinfo=timezone.utc),
    )
    prev_job = _make_job(
        tenant_id=tenant_id,
        profile_id=profile_id,
        urls_crawled=80,
        created_at=datetime(2026, 4, 7, tzinfo=timezone.utc),
    )

    db = MagicMock()

    current_agg = CrawlSnapshotAggregates(
        job_id=str(current_job.id),
        target_url=current_job.target_url,
        completed_at=current_job.completed_at,
        urls_crawled=100,
        avg_response_time_ms=150.0,
        issues_count=5,
        issue_type_counts=[
            IssueTypeCount(issue_type="missing_alt", count=3),
            IssueTypeCount(issue_type="duplicate_title", count=2),
        ],
        status_codes=StatusCodeDistribution(status_2xx=90, status_4xx=10),
        status_code_counts=[
            ExactStatusCodeCount(status_code=200, count=90),
            ExactStatusCodeCount(status_code=404, count=10),
        ],
        indexability=IndexabilityDistribution(indexable=85, non_indexable=15),
        sitemap_coverage=SitemapCoverage(in_sitemap=80, not_in_sitemap=20),
    )
    prev_agg = CrawlSnapshotAggregates(
        job_id=str(prev_job.id),
        target_url=prev_job.target_url,
        completed_at=prev_job.completed_at,
        urls_crawled=80,
        avg_response_time_ms=200.0,
        issues_count=3,
        issue_type_counts=[
            IssueTypeCount(issue_type="missing_alt", count=5),
            IssueTypeCount(issue_type="broken_link", count=1),
        ],
        status_codes=StatusCodeDistribution(status_2xx=70, status_4xx=10),
        status_code_counts=[
            ExactStatusCodeCount(status_code=200, count=70),
            ExactStatusCodeCount(status_code=404, count=10),
        ],
        indexability=IndexabilityDistribution(indexable=65, non_indexable=15),
        sitemap_coverage=SitemapCoverage(in_sitemap=60, not_in_sitemap=20),
    )

    with (
        patch("app.services.crawl_summary._find_previous_job", return_value=prev_job),
        patch(
            "app.services.crawl_summary._build_aggregates",
            side_effect=[current_agg, prev_agg],
        ),
    ):
        summary = build_comparison_summary(db, current_job)

    assert summary.current.urls_crawled == 100
    assert summary.previous is not None
    assert summary.previous.urls_crawled == 80

    assert "duplicate_title" in summary.new_issue_types
    assert "broken_link" in summary.resolved_issue_types

    delta_map = {d.issue_type: d for d in summary.issue_type_deltas}
    assert delta_map["missing_alt"].delta == -2
    assert delta_map["duplicate_title"].delta == 2
    assert delta_map["broken_link"].delta == -1


def test_tenant_isolation_in_previous_job_query():
    """The _find_previous_job query filters by tenant_id, so a different
    tenant's job should never be returned."""
    tenant_a = uuid.uuid4()
    job = _make_job(tenant_id=tenant_a)

    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.return_value = None

    result = _find_previous_job(db, job)
    assert result is None

    call_args = db.execute.call_args
    stmt = call_args[0][0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": False}))
    assert "tenant_id" in compiled


def test_issue_type_count_rows_return_sorted_models():
    db = MagicMock()
    db.execute.return_value.all.return_value = [
        SimpleNamespace(issue_type="status_404", cnt=4),
        SimpleNamespace(issue_type="missing_title", cnt=2),
    ]

    rows = _issue_type_count_rows(db, uuid.uuid4())

    assert rows == [
        IssueTypeCount(issue_type="status_404", count=4),
        IssueTypeCount(issue_type="missing_title", count=2),
    ]


def test_status_code_counts_include_exact_codes_and_unknown_bucket():
    db = MagicMock()
    db.execute.return_value.all.return_value = [
        SimpleNamespace(status_code=200, cnt=12),
        SimpleNamespace(status_code=404, cnt=3),
        SimpleNamespace(status_code=None, cnt=1),
    ]

    rows = _status_code_counts(db, uuid.uuid4())

    assert rows == [
        ExactStatusCodeCount(status_code=200, count=12),
        ExactStatusCodeCount(status_code=404, count=3),
        ExactStatusCodeCount(status_code=None, count=1),
    ]
