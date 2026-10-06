"""Off-ramp classification for non-tech and low-confidence job searches."""

from app.services.jobs.schemas import JobResult
from app.services.jobs.search_enrichment import classify_search_off_ramp
from datetime import datetime, timezone
from uuid import uuid4


def _job(title: str, *, tier: str = "good") -> JobResult:
    now = datetime.now(timezone.utc)
    return JobResult(
        id=uuid4(),
        title=title,
        company="Acme",
        posted_date=now,
        relevance_tier=tier,
    )


def test_math_tutor_triggers_non_tech_off_ramp() -> None:
    reason = classify_search_off_ramp("Math Tutor", [], terms=["math", "tutor"])
    assert reason == "non_tech"


def test_programming_assistant_no_off_ramp_with_strong_hits() -> None:
    jobs = [
        _job("Programming Assistant", tier="strong"),
        _job("Software Engineer", tier="strong"),
        _job("Developer Advocate", tier="good"),
    ]
    reason = classify_search_off_ramp(
        "Programming Assistant",
        jobs,
        terms=["programming", "assistant"],
    )
    assert reason is None


def test_empty_results_off_ramp() -> None:
    reason = classify_search_off_ramp("Backend engineer", [], terms=["backend", "engineer"])
    assert reason == "empty_results"
