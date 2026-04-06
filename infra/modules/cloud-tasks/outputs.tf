output "queue_id" {
  value = google_cloud_tasks_queue.crawl_orchestration.name
}

output "queue_path" {
  value = "projects/${google_cloud_tasks_queue.crawl_orchestration.project}/locations/${google_cloud_tasks_queue.crawl_orchestration.location}/queues/${google_cloud_tasks_queue.crawl_orchestration.name}"
}
