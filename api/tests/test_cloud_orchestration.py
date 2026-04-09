from __future__ import annotations

from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

from starlette.datastructures import URLPath
from starlette.requests import Request

from app.config import Settings
from app.models import JobExecutor
from app.routers import crawls, internal
from app.schemas import CrawlJobCreate
from crawler import executor


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    def __init__(self, value):
        self._value = value
        self.added = []

    def execute(self, _query):
        return _FakeResult(self._value)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        return None

    def refresh(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid4()


class _FakeApp:
    def url_path_for(self, name: str, **_params):
        assert name == "internal_launch_worker"
        return URLPath("/internal/launch-worker")


def _request(url: str, headers: list[tuple[str, str]] | None = None) -> Request:
    parsed = urlsplit(url)
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "POST",
        "scheme": parsed.scheme,
        "path": parsed.path,
        "raw_path": parsed.path.encode("utf-8"),
        "query_string": parsed.query.encode("utf-8"),
        "headers": [(name.lower().encode("utf-8"), value.encode("utf-8")) for name, value in (headers or [])],
        "server": (
            parsed.hostname,
            parsed.port or (443 if parsed.scheme == "https" else 80),
        ),
        "client": ("testclient", 50000),
        "root_path": "",
        "app": _FakeApp(),
    }
    return Request(scope)


def test_settings_accept_cloud_runtime_aliases(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://frog:frog@localhost:5432/frog")
    monkeypatch.setenv("GCS_ARTIFACTS_BUCKET", "frog-artifacts")
    monkeypatch.setenv("CLOUD_SQL_CONN_NAME", "fox-seo-sandbox:us-central1:staging-frog-pg")
    monkeypatch.setenv("CLOUD_TASKS_QUEUE_ID", "crawl-orchestration-staging")
    monkeypatch.setenv("CLOUD_TASKS_LOCATION", "us-central1")
    monkeypatch.setenv(
        "CLOUD_TASKS_INVOKER_SERVICE_ACCOUNT_EMAIL",
        "staging-frog-tasks-oidc@fox-seo-sandbox.iam.gserviceaccount.com",
    )

    settings = Settings(_env_file=None)

    assert settings.gcs_bucket == "frog-artifacts"
    assert settings.cloud_sql_instance == "fox-seo-sandbox:us-central1:staging-frog-pg"
    assert settings.cloud_tasks_queue_id == "crawl-orchestration-staging"
    assert settings.cloud_tasks_location == "us-central1"
    assert settings.gce_dispatch_mode == "ephemeral"
    assert (
        settings.cloud_tasks_invoker_service_account_email
        == "staging-frog-tasks-oidc@fox-seo-sandbox.iam.gserviceaccount.com"
    )


def test_verify_google_oidc_falls_back_to_request_url_when_audience_missing(
    monkeypatch,
):
    captured: dict[str, str] = {}

    monkeypatch.setattr(
        internal,
        "get_settings",
        lambda: SimpleNamespace(internal_oidc_audience=None),
    )

    def _fake_verify(token, _request, audience):
        captured["token"] = token
        captured["audience"] = audience
        return {"sub": "task"}

    monkeypatch.setattr(internal.id_token, "verify_oauth2_token", _fake_verify)

    claims = internal.verify_google_oidc(
        request=_request("https://api.example.com/internal/launch-worker"),
        authorization="Bearer signed-token",
    )

    assert claims == {"sub": "task"}
    assert captured["token"] == "signed-token"
    assert captured["audience"] == "https://api.example.com/internal/launch-worker"


def test_verify_google_oidc_prefers_forwarded_https_audience(monkeypatch):
    captured: dict[str, str] = {}

    monkeypatch.setattr(
        internal,
        "get_settings",
        lambda: SimpleNamespace(internal_oidc_audience=None),
    )

    def _fake_verify(token, _request, audience):
        captured["token"] = token
        captured["audience"] = audience
        return {"sub": "task"}

    monkeypatch.setattr(internal.id_token, "verify_oauth2_token", _fake_verify)

    claims = internal.verify_google_oidc(
        request=_request(
            "http://api.example.com/internal/launch-worker",
            headers=[("x-forwarded-proto", "https")],
        ),
        authorization="Bearer signed-token",
    )

    assert claims == {"sub": "task"}
    assert captured["token"] == "signed-token"
    assert captured["audience"] == "https://api.example.com/internal/launch-worker"


def test_enqueue_job_execution_routes_gce_jobs_to_cloud_tasks(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        executor,
        "get_settings",
        lambda: SimpleNamespace(gce_dispatch_mode="ephemeral"),
    )

    def _fake_enqueue(*, job_id, launch_url):
        captured["job_id"] = job_id
        captured["launch_url"] = launch_url
        return "tasks/launch-worker-1"

    monkeypatch.setattr(executor, "enqueue_launch_worker_task", _fake_enqueue, raising=False)

    result = executor.enqueue_job_execution(
        uuid4(),
        JobExecutor.gce,
        launch_url="https://api.example.com/internal/launch-worker",
    )

    assert result == "tasks/launch-worker-1"
    assert captured["launch_url"] == "https://api.example.com/internal/launch-worker"


def test_enqueue_job_execution_leaves_gce_jobs_queued_in_persistent_mode(monkeypatch):
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        executor,
        "get_settings",
        lambda: SimpleNamespace(gce_dispatch_mode="persistent"),
    )

    def _fake_enqueue(*, job_id, launch_url):
        captured["job_id"] = job_id
        captured["launch_url"] = launch_url
        return "tasks/launch-worker-1"

    monkeypatch.setattr(executor, "enqueue_launch_worker_task", _fake_enqueue, raising=False)

    result = executor.enqueue_job_execution(
        uuid4(),
        JobExecutor.gce,
        launch_url="https://api.example.com/internal/launch-worker",
    )

    assert result is None
    assert captured == {}


def test_create_crawl_enqueues_gce_job_with_internal_launch_url(monkeypatch):
    tenant = SimpleNamespace(id=uuid4())
    profile = SimpleNamespace(id=uuid4(), tenant_id=tenant.id)
    db = _FakeSession(profile)
    captured: dict[str, object] = {}

    monkeypatch.setattr(crawls, "validate_public_http_url", lambda _url: None)
    monkeypatch.setattr(crawls, "_executor_for_request", lambda: JobExecutor.gce)

    def _fake_enqueue(job_id, executor_kind, *, launch_url=None):
        captured["job_id"] = job_id
        captured["executor"] = executor_kind
        captured["launch_url"] = launch_url
        return "tasks/launch-worker-1"

    monkeypatch.setattr(crawls, "enqueue_job_execution", _fake_enqueue)

    accepted = crawls.create_crawl(
        body=CrawlJobCreate(profile_id=str(profile.id), target_url="https://example.com"),
        request=_request(
            "http://api.example.com/api/crawls",
            headers=[("x-forwarded-proto", "https")],
        ),
        tenant=tenant,
        db=db,
    )

    assert accepted.status == "queued"
    assert captured["executor"] == JobExecutor.gce
    assert captured["launch_url"] == "https://api.example.com/internal/launch-worker"
