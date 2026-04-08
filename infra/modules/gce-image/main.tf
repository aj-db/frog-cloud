locals {
  metadata_startup = var.startup_script_url != "" ? {
    startup-script-url = var.startup_script_url
    } : var.startup_script != "" ? {
    startup-script = var.startup_script
  } : {}
}

resource "google_compute_instance_template" "worker" {
  name_prefix  = "${var.environment}-frog-worker-"
  project      = var.project_id
  machine_type = var.machine_type

  labels = var.labels

  disk {
    boot         = true
    auto_delete  = true
    disk_size_gb = var.disk_size_gb
    disk_type    = "pd-balanced"
    source_image = var.source_image
  }

  network_interface {
    subnetwork = var.subnetwork_id
    access_config {
      # Ephemeral public IP required for crawling external URLs.
    }
  }

  service_account {
    email  = var.service_account_email
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }

  metadata = merge(
    {
      enable-oslogin = "TRUE"
      gce_dispatch_mode = "ephemeral"
    },
    local.metadata_startup
  )

  tags = var.network_tags

  scheduling {
    automatic_restart   = true
    on_host_maintenance = "MIGRATE"
  }

  lifecycle {
    create_before_destroy = true
  }
}
