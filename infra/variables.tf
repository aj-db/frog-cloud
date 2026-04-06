variable "project_id" {
  description = "GCP project ID for all resources."
  type        = string
}

variable "region" {
  description = "Primary GCP region (Cloud Run, Cloud SQL, queues, GCE zone family)."
  type        = string
  default     = "us-central1"
}

variable "zone" {
  description = "Zone for zonal resources (GCE template default, Packer builds)."
  type        = string
  default     = "us-central1-a"
}

variable "environment" {
  description = "Deployment stage: dev, staging, or prod."
  type        = string
  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod."
  }
}

variable "db_password" {
  description = "PostgreSQL application user password (sensitive). Prefer short-lived rotation via Secret Manager after bootstrap."
  type        = string
  sensitive   = true
}

variable "db_tier" {
  description = "Cloud SQL machine tier (e.g. db-f1-micro for dev, db-custom-2-8192 for production)."
  type        = string
  default     = "db-f1-micro"
}

variable "db_name" {
  description = "Logical database name inside the instance."
  type        = string
  default     = "frog"
}

variable "db_user" {
  description = "PostgreSQL application username."
  type        = string
  default     = "frog_api"
}

variable "cloud_run_image" {
  description = "Fully qualified container image for the FastAPI service (Artifact Registry or GCR)."
  type        = string
}

variable "api_service_account_email" {
  description = "Runtime service account for Cloud Run (API). If null, Terraform creates google_service_account.api."
  type        = string
  default     = null
}

variable "worker_service_account_email" {
  description = "Service account attached to GCE worker VMs. If null, Terraform creates google_service_account.worker."
  type        = string
  default     = null
}

variable "clerk_secret_key" {
  description = "Clerk secret key for JWT verification (stored in Secret Manager; not logged)."
  type        = string
  sensitive   = true
}

variable "clerk_webhook_secret" {
  description = "Clerk webhook signing secret (stored in Secret Manager)."
  type        = string
  sensitive   = true
}

variable "sf_license_key" {
  description = "Screaming Frog license key material for workers (Secret Manager only; never in images)."
  type        = string
  sensitive   = true
}

variable "domain_name" {
  description = "Optional public hostname for the API (documentation / future DNS). Map TLS via Cloud Run domain mappings, external LB, or DNS; not applied automatically by this stack."
  type        = string
  default     = null
}

variable "terraform_state_bucket" {
  description = "GCS bucket for remote Terraform state (must exist before first init)."
  type        = string
}

variable "terraform_state_prefix" {
  description = "Prefix inside the state bucket for this stack."
  type        = string
  default     = "frog-in-the-cloud"
}

variable "crawl_artifacts_retention_days" {
  description = "Lifecycle rule: delete crawl artifacts after N days."
  type        = number
  default     = 90
}

variable "worker_machine_type" {
  description = "Default GCE machine type for worker instance template."
  type        = string
  default     = "e2-standard-4"
}

variable "worker_source_image" {
  description = "Boot image for workers (output from Packer build, e.g. projects/.../global/images/frog-worker-...)."
  type        = string
}

variable "cloud_run_min_instances" {
  description = "Minimum Cloud Run instances (0 allows scale-to-zero)."
  type        = number
  default     = 0
}

variable "cloud_run_max_instances" {
  description = "Maximum Cloud Run instances."
  type        = number
  default     = 10
}

variable "allow_unauthenticated_cloud_run" {
  description = "If true, grant roles/run.invoker to allUsers so browsers can call the API with Clerk JWTs. If false, restrict via additional IAM members only."
  type        = bool
  default     = true
}

variable "cloud_tasks_invoker_service_account_email" {
  description = "Service account whose identity Cloud Tasks uses for OIDC tokens to Cloud Run. If null, Terraform creates one."
  type        = string
  default     = null
}

variable "labels" {
  description = "Resource labels applied across the stack."
  type        = map(string)
  default     = {}
}

variable "enable_deletion_protection" {
  description = "Protect Cloud SQL from destroy (enable in production)."
  type        = bool
  default     = true
}
