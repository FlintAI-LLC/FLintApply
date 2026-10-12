"""iCIMS adapter tests (mocked HTTP)."""

from __future__ import annotations

import httpx
import pytest

from app.models.career_watch import CareerAtsType, WatchedCompany
from app.services.career_watch.http_client import create_career_watch_client
from app.services.career_watch.icims import IcimsAdapter, parse_icims_html

ICIMS_HTML = """
<html><body>
  <div class="iCIMS_JobsTable">
    <a href="/jobs/12345/software-engineer">Software Engineer</a>
  </div>
</body></html>
"""


def test_parse_icims_html_extracts_job_rows() -> None:
    jobs = parse_icims_html(
        ICIMS_HTML,
        base_url="https://careers-costco.icims.com/jobs/search",
    )
    assert len(jobs) == 1
    assert jobs[0].title == "Software Engineer"
    assert "12345" in jobs[0].apply_url


def test_parse_icims_html_unescapes_html_entities_in_title() -> None:
    """This extractor is also reused as the generic post-render fallback
    for headless Workday/SPA extraction, so a raw &amp; in a title must
    come out as a plain & for every caller, not just the iCIMS adapter."""
    html = """
    <div class="iCIMS_JobsTable">
      <a href="/jobs/999/role">Workplace Portfolio &amp; Analytics</a>
    </div>
    """
    jobs = parse_icims_html(html, base_url="https://careers-costco.icims.com/jobs/search")
    assert len(jobs) == 1
    assert jobs[0].title == "Workplace Portfolio & Analytics"
    assert "&amp;" not in jobs[0].title


@pytest.mark.asyncio
async def test_icims_adapter_fetches_html_jobs() -> None:
    company = WatchedCompany(
        name="Costco",
        slug="costco",
        careers_page_url="https://careers-costco.icims.com/jobs/search",
        ats_type=CareerAtsType.icims,
        ats_board_token="careers-costco",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("format=json"):
            return httpx.Response(404)
        return httpx.Response(200, text=ICIMS_HTML)

    adapter = IcimsAdapter()
    async with create_career_watch_client(
        transport=httpx.MockTransport(handler)
    ) as client:
        jobs = await adapter.fetch_jobs(company, client=client)
    assert len(jobs) == 1
