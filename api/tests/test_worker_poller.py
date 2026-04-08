from __future__ import annotations

from datetime import datetime, timedelta, timezone
import subprocess
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
        lambda db_arg, job_id_arg, progress_pct=None: heartbeats.append((db_arg, job_id_arg)),
    )

    returncode = worker._wait_for_crawl_process(
        process,
        db=db,
        job_id=job_id,
        heartbeat_interval_seconds=15.0,
    )

    assert returncode == 0
    assert heartbeats == [(db, job_id), (db, job_id)]
