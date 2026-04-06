output "service_name" {
  value = google_cloud_run_v2_service.api.name
}

output "service_uri" {
  value = google_cloud_run_v2_service.api.uri
}

output "service_id" {
  value = google_cloud_run_v2_service.api.id
}
