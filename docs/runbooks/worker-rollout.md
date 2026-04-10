# Worker Rollout Runbook

## Purpose

Use this runbook for the persistent GCE worker release path. The worker now deploys separately from the Cloud Run API so merges to `main` that touch worker runtime code also rebuild and roll the staging worker image forward.

## Automated Staging Path

`main` pushes trigger `.github/workflows/packer-build.yml` when they touch any of these worker-relevant paths:

- `.github/workflows/packer-build.yml`
- `infra/packer/**`
- `infra/main.tf`
- `infra/variables.tf`
- `infra/modules/gce-image/**`
- `infra/templates/worker-startup.sh.tftpl`
- `api/app/**`
- `api/crawler/**`
- `api/requirements.txt`

The workflow now does four things in sequence:

1. Builds a new image named `frog-worker-${GITHUB_SHA}` with Packer.
2. Resolves the concrete image ref as `projects/<project>/global/images/frog-worker-${GITHUB_SHA}`.
3. Runs a targeted Terraform plan/apply for `module.gce_image` and `google_compute_instance.persistent_worker` in staging.
4. Verifies the staging worker metadata and startup markers against the expected SHA.

The workflow concurrency is serialized (`cancel-in-progress: false`) so a newer `main` push waits for the active worker rollout to finish instead of cancelling Terraform midway through an apply.

Manual dispatches support two modes:

- `staging`: build and roll staging forward through the same workflow.
- `production`: build only. Production rollout stays manual until the staging path has more runtime history.

The Terraform rollout intentionally targets the worker template and persistent worker instance instead of doing a full-stack reconcile. Use the normal infra workflow for broad environment changes; use this worker rollout path when the goal is to move the worker image and startup metadata forward without touching unrelated API or database resources.

## Required GitHub Environment Configuration

The `staging` GitHub Environment must provide these variables:

- `GCP_PROJECT_ID`
- `GCP_REGION`
- `CLOUD_RUN_SERVICE_NAME`
- `SCREAMING_FROG_DEB_GS_URI`
- `TERRAFORM_STATE_BUCKET`
- `GCP_ZONE` optional, defaults to `us-central1-a`
- `TERRAFORM_STATE_PREFIX` optional, defaults to `frog-in-the-cloud/staging`

The `staging` GitHub Environment must provide these secrets:

- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_PACKER_SERVICE_ACCOUNT_EMAIL`
- `GCP_SERVICE_ACCOUNT_EMAIL`
- `GCP_DATABASE_URL_SECRET_ID`

The service account in `GCP_SERVICE_ACCOUNT_EMAIL` must also be able to:

- read the current Cloud Run service to capture the existing API image
- read Secret Manager values for the database URL, Clerk secrets, and Screaming Frog license
- run Terraform against the existing staging state and update GCE resources
- read the staging instance metadata and serial output for verification

## Release Observability

The worker release is now exposed in three places:

- the built image contains `/opt/frog/WORKER_RELEASE_SHA` and `/opt/frog/WORKER_IMAGE_NAME`
- Terraform writes `worker_release_sha` and `worker_source_image` into the persistent worker metadata
- the startup script logs the resolved release and emits service-active markers after bootstrap

The `frog-worker` service also writes a startup banner into `/var/log/frog/worker.log` before entering `python -m crawler.worker`.

## Staging Verification Checklist

After the workflow finishes, confirm all of the following:

1. The Packer job reported a concrete image ref like `projects/<project>/global/images/frog-worker-<sha>`.
2. The rollout job passed both verification steps:
   - instance metadata matches the expected `worker_source_image`
   - instance metadata matches the expected `worker_release_sha`
3. The serial console output includes:
   - `frog-worker.service active: active`
   - `Worker bootstrap complete for release <sha>`
4. The crawl detail UI can complete a small smoke crawl without falling back to the partial-data state.

## Manual Staging Rollback

If the new image is bad, roll the worker back by applying the previous image ref through Terraform.

1. Pick the last known-good image ref, for example `projects/<project>/global/images/frog-worker-<old_sha>`.
2. Authenticate to GCP with the staging Terraform/deployer service account.
3. Export the same Terraform inputs that the workflow prepares, but set:

```bash
export TF_VAR_worker_source_image="projects/<project>/global/images/frog-worker-<old_sha>"
export TF_VAR_worker_release_sha="<old_sha>"
```

4. Re-run the targeted apply from `infra/`:

```bash
terraform init \
  -input=false \
  -backend-config="bucket=${TERRAFORM_STATE_BUCKET}" \
  -backend-config="prefix=${TERRAFORM_STATE_PREFIX:-frog-in-the-cloud/staging}"

terraform plan \
  -input=false \
  -lock-timeout=5m \
  -out=tfplan \
  -target=module.gce_image \
  -target=google_compute_instance.persistent_worker

terraform apply -input=false -auto-approve tfplan
```

5. Re-run the staging verification checklist above.

## Incident Notes

This rollout path exists to prevent the specific failure mode where worker code changed in `main`, Cloud Run updated, but the persistent GCE worker kept running an older Python build. If a crawl gets stuck in `loading` again, check the worker metadata and startup markers before assuming the runtime bug has regressed.
