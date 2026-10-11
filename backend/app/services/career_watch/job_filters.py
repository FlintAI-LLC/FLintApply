"""Shared job-list filtering helpers for probe, poller, and headless tier."""

from __future__ import annotations

from app.models.career_watch import CareerAtsType
from app.services.career_watch.types import ParsedJob


def meaningful_jobs(ats_type: CareerAtsType, jobs: list[ParsedJob]) -> list[ParsedJob]:
    """Drop generic-html nav false positives (e.g. Costco \"Search Jobs\" link)."""
    if ats_type != CareerAtsType.generic_html:
        return jobs
    meaningful: list[ParsedJob] = []
    for job in jobs:
        url_l = job.apply_url.lower()
        title_l = job.title.lower().strip()
        if len(job.description_text or "") >= 80:
            meaningful.append(job)
            continue
        if any(
            token in url_l
            for token in (
                "/job/",
                "/jobs/",
                "/posting/",
                "/position/",
                "/opening/",
                "/requisition/",
            )
        ):
            meaningful.append(job)
            continue
        if title_l in {
            "careers home",
            "search jobs",
            "resources for applying",
            "returning users",
        }:
            continue
        if title_l.startswith("see jobs"):
            continue
        if len(title_l) >= 8 and (
            "engineer" in title_l or "manager" in title_l or "analyst" in title_l
        ):
            meaningful.append(job)
    return meaningful


__all__ = ["meaningful_jobs"]
