"""Server-side filtering for job search results (§18.10 blocked companies)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.jobs.schemas import JobResult


def normalize_company_name(name: str) -> str:
    return name.strip().lower()


def filter_blocked_companies(
    jobs: list[JobResult],
    blocked_companies: list[str] | None,
) -> list[JobResult]:
    """Remove jobs whose company matches a user blocklist (case-insensitive)."""
    if not blocked_companies:
        return jobs
    blocked = {normalize_company_name(c) for c in blocked_companies if c and c.strip()}
    if not blocked:
        return jobs
    return [
        job
        for job in jobs
        if normalize_company_name(job.company) not in blocked
    ]


def _date_posted_cutoff(value: str | None) -> datetime | None:
    if not value:
        return None
    now = datetime.now(timezone.utc)
    mapping = {
        "24h": timedelta(days=1),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
    }
    delta = mapping.get(str(value).lower())
    if delta is None:
        return None
    return now - delta


def apply_job_result_filters(
    jobs: list[JobResult],
    filters: dict[str, Any] | None,
) -> list[JobResult]:
    """Post-filter Hirebase match results (same semantics as cache search)."""
    if not filters:
        return jobs
    out: list[JobResult] = []
    cutoff = _date_posted_cutoff(filters.get("date_posted"))
    min_salary = filters.get("salary_min_usd")
    employment = filters.get("employment_type")
    for job in jobs:
        if filters.get("remote") and not job.remote:
            continue
        if min_salary is not None:
            try:
                floor = int(min_salary)
            except (TypeError, ValueError):
                floor = None
            if floor is not None:
                job_min = job.salary_min_usd
                if job_min is None or job_min < floor:
                    continue
        if employment and job.employment_type:
            if str(employment).lower() != str(job.employment_type).lower():
                continue
        if cutoff and job.posted_date:
            posted = job.posted_date
            if posted.tzinfo is None:
                posted = posted.replace(tzinfo=timezone.utc)
            if posted < cutoff:
                continue
        out.append(job)
    return out


__all__ = [
    "apply_job_result_filters",
    "filter_blocked_companies",
    "normalize_company_name",
]
