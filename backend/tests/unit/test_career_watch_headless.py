"""Headless tier tests (Playwright mocked)."""

from __future__ import annotations

import pytest

from app.models.career_watch import CareerAtsType, WatchedCompany
from app.services.career_watch import registry
from app.services.career_watch.greenhouse import GreenhouseAdapter
from app.services.career_watch.headless import _extract_rendered_jobs, fetch_jobs_headless
from app.services.career_watch.ssrf_guard import CareerWatchSsrfError
from app.services.career_watch.types import ParsedJob
from app.services.career_watch.workday import WorkdayAdapter

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


_WORKDAY_RENDERED = """
<html><body>
<ul>
<li><a data-automation-id="jobTitle" href="/en-US/Acme/job/Remote/Backend-Engineer_JR-1">Backend Engineer</a></li>
<li><a data-automation-id="jobTitle" href="/en-US/Acme/job/Remote/Nav-Link">Search Jobs</a></li>
</ul>
</body></html>
"""


def test_extract_rendered_jobs_workday_finds_post_render_links() -> None:
    """Workday's job list only exists in the DOM after client-side XHR runs,
    so this must be extracted from the *rendered* HTML (headless tier),
    unlike the plain-HTTP WorkdayAdapter which only sees the empty shell."""
    jobs = _extract_rendered_jobs(
        _WORKDAY_RENDERED,
        base_url="https://acme.wd5.myworkdayjobs.com/Acme",
        ats_type=CareerAtsType.workday,
    )
    titles = {job.title for job in jobs}
    assert "Backend Engineer" in titles
    # Apply URL must resolve against the origin, not duplicate the base path.
    backend_job = next(job for job in jobs if job.title == "Backend Engineer")
    assert backend_job.apply_url == (
        "https://acme.wd5.myworkdayjobs.com/en-US/Acme/job/Remote/Backend-Engineer_JR-1"
    )


@pytest.mark.asyncio
async def test_registry_falls_back_to_headless_for_workday(monkeypatch) -> None:
    """The direct Workday adapter sees only the pre-render HTML shell (0
    jobs) for a modern SPA career site; the headless fallback must now be
    eligible for ats_type=workday, not just generic_html/icims."""

    async def _empty_fetch(self, company, *, client):
        return []

    async def _fake_headless(company, *, browser=None):
        return [
            ParsedJob(
                external_job_id="1",
                title="Headless-rendered Role",
                location="",
                apply_url="https://acme.wd5.myworkdayjobs.com/job/1",
                description_text="",
                posted_at=None,
                raw_payload={},
            )
        ]

    monkeypatch.setattr(WorkdayAdapter, "fetch_jobs", _empty_fetch)
    monkeypatch.setattr(registry, "fetch_jobs_headless", _fake_headless)

    company = WatchedCompany(
        name="Acme",
        slug="acme",
        careers_page_url="https://acme.wd5.myworkdayjobs.com/Acme",
        ats_type=CareerAtsType.workday,
        ats_board_token="acme/Acme",
    )
    jobs = await registry.fetch_company_jobs(company)
    assert len(jobs) == 1
    assert jobs[0].title == "Headless-rendered Role"


@pytest.mark.asyncio
async def test_registry_does_not_fall_back_to_headless_for_greenhouse(monkeypatch) -> None:
    """Negative control for the gate above: an ATS type that is API-backed
    (no JS rendering needed) must NOT trigger headless on 0 jobs, otherwise
    a bug that opens the gate to every ats_type (e.g. `if allow_headless:`
    with the type check dropped) would go undetected."""

    headless_calls: list[WatchedCompany] = []

    async def _empty_fetch(self, company, *, client):
        return []

    async def _spy_headless(company, *, browser=None):
        headless_calls.append(company)
        return []

    monkeypatch.setattr(GreenhouseAdapter, "fetch_jobs", _empty_fetch)
    monkeypatch.setattr(registry, "fetch_jobs_headless", _spy_headless)

    company = WatchedCompany(
        name="Acme",
        slug="acme",
        careers_page_url="https://boards.greenhouse.io/acme",
        ats_type=CareerAtsType.greenhouse,
        ats_board_token="acme",
    )
    jobs = await registry.fetch_company_jobs(company)
    assert jobs == []
    assert headless_calls == []
