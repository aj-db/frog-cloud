variable "project_id" {
  type = string
}

variable "bucket_name" {
  description = "Globally unique GCS bucket name."
  type        = string
}

variable "location" {
  description = "Bucket location (region or multi-region)."
  type        = string
}

variable "labels" {
  type    = map(string)
  default = {}
}

variable "artifact_retention_days" {
  description = "Delete objects after this many days."
  type        = number
  default     = 90
}
