"""End-to-end tests for the filter query parameter on the pages endpoint.

Uses FastAPI TestClient with mocked auth to test the full HTTP -> SQL path.
"""

from __future__ import annotations

import json
import os
from uuid import uuid4
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.auth import get_current_tenant
from app.db import get_db
from app.main import app
from app.models import Tenant


DB_URL = os.environ.get("DATABASE_URL")
needs_pg = pytest.mark.skipif(not DB_URL, reason="DATABASE_URL not set")


@pytest.fixture()
def pg_engine():
    if not DB_URL:
        pytest.skip("DATABASE_URL not set")
    return create_engine(DB_URL)


@pytest.fixture()
def pg_session(pg_engine):
    conn = pg_engine.connect()
    txn = conn.begin()
    session = Session(bind=conn)
    yield session
    session.close()
    txn.rollback()
    conn.close()


@pytest.fixture()
def test_data(pg_session):
    """Seed a tenant, job, pages, and issues via raw SQL."""
    db = pg_session
    tid = uuid4()
    pid = uuid4()
    jid = uuid4()
    page_ids = [uuid4() for _ in range(3)]

    db.execute(text(
        "INSERT INTO tenants (id, clerk_org_id, name, plan, settings) "
        "VALUES (:id, :org, 'Test', 'free', '{}')"
    ), {"id": str(tid), "org": f"org_{uuid4().hex[:12]}"})

    db.execute(text(
        "INSERT INTO crawl_profiles (id, tenant_id, name, config_path) "
        "VALUES (:id, :tid, 'Default', '/cfg')"
    ), {"id": str(pid), "tid": str(tid)})

    db.execute(text(
        "INSERT INTO crawl_jobs (id, tenant_id, profile_id, target_url, status, executor, urls_crawled) "
        "VALUES (:id, :tid, :pid, 'https://test.com', 'complete', 'local', 0)"
    ), {"id": str(jid), "tid": str(tid), "pid": str(pid)})

    pages = [
        dict(id=str(page_ids[0]), address="https://test.com/", status_code=200,
             title="Home", indexability="Indexable", content_type="text/html",
             word_count=500, crawl_depth=0, response_time=100.0, size_bytes=10000,
             in_sitemap=True, inlinks=5, outlinks=3,
             meta_description="Home page", h1="Home", redirect_url=None),
        dict(id=str(page_ids[1]), address="https://test.com/about", status_code=200,
             title="About", indexability="Indexable", content_type="text/html",
             word_count=200, crawl_depth=1, response_time=80.0, size_bytes=5000,
             in_sitemap=False, inlinks=2, outlinks=1,
             meta_description=None, h1="About", redirect_url=None),
        dict(id=str(page_ids[2]), address="https://test.com/error", status_code=500,
             title=None, indexability="Non-Indexable", content_type="text/html",
             word_count=10, crawl_depth=1, response_time=500.0, size_bytes=100,
             in_sitemap=None, inlinks=0, outlinks=0,
             meta_description=None, h1=None, redirect_url=None),
    ]
    for p in pages:
        db.execute(text(
            "INSERT INTO crawl_pages "
            "(id, job_id, address, status_code, title, indexability, content_type, "
            "word_count, crawl_depth, response_time, size_bytes, in_sitemap, "
            "inlinks, outlinks, meta_description, h1, redirect_url, metadata) "
            "VALUES (:id, :jid, :address, :status_code, :title, :indexability, :content_type, "
            ":word_count, :crawl_depth, :response_time, :size_bytes, :in_sitemap, "
            ":inlinks, :outlinks, :meta_description, :h1, :redirect_url, '{}')"
        ), {**p, "jid": str(jid)})

    db.execute(text(
        "INSERT INTO crawl_issues (id, job_id, page_id, issue_type, severity) "
        "VALUES (:id, :jid, :pid, 'server_error', 'error')"
    ), {"id": str(uuid4()), "jid": str(jid), "pid": str(page_ids[2])})

    db.flush()

    return {
        "tenant_id": tid, "job_id": jid, "page_ids": page_ids,
        "tenant": db.execute(text("SELECT * FROM tenants WHERE id = :id"), {"id": str(tid)}).mappings().one(),
    }


@pytest.fixture()
def client(pg_session, test_data):
    """TestClient with auth and DB overridden to use test transaction."""
    tenant_obj = Tenant(
        id=test_data["tenant_id"],
        clerk_org_id=test_data["tenant"]["clerk_org_id"],
        name="Test",
    )

    async def _override_tenant():
        return tenant_obj

    def _override_db():
        yield pg_session

    app.dependency_overrides[get_current_tenant] = _override_tenant
    app.dependency_overrides[get_db] = _override_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@needs_pg
class TestFilterEndpoint:
    def test_no_filters_returns_all(self, client, test_data):
        jid = test_data["job_id"]
        resp = client.get(f"/api/crawls/{jid}/pages")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] == 3

    def test_string_contains_filter(self, client, test_data):
        jid = test_data["job_id"]
        filters = json.dumps([{"field": "address", "op": "contains", "value": "about"}])
        resp = client.get(f"/api/crawls/{jid}/pages?filters={filters}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] == 1
        assert "about" in data["items"][0]["address"]

    def test_number_eq_filter(self, client, test_data):
        jid = test_data["job_id"]
        filters = json.dumps([{"field": "status_code", "op": "eq", "value": "200"}])
        resp = client.get(f"/api/crawls/{jid}/pages?filters={filters}")
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 2

    def test_number_gt_filter(self, client, test_data):
        jid = test_data["job_id"]
        filters = json.dumps([{"field": "status_code", "op": "gt", "value": "400"}])
        resp = client.get(f"/api/crawls/{jid}/pages?filters={filters}")
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 1

    def test_boolean_filter(self, client, test_data):
        jid = test_data["job_id"]
        filters = json.dumps([{"field": "in_sitemap", "op": "is_true"}])
        resp = client.get(f"/api/crawls/{jid}/pages?filters={filters}")
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 1

    def test_is_empty_filter(self, client, test_data):
        jid = test_data["job_id"]
        filters = json.dumps([{"field": "title", "op": "is_empty"}])
        resp = client.get(f"/api/crawls/{jid}/pages?filters={filters}")
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 1

    def test_has_issues_filter(self, client, test_data):
        jid = test_data["job_id"]
        filters = json.dumps([{"field": "has_issues", "op": "is_true"}])
        resp = client.get(f"/api/crawls/{jid}/pages?filters={filters}")
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 1

    def test_issue_type_filter(self, client, test_data):
        jid = test_data["job_id"]
        filters = json.dumps([{"field": "issue_type", "op": "equals", "value": "server_error"}])
        resp = client.get(f"/api/crawls/{jid}/pages?filters={filters}")
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 1

    def test_or_logic(self, client, test_data):
        jid = test_data["job_id"]
        filters = json.dumps([
            {"field": "status_code", "op": "eq", "value": "500"},
            {"field": "address", "op": "contains", "value": "about"},
        ])
        resp = client.get(f"/api/crawls/{jid}/pages?filters={filters}&filter_logic=or")
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 2

    def test_and_logic_multiple(self, client, test_data):
        jid = test_data["job_id"]
        filters = json.dumps([
            {"field": "status_code", "op": "eq", "value": "200"},
            {"field": "word_count", "op": "gt", "value": "300"},
        ])
        resp = client.get(f"/api/crawls/{jid}/pages?filters={filters}&filter_logic=and")
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 1  # only Home (500 words)

    def test_invalid_json_returns_400(self, client, test_data):
        jid = test_data["job_id"]
        resp = client.get(f"/api/crawls/{jid}/pages?filters=not_json")
        assert resp.status_code == 400

    def test_unknown_field_returns_400(self, client, test_data):
        jid = test_data["job_id"]
        filters = json.dumps([{"field": "nonexistent", "op": "equals", "value": "x"}])
        resp = client.get(f"/api/crawls/{jid}/pages?filters={filters}")
        assert resp.status_code == 400

    def test_invalid_number_value_returns_400(self, client, test_data):
        jid = test_data["job_id"]
        filters = json.dumps([{"field": "status_code", "op": "eq", "value": "abc"}])
        resp = client.get(f"/api/crawls/{jid}/pages?filters={filters}")
        assert resp.status_code == 400

    def test_empty_filter_array_returns_all(self, client, test_data):
        jid = test_data["job_id"]
        resp = client.get(f"/api/crawls/{jid}/pages?filters=[]")
        assert resp.status_code == 200
        assert resp.json()["total_count"] == 3
