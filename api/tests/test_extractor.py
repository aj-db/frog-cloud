from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from uuid import uuid4

from app.models import CrawlIssue, CrawlJob, IssueSeverity, JobExecutor, JobStatus
from crawler import extractor


def test_load_crawl_artifact_uses_csv_backend_for_seospider(monkeypatch):
    captured: dict[str, object] = {}

    class FakeCrawl:
        @staticmethod
        def load(path, **kwargs):
            captured["path"] = path
            captured["kwargs"] = kwargs
            return "crawl"

    fake_module = ModuleType("screamingfrog")
    fake_module.Crawl = FakeCrawl
    monkeypatch.setitem(sys.modules, "screamingfrog", fake_module)

    result = extractor._load_crawl_artifact(
        Path("/tmp/crawl.seospider"),
        cli_path="/usr/bin/screamingfrogseospider",
    )

    assert result == "crawl"
    assert captured["path"] == "/tmp/crawl.seospider"
    assert captured["kwargs"] == {
        "cli_path": "/usr/bin/screamingfrogseospider",
        "source_type": "seospider",
        "seospider_backend": "csv",
    }


def test_load_crawl_artifact_keeps_default_loader_for_dbseospider(monkeypatch):
    captured: dict[str, object] = {}

    class FakeCrawl:
        @staticmethod
        def load(path, **kwargs):
            captured["path"] = path
            captured["kwargs"] = kwargs
            return "crawl"

    fake_module = ModuleType("screamingfrog")
    fake_module.Crawl = FakeCrawl
    monkeypatch.setitem(sys.modules, "screamingfrog", fake_module)

    result = extractor._load_crawl_artifact(
        Path("/tmp/crawl.dbseospider"),
        cli_path="/usr/bin/screamingfrogseospider",
    )

    assert result == "crawl"
    assert captured["path"] == "/tmp/crawl.dbseospider"
    assert captured["kwargs"] == {"cli_path": "/usr/bin/screamingfrogseospider"}


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    def __init__(self, job):
        self.job = job
        self.bulk_insert_calls: list[tuple[object, list[dict[str, object]]]] = []

    def execute(self, statement):
        if getattr(statement, "is_select", False):
            return _FakeResult(self.job)
        return _FakeResult(None)

    def bulk_insert_mappings(self, model, rows):
        self.bulk_insert_calls.append((model, list(rows)))

    def add(self, _obj):
        return None

    def commit(self):
        return None

    def refresh(self, _obj):
        return None


class _FakeCrawl:
    def __init__(self, rows, *, tabs=None, links=None):
        self._rows = rows
        self._tabs = tabs or {}
        self._links = links or ()

    def tab(self, name):
        if name in {"internal_all.csv", "internal_all"}:
            return iter(self._rows)
        return iter(self._tabs.get(name, ()))

    def links(self, _direction):
        return iter(self._links)


def _fake_settings(**overrides):
    """Return a SimpleNamespace that quacks like Settings for extractor reads."""
    defaults = {
        "extract_skip_orphan_issues": False,
        "extract_max_issues_per_tab": 50_000,
        "extract_max_issues_total": 500_000,
        "extract_issue_phase_timeout_seconds": 3600.0,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _patch_extraction(monkeypatch, crawl, *, settings=None):
    """Wire common monkeypatches shared by most extraction tests."""
    monkeypatch.setattr(extractor, "_load_crawl_artifact", lambda *_a, **_k: crawl)
    monkeypatch.setattr(extractor, "set_job_error", lambda *_a, **_k: None)
    monkeypatch.setattr(extractor, "transition_job_status", lambda *_a, **_k: True)
    monkeypatch.setattr(extractor, "update_heartbeat", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "crawler.extractor.get_settings",
        lambda: settings or _fake_settings(),
    )


# --- _normalize_row / _cell refactor tests ---


def test_normalize_row_lowercases_and_collapses():
    result = extractor._normalize_row({"Status-Code": 200, "Content_Type": "text/html"})
    assert result["status code"] == 200
    assert result["content type"] == "text/html"


def test_cell_uses_prenormalized_dict():
    nr = extractor._normalize_row({"Status Code": 200})
    assert extractor._cell(nr, "status code") == 200
    assert extractor._cell(nr, "missing_key") is None


# --- _row_to_page_dict tests ---


def test_row_to_page_dict_normalizes_crawl_depth_sentinel():
    sentinel = 2_147_483_647
    result = extractor._row_to_page_dict(uuid4(), {"Address": "https://example.com/", "Crawl Depth": str(sentinel)})
    assert result["crawl_depth"] is None


def test_row_to_page_dict_preserves_valid_crawl_depth():
    result = extractor._row_to_page_dict(uuid4(), {"Address": "https://example.com/", "Crawl Depth": "3"})
    assert result["crawl_depth"] == 3


def test_row_to_page_dict_handles_missing_crawl_depth():
    result = extractor._row_to_page_dict(uuid4(), {"Address": "https://example.com/"})
    assert result["crawl_depth"] is None


# --- _tab_issue_row classification tests ---


def test_tab_issue_row_uses_issue_column_not_type():
    """Prove that a numeric Type column is NOT used as issue_type."""
    job_id = uuid4()
    page_id = uuid4()
    row = {"Address": "https://example.com/", "Issue": "Missing HSTS Header", "Type": "20"}
    result = extractor._tab_issue_row(
        job_id=job_id,
        address_to_page_id={"https://example.com/": page_id},
        issue_label="Security Issue",
        row=row,
    )
    assert result["issue_type"] == "Missing HSTS Header"
    assert result["page_id"] == page_id


def test_tab_issue_row_falls_back_to_label_without_issue_column():
    """When there is no Issue column, fall back to the tab label, not 'type'."""
    job_id = uuid4()
    page_id = uuid4()
    row = {"Address": "https://example.com/", "Type": "4"}
    result = extractor._tab_issue_row(
        job_id=job_id,
        address_to_page_id={"https://example.com/": page_id},
        issue_label="Mixed Content",
        row=row,
    )
    assert result["issue_type"] == "Mixed Content"


def test_tab_issue_row_resolves_via_normalized_address():
    """Prove address normalization resolves trailing-slash mismatches."""
    job_id = uuid4()
    page_id = uuid4()
    row = {"Address": "https://example.com/about/", "Issue": "Missing H1"}
    result = extractor._tab_issue_row(
        job_id=job_id,
        address_to_page_id={"https://example.com/about": page_id},
        issue_label="Content Issue",
        row=row,
    )
    assert result["page_id"] == page_id


def test_tab_issue_row_orphan_no_match():
    """Orphan row when address cannot be resolved at all."""
    job_id = uuid4()
    row = {"Address": "https://unknown.example.com/", "Issue": "Test"}
    result = extractor._tab_issue_row(
        job_id=job_id,
        address_to_page_id={},
        issue_label="Test Label",
        row=row,
    )
    assert result["page_id"] is None


# --- heartbeat / extraction integration tests ---


def test_extract_crawl_to_postgres_emits_heartbeats_during_page_loading(monkeypatch, tmp_path):
    job = CrawlJob(
        id=uuid4(),
        tenant_id=uuid4(),
        profile_id=uuid4(),
        target_url="https://example.com",
        executor=JobExecutor.gce,
        status=JobStatus.running,
    )
    db = _FakeSession(job)
    crawl = _FakeCrawl(
        [
            {"Address": "https://example.com/"},
            {"Address": "https://example.com/about"},
            {"Address": "https://example.com/contact"},
        ]
    )
    heartbeats: list[tuple[int | None, str | None]] = []

    def _counting_monotonic(_counter=[0.0]):
        val = _counter[0]
        _counter[0] += 12.0
        return val

    monkeypatch.setattr(extractor, "_load_crawl_artifact", lambda *_args, **_kwargs: crawl)
    monkeypatch.setattr(extractor, "set_job_error", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(extractor, "transition_job_status", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        extractor,
        "update_heartbeat",
        lambda _db, _job_id, progress_pct=None, urls_crawled=None, status_message=None, commit=True: heartbeats.append(
            (urls_crawled, status_message)
        ),
    )
    monkeypatch.setattr(
        extractor,
        "time",
        SimpleNamespace(monotonic=_counting_monotonic),
        raising=False,
    )
    monkeypatch.setattr(extractor, "ISSUE_TABS", (), raising=False)
    monkeypatch.setattr(extractor, "EXTRACTION_HEARTBEAT_INTERVAL_SECONDS", 10.0, raising=False)
    monkeypatch.setattr(extractor, "CHUNK_SIZE", 10000)
    monkeypatch.setattr(
        "crawler.extractor.get_settings",
        lambda: _fake_settings(),
    )

    extractor.extract_crawl_to_postgres(
        db,
        job_id=job.id,
        tenant_id=job.tenant_id,
        artifact_path=tmp_path / "crawl.seospider",
        cli_path=None,
    )

    assert any(
        urls_crawled == 2 and message == "Loading pages into the database…" for urls_crawled, message in heartbeats
    )


def test_extract_crawl_to_postgres_derives_status_code_issues(monkeypatch, tmp_path):
    job = CrawlJob(
        id=uuid4(),
        tenant_id=uuid4(),
        profile_id=uuid4(),
        target_url="https://example.com",
        executor=JobExecutor.gce,
        status=JobStatus.running,
    )
    db = _FakeSession(job)
    crawl = _FakeCrawl(
        [
            {"Address": "https://example.com/", "Status Code": "200"},
            {"Address": "https://example.com/redirect", "Status Code": "301"},
            {"Address": "https://example.com/missing", "Status Code": "404"},
            {"Address": "https://example.com/error", "Status Code": "500"},
            {"Address": "https://example.com/no-status"},
        ]
    )

    _patch_extraction(monkeypatch, crawl)

    extractor.extract_crawl_to_postgres(
        db,
        job_id=job.id,
        tenant_id=job.tenant_id,
        artifact_path=tmp_path / "crawl.seospider",
        cli_path=None,
    )

    issue_rows = [rows for model, rows in db.bulk_insert_calls if model is CrawlIssue]

    assert len(issue_rows) == 1
    issue_map = {row["issue_type"]: row for row in issue_rows[0]}
    assert set(issue_map) == {"status_200", "status_301", "status_404", "status_500"}
    assert issue_map["status_200"]["severity"] == IssueSeverity.info
    assert issue_map["status_301"]["severity"] == IssueSeverity.warning
    assert issue_map["status_404"]["severity"] == IssueSeverity.error
    assert issue_map["status_500"]["severity"] == IssueSeverity.error
    assert all(row["page_id"] is not None for row in issue_rows[0])


def test_extract_crawl_to_postgres_streams_issue_tabs_without_report_helpers(monkeypatch, tmp_path):
    job = CrawlJob(
        id=uuid4(),
        tenant_id=uuid4(),
        profile_id=uuid4(),
        target_url="https://example.com",
        executor=JobExecutor.gce,
        status=JobStatus.running,
    )
    db = _FakeSession(job)

    class _StreamingIssueCrawl(_FakeCrawl):
        def security_issues_report(self):
            raise AssertionError("report helper should not be called")

        def canonical_issues_report(self):
            raise AssertionError("report helper should not be called")

        def hreflang_issues_report(self):
            raise AssertionError("report helper should not be called")

        def redirect_issues_report(self):
            raise AssertionError("report helper should not be called")

    crawl = _StreamingIssueCrawl(
        [{"Address": "https://example.com/", "Status Code": "200"}],
        tabs={"security_missing_hsts_header": [{"Address": "https://example.com/", "Details": "Header not present"}]},
    )

    _patch_extraction(monkeypatch, crawl)

    extractor.extract_crawl_to_postgres(
        db,
        job_id=job.id,
        tenant_id=job.tenant_id,
        artifact_path=tmp_path / "crawl.seospider",
        cli_path=None,
    )

    issue_rows = [rows for model, rows in db.bulk_insert_calls if model is CrawlIssue]
    all_rows = [row for rows in issue_rows for row in rows]
    issue_map = {row["issue_type"]: row for row in all_rows}

    assert "status_200" in issue_map
    assert "Missing HSTS Header" in issue_map
    assert issue_map["Missing HSTS Header"]["severity"] == IssueSeverity.error


def test_tab_issue_row_does_not_use_numeric_type_as_issue_type(monkeypatch, tmp_path):
    """Full integration: numeric Type column must not appear as issue_type."""
    job = CrawlJob(
        id=uuid4(),
        tenant_id=uuid4(),
        profile_id=uuid4(),
        target_url="https://example.com",
        executor=JobExecutor.gce,
        status=JobStatus.running,
    )
    db = _FakeSession(job)
    crawl = _FakeCrawl(
        [{"Address": "https://example.com/", "Status Code": "200"}],
        tabs={"security_mixed_content": [{"Address": "https://example.com/", "Type": "20", "Details": "mixed"}]},
    )

    _patch_extraction(monkeypatch, crawl)

    extractor.extract_crawl_to_postgres(
        db,
        job_id=job.id,
        tenant_id=job.tenant_id,
        artifact_path=tmp_path / "crawl.seospider",
        cli_path=None,
    )

    issue_rows = [rows for model, rows in db.bulk_insert_calls if model is CrawlIssue]
    all_rows = [row for rows in issue_rows for row in rows]
    issue_types = {row["issue_type"] for row in all_rows}
    assert "20" not in issue_types
    assert "Mixed Content" in issue_types


def test_extract_skips_orphan_issues_when_flag_enabled(monkeypatch, tmp_path):
    """With EXTRACT_SKIP_ORPHAN_ISSUES=true, orphan rows are dropped."""
    job = CrawlJob(
        id=uuid4(),
        tenant_id=uuid4(),
        profile_id=uuid4(),
        target_url="https://example.com",
        executor=JobExecutor.gce,
        status=JobStatus.running,
    )
    db = _FakeSession(job)
    crawl = _FakeCrawl(
        [{"Address": "https://example.com/", "Status Code": "200"}],
        tabs={
            "security_mixed_content": [
                {"Address": "https://unknown.example.com/", "Issue": "Mixed Content"},
            ]
        },
    )

    _patch_extraction(
        monkeypatch,
        crawl,
        settings=_fake_settings(extract_skip_orphan_issues=True),
    )

    extractor.extract_crawl_to_postgres(
        db,
        job_id=job.id,
        tenant_id=job.tenant_id,
        artifact_path=tmp_path / "crawl.seospider",
        cli_path=None,
    )

    issue_rows = [rows for model, rows in db.bulk_insert_calls if model is CrawlIssue]
    all_rows = [row for rows in issue_rows for row in rows]
    tab_issues = [r for r in all_rows if not r["issue_type"].startswith("status_")]
    assert len(tab_issues) == 0


def test_extract_keeps_orphan_issues_when_flag_disabled(monkeypatch, tmp_path):
    """With EXTRACT_SKIP_ORPHAN_ISSUES=false (default), orphan rows are kept."""
    job = CrawlJob(
        id=uuid4(),
        tenant_id=uuid4(),
        profile_id=uuid4(),
        target_url="https://example.com",
        executor=JobExecutor.gce,
        status=JobStatus.running,
    )
    db = _FakeSession(job)
    crawl = _FakeCrawl(
        [{"Address": "https://example.com/", "Status Code": "200"}],
        tabs={
            "security_mixed_content": [
                {"Address": "https://unknown.example.com/", "Issue": "Mixed Content"},
            ]
        },
    )

    _patch_extraction(
        monkeypatch,
        crawl,
        settings=_fake_settings(extract_skip_orphan_issues=False),
    )

    extractor.extract_crawl_to_postgres(
        db,
        job_id=job.id,
        tenant_id=job.tenant_id,
        artifact_path=tmp_path / "crawl.seospider",
        cli_path=None,
    )

    issue_rows = [rows for model, rows in db.bulk_insert_calls if model is CrawlIssue]
    all_rows = [row for rows in issue_rows for row in rows]
    tab_issues = [r for r in all_rows if not r["issue_type"].startswith("status_")]
    assert len(tab_issues) == 1
    assert tab_issues[0]["page_id"] is None


def test_normalize_address():
    assert extractor._normalize_address("https://Example.com/About/") == "https://example.com/about"
    assert extractor._normalize_address("https://example.com") == "https://example.com"
    assert extractor._normalize_address("/") == "/"


def test_extract_caps_issues_per_tab(monkeypatch, tmp_path):
    """Per-tab cap limits the number of issues inserted from a single tab."""
    job = CrawlJob(
        id=uuid4(),
        tenant_id=uuid4(),
        profile_id=uuid4(),
        target_url="https://example.com",
        executor=JobExecutor.gce,
        status=JobStatus.running,
    )
    db = _FakeSession(job)
    issue_rows = [{"Address": "https://example.com/", "Issue": f"Issue {i}"} for i in range(20)]
    crawl = _FakeCrawl(
        [{"Address": "https://example.com/", "Status Code": "200"}],
        tabs={"security_mixed_content": issue_rows},
    )

    _patch_extraction(
        monkeypatch,
        crawl,
        settings=_fake_settings(extract_max_issues_per_tab=5),
    )

    extractor.extract_crawl_to_postgres(
        db,
        job_id=job.id,
        tenant_id=job.tenant_id,
        artifact_path=tmp_path / "crawl.seospider",
        cli_path=None,
    )

    all_issue_rows = [row for model, rows in db.bulk_insert_calls if model is CrawlIssue for row in rows]
    tab_issues = [r for r in all_issue_rows if not r["issue_type"].startswith("status_")]
    assert len(tab_issues) == 5


def test_extract_caps_total_issues(monkeypatch, tmp_path):
    """Total issue cap stops processing remaining tabs."""
    job = CrawlJob(
        id=uuid4(),
        tenant_id=uuid4(),
        profile_id=uuid4(),
        target_url="https://example.com",
        executor=JobExecutor.gce,
        status=JobStatus.running,
    )
    db = _FakeSession(job)

    tab_a_rows = [{"Address": "https://example.com/", "Issue": f"A-{i}"} for i in range(10)]
    tab_b_rows = [{"Address": "https://example.com/", "Issue": f"B-{i}"} for i in range(10)]
    crawl = _FakeCrawl(
        [{"Address": "https://example.com/", "Status Code": "200"}],
        tabs={
            "security_mixed_content": tab_a_rows,
            "security_http_urls": tab_b_rows,
        },
    )

    _patch_extraction(
        monkeypatch,
        crawl,
        settings=_fake_settings(
            extract_max_issues_per_tab=50_000,
            extract_max_issues_total=12,
        ),
    )

    extractor.extract_crawl_to_postgres(
        db,
        job_id=job.id,
        tenant_id=job.tenant_id,
        artifact_path=tmp_path / "crawl.seospider",
        cli_path=None,
    )

    all_issue_rows = [row for model, rows in db.bulk_insert_calls if model is CrawlIssue for row in rows]
    assert len(all_issue_rows) <= 12


def test_extraction_metrics_partial_flag():
    """_ExtractionMetrics.is_partial reflects caps/skips."""
    m = extractor._ExtractionMetrics()
    assert not m.is_partial

    m.capped_tabs.append("some_tab")
    assert m.is_partial

    m2 = extractor._ExtractionMetrics()
    m2.total_issues_capped = True
    assert m2.is_partial

    m3 = extractor._ExtractionMetrics()
    m3.skipped_tabs.append("skipped")
    assert m3.is_partial
