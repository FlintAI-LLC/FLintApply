"""Career Watch ATS adapter tests."""

from __future__ import annotations

from app.models.career_watch import CareerAtsType
from app.services.career_watch.ashby import parse_ashby_payload
from app.services.career_watch.detect import detect_ats_from_url
from app.services.career_watch.generic_html import parse_generic_html
from app.services.career_watch.greenhouse import parse_greenhouse_payload
from app.services.career_watch.lever import parse_lever_payload
from app.services.career_watch.registry import get_adapter
from app.services.career_watch.workday import (
    build_workday_job_url,
    parse_workday_cxs_payload,
    parse_workday_html,
    workday_cxs_api_url,
)


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


def test_detect_workday_url_strips_locale_segment() -> None:
    """A locale-prefixed Workday path (the common real-world shape) must
    resolve to the actual site token, not the locale code."""
    result = detect_ats_from_url("https://acme.wd5.myworkdayjobs.com/en-US/External")
    assert result.ats_type == CareerAtsType.workday
    assert result.board_token == "acme/External"


def test_detect_workday_url_single_segment_locale_like_name_unaffected() -> None:
    """A single-segment site path is never stripped, even if it happens to
    look locale-like, since there is nothing left to fall back to."""
    result = detect_ats_from_url("https://acme.wd5.myworkdayjobs.com/en")
    assert result.ats_type == CareerAtsType.workday
    assert result.board_token == "acme/en"


def test_detect_workday_url_non_locale_first_segment_is_preserved() -> None:
    """A multi-segment path whose first segment is NOT locale-shaped must
    keep that segment as the site token — pins the actual regex check, not
    just "always drop the first of 2+ segments" (which would wrongly turn
    this into acme/job instead of acme/External)."""
    result = detect_ats_from_url(
        "https://acme.wd5.myworkdayjobs.com/External/job/123"
    )
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


def test_workday_cxs_api_url_from_board_token() -> None:
    url = workday_cxs_api_url(
        "https://workday.wd5.myworkdayjobs.com/en-US/Workday",
        "workday/Workday",
    )
    assert url == "https://workday.wd5.myworkdayjobs.com/wday/cxs/workday/Workday/jobs"


def test_parse_workday_cxs_payload_builds_apply_urls() -> None:
    payload = {
        "total": 1,
        "jobPostings": [
            {
                "title": "Backend Engineer",
                "externalPath": "/job/USA-CA-Pleasanton/Role_JR-1",
                "locationsText": "USA, CA, Pleasanton",
                "bulletFields": ["JR-1"],
            }
        ],
    }
    jobs = parse_workday_cxs_payload(
        payload,
        origin="https://workday.wd5.myworkdayjobs.com",
        locale="en-US",
        site="Workday",
    )
    assert len(jobs) == 1
    assert jobs[0].title == "Backend Engineer"
    assert jobs[0].apply_url == build_workday_job_url(
        origin="https://workday.wd5.myworkdayjobs.com",
        locale="en-US",
        site="Workday",
        external_path="/job/USA-CA-Pleasanton/Role_JR-1",
    )


def test_workday_parse_html_links() -> None:
    html = '<a href="/en-US/job/Backend-Engineer_R123">Backend Engineer</a>'
    jobs = parse_workday_html(
        html,
        base_url="https://acme.wd5.myworkdayjobs.com/External",
    )
    assert len(jobs) == 1
    assert jobs[0].title == "Backend Engineer"


def test_workday_parse_html_apply_url_does_not_duplicate_base_path() -> None:
    """Regression: apply_url must resolve against the origin, not get the
    base_url's own path segment concatenated in front of the absolute href
    (previously produced .../Workday/en-US/Workday/job/... instead of
    .../en-US/Workday/job/...)."""
    html = (
        '<a href="/en-US/Workday/job/USA-CA-Pleasanton/Role_JR-1">Role &amp; Title</a>'
    )
    jobs = parse_workday_html(
        html,
        base_url="https://workday.wd5.myworkdayjobs.com/Workday",
    )
    assert len(jobs) == 1
    assert jobs[0].apply_url == (
        "https://workday.wd5.myworkdayjobs.com/en-US/Workday/job/USA-CA-Pleasanton/Role_JR-1"
    )
    assert jobs[0].title == "Role & Title"


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
