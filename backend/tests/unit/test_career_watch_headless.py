"""Headless tier tests (Playwright mocked)."""

from __future__ import annotations

import pytest

from app.models.career_watch import CareerAtsType, WatchedCompany
from app.services.career_watch.headless import fetch_jobs_headless
from app.services.career_watch.ssrf_guard import CareerWatchSsrfError

RENDERED = """
<html><body>
<script type="application/ld+json">
{"@type":"JobPosting","title":"Staff Engineer","identifier":"job-99",
 "url":"https://careers-costco.icims.com/jobs/99"}
</script>
</body></html>
"""


class _FakeBrowser:
    def __init__(self, html: str = RENDERED) -> None:
        self._html = html
        self.last_url: str | None = None

    async def render_html(self, url: str, *, user_agent: str, timeout_ms: int) -> str:
        self.last_url = url
        if "127.0.0.1" in url:
            raise CareerWatchSsrfError("blocked")
        return self._html


@pytest.mark.asyncio
async def test_headless_extracts_jsonld_jobs() -> None:
    company = WatchedCompany(
        name="Costco",
        slug="costco",
        careers_page_url="https://careers.costco.com/jobs",
        canonical_poll_url="https://careers-costco.icims.com/jobs/search",
        ats_type=CareerAtsType.icims,
        ats_board_token="careers-costco",
    )
    browser = _FakeBrowser()
    jobs = await fetch_jobs_headless(company, browser=browser)
    assert len(jobs) == 1
    assert jobs[0].title == "Staff Engineer"
    assert browser.last_url == company.effective_poll_url


@pytest.mark.asyncio
async def test_headless_ssrf_blocks_private_target() -> None:
    company = WatchedCompany(
        name="Bad",
        slug="bad",
        careers_page_url="http://127.0.0.1/jobs",
        ats_type=CareerAtsType.generic_html,
    )
    with pytest.raises(CareerWatchSsrfError):
        await fetch_jobs_headless(company, browser=_FakeBrowser())
