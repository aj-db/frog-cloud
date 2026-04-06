output "cloud_run_url" {
  description = "HTTPS URL of the Cloud Run API service."
  value       = module.cloud_run.service_uri
}

output "cloud_sql_instance" {
  description = "Cloud SQL instance resource name (projects/.../instances/...)."
  value       = module.cloud_sql.instance_name
}

output "cloud_sql_connection_name" {
  description = "Cloud SQL instance connection name for unix socket / connectors."
  value       = module.cloud_sql.instance_connection_name
}

output "gcs_bucket_name" {
  description = "Private GCS bucket for tenant-prefixed crawl artifacts."
  value       = module.gcs.bucket_name
}

output "cloud_tasks_queue_name" {
  description = "Cloud Tasks queue ID."
  value       = module.cloud_tasks.queue_id
}

output "cloud_tasks_queue_path" {
  description = "Full queue path for application enqueue calls."
  value       = module.cloud_tasks.queue_path
}

output "vpc_network_name" {
  description = "VPC used for private Cloud SQL peering and GCE workers."
  value       = google_compute_network.main.name
}

output "worker_instance_template_self_link" {
  description = "Self link of the worker compute instance template."
  value       = module.gce_image.instance_template_self_link
}

output "api_service_account_email" {
  description = "Email of the API runtime service account."
  value       = local.api_sa_email
}

output "worker_service_account_email" {
  description = "Email of the GCE worker service account."
  value       = local.worker_sa_email
}

output "cloud_tasks_oidc_service_account_email" {
  description = "Service account used as Cloud Tasks OIDC identity when invoking Cloud Run."
  value       = local.cloud_tasks_oidc_sa_email
}

output "artifact_registry_repository" {
  description = "Docker Artifact Registry repository for API images."
  value       = google_artifact_registry_repository.api.name
}

output "domain_name" {
  description = "Optional hostname recorded for the API (see variable domain_name)."
  value       = var.domain_name
}
