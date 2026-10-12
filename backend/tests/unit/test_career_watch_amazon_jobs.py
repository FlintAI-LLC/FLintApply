"""Amazon Jobs adapter tests (mocked HTTP)."""

from __future__ import annotations

import httpx
import pytest

from app.models.career_watch import CareerAtsType, WatchedCompany
from app.services.career_watch.amazon_jobs import (
    AmazonJobsAdapter,
    amazon_locale_from_url,
    amazon_search_api_url,
    parse_amazon_search_payload,
)
from app.services.career_watch.detect import detect_ats_from_url
from app.services.career_watch.http_client import create_career_watch_client


def test_detect_amazon_jobs_url() -> None:
    result = detect_ats_from_url("https://www.amazon.jobs/")
    assert result.ats_type == CareerAtsType.amazon_jobs
    assert result.board_token == "en"
    assert result.company_name == "Amazon"


def test_amazon_locale_from_en_search_path() -> None:
    assert amazon_locale_from_url("https://www.amazon.jobs/en/search") == "en"
    assert amazon_locale_from_url("https://www.amazon.jobs/en-gb/search") == "en-gb"
    assert amazon_search_api_url("https://www.amazon.jobs/", "en") == (
        "https://www.amazon.jobs/en/search.json"
    )


def test_parse_amazon_search_payload_maps_jobs() -> None:
    payload = {
        "error": None,
        "hits": 1,
        "jobs": [
            {
                "id": "abc-123",
                "title": "Software Engineer",
                "job_path": "/en/jobs/1/software-engineer",
                "normalized_location": "Seattle, WA, USA",
                "description": "<p>Build things</p>",
                "posted_date": "July  3, 2026",
            }
        ],
    }
    jobs = parse_amazon_search_payload(payload)
    assert len(jobs) == 1
    assert jobs[0].title == "Software Engineer"
    assert jobs[0].external_job_id == "abc-123"
    assert jobs[0].apply_url == "https://www.amazon.jobs/en/jobs/1/software-engineer"
    assert jobs[0].location == "Seattle, WA, USA"
    assert jobs[0].description_text == "Build things"
    assert jobs[0].posted_at is not None


@pytest.mark.asyncio
async def test_amazon_adapter_paginates_search_json() -> None:
    company = WatchedCompany(
        name="Amazon",
        slug="amazon",
        careers_page_url="https://www.amazon.jobs/en/",
        ats_type=CareerAtsType.amazon_jobs,
        ats_board_token="en",
    )
    seen_offsets: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/en/search.json")
        seen_offsets.append(int(request.url.params["offset"]))
        return httpx.Response(
            200,
            json={
                "error": None,
                "hits": 2,
                "jobs": [
                    {
                        "id": "1",
                        "title": "Role A",
                        "job_path": "/en/jobs/1/a",
                        "location": "Remote",
                    },
                    {
                        "id": "2",
                        "title": "Role B",
                        "job_path": "/en/jobs/2/b",
                        "location": "Remote",
                    },
                ],
            },
            request=request,
        )

    adapter = AmazonJobsAdapter()
    async with create_career_watch_client(
        transport=httpx.MockTransport(handler)
    ) as client:
        jobs = await adapter.fetch_jobs(company, client=client, max_jobs=20)
    assert seen_offsets == [0]
    assert len(jobs) == 2
