"""Career Watch URL probe helpers."""

import pytest

from app.models.career_watch import CareerAtsType
from app.services.career_watch import probe as probe_module
from app.services.career_watch.job_filters import meaningful_jobs as _meaningful_jobs
from app.services.career_watch.probe import ProbeStatus, probe_careers_page
from app.services.career_watch.types import ParsedJob


def test_meaningful_jobs_filters_generic_nav_links() -> None:
    jobs = [
        ParsedJob(
            external_job_id="1",
            title="Search Jobs",
            location="",
            apply_url="https://careers.costco.com/jobs",
            description_text="",
            posted_at=None,
            raw_payload={},
        ),
        ParsedJob(
            external_job_id="2",
            title="Software Engineer",
            location="Remote",
            apply_url="https://careers.costco.com/job/123",
            description_text="",
            posted_at=None,
            raw_payload={},
        ),
    ]
    meaningful = _meaningful_jobs(CareerAtsType.generic_html, jobs)
    assert len(meaningful) == 1
    assert meaningful[0].title == "Software Engineer"


def test_meaningful_jobs_keeps_ats_api_rows() -> None:
    jobs = [
        ParsedJob(
            external_job_id="gh-1",
            title="Backend Engineer",
            location="SF",
            apply_url="https://boards.greenhouse.io/acme/jobs/1",
            description_text="long " * 20,
            posted_at=None,
            raw_payload={},
        ),
    ]
    assert len(_meaningful_jobs(CareerAtsType.greenhouse, jobs)) == 1


@pytest.mark.asyncio
async def test_probe_workday_zero_jobs_warns_instead_of_blocking(monkeypatch) -> None:
    """Workday career sites are frequently client-rendered; the live probe
    intentionally skips headless rendering (cost/latency/abuse surface), so
    a correct Workday URL with 0 synchronously-visible jobs must warn, not
    hard-reject — the background poll worker's headless fallback may still
    find jobs even though this quick check could not confirm it."""

    async def _no_jobs(company, *, client=None, allow_headless=True):
        assert allow_headless is False, "live probe must never trigger headless Chromium"
        return []

    monkeypatch.setattr(probe_module, "fetch_company_jobs", _no_jobs)

    result = await probe_careers_page("https://acme.wd5.myworkdayjobs.com/en-US/Acme")
    assert result.status == ProbeStatus.warning
    assert result.job_count == 0
    assert "workday" in result.message.lower()


@pytest.mark.asyncio
async def test_probe_greenhouse_zero_jobs_still_errors(monkeypatch) -> None:
    """Non-SPA ATS platforms (API-backed, no rendering needed) should still
    hard-reject on 0 jobs — only Workday gets the leniency above."""

    async def _no_jobs(company, *, client=None, allow_headless=True):
        return []

    monkeypatch.setattr(probe_module, "fetch_company_jobs", _no_jobs)

    result = await probe_careers_page("https://boards.greenhouse.io/does-not-exist")
    assert result.status == ProbeStatus.error
