variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "service_name" {
  type = string
}

variable "container_image" {
  type = string
}

variable "service_account_email" {
  type = string
}

variable "vpc_connector_id" {
  description = "Serverless VPC connector id for private IP Cloud SQL."
  type        = string
}

variable "cloud_sql_connection_name" {
  description = "Cloud SQL connection name (project:region:instance)."
  type        = string
}

variable "min_instances" {
  type = number
}

variable "max_instances" {
  type = number
}

variable "cpu" {
  type    = string
  default = "2"
}

variable "memory" {
  type    = string
  default = "2Gi"
}

variable "timeout_seconds" {
  type    = number
  default = 300
}

variable "env_plain" {
  description = "Non-secret environment variables."
  type        = map(string)
  default     = {}
}

variable "env_secrets" {
  description = "Map of env var name => { secret_id, version } for Secret Manager refs."
  type = map(object({
    secret_id = string
    version   = string
  }))
  default = {}
}

variable "allow_unauthenticated" {
  type = bool
}

variable "cloud_tasks_invoker_sa_email" {
  description = "Grant run.invoker to this SA for Cloud Tasks OIDC."
  type        = string
}

variable "labels" {
  type    = map(string)
  default = {}
}
