"""Tests for the GET /{job_id}/summary endpoint."""

from __future__ import annotations


from app.schemas import (
    CrawlComparisonSummary,
    CrawlSnapshotAggregates,
    ExactStatusCodeCount,
    IndexabilityDistribution,
    IssueTypeCount,
    SitemapCoverage,
    StatusCodeDistribution,
)


def _make_summary(*, with_previous: bool = True) -> CrawlComparisonSummary:
    current = CrawlSnapshotAggregates(
        job_id="aaaa-1111",
        target_url="https://example.com",
        completed_at=None,
        urls_crawled=100,
        avg_response_time_ms=150.0,
        issues_count=5,
        issue_type_counts=[
            IssueTypeCount(issue_type="missing_title", count=3),
            IssueTypeCount(issue_type="status_404", count=2),
        ],
        status_codes=StatusCodeDistribution(status_2xx=90, status_4xx=10),
        status_code_counts=[
            ExactStatusCodeCount(status_code=200, count=90),
            ExactStatusCodeCount(status_code=404, count=10),
        ],
        indexability=IndexabilityDistribution(indexable=85, non_indexable=15),
        sitemap_coverage=SitemapCoverage(in_sitemap=80, not_in_sitemap=20),
    )
    if not with_previous:
        return CrawlComparisonSummary(current=current)

    previous = CrawlSnapshotAggregates(
        job_id="bbbb-2222",
        target_url="https://example.com",
        completed_at=None,
        urls_crawled=80,
        avg_response_time_ms=200.0,
        issues_count=3,
        issue_type_counts=[
            IssueTypeCount(issue_type="missing_title", count=1),
            IssueTypeCount(issue_type="broken_link", count=2),
        ],
        status_codes=StatusCodeDistribution(status_2xx=70, status_4xx=10),
        status_code_counts=[
            ExactStatusCodeCount(status_code=200, count=70),
            ExactStatusCodeCount(status_code=404, count=10),
        ],
        indexability=IndexabilityDistribution(indexable=65, non_indexable=15),
        sitemap_coverage=SitemapCoverage(in_sitemap=60, not_in_sitemap=20),
    )
    return CrawlComparisonSummary(
        current=current,
        previous=previous,
        new_issue_types=["duplicate_title"],
        resolved_issue_types=["broken_link"],
    )


def test_summary_schema_serializes_correctly():
    summary = _make_summary(with_previous=True)
    data = summary.model_dump()

    assert data["current"]["urls_crawled"] == 100
    assert data["previous"]["urls_crawled"] == 80
    assert data["new_issue_types"] == ["duplicate_title"]
    assert data["resolved_issue_types"] == ["broken_link"]
    assert data["current"]["issue_type_counts"][1]["issue_type"] == "status_404"
    assert data["current"]["status_code_counts"][1]["status_code"] == 404


def test_summary_without_previous_serializes_correctly():
    summary = _make_summary(with_previous=False)
    data = summary.model_dump()

    assert data["current"]["urls_crawled"] == 100
    assert data["previous"] is None
    assert data["new_issue_types"] == []
    assert data["resolved_issue_types"] == []


def test_status_code_distribution_defaults():
    dist = StatusCodeDistribution()
    assert dist.status_2xx == 0
    assert dist.status_3xx == 0
    assert dist.status_4xx == 0
    assert dist.status_5xx == 0
    assert dist.other == 0


def test_indexability_distribution_defaults():
    dist = IndexabilityDistribution()
    assert dist.indexable == 0
    assert dist.non_indexable == 0


def test_sitemap_coverage_defaults():
    cov = SitemapCoverage()
    assert cov.in_sitemap == 0
    assert cov.not_in_sitemap == 0
    assert cov.unknown == 0


def test_sitemap_coverage_serializes():
    summary = _make_summary(with_previous=True)
    data = summary.model_dump()
    assert data["current"]["sitemap_coverage"]["in_sitemap"] == 80
    assert data["current"]["sitemap_coverage"]["not_in_sitemap"] == 20
    assert data["previous"]["sitemap_coverage"]["in_sitemap"] == 60
