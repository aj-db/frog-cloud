"""Pydantic v2 request/response models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_serializer

# --- Shared -----------------------------------------------------------------

JobStatusLiteral = Literal[
    "queued",
    "provisioning",
    "running",
    "extracting",
    "loading",
    "complete",
    "failed",
    "cancelled",
]
JobExecutorLiteral = Literal["local", "none", "gce"]
IssueSeverityLiteral = Literal["error", "warning", "info"]


class PaginatedResponse[T](BaseModel):
    model_config = ConfigDict(from_attributes=True)

    items: list[T]
    next_cursor: str | None = None
    total_count: int = 0


# --- Tenant -----------------------------------------------------------------

class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    clerk_org_id: str
    name: str
    plan: str
    settings: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    @field_serializer("id")
    def serialize_uuid(self, v: Any) -> str:
        return str(v)


# --- Crawl profile ------------------------------------------------------------

class CrawlProfileCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    config_path: str = Field(..., min_length=1)


class CrawlProfileUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    config_path: str | None = Field(default=None, min_length=1)


class CrawlProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    name: str
    description: str | None
    config_path: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("id", "tenant_id")
    def serialize_uuids(self, v: Any) -> str:
        return str(v)


# --- Crawl job ----------------------------------------------------------------

class CrawlJobCreate(BaseModel):
    profile_id: str
    target_url: str = Field(..., min_length=1)
    max_urls: int | None = Field(default=None, ge=1, le=1_000_000)


class CrawlJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    profile_id: UUID
    target_url: str
    status: JobStatusLiteral
    progress_pct: float | None
    executor: JobExecutorLiteral
    started_at: datetime | None
    completed_at: datetime | None
    last_heartbeat_at: datetime | None
    max_urls: int | None
    urls_crawled: int
    status_message: str | None
    error: str | None
    artifact_prefix: str | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("id", "tenant_id", "profile_id")
    def serialize_uuids(self, v: Any) -> str:
        return str(v)


class CrawlJobListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    profile_id: UUID
    target_url: str
    status: JobStatusLiteral
    progress_pct: float | None
    executor: JobExecutorLiteral
    started_at: datetime | None
    completed_at: datetime | None
    last_heartbeat_at: datetime | None
    max_urls: int | None
    urls_crawled: int
    status_message: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("id", "tenant_id", "profile_id")
    def serialize_uuids(self, v: Any) -> str:
        return str(v)


class CrawlJobCreateAccepted(BaseModel):
    job_id: str
    status: JobStatusLiteral = "queued"


class CrawlJobListEnvelope(BaseModel):
    items: list[CrawlJobListResponse]
    next_cursor: str | None = None


# --- Crawl page ---------------------------------------------------------------

class CrawlPageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    address: str
    status_code: int | None
    title: str | None
    meta_description: str | None
    h1: str | None
    word_count: int | None
    indexability: str | None
    crawl_depth: int | None
    response_time: float | None
    canonical: str | None
    content_type: str | None
    redirect_url: str | None
    size_bytes: int | None
    inlinks: int | None
    outlinks: int | None
    meta_robots: str | None
    canonical_link_element: str | None
    pagination_status: str | None
    http_version: str | None
    x_robots_tag: str | None
    link_score: float | None
    in_sitemap: bool | None
    extra_metadata: dict[str, Any] = Field(
        default_factory=dict,
        serialization_alias="metadata",
    )
    created_at: datetime
    updated_at: datetime

    @field_serializer("id", "job_id")
    def serialize_uuids(self, v: Any) -> str:
        return str(v)


# --- Issues / links -----------------------------------------------------------

class CrawlIssueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    page_id: UUID | None
    issue_type: str
    severity: IssueSeverityLiteral
    details: str | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("id", "job_id", "page_id")
    def serialize_uuids(self, v: Any) -> str | None:
        return str(v) if v is not None else None


class CrawlLinkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    source_url: str
    target_url: str
    link_type: str | None
    anchor_text: str | None
    status_code: int | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("id", "job_id")
    def serialize_uuids(self, v: Any) -> str:
        return str(v)


# --- Scheduled crawl ----------------------------------------------------------

class ScheduledCrawlCreate(BaseModel):
    profile_id: str
    target_url: str = Field(..., min_length=1)
    cron_expression: str = Field(..., min_length=1, max_length=128)
    timezone: str = Field(default="UTC", max_length=64)
    is_active: bool = True


class ScheduledCrawlUpdate(BaseModel):
    profile_id: str | None = None
    target_url: str | None = Field(default=None, min_length=1)
    cron_expression: str | None = Field(default=None, min_length=1, max_length=128)
    timezone: str | None = Field(default=None, max_length=64)
    is_active: bool | None = None


class ScheduledCrawlResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: UUID
    profile_id: UUID
    target_url: str
    cron_expression: str
    timezone: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @field_serializer("id", "tenant_id", "profile_id")
    def serialize_uuids(self, v: Any) -> str:
        return str(v)


# --- Crawl summary / comparison -----------------------------------------------


class StatusCodeDistribution(BaseModel):
    status_2xx: int = 0
    status_3xx: int = 0
    status_4xx: int = 0
    status_5xx: int = 0
    other: int = 0


class IndexabilityDistribution(BaseModel):
    indexable: int = 0
    non_indexable: int = 0


class SitemapCoverage(BaseModel):
    in_sitemap: int = 0
    not_in_sitemap: int = 0
    unknown: int = 0


class IssueTypeDelta(BaseModel):
    issue_type: str
    previous_count: int
    current_count: int
    delta: int


class CrawlSnapshotAggregates(BaseModel):
    job_id: str
    target_url: str
    completed_at: datetime | None
    urls_crawled: int
    avg_response_time_ms: float | None
    issues_count: int
    status_codes: StatusCodeDistribution
    indexability: IndexabilityDistribution
    sitemap_coverage: SitemapCoverage


class CrawlComparisonSummary(BaseModel):
    current: CrawlSnapshotAggregates
    previous: CrawlSnapshotAggregates | None = None
    new_issue_types: list[str] = []
    resolved_issue_types: list[str] = []
    issue_type_deltas: list[IssueTypeDelta] = []


# --- Internal payloads --------------------------------------------------------

class LaunchWorkerPayload(BaseModel):
    job_id: str


class ScheduleTriggerPayload(BaseModel):
    schedule_id: str


class ClerkWebhookEnvelope(BaseModel):
    """Minimal shape; raw body is verified separately."""

    type: str
    data: dict[str, Any] = Field(default_factory=dict)
