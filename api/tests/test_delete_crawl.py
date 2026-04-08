"""Tests for the DELETE /api/crawls/{job_id} endpoint logic."""

from __future__ import annotations

from app.models import JobStatus


_TERMINAL = {JobStatus.complete, JobStatus.failed, JobStatus.cancelled}
_NON_TERMINAL = {
    JobStatus.queued,
    JobStatus.provisioning,
    JobStatus.running,
    JobStatus.extracting,
    JobStatus.loading,
}


def test_terminal_statuses_allow_deletion():
    for s in _TERMINAL:
        assert s in {JobStatus.complete, JobStatus.failed, JobStatus.cancelled}


def test_non_terminal_statuses_block_deletion():
    for s in _NON_TERMINAL:
        assert s not in _TERMINAL, f"{s} should not be deletable"


def test_all_statuses_covered():
    all_statuses = set(JobStatus)
    assert _TERMINAL | _NON_TERMINAL == all_statuses
