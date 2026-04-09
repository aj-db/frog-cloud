"""Provision GCE worker VMs for queued crawl jobs (Phase 4)."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import CrawlJob, JobExecutor, JobStatus
from crawler.progress import transition_job_status

logger = logging.getLogger(__name__)


def launch_worker_vm(db: Session, job_id: UUID) -> str:
    """
    Idempotently transition job queued -> provisioning and call Compute Engine instances.insert.

    Returns the operation name or instance name on success.
    """
    settings = get_settings()
    if not settings.gcp_project_id or not settings.gce_zone or not settings.gce_instance_template:
        raise RuntimeError("GCE launcher is not configured (GCP_PROJECT_ID, GCE_ZONE, GCE_INSTANCE_TEMPLATE)")

    try:
        from google.cloud import compute_v1
    except ImportError as e:
        raise RuntimeError("google-cloud-compute is not installed. Add it to requirements and pip install.") from e

    job = db.execute(select(CrawlJob).where(CrawlJob.id == job_id)).scalar_one_or_none()
    if job is None:
        raise ValueError("Job not found")
    if job.executor != JobExecutor.gce:
        raise ValueError("Job is not configured for GCE executor")
    if job.status not in (JobStatus.queued, JobStatus.provisioning):
        raise ValueError(f"Job is not launchable in status {job.status}")

    if not transition_job_status(
        db,
        job_id,
        from_statuses=(JobStatus.queued,),
        to_status=JobStatus.provisioning,
    ):
        db.refresh(job)
        if job.status == JobStatus.provisioning:
            logger.info("Job %s already provisioning", job_id)
        else:
            raise ValueError("Could not acquire queued -> provisioning lock")

    client = compute_v1.InstancesClient()
    template_client = compute_v1.InstanceTemplatesClient()
    template_url = f"projects/{settings.gcp_project_id}/global/instanceTemplates/{settings.gce_instance_template}"

    instance_name = f"sf-worker-{str(job_id).replace('-', '')[:24]}"

    template = template_client.get(
        project=settings.gcp_project_id,
        instance_template=settings.gce_instance_template,
    )
    template_metadata = getattr(getattr(template, "properties", None), "metadata", None)
    metadata_by_key = {
        item.key: item.value for item in (getattr(template_metadata, "items", None) or []) if getattr(item, "key", None)
    }
    metadata_by_key.update(
        {
            "frog_job_id": str(job_id),
            "frog_tenant_id": str(job.tenant_id),
        }
    )
    metadata_items = [compute_v1.Items(key=key, value=value) for key, value in metadata_by_key.items()]

    body = compute_v1.Instance(
        name=instance_name,
        metadata=compute_v1.Metadata(items=metadata_items),
    )

    req = compute_v1.InsertInstanceRequest(
        project=settings.gcp_project_id,
        zone=settings.gce_zone,
        source_instance_template=template_url,
        instance_resource=body,
    )

    try:
        op = client.insert(request=req)
        logger.info("Started GCE insert for job %s: %s", job_id, op.name)
        return op.name or instance_name
    except Exception as e:
        logger.exception("instances.insert failed for job %s", job_id)
        transition_job_status(
            db,
            job_id,
            from_statuses=(JobStatus.provisioning,),
            to_status=JobStatus.failed,
            error=f"Provisioning failed: {e}",
        )
        raise
