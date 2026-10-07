"""Unit tests for post-match job filtering."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.services.jobs.filtering import apply_job_result_filters
from app.services.jobs.schemas import JobResult


def _job(**kwargs) -> JobResult:
    defaults = {
        "id": uuid.UUID("00000000-0000-0000-0000-000000000001"),
        "title": "Engineer",
        "company": "Acme",
        "remote": False,
        "salary_min_usd": 100_000,
        "posted_date": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    return JobResult(**defaults)


def test_remote_filter_excludes_onsite() -> None:
    jobs = [
        _job(remote=True),
        _job(id=uuid.UUID("00000000-0000-0000-0000-000000000002"), remote=False),
    ]
    out = apply_job_result_filters(jobs, {"remote": True})
    assert len(out) == 1
    assert out[0].remote is True


def test_salary_min_filter() -> None:
    jobs = [
        _job(salary_min_usd=120_000),
        _job(id=uuid.UUID("00000000-0000-0000-0000-000000000002"), salary_min_usd=60_000),
    ]
    out = apply_job_result_filters(jobs, {"salary_min_usd": 80_000})
    assert len(out) == 1
    assert out[0].salary_min_usd == 120_000
