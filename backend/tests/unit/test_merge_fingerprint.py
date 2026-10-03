"""Merge fingerprint dedup for projects and education."""

from app.models.master_resume import MasterResumeSectionType
from app.services.master_resume.crud import _merge_fingerprint


def test_project_fingerprint_ignores_body_differences() -> None:
    a = _merge_fingerprint(
        MasterResumeSectionType.project,
        "Movie Agent\nLong description A",
        {"title": "Movie Agent"},
    )
    b = _merge_fingerprint(
        MasterResumeSectionType.project,
        "Movie Agent\nDifferent bullets entirely",
        {},
    )
    assert a == b == "project:movie agent"


def test_education_fingerprint_uses_institution() -> None:
    with_dates = _merge_fingerprint(
        MasterResumeSectionType.education,
        "Portland Community College — Certificate — 2016 – 2017",
        {"institution": "Portland Community College"},
    )
    no_dates = _merge_fingerprint(
        MasterResumeSectionType.education,
        "Portland Community College — Certificate",
        {"school": "Portland Community College"},
    )
    assert with_dates == no_dates == "edu:portland community college"


def test_fingerprint_none_for_skills_and_empty_project() -> None:
    assert (
        _merge_fingerprint(MasterResumeSectionType.skills, "Python", {}) is None
    )
    assert _merge_fingerprint(MasterResumeSectionType.project, "", {}) is None
    assert (
        _merge_fingerprint(
            MasterResumeSectionType.experience,
            "Acme\nbullet",
            {"title": "Acme"},
        )
        is None
    )


def test_distinct_project_titles_do_not_share_fingerprint() -> None:
    a = _merge_fingerprint(
        MasterResumeSectionType.project,
        "Flint\n...",
        {"title": "Flint"},
    )
    b = _merge_fingerprint(
        MasterResumeSectionType.project,
        "Other\n...",
        {"title": "Other"},
    )
    assert a != b
