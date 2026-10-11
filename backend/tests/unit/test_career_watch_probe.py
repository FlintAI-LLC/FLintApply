"""Career Watch URL probe helpers."""

from app.models.career_watch import CareerAtsType
from app.services.career_watch.job_filters import meaningful_jobs as _meaningful_jobs
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
