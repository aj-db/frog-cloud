locals {
  # Cloud SQL PostgreSQL database_flags.shared_buffers is specified in 8kB blocks.
  shared_buffers_blocks = max(128, floor(var.shared_buffers_mb * 1024 / 8))
}

resource "google_sql_database_instance" "postgres" {
  name             = var.instance_name
  project          = var.project_id
  region           = var.region
  database_version = var.database_version

  settings {
    tier              = var.tier
    disk_type         = "PD_SSD"
    disk_size         = var.disk_size_gb
    availability_type = "ZONAL"
    user_labels       = var.labels

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "03:00"
      transaction_log_retention_days = 7

      backup_retention_settings {
        retained_backups = 14
        retention_unit   = "COUNT"
      }
    }

    ip_configuration {
      ipv4_enabled                                  = false
      private_network                               = var.vpc_network_id
      enable_private_path_for_google_cloud_services = true
    }

    maintenance_window {
      day          = 7
      hour         = 4
      update_track = "stable"
    }

    insights_config {
      query_insights_enabled  = true
      query_string_length     = 1024
      record_application_tags = true
      record_client_address   = true
    }

    database_flags {
      name  = "max_connections"
      value = tostring(var.max_connections)
    }

    database_flags {
      name  = "shared_buffers"
      value = tostring(local.shared_buffers_blocks)
    }
  }

  deletion_protection = var.deletion_protection
}

resource "google_sql_database" "app" {
  name     = var.database_name
  instance = google_sql_database_instance.postgres.name
  project  = var.project_id
}

resource "google_sql_user" "app" {
  name     = var.user_name
  instance = google_sql_database_instance.postgres.name
  project  = var.project_id
  password = var.user_password
}
