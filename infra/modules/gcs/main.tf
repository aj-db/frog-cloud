resource "google_storage_bucket" "crawl_artifacts" {
  name                        = var.bucket_name
  project                     = var.project_id
  location                    = var.location
  storage_class               = "STANDARD"
  uniform_bucket_level_access = true
  force_destroy               = false

  labels = var.labels

  public_access_prevention = "enforced"

  versioning {
    enabled = false
  }

  lifecycle_rule {
    condition {
      age = var.artifact_retention_days
    }
    action {
      type = "Delete"
    }
  }
}
