variable "project_id" {
  type = string
}

variable "region" {
  type = string
}

variable "queue_id" {
  type = string
}

variable "enqueue_service_account_email" {
  description = "Service account allowed to create tasks (API runtime)."
  type        = string
}

variable "labels" {
  type    = map(string)
  default = {}
}

variable "max_dispatches_per_second" {
  type    = number
  default = 50
}
