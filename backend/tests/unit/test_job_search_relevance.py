"""Seniority alignment and match_reasons on job search results."""

import re
from datetime import datetime, timezone
from uuid import uuid4

from app.services.jobs.schemas import JobResult
from app.services.jobs.search_enrichment import enrich_search_results, _term_hits_title


def _job(title: str, description: str = "") -> JobResult:
    now = datetime.now(timezone.utc)
    return JobResult(
        id=uuid4(),
        title=title,
        company="Corp",
        description=description,
        posted_date=now,
    )


def test_tutor_does_not_match_tutorial_in_title() -> None:
    assert not _term_hits_title("tutor", "Tutorial Author")
    assert _term_hits_title("tutor", "Math Tutor")


def test_intern_query_flags_senior_title_mismatch() -> None:
    jobs = enrich_search_results(
        "software intern",
        [_job("Senior Software Engineer")],
    )
    assert jobs[0].relevance_tier == "mismatch"
    assert any("Seniority mismatch" in r for r in jobs[0].match_reasons)


def test_match_reasons_include_title_hit() -> None:
    jobs = enrich_search_results(
        "python engineer",
        [_job("Python Backend Engineer")],
    )
    assert jobs[0].relevance_tier in ("strong", "good")
    assert any("Title matches" in r for r in jobs[0].match_reasons)
