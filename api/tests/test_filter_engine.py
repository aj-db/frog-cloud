"""Tests for the dynamic filter engine in api/app/routers/results.py.

Unit tests exercise clause builders and parsing without a database.
Integration tests run against the real PostgreSQL database.
"""

from __future__ import annotations

import json
import os
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, func, text
from sqlalchemy.orm import Session

from app.models import Base, CrawlIssue, CrawlPage, CrawlJob, CrawlProfile, Tenant, IssueSeverity, JobStatus, JobExecutor
from app.schemas import PageFilterRule
from app.routers.results import (
    _rule_to_clause,
    _string_clause,
    _number_clause,
    _boolean_clause,
    _pseudo_field_clause,
    _parse_filter_rules,
    _apply_dynamic_filters,
    FILTERABLE_FIELDS,
    STRING_OPS,
    NUMBER_OPS,
    BOOLEAN_OPS,
)


# ---------------------------------------------------------------------------
# Unit tests (no database required)
# ---------------------------------------------------------------------------

class TestParseFilterRules:
    def test_none_returns_empty(self):
        assert _parse_filter_rules(None) == []

    def test_empty_string_returns_empty(self):
        assert _parse_filter_rules("") == []

    def test_valid_json_parsed(self):
        raw = json.dumps([{"field": "address", "op": "contains", "value": "blog"}])
        rules = _parse_filter_rules(raw)
        assert len(rules) == 1
        assert rules[0].field == "address"
        assert rules[0].op == "contains"
        assert rules[0].value == "blog"

    def test_multiple_rules(self):
        raw = json.dumps([
            {"field": "address", "op": "contains", "value": "blog"},
            {"field": "status_code", "op": "eq", "value": "200"},
        ])
        rules = _parse_filter_rules(raw)
        assert len(rules) == 2

    def test_value_defaults_to_empty_string(self):
        raw = json.dumps([{"field": "address", "op": "is_empty"}])
        rules = _parse_filter_rules(raw)
        assert rules[0].value == ""

    def test_invalid_json_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            _parse_filter_rules("not json")
        assert exc_info.value.status_code == 400

    def test_non_array_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            _parse_filter_rules('{"field": "address"}')
        assert exc_info.value.status_code == 400

    def test_missing_required_field_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            _parse_filter_rules(json.dumps([{"op": "contains"}]))
        assert exc_info.value.status_code == 400


class TestStringClauseValidation:
    def test_invalid_op_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            _string_clause(CrawlPage.address, "invalid_op", "test")
        assert exc_info.value.status_code == 400

    def test_all_ops_accepted(self):
        for op in STRING_OPS:
            clause = _string_clause(CrawlPage.address, op, "test")
            assert clause is not None


class TestNumberClauseValidation:
    def test_invalid_op_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            _number_clause(CrawlPage.status_code, "contains", "200")
        assert exc_info.value.status_code == 400

    def test_invalid_value_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            _number_clause(CrawlPage.status_code, "eq", "not_a_number")
        assert exc_info.value.status_code == 400

    def test_is_empty_no_value_needed(self):
        clause = _number_clause(CrawlPage.status_code, "is_empty", "")
        assert clause is not None

    def test_is_not_empty_no_value_needed(self):
        clause = _number_clause(CrawlPage.status_code, "is_not_empty", "")
        assert clause is not None

    def test_all_ops_accepted(self):
        for op in NUMBER_OPS:
            val = "" if op in ("is_empty", "is_not_empty") else "42"
            clause = _number_clause(CrawlPage.status_code, op, val)
            assert clause is not None


class TestBooleanClauseValidation:
    def test_invalid_op_raises_400(self):
        with pytest.raises(HTTPException) as exc_info:
            _boolean_clause(CrawlPage.in_sitemap, "contains")
        assert exc_info.value.status_code == 400

    def test_all_ops_accepted(self):
        for op in BOOLEAN_OPS:
            clause = _boolean_clause(CrawlPage.in_sitemap, op)
            assert clause is not None


class TestRuleToClauseValidation:
    def test_unknown_field_raises_400(self):
        rule = PageFilterRule(field="nonexistent_column", op="equals", value="x")
        with pytest.raises(HTTPException) as exc_info:
            _rule_to_clause(rule, uuid4())
        assert exc_info.value.status_code == 400

    def test_unknown_pseudo_field_raises_400(self):
        rule = PageFilterRule(field="unknown_pseudo", op="equals", value="x")
        with pytest.raises(HTTPException):
            _pseudo_field_clause(rule, uuid4())

    def test_all_filterable_fields_produce_clause(self):
        job_id = uuid4()
        for field, (_, ftype) in FILTERABLE_FIELDS.items():
            if ftype == "string":
                rule = PageFilterRule(field=field, op="contains", value="test")
            elif ftype == "number":
                rule = PageFilterRule(field=field, op="eq", value="1")
            else:
                rule = PageFilterRule(field=field, op="is_true")
            clause = _rule_to_clause(rule, job_id)
            assert clause is not None, f"Failed for field {field}"


class TestFieldRegistryCompleteness:
    def test_all_model_columns_represented(self):
        """Every column on CrawlPage that is a data column (not id/job_id/timestamps/extra)
        should be in FILTERABLE_FIELDS or explicitly excluded."""
        skip = {"id", "job_id", "created_at", "updated_at", "extra_metadata", "metadata"}
        model_cols = {c.key for c in CrawlPage.__table__.columns} - skip
        registry_keys = set(FILTERABLE_FIELDS.keys())
        missing = model_cols - registry_keys
        assert not missing, f"Columns missing from FILTERABLE_FIELDS: {missing}"


# ---------------------------------------------------------------------------
# Integration tests (require PostgreSQL)
# ---------------------------------------------------------------------------

DB_URL = os.environ.get("DATABASE_URL")
needs_pg = pytest.mark.skipif(not DB_URL, reason="DATABASE_URL not set")


@pytest.fixture()
def pg_session():
    """Session connected to real PostgreSQL, rolled back after each test."""
    if not DB_URL:
        pytest.skip("DATABASE_URL not set")
    engine = create_engine(DB_URL)
    conn = engine.connect()
    txn = conn.begin()
    session = Session(bind=conn)
    yield session
    session.close()
    txn.rollback()
    conn.close()


def _insert_via_sql(db: Session, tenant_id, profile_id, job_id, pages_data, issues_data):
    """Insert seed data via raw SQL to bypass ORM column mismatches."""
    db.execute(text(
        "INSERT INTO tenants (id, clerk_org_id, name, plan, settings) "
        "VALUES (:id, :clerk_org_id, :name, 'free', '{}')"
    ), {"id": str(tenant_id), "clerk_org_id": f"org_test_{uuid4().hex[:8]}", "name": "Test Org"})

    db.execute(text(
        "INSERT INTO crawl_profiles (id, tenant_id, name, config_path) "
        "VALUES (:id, :tid, :name, :cfg)"
    ), {"id": str(profile_id), "tid": str(tenant_id), "name": "Default", "cfg": "/cfg"})

    db.execute(text(
        "INSERT INTO crawl_jobs (id, tenant_id, profile_id, target_url, status, executor, urls_crawled) "
        "VALUES (:id, :tid, :pid, :url, 'complete', 'local', 0)"
    ), {"id": str(job_id), "tid": str(tenant_id), "pid": str(profile_id), "url": "https://example.com"})

    for p in pages_data:
        db.execute(text(
            "INSERT INTO crawl_pages "
            "(id, job_id, address, status_code, title, indexability, content_type, "
            "word_count, crawl_depth, response_time, size_bytes, in_sitemap, "
            "inlinks, outlinks, meta_description, h1, redirect_url, metadata) "
            "VALUES (:id, :jid, :address, :status_code, :title, :indexability, :content_type, "
            ":word_count, :crawl_depth, :response_time, :size_bytes, :in_sitemap, "
            ":inlinks, :outlinks, :meta_description, :h1, :redirect_url, :metadata)"
        ), {**p, "jid": str(job_id), "metadata": "{}"})

    for i in issues_data:
        db.execute(text(
            "INSERT INTO crawl_issues (id, job_id, page_id, issue_type, severity) "
            "VALUES (:id, :jid, :pid, :issue_type, :severity)"
        ), {**i, "jid": str(job_id)})

    db.flush()


@pytest.fixture()
def seed(pg_session):
    db = pg_session
    tenant_id = uuid4()
    profile_id = uuid4()
    job_id = uuid4()
    page_ids = [uuid4() for _ in range(5)]

    pages_data = [
        dict(id=str(page_ids[0]), address="https://example.com/", status_code=200,
             title="Home Page", indexability="Indexable", content_type="text/html",
             word_count=500, crawl_depth=0, response_time=120.5, size_bytes=15000,
             in_sitemap=True, inlinks=10, outlinks=5,
             meta_description="Welcome to example", h1="Welcome", redirect_url=None),
        dict(id=str(page_ids[1]), address="https://example.com/about", status_code=200,
             title="About Us", indexability="Indexable", content_type="text/html",
             word_count=300, crawl_depth=1, response_time=95.0, size_bytes=8000,
             in_sitemap=True, inlinks=5, outlinks=3,
             meta_description="About our company", h1="About", redirect_url=None),
        dict(id=str(page_ids[2]), address="https://example.com/404-page", status_code=404,
             title="Not Found", indexability="Non-Indexable", content_type="text/html",
             word_count=50, crawl_depth=2, response_time=45.0, size_bytes=2000,
             in_sitemap=False, inlinks=0, outlinks=0,
             meta_description=None, h1=None, redirect_url=None),
        dict(id=str(page_ids[3]), address="https://example.com/redirect", status_code=301,
             title=None, indexability="Non-Indexable", content_type=None,
             word_count=None, crawl_depth=1, response_time=30.0, size_bytes=0,
             in_sitemap=None, inlinks=2, outlinks=1,
             meta_description=None, h1=None, redirect_url="https://example.com/about"),
        dict(id=str(page_ids[4]), address="https://example.com/blog/post-1", status_code=200,
             title="Blog Post 1", indexability="Indexable", content_type="text/html",
             word_count=1200, crawl_depth=2, response_time=200.0, size_bytes=25000,
             in_sitemap=True, inlinks=8, outlinks=12,
             meta_description="First blog post", h1="Blog Post 1", redirect_url=None),
    ]

    issues_data = [
        dict(id=str(uuid4()), pid=str(page_ids[2]),
             issue_type="missing_title", severity="error"),
        dict(id=str(uuid4()), pid=str(page_ids[2]),
             issue_type="broken_link", severity="warning"),
        dict(id=str(uuid4()), pid=str(page_ids[3]),
             issue_type="redirect_chain", severity="warning"),
    ]

    _insert_via_sql(db, tenant_id, profile_id, job_id, pages_data, issues_data)

    return {"job_id": job_id, "page_ids": page_ids}


def _count(db, job_id, rules, logic="and"):
    stmt = select(func.count(CrawlPage.id))
    stmt = _apply_dynamic_filters(stmt, job_id, rules, logic)
    return db.execute(stmt).scalar_one()


def _addresses(db, job_id, rules, logic="and"):
    stmt = select(CrawlPage.address)
    stmt = _apply_dynamic_filters(stmt, job_id, rules, logic)
    return sorted(db.execute(stmt).scalars().all())


@needs_pg
class TestStringFilters:
    def test_contains(self, pg_session, seed):
        rules = [PageFilterRule(field="address", op="contains", value="blog")]
        assert _count(pg_session, seed["job_id"], rules) == 1

    def test_contains_case_insensitive(self, pg_session, seed):
        rules = [PageFilterRule(field="title", op="contains", value="home")]
        assert _count(pg_session, seed["job_id"], rules) == 1

    def test_not_contains(self, pg_session, seed):
        rules = [PageFilterRule(field="address", op="not_contains", value="blog")]
        assert _count(pg_session, seed["job_id"], rules) == 4

    def test_equals(self, pg_session, seed):
        rules = [PageFilterRule(field="indexability", op="equals", value="Indexable")]
        assert _count(pg_session, seed["job_id"], rules) == 3

    def test_not_equals(self, pg_session, seed):
        rules = [PageFilterRule(field="indexability", op="not_equals", value="Indexable")]
        assert _count(pg_session, seed["job_id"], rules) == 2

    def test_starts_with(self, pg_session, seed):
        rules = [PageFilterRule(field="address", op="starts_with", value="https://example.com/b")]
        addrs = _addresses(pg_session, seed["job_id"], rules)
        assert len(addrs) == 1
        assert "blog" in addrs[0]

    def test_ends_with(self, pg_session, seed):
        rules = [PageFilterRule(field="address", op="ends_with", value="about")]
        assert _count(pg_session, seed["job_id"], rules) == 1

    def test_is_empty_null(self, pg_session, seed):
        rules = [PageFilterRule(field="meta_description", op="is_empty")]
        count = _count(pg_session, seed["job_id"], rules)
        assert count == 2

    def test_is_not_empty(self, pg_session, seed):
        rules = [PageFilterRule(field="meta_description", op="is_not_empty")]
        assert _count(pg_session, seed["job_id"], rules) == 3

    def test_regex(self, pg_session, seed):
        rules = [PageFilterRule(field="address", op="regex", value="blog.*post")]
        assert _count(pg_session, seed["job_id"], rules) == 1


@needs_pg
class TestNumberFilters:
    def test_eq(self, pg_session, seed):
        rules = [PageFilterRule(field="status_code", op="eq", value="200")]
        assert _count(pg_session, seed["job_id"], rules) == 3

    def test_neq(self, pg_session, seed):
        rules = [PageFilterRule(field="status_code", op="neq", value="200")]
        assert _count(pg_session, seed["job_id"], rules) == 2

    def test_gt(self, pg_session, seed):
        rules = [PageFilterRule(field="status_code", op="gt", value="300")]
        assert _count(pg_session, seed["job_id"], rules) == 2

    def test_gte(self, pg_session, seed):
        rules = [PageFilterRule(field="status_code", op="gte", value="301")]
        assert _count(pg_session, seed["job_id"], rules) == 2

    def test_lt(self, pg_session, seed):
        rules = [PageFilterRule(field="status_code", op="lt", value="300")]
        assert _count(pg_session, seed["job_id"], rules) == 3

    def test_lte(self, pg_session, seed):
        rules = [PageFilterRule(field="status_code", op="lte", value="200")]
        assert _count(pg_session, seed["job_id"], rules) == 3

    def test_is_empty(self, pg_session, seed):
        rules = [PageFilterRule(field="word_count", op="is_empty")]
        assert _count(pg_session, seed["job_id"], rules) == 1

    def test_is_not_empty(self, pg_session, seed):
        rules = [PageFilterRule(field="word_count", op="is_not_empty")]
        assert _count(pg_session, seed["job_id"], rules) == 4

    def test_float_gt(self, pg_session, seed):
        rules = [PageFilterRule(field="response_time", op="gt", value="100")]
        assert _count(pg_session, seed["job_id"], rules) == 2


@needs_pg
class TestBooleanFilters:
    def test_is_true(self, pg_session, seed):
        rules = [PageFilterRule(field="in_sitemap", op="is_true")]
        assert _count(pg_session, seed["job_id"], rules) == 3

    def test_is_false(self, pg_session, seed):
        rules = [PageFilterRule(field="in_sitemap", op="is_false")]
        assert _count(pg_session, seed["job_id"], rules) == 1

    def test_is_empty(self, pg_session, seed):
        rules = [PageFilterRule(field="in_sitemap", op="is_empty")]
        assert _count(pg_session, seed["job_id"], rules) == 1


@needs_pg
class TestPseudoFieldFilters:
    def test_has_issues_true(self, pg_session, seed):
        rules = [PageFilterRule(field="has_issues", op="is_true")]
        assert _count(pg_session, seed["job_id"], rules) == 2

    def test_has_issues_false(self, pg_session, seed):
        rules = [PageFilterRule(field="has_issues", op="is_false")]
        assert _count(pg_session, seed["job_id"], rules) == 3

    def test_issue_type_equals(self, pg_session, seed):
        rules = [PageFilterRule(field="issue_type", op="equals", value="missing_title")]
        assert _count(pg_session, seed["job_id"], rules) == 1

    def test_issue_type_not_equals(self, pg_session, seed):
        rules = [PageFilterRule(field="issue_type", op="not_equals", value="missing_title")]
        assert _count(pg_session, seed["job_id"], rules) == 4


@needs_pg
class TestFilterLogic:
    def test_and_logic(self, pg_session, seed):
        rules = [
            PageFilterRule(field="status_code", op="eq", value="200"),
            PageFilterRule(field="word_count", op="gt", value="400"),
        ]
        assert _count(pg_session, seed["job_id"], rules, "and") == 2

    def test_or_logic(self, pg_session, seed):
        rules = [
            PageFilterRule(field="status_code", op="eq", value="404"),
            PageFilterRule(field="status_code", op="eq", value="301"),
        ]
        assert _count(pg_session, seed["job_id"], rules, "or") == 2

    def test_no_rules_returns_all(self, pg_session, seed):
        assert _count(pg_session, seed["job_id"], []) == 5


@needs_pg
class TestCombinedFilters:
    def test_string_and_number(self, pg_session, seed):
        rules = [
            PageFilterRule(field="address", op="contains", value="example"),
            PageFilterRule(field="status_code", op="eq", value="200"),
        ]
        assert _count(pg_session, seed["job_id"], rules) == 3

    def test_three_filters_and(self, pg_session, seed):
        rules = [
            PageFilterRule(field="status_code", op="eq", value="200"),
            PageFilterRule(field="in_sitemap", op="is_true"),
            PageFilterRule(field="word_count", op="gt", value="400"),
        ]
        assert _count(pg_session, seed["job_id"], rules) == 2

    def test_issue_type_with_status_code(self, pg_session, seed):
        rules = [
            PageFilterRule(field="issue_type", op="equals", value="broken_link"),
            PageFilterRule(field="status_code", op="eq", value="404"),
        ]
        assert _count(pg_session, seed["job_id"], rules) == 1

    def test_or_across_types(self, pg_session, seed):
        rules = [
            PageFilterRule(field="in_sitemap", op="is_false"),
            PageFilterRule(field="word_count", op="gt", value="1000"),
        ]
        assert _count(pg_session, seed["job_id"], rules, "or") == 2
