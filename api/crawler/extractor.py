"""Load Screaming Frog artifacts and bulk-insert into PostgreSQL."""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

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

CHUNK_SIZE = 400
EXTRACTION_HEARTBEAT_INTERVAL_SECONDS = 15.0
STATUS_ISSUE_PREFIX = "status_"


def _load_crawl_artifact(artifact_path: Path, cli_path: str | None):
    from screamingfrog import Crawl

    load_kwargs: dict[str, Any] = {"cli_path": cli_path}
    if artifact_path.suffix.lower() == ".seospider":
        # Saved .seospider projects can be exported directly to CSV without relying
        # on transient ProjectInstanceData directories surviving after the crawl exits.
        load_kwargs.update(source_type="seospider", seospider_backend="csv")
    return Crawl.load(str(artifact_path), **load_kwargs)


def _norm_key(k: str) -> str:
    return k.strip().lower().replace("-", " ").replace("_", " ")


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


def _cell(row: dict[str, Any], *candidates: str) -> Any:
    by_lower = {_norm_key(str(k)): v for k, v in row.items()}
    for c in candidates:
        nk = _norm_key(c)
        if nk in by_lower:
            return by_lower[nk]
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
    address = _cell(row, "address", "url", "Address") or ""
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
        "status_code": _to_int(_cell(row, "status_code", "status code", "Status Code")),
        "title": _as_str(_cell(row, "title", "Title")),
        "meta_description": _as_str(
            _cell(
                row,
                "meta_description",
                "meta description 1",
                "Meta Description 1",
                "Meta Description",
            )
        ),
        "h1": _as_str(_cell(row, "h1", "h1-1", "H1-1", "H1")),
        "word_count": _to_int(_cell(row, "word_count", "word count", "Word Count")),
        "indexability": _as_str(_cell(row, "indexability", "Indexability")),
        "crawl_depth": _to_crawl_depth(_cell(row, "crawl_depth", "crawl depth", "Crawl Depth")),
        "response_time": _to_float(_cell(row, "response_time", "response time", "Response Time")),
        "canonical": _as_str(_cell(row, "canonical", "Canonical")),
        "canonical_link_element": _as_str(
            _cell(
                row,
                "canonical link element 1",
                "canonical link element",
                "Canonical Link Element 1",
            )
        ),
        "content_type": _as_str(_cell(row, "content_type", "content type", "Content Type")),
        "redirect_url": _as_str(_cell(row, "redirect url", "Redirect URL", "redirect_url")),
        "size_bytes": _to_int(_cell(row, "size", "size_bytes", "Size")),
        "inlinks": _to_int(_cell(row, "inlinks", "inlinks count", "Inlinks")),
        "outlinks": _to_int(_cell(row, "outlinks", "outlinks count", "Outlinks")),
        "meta_robots": _as_str(_cell(row, "meta robots 1", "meta robots", "Meta Robots 1")),
        "pagination_status": _as_str(_cell(row, "pagination", "pagination_status", "Pagination")),
        "http_version": _as_str(_cell(row, "http version", "HTTP Version")),
        "x_robots_tag": _as_str(_cell(row, "x-robots-tag 1", "x-robots-tag", "X-Robots-Tag 1")),
        "link_score": _to_float(_cell(row, "link score", "Link Score")),
        "in_sitemap": _to_bool(_cell(row, "in_sitemap", "in sitemap", "In Sitemap")),
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


def extract_crawl_to_postgres(
    db: Session,
    *,
    job_id: UUID,
    tenant_id: UUID,
    artifact_path: Path,
    cli_path: str | None,
) -> None:
    """Load SF artifact, write pages/issues/links, complete job."""
    del tenant_id  # reserved for future RLS / validation hooks

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

    update_heartbeat(db, job_id, status_message="Loading pages into the database…")
    last_loading_heartbeat_at = time.monotonic()

    tab_name = "internal_all.csv"
    try:
        tab_iter = iter(crawl.tab(tab_name))
    except Exception:
        tab_name = "internal_all"
        tab_iter = iter(crawl.tab(tab_name))

    address_to_page_id: dict[str, uuid.UUID] = {}
    batch: list[dict[str, Any]] = []
    status_issue_batch: list[dict[str, Any]] = []
    total = 0

    def flush_pages() -> None:
        nonlocal batch, last_loading_heartbeat_at, status_issue_batch, total
        if not batch:
            return
        db.bulk_insert_mappings(CrawlPage, batch)
        db.commit()
        for m in batch:
            addr = m["address"]
            if addr:
                address_to_page_id[addr] = m["id"]
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
        )
        last_loading_heartbeat_at = time.monotonic()

    try:
        for row in tab_iter:
            if not isinstance(row, dict):
                continue
            batch.append(_row_to_page_dict(job_id, row))
            last_loading_heartbeat_at = _maybe_emit_loading_heartbeat(
                db,
                job_id,
                last_heartbeat_at=last_loading_heartbeat_at,
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

    job.urls_crawled = total
    db.add(job)
    db.commit()
    update_heartbeat(
        db,
        job_id,
        urls_crawled=total,
        status_message="Loading issues into the database…",
    )
    last_loading_heartbeat_at = time.monotonic()

    # --- Issues from bundled reports ---------------------------------
    issue_batch: list[dict[str, Any]] = list(status_issue_batch)

    def collect_issue_rows(method: str) -> None:
        nonlocal last_loading_heartbeat_at
        fn = getattr(crawl, method, None)
        if not callable(fn):
            return
        try:
            rows = fn()
        except Exception:
            logger.debug("issue report %s not available", method, exc_info=True)
            return
        for row in rows:
            if not isinstance(row, dict):
                continue
            addr = _as_str(_cell(row, "address", "Address", "URL")) or ""
            itype = _as_str(_cell(row, "issue", "Issue", "type")) or "issue"
            details = _as_str(_cell(row, "details", "Details", "detail"))
            issue_batch.append(
                {
                    "id": uuid.uuid4(),
                    "job_id": job_id,
                    "page_id": address_to_page_id.get(addr),
                    "issue_type": itype[:255],
                    "severity": _severity_for_issue(itype),
                    "details": details,
                }
            )
            last_loading_heartbeat_at = _maybe_emit_loading_heartbeat(
                db,
                job_id,
                last_heartbeat_at=last_loading_heartbeat_at,
                status_message="Loading issues into the database…",
                urls_crawled=total,
            )

    for m in (
        "security_issues_report",
        "canonical_issues_report",
        "hreflang_issues_report",
        "redirect_issues_report",
    ):
        collect_issue_rows(m)

    if issue_batch:
        db.bulk_insert_mappings(CrawlIssue, issue_batch)
        db.commit()
    update_heartbeat(
        db,
        job_id,
        urls_crawled=total,
        status_message="Loading links into the database…",
    )
    last_loading_heartbeat_at = time.monotonic()

    # --- Outlinks -----------------------------------------------------
    link_batch: list[dict[str, Any]] = []
    try:
        for row in crawl.links("out"):
            if not isinstance(row, dict):
                continue
            src = _as_str(_cell(row, "source", "Source"))
            tgt = _as_str(_cell(row, "destination", "Destination", "Target"))
            if not src or not tgt:
                continue
            link_batch.append(
                {
                    "id": uuid.uuid4(),
                    "job_id": job_id,
                    "source_url": src,
                    "target_url": tgt,
                    "link_type": _as_str(_cell(row, "type", "Type", "Link Type")),
                    "anchor_text": _as_str(_cell(row, "anchor", "Anchor", "Anchor Text")),
                    "status_code": _to_int(_cell(row, "status code", "Status Code")),
                }
            )
            last_loading_heartbeat_at = _maybe_emit_loading_heartbeat(
                db,
                job_id,
                last_heartbeat_at=last_loading_heartbeat_at,
                status_message="Loading links into the database…",
                urls_crawled=total,
            )
            if len(link_batch) >= CHUNK_SIZE:
                db.bulk_insert_mappings(CrawlLink, link_batch)
                db.commit()
                link_batch = []
                update_heartbeat(
                    db,
                    job_id,
                    urls_crawled=total,
                    status_message="Loading links into the database…",
                )
                last_loading_heartbeat_at = time.monotonic()
        if link_batch:
            db.bulk_insert_mappings(CrawlLink, link_batch)
            db.commit()
    except Exception as e:
        logger.warning("Link extraction failed (non-fatal): %s", e)

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
