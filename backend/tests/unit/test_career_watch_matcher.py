"""Career Watch matcher unit tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.models.career_watch import CareerJobCache
from app.services.career_watch.apply_url import normalize_apply_url
from app.services.career_watch.matcher import (
    keyword_match_score,
    match_baseline_for_watch,
    passes_career_watch_keyword_match,
)
from app.models.career_watch import UserWatchedCompany


def _job(**kwargs: object) -> CareerJobCache:
    defaults = {
        "id": uuid.uuid4(),
        "watched_company_id": uuid.uuid4(),
        "external_job_id": "1",
        "title": "Senior Backend Engineer",
        "location": "Remote",
        "description_text": "Python, FastAPI, PostgreSQL",
        "description_hash": "abc",
        "first_seen_at": datetime.now(timezone.utc),
        "last_seen_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    return CareerJobCache(**defaults)  # type: ignore[arg-type]


def test_keyword_match_score_hits() -> None:
    job = _job()
    score, reason = keyword_match_score(["python", "backend"], job)
    assert score > 0
    assert "python" in reason.lower()


def test_keyword_match_score_miss() -> None:
    job = _job(title="Office Manager")
    score, reason = keyword_match_score(["kernel", "rust"], job)
    assert score == 0.0
    assert reason == ""


def test_keyword_match_without_keywords_scores_zero() -> None:
    job = _job()
    score, reason = keyword_match_score([], job)
    assert score == 0.0
    assert reason == ""


def test_passes_requires_two_hits_or_title() -> None:
    job_desc_only = _job(
        title="Office Manager",
        description_text="We use python sometimes",
    )
    score, _ = keyword_match_score(["python", "backend"], job_desc_only)
    assert score > 0
    assert not passes_career_watch_keyword_match(
        ["python", "backend"], job_desc_only, score=score
    )

    job_title = _job(title="Python Backend Engineer", description_text="General role")
    score2, _ = keyword_match_score(["python", "backend"], job_title)
    assert passes_career_watch_keyword_match(
        ["python", "backend"], job_title, score=score2
    )

    job_two = _job(title="Engineer", description_text="python and backend stack")
    score3, _ = keyword_match_score(["python", "backend"], job_two)
    assert passes_career_watch_keyword_match(["python", "backend"], job_two, score=score3)


def test_normalize_apply_url_strips_tracking() -> None:
    a = normalize_apply_url("https://jobs.example/role?utm_source=x")
    b = normalize_apply_url("https://jobs.example/role")
    assert a == b


def test_match_baseline_uses_last_matched_at() -> None:
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    matched = datetime(2026, 2, 1, tzinfo=timezone.utc)
    watch = UserWatchedCompany(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        watched_company_id=uuid.uuid4(),
        keywords=[],
        created_at=created,
        last_matched_at=matched,
        is_active=True,
    )
    assert match_baseline_for_watch(watch) == matched
