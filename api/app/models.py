"""SQLAlchemy ORM models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class JobStatus(str, enum.Enum):
    queued = "queued"
    provisioning = "provisioning"
    running = "running"
    extracting = "extracting"
    loading = "loading"
    complete = "complete"
    failed = "failed"
    cancelled = "cancelled"


class JobExecutor(str, enum.Enum):
    local = "local"
    none = "none"
    gce = "gce"


class IssueSeverity(str, enum.Enum):
    error = "error"
    warning = "warning"
    info = "info"


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    clerk_org_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    plan: Mapped[str] = mapped_column(String(64), default="free", nullable=False)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    crawl_profiles: Mapped[list[CrawlProfile]] = relationship(back_populates="tenant")
    crawl_jobs: Mapped[list[CrawlJob]] = relationship(back_populates="tenant")
    scheduled_crawls: Mapped[list[ScheduledCrawl]] = relationship(back_populates="tenant")


class CrawlProfile(Base):
    __tablename__ = "crawl_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    config_path: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    tenant: Mapped[Tenant] = relationship(back_populates="crawl_profiles")
    crawl_jobs: Mapped[list[CrawlJob]] = relationship(back_populates="profile")
    scheduled_crawls: Mapped[list[ScheduledCrawl]] = relationship(back_populates="profile")

    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_crawl_profiles_tenant_name"),
    )


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crawl_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(
            JobStatus,
            name="job_status",
            native_enum=False,
            values_callable=lambda m: [e.value for e in m],
        ),
        nullable=False,
        default=JobStatus.queued,
    )
    progress_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    executor: Mapped[JobExecutor] = mapped_column(
        Enum(
            JobExecutor,
            name="job_executor",
            native_enum=False,
            values_callable=lambda m: [e.value for e in m],
        ),
        nullable=False,
        default=JobExecutor.local,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    max_urls: Mapped[int | None] = mapped_column(Integer, nullable=True)
    urls_crawled: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_prefix: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    tenant: Mapped[Tenant] = relationship(back_populates="crawl_jobs")
    profile: Mapped[CrawlProfile] = relationship(back_populates="crawl_jobs")
    pages: Mapped[list[CrawlPage]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    issues: Mapped[list[CrawlIssue]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    links: Mapped[list[CrawlLink]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class CrawlPage(Base):
    __tablename__ = "crawl_pages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False
    )
    address: Mapped[str] = mapped_column(Text, nullable=False)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    h1: Mapped[str | None] = mapped_column(Text, nullable=True)
    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    indexability: Mapped[str | None] = mapped_column(String(255), nullable=True)
    crawl_depth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    canonical: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(512), nullable=True)
    redirect_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    inlinks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    outlinks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meta_robots: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical_link_element: Mapped[str | None] = mapped_column(Text, nullable=True)
    pagination_status: Mapped[str | None] = mapped_column(String(255), nullable=True)
    http_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    x_robots_tag: Mapped[str | None] = mapped_column(Text, nullable=True)
    link_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    in_sitemap: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    job: Mapped[CrawlJob] = relationship(back_populates="pages")
    issues: Mapped[list[CrawlIssue]] = relationship(back_populates="page")


class CrawlIssue(Base):
    __tablename__ = "crawl_issues"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False
    )
    page_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crawl_pages.id", ondelete="SET NULL"), nullable=True
    )
    issue_type: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[IssueSeverity] = mapped_column(
        Enum(
            IssueSeverity,
            name="issue_severity",
            native_enum=False,
            values_callable=lambda m: [e.value for e in m],
        ),
        nullable=False,
        default=IssueSeverity.warning,
    )
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    job: Mapped[CrawlJob] = relationship(back_populates="issues")
    page: Mapped[CrawlPage | None] = relationship(back_populates="issues")


class CrawlLink(Base):
    __tablename__ = "crawl_links"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crawl_jobs.id", ondelete="CASCADE"), nullable=False
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    link_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    anchor_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    job: Mapped[CrawlJob] = relationship(back_populates="links")


class ScheduledCrawl(Base):
    __tablename__ = "scheduled_crawls"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("crawl_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    target_url: Mapped[str] = mapped_column(Text, nullable=False)
    cron_expression: Mapped[str] = mapped_column(String(128), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    tenant: Mapped[Tenant] = relationship(back_populates="scheduled_crawls")
    profile: Mapped[CrawlProfile] = relationship(back_populates="scheduled_crawls")
