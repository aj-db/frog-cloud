variable "project_id" {
  type = string
}

variable "environment" {
  type = string
}

variable "machine_type" {
  type = string
}

variable "source_image" {
  description = "Worker boot image (Packer artifact)."
  type        = string
}

variable "subnetwork_id" {
  description = "Subnetwork self link or id for worker NICs."
  type        = string
}

variable "service_account_email" {
  type = string
}

variable "disk_size_gb" {
  type    = number
  default = 50
}

variable "network_tags" {
  description = "Firewall / NAT tags for worker instances."
  type        = list(string)
  default     = ["frog-worker", "allow-egress"]
}

variable "startup_script" {
  description = "Optional inline startup script (use empty string with startup_script_url)."
  type        = string
  default     = ""
}

variable "startup_script_url" {
  description = "Optional gs:// URL for startup script (preferred for large scripts)."
  type        = string
  default     = ""
}

variable "labels" {
  type    = map(string)
  default = {}
}
