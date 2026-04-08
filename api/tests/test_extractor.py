from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from uuid import uuid4

from app.models import CrawlJob, JobExecutor, JobStatus
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
    def __init__(self, rows):
        self._rows = rows

    def tab(self, _name):
        return iter(self._rows)

    def links(self, _direction):
        return iter(())


def test_row_to_page_dict_normalizes_crawl_depth_sentinel():
    from crawler.extractor import _row_to_page_dict

    sentinel = 2_147_483_647
    result = _row_to_page_dict(uuid4(), {"Address": "https://example.com/", "Crawl Depth": str(sentinel)})
    assert result["crawl_depth"] is None, f"Expected None for sentinel depth, got {result['crawl_depth']}"


def test_row_to_page_dict_preserves_valid_crawl_depth():
    from crawler.extractor import _row_to_page_dict

    result = _row_to_page_dict(uuid4(), {"Address": "https://example.com/", "Crawl Depth": "3"})
    assert result["crawl_depth"] == 3


def test_row_to_page_dict_handles_missing_crawl_depth():
    from crawler.extractor import _row_to_page_dict

    result = _row_to_page_dict(uuid4(), {"Address": "https://example.com/"})
    assert result["crawl_depth"] is None


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
    monotonic_values = iter([0.0, 0.0, 12.0, 24.0, 36.0, 48.0, 60.0, 72.0])

    monkeypatch.setattr(extractor, "_load_crawl_artifact", lambda *_args, **_kwargs: crawl)
    monkeypatch.setattr(extractor, "set_job_error", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(extractor, "transition_job_status", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(
        extractor,
        "update_heartbeat",
        lambda _db, _job_id, progress_pct=None, urls_crawled=None, status_message=None: heartbeats.append(
            (urls_crawled, status_message)
        ),
    )
    monkeypatch.setattr(
        extractor,
        "time",
        SimpleNamespace(monotonic=lambda: next(monotonic_values)),
        raising=False,
    )
    monkeypatch.setattr(extractor, "EXTRACTION_HEARTBEAT_INTERVAL_SECONDS", 10.0, raising=False)
    monkeypatch.setattr(extractor, "CHUNK_SIZE", 1000)

    extractor.extract_crawl_to_postgres(
        db,
        job_id=job.id,
        tenant_id=job.tenant_id,
        artifact_path=tmp_path / "crawl.seospider",
        cli_path=None,
    )

    assert any(
        urls_crawled == 2 and message == "Loading pages into the database…"
        for urls_crawled, message in heartbeats
    )
