terraform {
  required_version = ">= 1.6"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # Configure at init time, e.g.:
  # terraform init -backend-config="bucket=YOUR_STATE_BUCKET" -backend-config="prefix=frog-in-the-cloud/prod"
  backend "gcs" {}
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  common_labels = merge(var.labels, {
    app         = "frog-in-the-cloud"
    environment = var.environment
  })

  api_sa_email = var.api_service_account_email != null ? var.api_service_account_email : google_service_account.api[0].email

  worker_sa_email = var.worker_service_account_email != null ? var.worker_service_account_email : google_service_account.worker[0].email

  cloud_tasks_oidc_sa_email = var.cloud_tasks_invoker_service_account_email != null ? var.cloud_tasks_invoker_service_account_email : google_service_account.cloud_tasks_oidc[0].email

  gcs_bucket_name = "${var.project_id}-frog-crawl-artifacts-${var.environment}"

  queue_id = "crawl-orchestration-${var.environment}"

  worker_startup_script = templatefile("${path.module}/templates/worker-startup.sh.tftpl", {
    project_id             = var.project_id
    database_url_secret_id = google_secret_manager_secret.database_url.secret_id
    sf_license_secret_id   = google_secret_manager_secret.sf_license_key.secret_id
    cloud_sql_connection   = module.cloud_sql.instance_connection_name
    gcs_bucket             = module.gcs.bucket_name
  })
}

resource "google_service_account" "api" {
  count        = var.api_service_account_email == null ? 1 : 0
  project      = var.project_id
  account_id   = "${var.environment}-frog-api"
  display_name = "Frog in the Cloud API (Cloud Run)"
}

resource "google_service_account" "worker" {
  count        = var.worker_service_account_email == null ? 1 : 0
  project      = var.project_id
  account_id   = "${var.environment}-frog-worker"
  display_name = "Frog in the Cloud GCE crawl worker"
}

resource "google_service_account" "cloud_tasks_oidc" {
  count        = var.cloud_tasks_invoker_service_account_email == null ? 1 : 0
  project      = var.project_id
  account_id   = "${var.environment}-frog-tasks-oidc"
  display_name = "Frog in the Cloud Cloud Tasks OIDC invoker"
}

resource "google_project_service" "apis" {
  for_each = toset([
    "compute.googleapis.com",
    "run.googleapis.com",
    "sqladmin.googleapis.com",
    "servicenetworking.googleapis.com",
    "vpcaccess.googleapis.com",
    "cloudtasks.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
  ])

  project            = var.project_id
  service            = each.key
  disable_on_destroy = false
}

resource "google_compute_network" "main" {
  name                    = "${var.environment}-frog-vpc"
  project                 = var.project_id
  auto_create_subnetworks = false
  routing_mode            = "REGIONAL"

  depends_on = [google_project_service.apis]
}

resource "google_compute_subnetwork" "primary" {
  name                     = "${var.environment}-frog-subnet"
  project                  = var.project_id
  ip_cidr_range            = "10.10.0.0/20"
  region                   = var.region
  network                  = google_compute_network.main.id
  private_ip_google_access = true
}

resource "google_compute_subnetwork" "serverless" {
  name                     = "${var.environment}-frog-serverless-subnet"
  project                  = var.project_id
  ip_cidr_range            = "10.10.16.0/28"
  region                   = var.region
  network                  = google_compute_network.main.id
  private_ip_google_access = true
}

resource "google_compute_global_address" "google_managed_services" {
  name          = "${var.environment}-frog-servicenetworking"
  project       = var.project_id
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.main.id
}

resource "google_service_networking_connection" "private_vpc_connection" {
  network                 = google_compute_network.main.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.google_managed_services.name]

  depends_on = [google_project_service.apis]
}

resource "google_vpc_access_connector" "serverless" {
  name    = "${var.environment}-frog-serverless"
  project = var.project_id
  region  = var.region

  subnet {
    name       = google_compute_subnetwork.serverless.name
    project_id = var.project_id
  }

  machine_type   = "e2-micro"
  min_throughput = 200
  max_throughput = 300

  depends_on = [google_compute_subnetwork.serverless]
}

resource "google_artifact_registry_repository" "api" {
  project       = var.project_id
  location      = var.region
  repository_id = "frog-api"
  description   = "Docker images for the FastAPI control plane"
  format        = "DOCKER"
  labels        = local.common_labels

  depends_on = [google_project_service.apis]
}

module "gcs" {
  source = "./modules/gcs"

  project_id              = var.project_id
  bucket_name             = local.gcs_bucket_name
  location                = var.region
  labels                  = local.common_labels
  artifact_retention_days = var.crawl_artifacts_retention_days

  depends_on = [google_project_service.apis]
}

module "cloud_sql" {
  source = "./modules/cloud-sql"

  project_id          = var.project_id
  region              = var.region
  instance_name       = "${var.environment}-frog-pg"
  tier                = var.db_tier
  vpc_network_id      = google_compute_network.main.id
  database_name       = var.db_name
  user_name           = var.db_user
  user_password       = var.db_password
  max_connections     = var.db_tier == "db-f1-micro" ? 25 : 100
  shared_buffers_mb   = var.db_tier == "db-f1-micro" ? 128 : 256
  disk_size_gb        = 20
  deletion_protection = var.enable_deletion_protection
  labels              = local.common_labels

  depends_on = [
    google_service_networking_connection.private_vpc_connection,
    google_project_service.apis,
  ]
}

resource "google_secret_manager_secret" "database_url" {
  project   = var.project_id
  secret_id = "${var.environment}-frog-database-url"

  replication {
    auto {}
  }

  labels = local.common_labels

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "database_url" {
  secret = google_secret_manager_secret.database_url.id

  secret_data = format(
    "postgresql://%s:%s@/%s?host=/cloudsql/%s",
    var.db_user,
    urlencode(var.db_password),
    var.db_name,
    module.cloud_sql.instance_connection_name
  )

  lifecycle {
    create_before_destroy = true
  }
}

resource "google_secret_manager_secret" "clerk_secret_key" {
  project   = var.project_id
  secret_id = "${var.environment}-frog-clerk-secret-key"

  replication {
    auto {}
  }

  labels = local.common_labels

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "clerk_secret_key" {
  secret      = google_secret_manager_secret.clerk_secret_key.id
  secret_data = var.clerk_secret_key
}

resource "google_secret_manager_secret" "clerk_webhook_secret" {
  project   = var.project_id
  secret_id = "${var.environment}-frog-clerk-webhook-secret"

  replication {
    auto {}
  }

  labels = local.common_labels

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "clerk_webhook_secret" {
  secret      = google_secret_manager_secret.clerk_webhook_secret.id
  secret_data = var.clerk_webhook_secret
}

resource "google_secret_manager_secret" "sf_license_key" {
  project   = var.project_id
  secret_id = "${var.environment}-frog-sf-license-key"

  replication {
    auto {}
  }

  labels = local.common_labels

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "sf_license_key" {
  secret      = google_secret_manager_secret.sf_license_key.id
  secret_data = var.sf_license_key
}

module "cloud_run" {
  source = "./modules/cloud-run"

  project_id                   = var.project_id
  region                       = var.region
  service_name                 = "${var.environment}-frog-api"
  container_image              = var.cloud_run_image
  service_account_email        = local.api_sa_email
  vpc_connector_id             = google_vpc_access_connector.serverless.id
  cloud_sql_connection_name    = module.cloud_sql.instance_connection_name
  min_instances                = var.cloud_run_min_instances
  max_instances                = var.cloud_run_max_instances
  allow_unauthenticated        = var.allow_unauthenticated_cloud_run
  cloud_tasks_invoker_sa_email = local.cloud_tasks_oidc_sa_email

  env_plain = {
    EXECUTOR_BACKEND                          = "gce"
    GCE_DISPATCH_MODE                         = var.gce_dispatch_mode
    GCP_PROJECT_ID                            = var.project_id
    GCS_BUCKET                                = module.gcs.bucket_name
    CLOUD_TASKS_QUEUE_ID                      = local.queue_id
    CLOUD_TASKS_LOCATION                      = var.region
    CLOUD_TASKS_INVOKER_SERVICE_ACCOUNT_EMAIL = local.cloud_tasks_oidc_sa_email
    ENVIRONMENT                               = var.environment
    CLOUD_SQL_INSTANCE                        = module.cloud_sql.instance_connection_name
    GCE_ZONE                                  = var.zone
    GCE_INSTANCE_TEMPLATE                     = module.gce_image.instance_template_name
  }

  env_secrets = {
    DATABASE_URL = {
      secret_id = google_secret_manager_secret.database_url.secret_id
      version   = "latest"
    }
    CLERK_SECRET_KEY = {
      secret_id = google_secret_manager_secret.clerk_secret_key.secret_id
      version   = "latest"
    }
    CLERK_WEBHOOK_SECRET = {
      secret_id = google_secret_manager_secret.clerk_webhook_secret.secret_id
      version   = "latest"
    }
  }

  labels = local.common_labels

  depends_on = [
    module.cloud_sql,
    google_secret_manager_secret_version.database_url,
    google_secret_manager_secret_version.clerk_secret_key,
    google_secret_manager_secret_version.clerk_webhook_secret,
    google_vpc_access_connector.serverless,
  ]
}

module "cloud_tasks" {
  source = "./modules/cloud-tasks"

  project_id                    = var.project_id
  region                        = var.region
  queue_id                      = local.queue_id
  enqueue_service_account_email = local.api_sa_email

  depends_on = [google_project_service.apis]
}

module "gce_image" {
  source = "./modules/gce-image"

  project_id            = var.project_id
  environment           = var.environment
  machine_type          = var.worker_machine_type
  source_image          = var.worker_source_image
  subnetwork_id         = google_compute_subnetwork.primary.id
  service_account_email = local.worker_sa_email
  disk_size_gb          = 50
  network_tags          = ["frog-worker", "https-server"]
  startup_script        = local.worker_startup_script
  labels                = local.common_labels
}

resource "google_compute_instance" "persistent_worker" {
  count        = var.gce_dispatch_mode == "persistent" ? 1 : 0
  project      = var.project_id
  zone         = var.zone
  name         = "${var.environment}-frog-worker-persistent"
  machine_type = var.worker_machine_type
  labels       = local.common_labels

  boot_disk {
    auto_delete = true
    initialize_params {
      image = var.worker_source_image
      size  = 50
      type  = "pd-balanced"
    }
  }

  network_interface {
    subnetwork = google_compute_subnetwork.primary.id
    access_config {
      # Persistent worker still needs outbound internet access for crawling.
    }
  }

  service_account {
    email  = local.worker_sa_email
    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }

  metadata = {
    enable-oslogin    = "TRUE"
    startup-script    = local.worker_startup_script
    gce_dispatch_mode = "persistent"
  }

  tags = ["frog-worker", "https-server"]

  scheduling {
    automatic_restart   = true
    on_host_maintenance = "MIGRATE"
  }

  allow_stopping_for_update = true

  depends_on = [
    module.cloud_sql,
    module.gcs,
    google_secret_manager_secret_version.database_url,
    google_secret_manager_secret_version.sf_license_key,
    google_secret_manager_secret_iam_member.worker_database_url,
    google_secret_manager_secret_iam_member.worker_sf_license,
    google_project_iam_member.worker_cloudsql_client,
    google_project_iam_member.worker_compute_admin,
    google_storage_bucket_iam_member.worker_artifacts_admin,
  ]
}

# --- IAM: least-privilege bindings ---

resource "google_project_iam_member" "api_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${local.api_sa_email}"
}

resource "google_project_iam_member" "worker_cloudsql_client" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${local.worker_sa_email}"
}

resource "google_project_iam_member" "api_compute_admin" {
  project = var.project_id
  role    = "roles/compute.instanceAdmin.v1"
  member  = "serviceAccount:${local.api_sa_email}"
}

resource "google_project_iam_member" "worker_compute_admin" {
  project = var.project_id
  role    = "roles/compute.instanceAdmin.v1"
  member  = "serviceAccount:${local.worker_sa_email}"
}

resource "google_service_account_iam_member" "api_uses_worker_sa" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${local.worker_sa_email}"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${local.api_sa_email}"
}

resource "google_service_account_iam_member" "api_act_as_tasks_oidc" {
  service_account_id = "projects/${var.project_id}/serviceAccounts/${local.cloud_tasks_oidc_sa_email}"
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${local.api_sa_email}"
}

resource "google_secret_manager_secret_iam_member" "api_database_url" {
  secret_id = google_secret_manager_secret.database_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${local.api_sa_email}"
}

resource "google_secret_manager_secret_iam_member" "api_clerk_secret" {
  secret_id = google_secret_manager_secret.clerk_secret_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${local.api_sa_email}"
}

resource "google_secret_manager_secret_iam_member" "api_clerk_webhook" {
  secret_id = google_secret_manager_secret.clerk_webhook_secret.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${local.api_sa_email}"
}

resource "google_secret_manager_secret_iam_member" "worker_database_url" {
  secret_id = google_secret_manager_secret.database_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${local.worker_sa_email}"
}

resource "google_secret_manager_secret_iam_member" "worker_sf_license" {
  secret_id = google_secret_manager_secret.sf_license_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${local.worker_sa_email}"
}

resource "google_storage_bucket_iam_member" "worker_artifacts_admin" {
  bucket = module.gcs.bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${local.worker_sa_email}"
}

resource "google_storage_bucket_iam_member" "api_artifacts_admin" {
  bucket = module.gcs.bucket_name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${local.api_sa_email}"
}
