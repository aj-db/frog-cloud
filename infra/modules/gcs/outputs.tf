output "bucket_name" {
  value = google_storage_bucket.crawl_artifacts.name
}

output "bucket_url" {
  value = google_storage_bucket.crawl_artifacts.url
}

output "bucket_self_link" {
  value = google_storage_bucket.crawl_artifacts.self_link
}
