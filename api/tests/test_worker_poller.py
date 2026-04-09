from __future__ import annotations

from datetime import datetime, timedelta, timezone
import subprocess
from types import ModuleType
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.models import CrawlJob, JobExecutor, JobStatus
from crawler import worker


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    def __init__(self, value):
        self._value = value
        self.added: list[object] = []
        self.commits = 0
        self.statements: list[object] = []

    def execute(self, statement):
        self.statements.append(statement)
        return _FakeResult(self._value)

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1

    def close(self):
        return None


class _StopLoop(Exception):
    pass


class _FakeProcess:
    def __init__(self, outcomes):
        self._outcomes = iter(outcomes)
        self.pid = 12345

    def wait(self, timeout):
        outcome = next(self._outcomes)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def _queued_gce_job(created_at: datetime) -> CrawlJob:
    return CrawlJob(
        id=uuid4(),
        tenant_id=uuid4(),
        profile_id=uuid4(),
        target_url="https://example.com",
        executor=JobExecutor.gce,
        status=JobStatus.queued,
        created_at=created_at,
    )


def test_claim_next_gce_job_transitions_a_queued_gce_job_to_running():
    job = _queued_gce_job(datetime.now(timezone.utc) - timedelta(minutes=5))
    session = _FakeSession(job)

    claimed_job_id = worker.claim_next_gce_job(session)
    compiled = str(session.statements[0].compile(dialect=postgresql.dialect()))

    assert claimed_job_id == job.id
    assert job.status == JobStatus.running
    assert job.started_at is not None
    assert job.last_heartbeat_at is not None
    assert job.updated_at is not None
    assert session.added == [job]
    assert session.commits == 1
    assert "crawl_jobs.executor" in compiled
    assert "crawl_jobs.status" in compiled
    assert "ORDER BY crawl_jobs.created_at ASC, crawl_jobs.id ASC" in compiled
    assert "FOR UPDATE SKIP LOCKED" in compiled


def test_claim_next_gce_job_returns_none_when_queue_is_empty():
    session = _FakeSession(None)

    assert worker.claim_next_gce_job(session) is None
    assert session.added == []
    assert session.commits == 0


def test_run_persistent_worker_loop_processes_claimed_jobs_serially(monkeypatch):
    job_ids = [uuid4(), uuid4()]
    claims = iter([*job_ids, None])
    processed: list[tuple[object, bool]] = []

    monkeypatch.setattr(
        worker,
        "_session_factory",
        lambda: lambda: _FakeSession(None),
    )
    monkeypatch.setattr(worker, "claim_next_gce_job", lambda _db: next(claims))
    monkeypatch.setattr(
        worker,
        "process_gce_job",
        lambda job_id, *, delete_self: processed.append((job_id, delete_self)),
    )
    monkeypatch.setattr(worker.time, "sleep", lambda _seconds: (_ for _ in ()).throw(_StopLoop))

    with pytest.raises(_StopLoop):
        worker.run_persistent_worker_loop(poll_interval_seconds=0.01)

    assert processed == [
        (job_ids[0], False),
        (job_ids[1], False),
    ]


def test_wait_for_crawl_process_updates_heartbeats_until_exit(monkeypatch):
    job_id = uuid4()
    db = object()
    process = _FakeProcess(
        [
            subprocess.TimeoutExpired(cmd=["sf"], timeout=15.0),
            subprocess.TimeoutExpired(cmd=["sf"], timeout=15.0),
            0,
        ]
    )
    heartbeats: list[tuple[object, object]] = []

    monkeypatch.setattr(
        worker,
        "update_heartbeat",
        lambda db_arg, job_id_arg, progress_pct=None, urls_crawled=None, status_message=None: heartbeats.append(
            (db_arg, job_id_arg)
        ),
    )

    returncode, stopped_due_to_limit = worker._wait_for_crawl_process(
        process,
        db=db,
        job_id=job_id,
        heartbeat_interval_seconds=15.0,
    )

    assert returncode == 0
    assert stopped_due_to_limit is False
    assert heartbeats == [(db, job_id), (db, job_id)]


def test_wait_for_crawl_process_stops_when_max_urls_reached(monkeypatch, tmp_path):
    job_id = uuid4()
    db = object()
    stdout_log = tmp_path / "sf.log"
    stdout_log.write_text("SpiderProgress [mActive=9, mCompleted=200, mWaiting=50, mCompleted=80.0%]\n")

    process = _FakeProcess(
        [
            subprocess.TimeoutExpired(cmd=["sf"], timeout=15.0),
            143,
        ]
    )

    heartbeats: list[tuple[object, object, float | None, int | None, str | None]] = []
    signalled: list[tuple[int, int]] = []

    monkeypatch.setattr(
        worker,
        "update_heartbeat",
        lambda db_arg, job_id_arg, progress_pct=None, urls_crawled=None, status_message=None: heartbeats.append(
            (db_arg, job_id_arg, progress_pct, urls_crawled, status_message)
        ),
    )
    monkeypatch.setattr(worker.os, "killpg", lambda pid, sig: signalled.append((pid, sig)))

    returncode, stopped_due_to_limit = worker._wait_for_crawl_process(
        process,
        db=db,
        job_id=job_id,
        heartbeat_interval_seconds=15.0,
        stdout_log=stdout_log,
        max_urls=200,
    )

    assert returncode == 143
    assert stopped_due_to_limit is True
    assert signalled == [(process.pid, worker.signal.SIGTERM)]
    assert heartbeats == [
        (
            db,
            job_id,
            80.0,
            200,
            "Crawl limit reached — stopping at 200 URLs",
        )
    ]


def test_find_internal_db_artifact_from_stdout_reads_dbcontext_path(tmp_path):
    internal_db = tmp_path / "ProjectInstanceData" / "abc123"
    internal_db.mkdir(parents=True)
    stdout_log = tmp_path / "screamingfrog.stdout.log"
    stdout_log.write_text(
        "\n".join(
            [
                "some log line",
                f"Torn down DbContext with path {internal_db}",
                "Application Exited",
            ]
        )
    )

    assert worker._find_internal_db_artifact_from_stdout(stdout_log) == internal_db


def test_wait_for_crawl_artifact_polls_until_internal_db_path_appears(monkeypatch, tmp_path):
    stdout_log = tmp_path / "screamingfrog.stdout.log"
    stdout_log.write_text("initial\n")
    internal_db = tmp_path / "ProjectInstanceData" / "late-db"
    internal_db.mkdir(parents=True)

    state = {"calls": 0}

    def fake_find_crawl_artifact(_output_dir):
        return None

    def fake_find_internal_db(_stdout_log):
        state["calls"] += 1
        if state["calls"] == 2:
            return internal_db
        return None

    monkeypatch.setattr(worker, "_find_crawl_artifact", fake_find_crawl_artifact)
    monkeypatch.setattr(worker, "_find_internal_db_artifact_from_stdout", fake_find_internal_db)
    monkeypatch.setattr(worker.time, "sleep", lambda _seconds: None)

    artifact = worker._wait_for_crawl_artifact(tmp_path, stdout_log)

    assert artifact == internal_db
    assert state["calls"] >= 2


def test_run_crawl_cli_does_not_raise_when_limit_stop_returns_nonzero(monkeypatch, tmp_path):
    fake_exports = ModuleType("screamingfrog.cli.exports")
    fake_exports.resolve_cli_path = lambda _cli: "/usr/bin/sf"
    monkeypatch.setitem(__import__("sys").modules, "screamingfrog.cli.exports", fake_exports)

    class _Popen:
        def __init__(self, *args, **kwargs):
            self.pid = 12345

    monkeypatch.setattr(worker.subprocess, "Popen", _Popen)
    monkeypatch.setattr(
        worker,
        "_wait_for_crawl_process",
        lambda *args, **kwargs: (143, True),
    )

    stdout_log = tmp_path / "screamingfrog.stdout.log"
    stderr_log = tmp_path / "screamingfrog.stderr.log"
    stdout_log.write_text("")
    stderr_log.write_text("")

    worker._run_crawl_cli(
        db=object(),
        job_id=uuid4(),
        start_url="https://example.com",
        output_dir=tmp_path,
        cli_path=None,
        config=None,
        max_urls=200,
    )
