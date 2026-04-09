"""Tests for the issues trend schema, service, and endpoint."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.auth import get_current_tenant
from app.db import get_db
from app.main import app
from app.models import Tenant
from app.schemas import IssueTrendPoint, IssueTrendResponse
from app.services.crawl_summary import build_issues_trend


def test_issue_trend_schema_serializes_correctly():
    completed_at = datetime(2026, 4, 8, 12, 30, tzinfo=timezone.utc)
    response = IssueTrendResponse(
        points=[
            IssueTrendPoint(
                job_id="job-1",
                completed_at=completed_at,
                target_url="https://example.com",
                issue_type="missing_title",
                url_count=3,
            )
        ],
        issue_types=["missing_title"],
    )

    data = response.model_dump()

    assert data["issue_types"] == ["missing_title"]
    assert data["points"][0]["job_id"] == "job-1"
    assert data["points"][0]["completed_at"] == completed_at
    assert data["points"][0]["url_count"] == 3


def test_build_issues_trend_returns_points_and_sorted_issue_types():
    tenant_id = uuid.uuid4()
    db = MagicMock()
    completed_at = datetime(2026, 4, 8, 12, 30, tzinfo=timezone.utc)

    db.execute.return_value.all.return_value = [
        SimpleNamespace(
            job_id=uuid.uuid4(),
            completed_at=completed_at,
            target_url="https://example.com",
            issue_type="missing_title",
            url_count=3,
        ),
        SimpleNamespace(
            job_id=uuid.uuid4(),
            completed_at=completed_at,
            target_url="https://example.com",
            issue_type="duplicate_h1",
            url_count=1,
        ),
        SimpleNamespace(
            job_id=uuid.uuid4(),
            completed_at=completed_at,
            target_url="https://example.com",
            issue_type="missing_title",
            url_count=2,
        ),
    ]

    summary = build_issues_trend(db, tenant_id)

    assert summary.issue_types == ["duplicate_h1", "missing_title"]
    assert len(summary.points) == 3
    assert summary.points[0].issue_type == "missing_title"
    assert summary.points[0].url_count == 3

    stmt = db.execute.call_args[0][0]
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": False})).upper()
    assert "COUNT(DISTINCT" in compiled
    assert "CRAWL_JOBS" in compiled
    assert "TENANT_ID" in compiled
    assert "STATUS" in compiled


def test_issues_trend_endpoint_uses_service_and_serializes_response():
    tenant = Tenant(
        id=uuid.uuid4(),
        clerk_org_id=f"org_{uuid.uuid4().hex[:12]}",
        name="Test tenant",
    )
    db = MagicMock()
    completed_at = datetime(2026, 4, 8, 12, 30, tzinfo=timezone.utc)
    trend = IssueTrendResponse(
        points=[
            IssueTrendPoint(
                job_id="job-1",
                completed_at=completed_at,
                target_url="https://example.com",
                issue_type="missing_title",
                url_count=3,
            )
        ],
        issue_types=["missing_title"],
    )

    async def _override_tenant():
        return tenant

    def _override_db():
        yield db

    app.dependency_overrides[get_current_tenant] = _override_tenant
    app.dependency_overrides[get_db] = _override_db

    try:
        with patch("app.routers.crawls.build_issues_trend", return_value=trend) as mock_build:
            client = TestClient(app)
            response = client.get("/api/crawls/issues-trend")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["issue_types"] == ["missing_title"]
    assert response.json()["points"][0]["job_id"] == "job-1"
    mock_build.assert_called_once_with(db, tenant.id)
