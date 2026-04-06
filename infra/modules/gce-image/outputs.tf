output "instance_template_id" {
  value = google_compute_instance_template.worker.id
}

output "instance_template_self_link" {
  value = google_compute_instance_template.worker.self_link
}

output "instance_template_name" {
  value = google_compute_instance_template.worker.name
}
