"""Tests for tech_classifier."""

from __future__ import annotations

import pytest

from app.services.career_watch.tech_classifier import (
    auto_pass,
    classify_company,
    classify_titles,
)

TECH = "Software Engineer"
OTHER = "Account Executive"


def test_tier1_slug_autopasses_regardless_of_titles() -> None:
    result = classify_company(slug="Stripe", tier1_slugs=["stripe"], job_titles=[OTHER] * 10)
    assert result.decision == "accept"


def test_pinned_source_autopasses() -> None:
    assert classify_company(slug="x", tier1_slugs=[], job_titles=[OTHER], source="pinned").decision == "accept"


@pytest.mark.parametrize(
    "category",
    [
        "Software",
        "Software Engineering",
        "AI/ML/Data",
        "Data Science, AI & Machine Learning",
        "Hardware",
        "Hardware Engineering",
        "Quant",
        "software",
    ],
)
def test_real_simplify_tech_categories_autopass(category: str) -> None:
    assert auto_pass(slug="x", tier1_slugs=[], categories=[category])


@pytest.mark.parametrize("category", ["Product", "Product Management", "Marketing", ""])
def test_non_tech_categories_do_not_autopass(category: str) -> None:
    assert not auto_pass(slug="x", tier1_slugs=[], categories=[category])


def test_any_tech_category_among_several_autopasses() -> None:
    assert auto_pass(slug="x", tier1_slugs=[], categories=["Product", "Software"])


def test_yc_provenance_autopasses_only_on_tech_signal() -> None:
    assert auto_pass(slug="x", tier1_slugs=[], industries=["Software", "B2B"])
    assert auto_pass(slug="x", tier1_slugs=[], tags=["Developer Tools"])
    assert not auto_pass(slug="x", tier1_slugs=[], industries=["Consumer", "Food"], tags=["Restaurants"])


@pytest.mark.parametrize(
    ("tech", "other", "decision"),
    [
        (3, 7, "accept"),  # ratio exactly 0.30
        (2, 8, "quarantine"),  # ratio 0.20, under 4 tech titles
        (3, 17, "quarantine"),  # ratio exactly 0.15, under 4 tech titles
        (2, 18, "omit"),  # ratio 0.10
        (4, 21, "accept"),  # 4 tech titles wins over low ratio (0.16)
        (0, 10, "omit"),
        (1, 0, "accept"),
    ],
)
def test_title_ratio_boundaries(tech: int, other: int, decision: str) -> None:
    assert classify_titles([TECH] * tech + [OTHER] * other).decision == decision


def test_empty_board_is_quarantined() -> None:
    assert classify_titles([]).decision == "quarantine"


def test_only_first_25_titles_are_sampled() -> None:
    titles = [OTHER] * 25 + [TECH] * 50
    assert classify_titles(titles).decision == "omit"


@pytest.mark.parametrize(
    "title",
    ["Senior Frontend Engineer", "Site Reliability Engineer (SRE)", "iOS Developer", "Staff Engineer, Platform", "Data Scientist", "QA Engineer"],
)
def test_tech_title_regex_matches(title: str) -> None:
    assert classify_titles([title]).decision == "accept"


@pytest.mark.parametrize("title", ["Account Executive", "Office Manager", "Recruiter", "Sales Development Rep"])
def test_non_tech_titles_do_not_match(title: str) -> None:
    assert classify_titles([title]).decision == "omit"
