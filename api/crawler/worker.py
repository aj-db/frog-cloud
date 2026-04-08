"""GCE VM worker entrypoint: run a single job or poll for queued work."""

from __future__ import annotations

import logging
import os
import shlex
import subprocess
import tempfile
import time
import traceback
from pathlib import Path
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db import get_engine
from app.models import CrawlJob, CrawlProfile, JobExecutor, JobStatus
from crawler.executor import _find_crawl_artifact  # reuse artifact discovery
from crawler.extractor import extract_crawl_to_postgres
from crawler.progress import (
    set_job_error,
    transition_job_status,
    update_heartbeat,
    utcnow,
)

logger = logging.getLogger(__name__)

METADATA_BASE = "http://metadata.google.internal/computeMetadata/v1"
DEFAULT_POLL_INTERVAL_SECONDS = 10.0
MAX_POLL_INTERVAL_SECONDS = 60.0
DEFAULT_CRAWL_HEARTBEAT_SECONDS = 15.0
CRAWL_LOG_TAIL_CHARS = 4000


def _metadata_get(path: str, timeout: float = 5.0) -> str:
    url = f"{METADATA_BASE}/{path}"
    with httpx.Client(timeout=timeout) as client:
        r = client.get(url, headers={"Metadata-Flavor": "Google"})
        r.raise_for_status()
        return r.text.strip()


def _download_gcs_uri(gs_uri: str, dest: Path) -> None:
    try:
        from google.cloud import storage
    except ImportError as e:
        raise RuntimeError("google-cloud-storage required on worker") from e
    assert gs_uri.startswith("gs://")
    rest = gs_uri[5:]
    bucket_name, _, blob_path = rest.partition("/")
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    blob.download_to_filename(str(dest))


def _upload_dir_to_gcs(prefix: str, local_dir: Path, bucket_name: str) -> None:
    from google.cloud import storage

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    for path in local_dir.rglob("*"):
        if path.is_file():
            rel = path.relative_to(local_dir)
            blob = bucket.blob(f"{prefix.rstrip('/')}/{rel.as_posix()}")
            blob.upload_from_filename(str(path))


def _session_factory() -> sessionmaker[Session]:
    engine = get_engine()
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


def _poll_interval_seconds() -> float:
    raw = os.environ.get("FROG_WORKER_POLL_INTERVAL_SECONDS")
    if not raw:
        return DEFAULT_POLL_INTERVAL_SECONDS
    try:
        return max(float(raw), 1.0)
    except ValueError:
        logger.warning(
            "Invalid FROG_WORKER_POLL_INTERVAL_SECONDS=%r; using %.1fs",
            raw,
            DEFAULT_POLL_INTERVAL_SECONDS,
        )
        return DEFAULT_POLL_INTERVAL_SECONDS


def _max_idle_poll_interval_seconds(base_interval: float) -> float:
    raw = os.environ.get("FROG_WORKER_MAX_IDLE_SECONDS")
    if not raw:
        return max(base_interval, MAX_POLL_INTERVAL_SECONDS)
    try:
        return max(float(raw), base_interval)
    except ValueError:
        logger.warning(
            "Invalid FROG_WORKER_MAX_IDLE_SECONDS=%r; using %.1fs",
            raw,
            max(base_interval, MAX_POLL_INTERVAL_SECONDS),
        )
        return max(base_interval, MAX_POLL_INTERVAL_SECONDS)


def _crawl_heartbeat_interval_seconds() -> float:
    raw = os.environ.get("FROG_WORKER_CRAWL_HEARTBEAT_SECONDS")
    if not raw:
        return DEFAULT_CRAWL_HEARTBEAT_SECONDS
    try:
        return max(float(raw), 1.0)
    except ValueError:
        logger.warning(
            "Invalid FROG_WORKER_CRAWL_HEARTBEAT_SECONDS=%r; using %.1fs",
            raw,
            DEFAULT_CRAWL_HEARTBEAT_SECONDS,
        )
        return DEFAULT_CRAWL_HEARTBEAT_SECONDS


def _delete_self_instance() -> None:
    try:
        name = _metadata_get("instance/name")
        zone_path = _metadata_get("instance/zone")  # .../zones/us-central1-a
        zone = zone_path.split("/")[-1]
        project = _metadata_get("project/project-id")
    except Exception as e:
        logger.warning("Could not read instance metadata for self-delete: %s", e)
        return

    try:
        subprocess.run(
            ["gcloud", "compute", "instances", "delete", name, "--zone", zone, "--quiet"],
            check=False,
            timeout=600,
            env=os.environ.copy(),
        )
    except Exception as e:
        logger.warning("Self-delete via gcloud failed: %s", e)

    try:
        from google.cloud import compute_v1

        client = compute_v1.InstancesClient()
        client.delete(project=project, zone=zone, instance=name)
    except Exception as e:
        logger.warning("Self-delete via API failed: %s", e)


def claim_next_gce_job(db: Session | None = None) -> UUID | None:
    owns_session = False
    if db is None:
        db = _session_factory()()
        owns_session = True

    try:
        job = db.execute(
            select(CrawlJob)
            .where(
                CrawlJob.executor == JobExecutor.gce,
                CrawlJob.status == JobStatus.queued,
            )
            .order_by(CrawlJob.created_at.asc(), CrawlJob.id.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        ).scalar_one_or_none()
        if job is None:
            return None

        now = utcnow()
        job.status = JobStatus.running
        job.updated_at = now
        job.last_heartbeat_at = now
        if job.started_at is None:
            job.started_at = now
        db.add(job)
        db.commit()
        return job.id
    finally:
        if owns_session:
            db.close()


def _prepare_gce_job_for_processing(db: Session, job_id: UUID) -> CrawlJob | None:
    job = db.execute(select(CrawlJob).where(CrawlJob.id == job_id)).scalar_one_or_none()
    if job is None:
        logger.error("Job %s not found", job_id)
        return None
    if job.executor != JobExecutor.gce:
        logger.error("Job %s is not a GCE job", job_id)
        return None

    if job.status == JobStatus.running:
        update_heartbeat(db, job_id)
        return db.execute(select(CrawlJob).where(CrawlJob.id == job_id)).scalar_one_or_none()

    if job.status in (JobStatus.provisioning, JobStatus.queued):
        if not transition_job_status(
            db,
            job_id,
            from_statuses=(JobStatus.provisioning, JobStatus.queued),
            to_status=JobStatus.running,
        ):
            logger.info("Job %s could not be moved to running", job_id)
            return None
        return db.execute(select(CrawlJob).where(CrawlJob.id == job_id)).scalar_one_or_none()

    logger.info("Job %s is in %s state; skipping", job_id, job.status.value)
    return None


def _resolve_profile_config(profile: CrawlProfile, output_dir: Path) -> Path | None:
    cfg = profile.config_path.strip()
    if cfg.startswith("gs://"):
        config_local = output_dir / "profile.seospiderconfig"
        _download_gcs_uri(cfg, config_local)
        return config_local
    if Path(cfg).exists():
        return Path(cfg)
    return None


def _tail_text(path: Path, *, max_chars: int = CRAWL_LOG_TAIL_CHARS) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return ""
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[-max_chars:]


def _format_crawl_failure(
    *,
    returncode: int,
    stdout_log: Path,
    stderr_log: Path,
) -> str:
    parts = [f"Screaming Frog CLI failed (exit {returncode})."]
    stdout_tail = _tail_text(stdout_log)
    stderr_tail = _tail_text(stderr_log)
    if stdout_tail:
        parts.append("STDOUT (tail):")
        parts.append(stdout_tail)
    if stderr_tail:
        parts.append("STDERR (tail):")
        parts.append(stderr_tail)
    return "\n".join(parts)


def _wait_for_crawl_process(
    process: subprocess.Popen[str],
    *,
    db: Session,
    job_id: UUID,
    heartbeat_interval_seconds: float,
) -> int:
    while True:
        try:
            return process.wait(timeout=heartbeat_interval_seconds)
        except subprocess.TimeoutExpired:
            update_heartbeat(db, job_id)


def _run_crawl_cli(
    *,
    db: Session,
    job_id: UUID,
    start_url: str,
    output_dir: Path,
    cli_path: str | None,
    config: Path | None,
) -> None:
    from screamingfrog.cli.exports import resolve_cli_path

    cmd = [
        str(resolve_cli_path(cli_path)),
        "--crawl",
        start_url,
        "--output-folder",
        str(output_dir),
        "--headless",
        "--overwrite",
        "--save-crawl",
        "--export-format",
        "csv",
    ]
    if config is not None:
        cmd.extend(["--config", str(config)])

    stdout_log = output_dir / "screamingfrog.stdout.log"
    stderr_log = output_dir / "screamingfrog.stderr.log"
    heartbeat_interval_seconds = _crawl_heartbeat_interval_seconds()

    logger.info(
        "Starting Screaming Frog crawl for job %s with command: %s",
        job_id,
        shlex.join(cmd),
    )
    logger.info(
        "Heartbeat interval for job %s is %.1fs",
        job_id,
        heartbeat_interval_seconds,
    )

    with (
        stdout_log.open("w", encoding="utf-8") as stdout_handle,
        stderr_log.open("w", encoding="utf-8") as stderr_handle,
    ):
        process = subprocess.Popen(
            cmd,
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
            env=os.environ.copy(),
        )
        returncode = _wait_for_crawl_process(
            process,
            db=db,
            job_id=job_id,
            heartbeat_interval_seconds=heartbeat_interval_seconds,
        )

    logger.info("Screaming Frog crawl for job %s exited with code %s", job_id, returncode)

    if returncode != 0:
        raise RuntimeError(
            _format_crawl_failure(
                returncode=returncode,
                stdout_log=stdout_log,
                stderr_log=stderr_log,
            )
        )


def process_gce_job(job_id: UUID, *, delete_self: bool) -> None:
    """Run the full worker pipeline for one job."""
    logging.basicConfig(level=logging.INFO)
    db = _session_factory()()
    bucket = os.environ.get("GCS_BUCKET")

    try:
        job = _prepare_gce_job_for_processing(db, job_id)
        if job is None:
            return

        profile = db.execute(
            select(CrawlProfile).where(CrawlProfile.id == job.profile_id)
        ).scalar_one_or_none()
        if profile is None:
            set_job_error(db, job_id, "Profile not found")
            return

        output_dir = Path(tempfile.mkdtemp(prefix=f"sf_gce_{job_id}_"))
        config_local = _resolve_profile_config(profile, output_dir)
        if config_local is None:
            set_job_error(db, job_id, f"Config not found: {profile.config_path.strip()}")
            return

        try:
            _run_crawl_cli(
                db=db,
                job_id=job_id,
                start_url=job.target_url,
                output_dir=output_dir,
                cli_path=os.environ.get("SF_CLI_PATH"),
                config=config_local,
            )
        except RuntimeError as e:
            set_job_error(db, job_id, str(e)[:8000])
            return
        except Exception as e:
            logger.exception("Screaming Frog crawl raised")
            set_job_error(db, job_id, f"Crawl failed to start: {e}\n{traceback.format_exc()}")
            return

        update_heartbeat(db, job_id)
        logger.info("Looking for crawl artifact for job %s in %s", job_id, output_dir)
        artifact = _find_crawl_artifact(output_dir)
        if artifact is None:
            set_job_error(db, job_id, "No crawl artifact found after GCE crawl")
            return

        logger.info("Found crawl artifact for job %s at %s", job_id, artifact)
        extract_crawl_to_postgres(
            db,
            job_id=job_id,
            tenant_id=job.tenant_id,
            artifact_path=artifact,
            cli_path=os.environ.get("SF_CLI_PATH"),
        )

        if bucket:
            prefix = f"tenants/{job.tenant_id}/jobs/{job_id}/artifacts"
            try:
                _upload_dir_to_gcs(prefix, output_dir, bucket)
                job = db.execute(select(CrawlJob).where(CrawlJob.id == job_id)).scalar_one()
                job.artifact_prefix = f"gs://{bucket}/{prefix}"
                db.add(job)
                db.commit()
            except Exception as e:
                logger.exception("GCS upload failed (non-fatal)")
                set_job_error(db, job_id, f"Crawl completed but artifact upload failed: {e}")
                return

        time.sleep(1)
    except Exception as e:
        logger.exception("Worker crashed for job %s", job_id)
        try:
            set_job_error(db, job_id, f"Worker error: {e}\n{traceback.format_exc()}")
        except Exception:
            pass
    finally:
        db.close()
        if delete_self:
            _delete_self_instance()


def run_worker_for_job(job_id: UUID) -> None:
    """Backward-compatible one-shot worker entrypoint."""
    process_gce_job(job_id, delete_self=True)


def run_persistent_worker_loop(poll_interval_seconds: float | None = None) -> None:
    """Poll for queued GCE jobs and process them serially."""
    logging.basicConfig(level=logging.INFO)
    SessionLocal = _session_factory()
    base_interval = poll_interval_seconds or _poll_interval_seconds()
    max_interval = _max_idle_poll_interval_seconds(base_interval)
    idle_interval = base_interval
    logger.info(
        "Starting persistent GCE worker loop (poll %.1fs, max idle %.1fs)",
        base_interval,
        max_interval,
    )

    while True:
        db = SessionLocal()
        try:
            job_id = claim_next_gce_job(db)
        except Exception:
            logger.exception("Failed to claim next queued GCE job")
            job_id = None
        finally:
            db.close()

        if job_id is None:
            time.sleep(idle_interval)
            idle_interval = min(idle_interval * 2, max_interval)
            continue

        logger.info("Claimed queued GCE job %s", job_id)
        idle_interval = base_interval
        process_gce_job(job_id, delete_self=False)


def main() -> None:
    job_id_raw = os.environ.get("FROG_JOB_ID")
    if not job_id_raw:
        try:
            job_id_raw = _metadata_get("instance/attributes/frog_job_id")
        except Exception:
            job_id_raw = None
    if job_id_raw:
        run_worker_for_job(UUID(job_id_raw))
        return

    if get_settings().gce_dispatch_mode == "persistent":
        run_persistent_worker_loop()
        return

    raise SystemExit("FROG_JOB_ID env or metadata frog_job_id required")


if __name__ == "__main__":
    main()
