"""Cloud Tasks helpers for GCE crawl orchestration."""

from __future__ import annotations

from uuid import UUID

from app.config import get_settings
from app.schemas import LaunchWorkerPayload


def enqueue_launch_worker_task(*, job_id: UUID, launch_url: str) -> str:
    """Create a Cloud Task that calls the internal launch-worker endpoint."""
    from google.cloud import tasks_v2

    settings = get_settings()
    if (
        not settings.gcp_project_id
        or not settings.cloud_tasks_location
        or not settings.cloud_tasks_queue_id
        or not settings.cloud_tasks_invoker_service_account_email
    ):
        raise RuntimeError(
            "Cloud Tasks is not configured "
            "(GCP_PROJECT_ID, CLOUD_TASKS_LOCATION, CLOUD_TASKS_QUEUE_ID, "
            "CLOUD_TASKS_INVOKER_SERVICE_ACCOUNT_EMAIL)"
        )

    client = tasks_v2.CloudTasksClient()
    parent = client.queue_path(
        settings.gcp_project_id,
        settings.cloud_tasks_location,
        settings.cloud_tasks_queue_id,
    )
    payload = LaunchWorkerPayload(job_id=str(job_id)).model_dump_json().encode("utf-8")
    task = tasks_v2.Task(
        http_request=tasks_v2.HttpRequest(
            http_method=tasks_v2.HttpMethod.POST,
            url=launch_url,
            headers={"Content-Type": "application/json"},
            body=payload,
            oidc_token=tasks_v2.OidcToken(
                service_account_email=settings.cloud_tasks_invoker_service_account_email,
                audience=settings.internal_oidc_audience or launch_url,
            ),
        )
    )
    created = client.create_task(request={"parent": parent, "task": task})
    return created.name
