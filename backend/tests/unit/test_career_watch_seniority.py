"""Seniority title filter tests."""

from app.services.career_watch.seniority import title_matches_seniority_levels


def test_empty_levels_pass_all() -> None:
    assert title_matches_seniority_levels("Senior Engineer", [])


def test_senior_level_matches() -> None:
    assert title_matches_seniority_levels("Senior Backend Engineer", ["senior"])
    assert not title_matches_seniority_levels("Junior Backend Engineer", ["senior"])
