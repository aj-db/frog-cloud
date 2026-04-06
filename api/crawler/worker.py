"""GCE VM worker entrypoint: run crawl, extract to DB, upload artifacts, self-delete."""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.db import get_engine
from app.models import CrawlJob, CrawlProfile, JobExecutor, JobStatus
from crawler.executor import _find_crawl_artifact  # reuse artifact discovery
from crawler.extractor import extract_crawl_to_postgres
from crawler.progress import set_job_error, transition_job_status, update_heartbeat

logger = logging.getLogger(__name__)

METADATA_BASE = "http://metadata.google.internal/computeMetadata/v1"


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


def run_worker_for_job(job_id: UUID) -> None:
    """Full worker pipeline for a given job (VM or local integration test)."""
    logging.basicConfig(level=logging.INFO)
    engine = get_engine()
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = SessionLocal()
    bucket = os.environ.get("GCS_BUCKET")

    try:
        job = db.execute(select(CrawlJob).where(CrawlJob.id == job_id)).scalar_one_or_none()
        if job is None:
            logger.error("Job %s not found", job_id)
            return
        if job.executor != JobExecutor.gce:
            logger.error("Job %s is not a GCE job", job_id)
            return

        profile = db.execute(
            select(CrawlProfile).where(CrawlProfile.id == job.profile_id)
        ).scalar_one_or_none()
        if profile is None:
            set_job_error(db, job_id, "Profile not found")
            return

        transition_job_status(
            db,
            job_id,
            from_statuses=(JobStatus.provisioning, JobStatus.queued),
            to_status=JobStatus.running,
        )
        update_heartbeat(db, job_id)

        output_dir = Path(tempfile.mkdtemp(prefix=f"sf_gce_{job_id}_"))
        config_local: Path | None = None
        cfg = profile.config_path.strip()
        if cfg.startswith("gs://"):
            config_local = output_dir / "profile.seospiderconfig"
            _download_gcs_uri(cfg, config_local)
        elif Path(cfg).exists():
            config_local = Path(cfg)
        else:
            set_job_error(db, job_id, f"Config not found: {cfg}")
            return

        from screamingfrog.cli.exports import start_crawl

        try:
            start_crawl(
                job.target_url,
                output_dir,
                cli_path=os.environ.get("SF_CLI_PATH"),
                config=config_local,
                headless=True,
                overwrite=True,
                save_crawl=True,
                export_format="csv",
            )
        except RuntimeError as e:
            set_job_error(db, job_id, str(e)[:8000])
            return

        artifact = _find_crawl_artifact(output_dir)
        if artifact is None:
            set_job_error(db, job_id, "No crawl artifact found after GCE crawl")
            return

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
    finally:
        db.close()

    _delete_self_instance()


def main() -> None:
    job_id_raw = os.environ.get("FROG_JOB_ID")
    if not job_id_raw:
        try:
            job_id_raw = _metadata_get("instance/attributes/frog_job_id")
        except Exception as e:
            raise SystemExit("FROG_JOB_ID env or metadata frog_job_id required") from e
    run_worker_for_job(UUID(job_id_raw))


if __name__ == "__main__":
    main()
