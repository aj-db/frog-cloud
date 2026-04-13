"""Application configuration from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ExecutorBackend = Literal["local", "none", "gce"]
GceDispatchMode = Literal["ephemeral", "persistent"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    database_url: str = Field(..., alias="DATABASE_URL")
    clerk_secret_key: str = Field(default="", alias="CLERK_SECRET_KEY")
    clerk_publishable_key: str = Field(default="", alias="CLERK_PUBLISHABLE_KEY")
    clerk_jwks_url: str | None = Field(default=None, alias="CLERK_JWKS_URL")
    clerk_webhook_secret: str | None = Field(default=None, alias="CLERK_WEBHOOK_SECRET")
    sf_cli_path: str | None = Field(default=None, alias="SF_CLI_PATH")
    java_home: str | None = Field(default=None, alias="JAVA_HOME")
    cors_origins: str = Field(
        default="http://localhost:3000",
        alias="CORS_ORIGINS",
        description="Comma-separated list of allowed browser origins.",
    )
    executor_backend: ExecutorBackend = Field(default="local", alias="EXECUTOR_BACKEND")
    gce_dispatch_mode: GceDispatchMode = Field(
        default="ephemeral",
        alias="GCE_DISPATCH_MODE",
    )
    gcp_project_id: str | None = Field(default=None, alias="GCP_PROJECT_ID")
    gcs_bucket: str | None = Field(
        default=None,
        validation_alias=AliasChoices("GCS_BUCKET", "GCS_ARTIFACTS_BUCKET"),
    )
    cloud_sql_instance: str | None = Field(
        default=None,
        validation_alias=AliasChoices("CLOUD_SQL_INSTANCE", "CLOUD_SQL_CONN_NAME"),
    )
    cloud_tasks_queue_id: str | None = Field(default=None, alias="CLOUD_TASKS_QUEUE_ID")
    cloud_tasks_location: str | None = Field(default=None, alias="CLOUD_TASKS_LOCATION")
    cloud_tasks_invoker_service_account_email: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "CLOUD_TASKS_INVOKER_SERVICE_ACCOUNT_EMAIL",
            "CLOUD_TASKS_INVOKER_SA_EMAIL",
        ),
    )
    # GCE / internal control plane
    gce_zone: str | None = Field(default=None, alias="GCE_ZONE")
    gce_instance_template: str | None = Field(default=None, alias="GCE_INSTANCE_TEMPLATE")
    gce_worker_service_account: str | None = Field(default=None, alias="GCE_WORKER_SERVICE_ACCOUNT")
    internal_oidc_audience: str | None = Field(
        default=None,
        alias="INTERNAL_OIDC_AUDIENCE",
        description="Expected audience for Google-signed OIDC tokens on /internal/*.",
    )
    extract_skip_orphan_issues: bool = Field(
        default=False,
        alias="EXTRACT_SKIP_ORPHAN_ISSUES",
        description="When true, issue rows that cannot be resolved to a crawl page are dropped during extraction.",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def cors_origin_list() -> list[str]:
    """Parse CORS_ORIGINS from settings (reads .env via pydantic-settings)."""
    raw = get_settings().cors_origins.strip()
    if not raw:
        return ["http://localhost:3000"]
    parts = [o.strip() for o in raw.split(",") if o.strip()]
    if "http://localhost:3000" not in parts:
        parts.append("http://localhost:3000")
    return parts
