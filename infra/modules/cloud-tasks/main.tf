resource "google_cloud_tasks_queue" "crawl_orchestration" {
  name     = var.queue_id
  project  = var.project_id
  location = var.region

  retry_config {
    max_attempts       = 3
    min_backoff        = "10s"
    max_backoff        = "300s"
    max_doublings      = 4
    max_retry_duration = "3600s"
  }

  rate_limits {
    max_dispatches_per_second = var.max_dispatches_per_second
  }

  stackdriver_logging_config {
    sampling_ratio = 1.0
  }
}

resource "google_cloud_tasks_queue_iam_member" "api_enqueuer" {
  project  = google_cloud_tasks_queue.crawl_orchestration.project
  location = google_cloud_tasks_queue.crawl_orchestration.location
  name     = google_cloud_tasks_queue.crawl_orchestration.name
  role     = "roles/cloudtasks.enqueuer"
  member   = "serviceAccount:${var.enqueue_service_account_email}"
}