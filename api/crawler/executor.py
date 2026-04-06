"""Local crawl execution: subprocess lifecycle around Screaming Frog CLI."""

from __future__ import annotations

import logging
import multiprocessing
import os
import tempfile
import traceback
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db import get_engine
from app.models import CrawlJob, CrawlProfile, JobExecutor, JobStatus
from crawler.extractor import extract_crawl_to_postgres
from crawler.progress import set_job_error, transition_job_status, update_heartbeat

logger = logging.getLogger(__name__)

def _find_crawl_artifact(output_dir: Path) -> Path | None:
    """Locate .dbseospider or .seospider project after crawl."""
    dbseo = list(output_dir.rglob("*.dbseospider"))
    if dbseo:
        return max(dbseo, key=lambda p: p.stat().st_mtime)
    seospider = list(output_dir.rglob("*.seospider"))
    if seospider:
        return max(seospider, key=lambda p: p.stat().st_mtime)
    return None


def _run_local_job_impl(job_id: UUID) -> None:
    """Runs inside worker process — opens its own DB session."""
    logging.basicConfig(level=logging.INFO)
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db: Session = SessionLocal()
    settings = get_settings()
    try:
        job = db.execute(select(CrawlJob).where(CrawlJob.id == job_id)).scalar_one_or_none()
        if job is None:
            logger.error("Job %s not found", job_id)
            return

        profile = db.execute(
            select(CrawlProfile).where(CrawlProfile.id == job.profile_id)
        ).scalar_one_or_none()
        if profile is None:
            set_job_error(db, job_id, "Crawl profile not found")
            return

        if not transition_job_status(
            db,
            job_id,
            from_statuses=(JobStatus.queued,),
            to_status=JobStatus.running,
        ):
            logger.info("Job %s not in queued state; skipping", job_id)
            return

        env = os.environ.copy()
        if settings.java_home:
            env["JAVA_HOME"] = settings.java_home
            env["PATH"] = f"{settings.java_home}/bin:{env.get('PATH', '')}"

        output_dir = Path(tempfile.mkdtemp(prefix=f"sf_job_{job_id}_"))

        try:
            from screamingfrog.cli.exports import start_crawl

            start_crawl(
                job.target_url,
                output_dir,
                cli_path=settings.sf_cli_path,
                config=profile.config_path if Path(profile.config_path).exists() else None,
                headless=True,
                overwrite=True,
                save_crawl=True,
                export_format="csv",
            )
        except RuntimeError as e:
            # start_crawl uses run_cli(check=True): non-zero exit raises RuntimeError
            set_job_error(db, job_id, str(e)[:8000])
            return
        except Exception as e:
            logger.exception("start_crawl raised")
            set_job_error(db, job_id, f"Crawl failed to start: {e}\n{traceback.format_exc()}")
            return

        artifact = _find_crawl_artifact(output_dir)
        if artifact is None:
            set_job_error(
                db,
                job_id,
                "Crawl finished but no .dbseospider or .seospider artifact was found in output.",
            )
            return

        extract_crawl_to_postgres(
            db,
            job_id=job_id,
            tenant_id=job.tenant_id,
            artifact_path=artifact,
            cli_path=settings.sf_cli_path,
        )

    except Exception as e:
        logger.exception("Worker crashed for job %s", job_id)
        try:
            set_job_error(db, job_id, f"Worker error: {e}\n{traceback.format_exc()}")
        except Exception:
            pass
    finally:
        db.close()


def _run_none_executor(job_id: UUID) -> None:
    """Mark job complete with zero URLs (CI / smoke)."""
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()
    try:
        job = db.execute(select(CrawlJob).where(CrawlJob.id == job_id)).scalar_one_or_none()
        if job is None:
            return
        transition_job_status(
            db,
            job_id,
            from_statuses=(JobStatus.queued,),
            to_status=JobStatus.running,
        )
        update_heartbeat(db, job_id)
        transition_job_status(
            db,
            job_id,
            from_statuses=(JobStatus.running,),
            to_status=JobStatus.extracting,
        )
        transition_job_status(
            db,
            job_id,
            from_statuses=(JobStatus.extracting,),
            to_status=JobStatus.loading,
        )
        transition_job_status(
            db,
            job_id,
            from_statuses=(JobStatus.loading,),
            to_status=JobStatus.complete,
            progress_pct=100.0,
        )
        job = db.execute(select(CrawlJob).where(CrawlJob.id == job_id)).scalar_one()
        job.urls_crawled = 0
        db.add(job)
        db.commit()
    finally:
        db.close()


def spawn_local_worker(job_id: UUID) -> None:
    """Fork-friendly entry: start background process for local executor."""
    ctx = multiprocessing.get_context("spawn")
    p = ctx.Process(target=_run_local_job_impl, args=(job_id,), name=f"sf-crawl-{job_id}")
    p.daemon = False
    p.start()


def spawn_none_worker(job_id: UUID) -> None:
    ctx = multiprocessing.get_context("spawn")
    p = ctx.Process(target=_run_none_executor, args=(job_id,), name=f"sf-none-{job_id}")
    p.daemon = False
    p.start()


def enqueue_job_execution(job_id: UUID, executor: JobExecutor) -> None:
    if executor == JobExecutor.local:
        spawn_local_worker(job_id)
    elif executor == JobExecutor.none:
        spawn_none_worker(job_id)
    elif executor == JobExecutor.gce:
        # Cloud Tasks → /internal/launch-worker; API layer enqueues separately
        raise ValueError("GCE executor must be scheduled via Cloud Tasks / launcher")
    else:
        raise ValueError(f"Unknown executor: {executor}")
