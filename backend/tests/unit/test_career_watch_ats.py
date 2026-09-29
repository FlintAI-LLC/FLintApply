"""Career Watch ATS adapter tests."""

from __future__ import annotations

import pytest

from app.models.career_watch import CareerAtsType
from app.services.career_watch.ashby import parse_ashby_payload
from app.services.career_watch.detect import detect_ats_from_url
from app.services.career_watch.generic_html import parse_generic_html
from app.services.career_watch.greenhouse import parse_greenhouse_payload
from app.services.career_watch.lever import parse_lever_payload
from app.services.career_watch.registry import get_adapter
from app.services.career_watch.workday import parse_workday_html


def test_detect_greenhouse_url() -> None:
    result = detect_ats_from_url("https://boards.greenhouse.io/acme/jobs")
    assert result.ats_type == CareerAtsType.greenhouse
    assert result.board_token == "acme"


def test_detect_lever_url() -> None:
    result = detect_ats_from_url("https://jobs.lever.co/flint")
    assert result.ats_type == CareerAtsType.lever
    assert result.board_token == "flint"


def test_detect_ashby_url() -> None:
    result = detect_ats_from_url("https://jobs.ashbyhq.com/flint-ai")
    assert result.ats_type == CareerAtsType.ashby
    assert result.board_token == "flint-ai"


def test_detect_workday_url() -> None:
    result = detect_ats_from_url("https://acme.wd5.myworkdayjobs.com/External")
    assert result.ats_type == CareerAtsType.workday
    assert result.board_token == "acme/External"


def test_detect_generic_html_fallback() -> None:
    result = detect_ats_from_url("https://careers.example.com/jobs")
    assert result.ats_type == CareerAtsType.generic_html


def test_greenhouse_parse_jobs() -> None:
    jobs = parse_greenhouse_payload(
        [
            {
                "id": 123,
                "title": "Backend Engineer",
                "location": {"name": "Remote"},
                "absolute_url": "https://boards.greenhouse.io/acme/jobs/123",
                "content": "<p>Build APIs</p>",
            }
        ]
    )
    assert len(jobs) == 1
    assert jobs[0].external_job_id == "123"
    assert jobs[0].title == "Backend Engineer"
    assert "Build APIs" in jobs[0].description_text


def test_lever_parse_jobs() -> None:
    jobs = parse_lever_payload(
        [
            {
                "id": "abc",
                "text": "Product Manager",
                "hostedUrl": "https://jobs.lever.co/acme/abc",
                "descriptionPlain": "Own roadmap",
                "categories": {"location": "SF"},
                "createdAt": 1_700_000_000_000,
            }
        ]
    )
    assert jobs[0].external_job_id == "abc"
    assert jobs[0].location == "SF"


def test_ashby_parse_jobs() -> None:
    jobs = parse_ashby_payload(
        [
            {
                "id": "job-1",
                "title": "Designer",
                "location": "NYC",
                "jobUrl": "https://jobs.ashbyhq.com/acme/job-1",
            }
        ]
    )
    assert jobs[0].title == "Designer"


def test_ashby_skips_unlisted_jobs() -> None:
    jobs = parse_ashby_payload(
        [
            {
                "id": "listed",
                "title": "Listed",
                "isListed": True,
            },
            {
                "id": "hidden",
                "title": "Hidden",
                "isListed": False,
            },
        ]
    )
    assert [job.external_job_id for job in jobs] == ["listed"]


def test_workday_parse_html_links() -> None:
    html = '<a href="/en-US/job/Backend-Engineer_R123">Backend Engineer</a>'
    jobs = parse_workday_html(
        html,
        base_url="https://acme.wd5.myworkdayjobs.com/External",
    )
    assert len(jobs) == 1
    assert jobs[0].title == "Backend Engineer"


def test_generic_html_extracts_job_links() -> None:
    html = """
    <a href="/jobs/backend-engineer">Backend Engineer Job</a>
    <a href="/about">About us</a>
    """
    jobs = parse_generic_html(html, base_url="https://careers.example.com")
    assert len(jobs) == 1
    assert "Backend Engineer" in jobs[0].title


def test_greenhouse_parse_strips_tags_and_entities() -> None:
    jobs = parse_greenhouse_payload(
        [
            {
                "id": 1,
                "title": "Engineer",
                "location": {"name": "Remote"},
                "absolute_url": "https://example.com/1",
                "content": "<p>Build &amp; ship</p>",
            }
        ]
    )
    assert jobs[0].description_text == "Build & ship"
    assert "<p" not in jobs[0].description_text.lower()


def test_lever_html_description_normalized() -> None:
    jobs = parse_lever_payload(
        [
            {
                "id": "x",
                "text": "SWE",
                "hostedUrl": "https://jobs.lever.co/acme/x",
                "description": "<ul><li>Own APIs</li></ul>",
                "categories": {"location": "Remote"},
            }
        ]
    )
    assert "- Own APIs" in jobs[0].description_text
    assert "<ul" not in jobs[0].description_text.lower()


def test_job_cache_to_result_normalizes_stale_html() -> None:
    from datetime import datetime, timezone
    from uuid import uuid4

    from app.models.jobs import JobCache
    from app.services.jobs.job_service import job_cache_to_result

    row = JobCache(
        id=uuid4(),
        sources=["corpus"],
        external_ids={},
        title="Role",
        company="Co",
        company_normalized="co",
        location="Remote",
        remote=True,
        employment_type="",
        posted_date=datetime.now(timezone.utc),
        description="<p>Legacy HTML body</p>",
        apply_url="https://example.com",
        raw_json={},
        cached_at=datetime.now(timezone.utc),
        expires_at=datetime.now(timezone.utc),
        dedup_key="test-key",
    )
    result = job_cache_to_result(row)
    assert result.description == "Legacy HTML body"
    assert "<p" not in result.description.lower()


def test_registry_returns_greenhouse_adapter() -> None:
    adapter = get_adapter(CareerAtsType.greenhouse)
    assert adapter.__class__.__name__ == "GreenhouseAdapter"
