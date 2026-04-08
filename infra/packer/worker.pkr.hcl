# Packer template: GCE image for Screaming Frog crawl workers (Ubuntu 24.04).
# No secrets are baked into the image. License and DB URLs load at runtime (Secret Manager + worker SA).
#
# The Screaming Frog CLI .deb must be readable from the build VM — typically a private GCS object
# (upload the .deb from a licensed workstation, then reference gs://... below).
#
# Example:
#   packer build \
#     -var=project_id=my-proj \
#     -var=zone=us-central1-a \
#     -var=image_version=$(git rev-parse --short HEAD) \
#     -var=screaming_frog_deb_gs_uri=gs://my-build-artifacts/internal/screamingfrogseospider_cli_amd64.deb \
#     worker.pkr.hcl

packer {
  required_plugins {
    googlecompute = {
      version = ">= 1.1.0"
      source  = "github.com/hashicorp/googlecompute"
    }
  }
}

variable "project_id" {
  type        = string
  description = "GCP project for the temporary build VM and resulting image."
}

variable "zone" {
  type    = string
  default = "us-central1-a"
}

variable "machine_type" {
  type    = string
  default = "e2-standard-4"
}

variable "image_version" {
  type        = string
  description = "Version label for the image name (e.g. git SHA or SemVer)."
}

variable "network" {
  type    = string
  default = "default"
}

variable "subnetwork" {
  type        = string
  default     = ""
  description = "Optional subnetwork name or self-link; empty uses the network default."
}

variable "screaming_frog_deb_gs_uri" {
  type        = string
  description = "gs:// URI of the Screaming Frog SEO Spider CLI .deb (private bucket; builder SA needs storage.objectViewer)."
}

variable "cloud_sql_proxy_version" {
  type    = string
  default = "2.14.1"
}

variable "api_source_dir" {
  type        = string
  default     = ""
  description = "Absolute or relative path to the api/ directory (Python app). Defaults to ../../api relative to this file."
}

locals {
  image_name   = "frog-worker-${var.image_version}"
  api_dir      = var.api_source_dir != "" ? var.api_source_dir : "${path.root}/../../api"
}

source "googlecompute" "frog_worker" {
  project_id              = var.project_id
  source_image_family     = "ubuntu-2404-lts-amd64"
  source_image_project_id = ["ubuntu-os-cloud"]
  zone                    = var.zone
  machine_type            = var.machine_type
  disk_size               = 50
  disk_type               = "pd-balanced"

  image_name        = local.image_name
  image_family      = "frog-worker"
  image_description = "Frog in the Cloud worker — OpenJDK 21, SF CLI, Python 3.13, Cloud SQL Auth Proxy"

  network    = var.network
  subnetwork = var.subnetwork != "" ? var.subnetwork : null

  metadata = {
    enable-oslogin = "TRUE"
  }

  ssh_username = "ubuntu"
  scopes       = ["https://www.googleapis.com/auth/cloud-platform"]
}

build {
  sources = ["source.googlecompute.frog_worker"]

  provisioner "shell" {
    inline = [
      "set -eu",
      "export DEBIAN_FRONTEND=noninteractive",
      "sudo apt-get update",
      "sudo apt-get upgrade -y",
      "sudo apt-get install -y --no-install-recommends ca-certificates curl gnupg lsb-release software-properties-common apt-transport-https",
      "sudo apt-get install -y --no-install-recommends openjdk-21-jre-headless",
      "sudo apt-get install -y --no-install-recommends fontconfig fonts-dejavu-core fonts-dejavu-extra fonts-dejavu-mono libasound2t64 libatk1.0-0t64 libatspi2.0-0t64 libgbm1 libx11-xcb1 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libxshmfence1 libxtst6",
      "sudo add-apt-repository -y ppa:deadsnakes/ppa",
      "sudo apt-get update",
      "sudo apt-get install -y --no-install-recommends python3.13 python3.13-venv python3.13-dev",
      "curl -fsSL https://bootstrap.pypa.io/get-pip.py | sudo python3.13",
    ]
  }

  provisioner "shell" {
    inline = [
      "set -eu",
      "gsutil cp '${var.screaming_frog_deb_gs_uri}' /tmp/screamingfrog.deb",
      "sudo dpkg -i /tmp/screamingfrog.deb || sudo apt-get -f install -y",
      "rm -f /tmp/screamingfrog.deb",
    ]
  }

  provisioner "shell" {
    inline = [
      "set -eu",
      "sudo groupadd --system frogworker 2>/dev/null || true",
      "sudo useradd --system --gid frogworker --create-home --shell /bin/bash frogworker 2>/dev/null || true",
      "sudo mkdir -p /opt/frog/app /opt/frog/configs",
      "sudo chown -R frogworker:frogworker /opt/frog",
    ]
  }

  provisioner "file" {
    source      = local.api_dir
    destination = "/tmp/frog-api-src"
  }

  provisioner "shell" {
    inline = [
      "set -eu",
      "sudo rm -rf /opt/frog/app/*",
      "sudo cp -a /tmp/frog-api-src/. /opt/frog/app/",
      "sudo rm -rf /opt/frog/app/.venv /opt/frog/app/.mypy_cache 2>/dev/null || true",
      "sudo find /opt/frog/app -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true",
      "sudo chown -R frogworker:frogworker /opt/frog/app",
      "sudo -u frogworker python3.13 -m venv /opt/frog/venv",
      "sudo -u frogworker /opt/frog/venv/bin/pip install --upgrade pip setuptools wheel",
      "sudo -u frogworker /opt/frog/venv/bin/pip install -r /opt/frog/app/requirements.txt",
      "sudo rm -rf /tmp/frog-api-src",
    ]
  }

  provisioner "shell" {
    inline = [
      "set -eu",
      "VER=${var.cloud_sql_proxy_version}",
      "curl -fsSL -o /tmp/cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v$${VER}/cloud-sql-proxy.linux.amd64",
      "sudo install -m 0755 /tmp/cloud-sql-proxy /usr/local/bin/cloud-sql-proxy",
      "rm -f /tmp/cloud-sql-proxy",
    ]
  }

  provisioner "shell" {
    inline = [
      "set -eu",
      "sudo apt-get autoremove -y",
      "sudo apt-get clean",
      "sudo rm -rf /var/lib/apt/lists/*",
    ]
  }
}
