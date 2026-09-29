"""Unit tests for resume-derived job title suggestions."""

from __future__ import annotations

import pytest

from app.agent import job_title_suggestions as jts


def test_extract_held_titles_from_experience() -> None:
    sections = {
        "experience": [
            {"title": "Mobile Developer", "company": "ShelfMark"},
            {"title": "Software Engineer", "company": "Acme"},
        ]
    }
    assert jts.extract_held_titles(sections) == [
        "Mobile Developer",
        "Software Engineer",
    ]


def test_heuristic_includes_mobile_titles_for_react_native_resume() -> None:
    resume = """
    ShelfMark — Mobile Developer
    Built a React Native book tracking app with 500 users.
    """
    held = ["Mobile Developer"]
    titles = jts._heuristic_suggestions(held_titles=held, resume_text=resume, count=10)
    assert "Mobile Developer" in titles
    assert any("React Native" in t or "Mobile" in t for t in titles)
    assert len(titles) == 10


def test_parse_llm_titles_accepts_json_array() -> None:
    raw = '["Backend Engineer", "Python Developer"]'
    assert jts._parse_llm_titles(raw) == ["Backend Engineer", "Python Developer"]


@pytest.mark.asyncio
async def test_suggest_job_titles_heuristic_without_llm() -> None:
    suggestions, held, source = await jts.suggest_job_titles(
        resume_text="Senior QA Engineer at TrustCo. Python automation.",
        parsed_sections={"experience": [{"title": "QA Engineer", "company": "TrustCo"}]},
        llm_client=None,
        count=10,
    )
    assert source == "heuristic"
    assert "QA Engineer" in held
    assert len(suggestions) == 10


def _heuristic(resume: str, held: list[str] | None = None, count: int = 10) -> list[str]:
    return jts._heuristic_suggestions(held_titles=held or [], resume_text=resume, count=count)


@pytest.mark.parametrize(
    "resume",
    [
        "Built landing pages with HTML and CSS. Deployed to the latest studios site.",
        "Wrote YAML configs and shipped the latest release for design studios.",
    ],
)
def test_keywords_do_not_match_inside_other_words(resume: str) -> None:
    titles = _heuristic(resume)
    assert "Machine Learning Engineer" not in titles
    assert "QA Engineer" not in titles
    assert "iOS Developer" not in titles


@pytest.mark.parametrize(
    ("resume", "expected"),
    [
        ("Wrote Go and Rust services for a payments ledger.", "Distributed Systems Engineer"),
        ("Ran Kubernetes and Terraform for CI/CD on-call rotations.", "Site Reliability Engineer"),
        ("Airflow and Spark ETL pipelines into Snowflake.", "Data Engineer"),
        ("Built React and TypeScript storefronts.", "Frontend Engineer"),
        ("Implemented OAuth and IAM policies, led an appsec review.", "Security Engineer"),
        ("Full stack developer on a Next.js product.", "Full Stack Engineer"),
    ],
)
def test_tech_families_get_adjacent_titles(resume: str, expected: str) -> None:
    assert expected in _heuristic(resume)


def test_staff_and_principal_holders_get_level_matched_titles() -> None:
    staff = _heuristic("Distributed systems in Go.", held=["Staff Software Engineer"])
    assert "Staff Software Engineer" in staff
    principal = _heuristic("Distributed systems in Go.", held=["Principal Engineer"])
    assert any(t.startswith("Principal") for t in principal)


def test_junior_resume_gets_no_staff_titles() -> None:
    titles = _heuristic("Junior developer, Python.", held=["Software Engineer"])
    assert not any("Staff" in t or "Principal" in t for t in titles)


def test_held_titles_come_first_and_output_is_deduped() -> None:
    titles = _heuristic("Python and Go.", held=["Backend Engineer"])
    assert titles[0] == "Backend Engineer"
    assert len({t.casefold() for t in titles}) == len(titles)
