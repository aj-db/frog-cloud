variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "instance_name" {
  type = string
}

variable "database_version" {
  type    = string
  default = "POSTGRES_16"
}

variable "tier" {
  type = string
}

variable "vpc_network_id" {
  description = "VPC network id (projects/.../global/networks/...)."
  type        = string
}

variable "database_name" {
  type = string
}

variable "user_name" {
  type = string
}

variable "user_password" {
  type      = string
  sensitive = true
}

variable "max_connections" {
  type    = number
  default = 100
}

variable "shared_buffers_mb" {
  description = "shared_buffers in MB for PostgreSQL (Cloud SQL expresses via flag in some setups; we set 8kB units: value * 1024 / 8)."
  type        = number
  default     = 128
}

variable "disk_size_gb" {
  type    = number
  default = 20
}

variable "deletion_protection" {
  type    = bool
  default = true
}

variable "labels" {
  type    = map(string)
  default = {}
}
