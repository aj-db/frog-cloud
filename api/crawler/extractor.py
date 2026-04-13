"""Load Screaming Frog artifacts and bulk-insert into PostgreSQL."""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    CrawlIssue,
    CrawlJob,
    CrawlLink,
    CrawlPage,
    IssueSeverity,
    JobStatus,
)
from crawler.progress import set_job_error, transition_job_status, update_heartbeat

logger = logging.getLogger(__name__)

CHUNK_SIZE = 2000
EXTRACTION_HEARTBEAT_INTERVAL_SECONDS = 15.0
STATUS_ISSUE_PREFIX = "status_"

ISSUE_TABS: tuple[tuple[str, str], ...] = (
    ("security_missing_hsts_header", "Missing HSTS Header"),
    ("security_missing_contentsecuritypolicy_header", "Missing Content-Security-Policy Header"),
    ("security_missing_secure_referrerpolicy_header", "Missing Referrer-Policy Header"),
    ("security_missing_xcontenttypeoptions_header", "Missing X-Content-Type-Options Header"),
    ("security_missing_xframeoptions_header", "Missing X-Frame-Options Header"),
    ("security_mixed_content", "Mixed Content"),
    ("security_http_urls", "HTTP URL"),
    ("security_form_url_insecure", "Insecure Form Action"),
    ("security_form_on_http_url", "Form On HTTP URL"),
    ("canonicals_missing", "Missing Canonical"),
    ("canonicals_multiple", "Multiple Canonicals"),
    ("canonicals_multiple_conflicting", "Conflicting Canonicals"),
    ("canonicals_nonindexable_canonical", "Canonical To Non-Indexable"),
    ("canonicals_nonindexable_canonicals", "Canonical To Non-Indexable"),
    ("canonicals_canonicalised", "Canonicalised"),
    ("canonicals_unlinked", "Unlinked Canonical"),
    ("canonicals_contains_fragment_url", "Canonical Contains Fragment"),
    ("canonicals_canonical_is_relative", "Relative Canonical"),
    ("canonicals_outside_head", "Canonical Outside Head"),
    ("javascript_canonical_mismatch", "JavaScript Canonical Mismatch"),
    ("javascript_canonical_only_in_rendered_html", "Canonical Only In Rendered HTML"),
    ("hreflang_not_using_canonical", "Not Using Canonical"),
    ("hreflang_missing", "Missing Hreflang"),
    ("hreflang_missing_self_reference", "Missing Self-Reference"),
    ("hreflang_missing_return_links", "Missing Return Links"),
    ("hreflang_missing_xdefault", "Missing x-default"),
    ("hreflang_multiple_entries", "Multiple Entries"),
    ("hreflang_incorrect_language_region_codes", "Incorrect Language/Region Codes"),
    ("hreflang_inconsistent_language_return_links", "Inconsistent Language Return Links"),
    ("hreflang_inconsistent_language_region_return_links", "Inconsistent Language/Region Return Links"),
    ("hreflang_noncanonical_return_links", "Non-Canonical Return Links"),
    ("hreflang_non_canonical_return_links", "Non-Canonical Return Links"),
    ("hreflang_non200_hreflang_urls", "Non-200 Hreflang URL"),
    ("hreflang_noindex_return_links", "Noindex Return Links"),
    ("hreflang_no_index_return_links", "Noindex Return Links"),
    ("hreflang_unlinked_hreflang_urls", "Unlinked Hreflang URL"),
    ("hreflang_outside_head", "Outside Head"),
    ("response_codes_internal_redirection_(3xx)", "Internal Redirect"),
    ("response_codes_internal_redirection_(meta_refresh)", "Meta Refresh Redirect"),
    ("response_codes_internal_redirection_(javascript)", "JavaScript Redirect"),
    ("response_codes_internal_redirect_chain", "Redirect Chain"),
    ("response_codes_internal_redirect_loop", "Redirect Loop"),
    ("redirect_chains", "Redirect Chain"),
)


@dataclass
class _TabStats:
    rows_seen: int = 0
    rows_resolved: int = 0
    rows_orphaned: int = 0
    elapsed: float = 0.0


@dataclass
class _ExtractionMetrics:
    page_elapsed: float = 0.0
    page_count: int = 0
    issue_elapsed: float = 0.0
    issue_count: int = 0
    link_elapsed: float = 0.0
    link_count: int = 0
    tab_stats: dict[str, _TabStats] = field(default_factory=dict)

    def log_summary(self, job_id: UUID) -> None:
        logger.info(
            "extraction_metrics job=%s pages=%d/%.1fs issues=%d/%.1fs links=%d/%.1fs",
            job_id,
            self.page_count,
            self.page_elapsed,
            self.issue_count,
            self.issue_elapsed,
            self.link_count,
            self.link_elapsed,
        )
        top_tabs = sorted(
            self.tab_stats.items(),
            key=lambda kv: kv[1].rows_seen,
            reverse=True,
        )[:10]
        for tab_name, stats in top_tabs:
            logger.info(
                "extraction_tab job=%s tab=%s seen=%d resolved=%d orphaned=%d elapsed=%.1fs",
                job_id,
                tab_name,
                stats.rows_seen,
                stats.rows_resolved,
                stats.rows_orphaned,
                stats.elapsed,
            )


def _load_crawl_artifact(artifact_path: Path, cli_path: str | None):
    from screamingfrog import Crawl

    load_kwargs: dict[str, Any] = {"cli_path": cli_path}
    if artifact_path.suffix.lower() == ".seospider":
        load_kwargs.update(source_type="seospider", seospider_backend="csv")
    return Crawl.load(str(artifact_path), **load_kwargs)


def _norm_key(k: str) -> str:
    return k.strip().lower().replace("-", " ").replace("_", " ")


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    """Build a normalized-key -> value map once per row."""
    return {_norm_key(str(k)): v for k, v in row.items()}


# Normalized keys we map to typed columns; other keys go to JSON metadata.
_SKIP_METADATA_KEYS = frozenset(
    {
        _norm_key(k)
        for k in (
            "address",
            "status_code",
            "status code",
            "title",
            "meta_description",
            "meta description 1",
            "meta description",
            "h1",
            "h1-1",
            "word_count",
            "word count",
            "indexability",
            "crawl_depth",
            "crawl depth",
            "response_time",
            "response time",
            "canonical",
            "canonical link element 1",
            "canonical link element",
            "content_type",
            "content type",
            "redirect_url",
            "redirect url",
            "size_bytes",
            "size",
            "inlinks",
            "inlinks count",
            "outlinks",
            "outlinks count",
            "meta_robots",
            "meta robots 1",
            "meta robots",
            "pagination_status",
            "pagination",
            "http_version",
            "http version",
            "x_robots_tag",
            "x-robots-tag 1",
            "x-robots-tag",
            "link_score",
            "link score",
            "in_sitemap",
            "in sitemap",
        )
    }
)


def _cell(normalized: dict[str, Any], *candidates: str) -> Any:
    """Look up a value by trying each candidate key against a pre-normalized row."""
    for c in candidates:
        nk = _norm_key(c)
        if nk in normalized:
            return normalized[nk]
    return None


def _to_int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(float(str(v).replace(",", "")))
    except (ValueError, TypeError):
        return None


def _to_float(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(str(v).replace(",", ""))
    except (ValueError, TypeError):
        return None


_DEPTH_SENTINEL = 2_147_483_647


def _to_crawl_depth(v: Any) -> int | None:
    n = _to_int(v)
    if n is not None and n >= _DEPTH_SENTINEL:
        return None
    return n


def _to_bool(v: Any) -> bool | None:
    if v is None or v == "":
        return None
    s = str(v).strip().lower()
    if s in ("true", "1", "yes"):
        return True
    if s in ("false", "0", "no"):
        return False
    return None


def _row_to_page_dict(job_id: UUID, row: dict[str, Any]) -> dict[str, Any]:
    nr = _normalize_row(row)
    address = _cell(nr, "address", "url") or ""
    address = str(address).strip()
    meta: dict[str, Any] = {}
    for k, v in row.items():
        nk = _norm_key(str(k))
        if nk in _SKIP_METADATA_KEYS:
            continue
        meta[str(k)] = v

    return {
        "id": uuid.uuid4(),
        "job_id": job_id,
        "address": address,
        "status_code": _to_int(_cell(nr, "status code", "status_code")),
        "title": _as_str(_cell(nr, "title")),
        "meta_description": _as_str(
            _cell(nr, "meta description 1", "meta description", "meta_description")
        ),
        "h1": _as_str(_cell(nr, "h1 1", "h1")),
        "word_count": _to_int(_cell(nr, "word count", "word_count")),
        "indexability": _as_str(_cell(nr, "indexability")),
        "crawl_depth": _to_crawl_depth(_cell(nr, "crawl depth", "crawl_depth")),
        "response_time": _to_float(_cell(nr, "response time", "response_time")),
        "canonical": _as_str(_cell(nr, "canonical")),
        "canonical_link_element": _as_str(
            _cell(nr, "canonical link element 1", "canonical link element")
        ),
        "content_type": _as_str(_cell(nr, "content type", "content_type")),
        "redirect_url": _as_str(_cell(nr, "redirect url", "redirect_url")),
        "size_bytes": _to_int(_cell(nr, "size", "size_bytes")),
        "inlinks": _to_int(_cell(nr, "inlinks", "inlinks count")),
        "outlinks": _to_int(_cell(nr, "outlinks", "outlinks count")),
        "meta_robots": _as_str(_cell(nr, "meta robots 1", "meta robots")),
        "pagination_status": _as_str(_cell(nr, "pagination", "pagination_status")),
        "http_version": _as_str(_cell(nr, "http version")),
        "x_robots_tag": _as_str(_cell(nr, "x robots tag 1", "x robots tag")),
        "link_score": _to_float(_cell(nr, "link score")),
        "in_sitemap": _to_bool(_cell(nr, "in sitemap", "in_sitemap")),
        "extra_metadata": meta,
    }


def _as_str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _maybe_emit_loading_heartbeat(
    db: Session,
    job_id: UUID,
    *,
    last_heartbeat_at: float,
    status_message: str,
    urls_crawled: int | None = None,
) -> float:
    now = time.monotonic()
    if now - last_heartbeat_at < EXTRACTION_HEARTBEAT_INTERVAL_SECONDS:
        return last_heartbeat_at

    update_heartbeat(
        db,
        job_id,
        urls_crawled=urls_crawled,
        status_message=status_message,
    )
    return now


def _severity_for_issue(issue_text: str) -> IssueSeverity:
    t = issue_text.lower()
    if any(x in t for x in ("error", "missing", "broken", "4xx", "5xx", "invalid")):
        return IssueSeverity.error
    if any(x in t for x in ("warning", "multiple", "duplicate")):
        return IssueSeverity.warning
    return IssueSeverity.info


def _status_issue_type(status_code: int) -> str:
    return f"{STATUS_ISSUE_PREFIX}{status_code}"


def _severity_for_status_code(status_code: int) -> IssueSeverity:
    if 400 <= status_code < 600:
        return IssueSeverity.error
    if 300 <= status_code < 400:
        return IssueSeverity.warning
    return IssueSeverity.info


def _status_issue_row(page_row: dict[str, Any]) -> dict[str, Any] | None:
    status_code = page_row.get("status_code")
    page_id = page_row.get("id")
    if type(status_code) is not int or page_id is None:
        return None
    return {
        "id": uuid.uuid4(),
        "job_id": page_row["job_id"],
        "page_id": page_id,
        "issue_type": _status_issue_type(status_code),
        "severity": _severity_for_status_code(status_code),
        "details": f"HTTP {status_code} response recorded for this URL.",
    }


def _normalize_address(addr: str) -> str:
    """Normalize an address for matching: lowercase, strip trailing slash."""
    addr = addr.strip().lower()
    if addr.endswith("/") and len(addr) > 1:
        addr = addr.rstrip("/")
    return addr


def _tab_issue_row(
    *,
    job_id: UUID,
    address_to_page_id: dict[str, uuid.UUID],
    issue_label: str,
    row: dict[str, Any],
) -> dict[str, Any]:
    nr = _normalize_row(row)
    addr = _as_str(_cell(nr, "address", "url")) or ""
    issue_type = _as_str(_cell(nr, "issue")) or issue_label
    details = _as_str(_cell(nr, "details", "detail"))

    page_id = address_to_page_id.get(addr)
    if page_id is None:
        page_id = address_to_page_id.get(_normalize_address(addr))

    return {
        "id": uuid.uuid4(),
        "job_id": job_id,
        "page_id": page_id,
        "issue_type": issue_type[:255],
        "severity": _severity_for_issue(issue_type),
        "details": details,
    }


def extract_crawl_to_postgres(
    db: Session,
    *,
    job_id: UUID,
    tenant_id: UUID,
    artifact_path: Path,
    cli_path: str | None,
) -> None:
    """Load SF artifact, write pages/issues/links, complete job."""
    del tenant_id

    job = db.execute(select(CrawlJob).where(CrawlJob.id == job_id)).scalar_one_or_none()
    if job is None:
        logger.error("extract: job %s missing", job_id)
        return

    if not transition_job_status(
        db,
        job_id,
        from_statuses=(JobStatus.running,),
        to_status=JobStatus.extracting,
    ):
        db.refresh(job)
        if job.status != JobStatus.extracting:
            logger.warning("extract: job %s not running; status=%s", job_id, job.status)
            return

    update_heartbeat(db, job_id)

    try:
        crawl = _load_crawl_artifact(artifact_path, cli_path)
    except Exception as e:
        logger.exception("Crawl.load failed")
        set_job_error(db, job_id, f"Failed to load crawl artifact: {e}")
        return

    db.execute(delete(CrawlLink).where(CrawlLink.job_id == job_id))
    db.execute(delete(CrawlIssue).where(CrawlIssue.job_id == job_id))
    db.execute(delete(CrawlPage).where(CrawlPage.job_id == job_id))
    db.commit()

    if not transition_job_status(
        db,
        job_id,
        from_statuses=(JobStatus.extracting,),
        to_status=JobStatus.loading,
    ):
        pass

    metrics = _ExtractionMetrics()
    skip_orphans = getattr(get_settings(), "extract_skip_orphan_issues", False)

    update_heartbeat(db, job_id, status_message="Loading pages into the database…")
    last_heartbeat_at = time.monotonic()

    # --- Pages --------------------------------------------------------
    page_start = time.monotonic()

    tab_name = "internal_all.csv"
    try:
        tab_iter = iter(crawl.tab(tab_name))
    except Exception:
        tab_name = "internal_all"
        tab_iter = iter(crawl.tab(tab_name))

    address_to_page_id: dict[str, uuid.UUID] = {}
    normalized_address_to_page_id: dict[str, uuid.UUID] = {}
    batch: list[dict[str, Any]] = []
    status_issue_batch: list[dict[str, Any]] = []
    total = 0

    def flush_pages() -> None:
        nonlocal batch, last_heartbeat_at, status_issue_batch, total
        if not batch:
            return
        db.bulk_insert_mappings(CrawlPage, batch)
        for m in batch:
            addr = m["address"]
            if addr:
                address_to_page_id[addr] = m["id"]
                normalized_address_to_page_id[_normalize_address(addr)] = m["id"]
            status_issue = _status_issue_row(m)
            if status_issue is not None:
                status_issue_batch.append(status_issue)
        total += len(batch)
        batch = []
        update_heartbeat(
            db,
            job_id,
            urls_crawled=total,
            status_message="Loading pages into the database…",
            commit=False,
        )
        db.commit()
        last_heartbeat_at = time.monotonic()

    try:
        for row in tab_iter:
            if not isinstance(row, dict):
                continue
            batch.append(_row_to_page_dict(job_id, row))
            last_heartbeat_at = _maybe_emit_loading_heartbeat(
                db,
                job_id,
                last_heartbeat_at=last_heartbeat_at,
                status_message="Loading pages into the database…",
                urls_crawled=total + len(batch),
            )
            if len(batch) >= CHUNK_SIZE:
                flush_pages()
        flush_pages()
    except Exception as e:
        logger.exception("Page ingestion failed")
        set_job_error(db, job_id, f"Failed while loading pages: {e}")
        return

    metrics.page_elapsed = time.monotonic() - page_start
    metrics.page_count = total

    job.urls_crawled = total
    db.add(job)
    db.commit()
    update_heartbeat(
        db,
        job_id,
        urls_crawled=total,
        status_message="Loading issues into the database…",
    )
    last_heartbeat_at = time.monotonic()

    # --- Issues from direct tab streams -------------------------------
    issue_start = time.monotonic()
    issue_batch: list[dict[str, Any]] = list(status_issue_batch)
    total_issues = len(issue_batch)

    def flush_issues() -> None:
        nonlocal issue_batch, last_heartbeat_at, total_issues
        if not issue_batch:
            return
        db.bulk_insert_mappings(CrawlIssue, issue_batch)
        total_issues += len(issue_batch)
        issue_batch = []
        update_heartbeat(
            db,
            job_id,
            urls_crawled=total,
            status_message="Loading issues into the database…",
            commit=False,
        )
        db.commit()
        last_heartbeat_at = time.monotonic()

    for tab_name, issue_label in ISSUE_TABS:
        tab_start = time.monotonic()
        stats = _TabStats()
        last_heartbeat_at = _maybe_emit_loading_heartbeat(
            db,
            job_id,
            last_heartbeat_at=last_heartbeat_at,
            status_message="Loading issues into the database…",
            urls_crawled=total,
        )
        try:
            rows = crawl.tab(tab_name)
        except Exception:
            logger.debug("issue tab %s not available", tab_name, exc_info=True)
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            issue_dict = _tab_issue_row(
                job_id=job_id,
                address_to_page_id=address_to_page_id,
                issue_label=issue_label,
                row=row,
            )
            stats.rows_seen += 1
            if issue_dict["page_id"] is not None:
                stats.rows_resolved += 1
            else:
                stats.rows_orphaned += 1
                if skip_orphans:
                    continue

            issue_batch.append(issue_dict)
            last_heartbeat_at = _maybe_emit_loading_heartbeat(
                db,
                job_id,
                last_heartbeat_at=last_heartbeat_at,
                status_message="Loading issues into the database…",
                urls_crawled=total,
            )
            if len(issue_batch) >= CHUNK_SIZE:
                flush_issues()

        stats.elapsed = time.monotonic() - tab_start
        metrics.tab_stats[tab_name] = stats

    flush_issues()
    metrics.issue_elapsed = time.monotonic() - issue_start
    metrics.issue_count = total_issues

    update_heartbeat(
        db,
        job_id,
        urls_crawled=total,
        status_message="Loading links into the database…",
    )
    last_heartbeat_at = time.monotonic()

    # --- Outlinks -----------------------------------------------------
    link_start = time.monotonic()
    link_batch: list[dict[str, Any]] = []
    total_links = 0
    try:
        for row in crawl.links("out"):
            if not isinstance(row, dict):
                continue
            nr = _normalize_row(row)
            src = _as_str(_cell(nr, "source"))
            tgt = _as_str(_cell(nr, "destination", "target"))
            if not src or not tgt:
                continue
            link_batch.append(
                {
                    "id": uuid.uuid4(),
                    "job_id": job_id,
                    "source_url": src,
                    "target_url": tgt,
                    "link_type": _as_str(_cell(nr, "type", "link type")),
                    "anchor_text": _as_str(_cell(nr, "anchor", "anchor text")),
                    "status_code": _to_int(_cell(nr, "status code")),
                }
            )
            last_heartbeat_at = _maybe_emit_loading_heartbeat(
                db,
                job_id,
                last_heartbeat_at=last_heartbeat_at,
                status_message="Loading links into the database…",
                urls_crawled=total,
            )
            if len(link_batch) >= CHUNK_SIZE:
                db.bulk_insert_mappings(CrawlLink, link_batch)
                total_links += len(link_batch)
                link_batch = []
                update_heartbeat(
                    db,
                    job_id,
                    urls_crawled=total,
                    status_message="Loading links into the database…",
                    commit=False,
                )
                db.commit()
                last_heartbeat_at = time.monotonic()
        if link_batch:
            db.bulk_insert_mappings(CrawlLink, link_batch)
            total_links += len(link_batch)
            db.commit()
    except Exception as e:
        logger.warning("Link extraction failed (non-fatal): %s", e)

    metrics.link_elapsed = time.monotonic() - link_start
    metrics.link_count = total_links
    metrics.log_summary(job_id)

    update_heartbeat(
        db,
        job_id,
        progress_pct=100.0,
        urls_crawled=total,
        status_message="Finished loading crawl results.",
    )

    transition_job_status(
        db,
        job_id,
        from_statuses=(JobStatus.loading,),
        to_status=JobStatus.complete,
        progress_pct=100.0,
    )
