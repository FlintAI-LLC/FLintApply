"""Unit tests for story draft completeness warnings."""

from app.agent.story_completeness import (
    completeness_warnings,
    narrative_mentions_education,
    truncated_bullet_warnings,
)


def test_narrative_mentions_education_detects_student() -> None:
    narrative = "I am a computer science student at Portland Community College."
    assert narrative_mentions_education(narrative)


def test_completeness_warns_missing_education_section() -> None:
    narrative = "I graduated from PCC with an associate degree in 2024."
    resume = """
PROFESSIONAL SUMMARY
Recent graduate.

EXPERIENCE
Camas Library | Volunteer | 2023 – 2024
• Shelved books
""".strip()
    warnings = completeness_warnings(narrative, resume)
    assert any("EDUCATION" in w for w in warnings)


def test_truncated_bullet_warning() -> None:
    resume = """
EXPERIENCE
Northline Health | Engineer | 2024 – Present
• Delivered approximately 56
""".strip()
    warnings = truncated_bullet_warnings(resume)
    assert len(warnings) == 1
    assert "incomplete" in warnings[0].lower()
