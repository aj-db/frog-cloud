from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

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
