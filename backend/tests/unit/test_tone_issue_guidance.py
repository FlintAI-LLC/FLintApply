"""Deterministic JD tone issue copy."""

from app.agent.tone_issue_guidance import (
    enrich_tone_vocabulary_suggestion,
    jd_snippet_for_term,
    resume_example_line,
)


def test_jd_snippet_finds_term_in_sentence() -> None:
    jd = "We need someone to establish secure platforms. Other text."
    snippet = jd_snippet_for_term(jd, "establish")
    assert snippet is not None
    assert "establish" in snippet.lower()


def test_enrich_adds_jd_line_and_example() -> None:
    jd = "You will establish cloud governance across the org."
    out = enrich_tone_vocabulary_suggestion("Mirror JD vocabulary: 'establish'", jd)
    assert "In the JD they use it like:" in out
    assert "establish" in out
    assert "Example for your resume" in out
    assert "established" in out


def test_enrich_without_jd_still_has_example() -> None:
    out = enrich_tone_vocabulary_suggestion("Mirror JD vocabulary: 'champion'", None)
    assert "championed" in out
    assert "In the JD" not in out


def test_resume_example_line_establish() -> None:
    line = resume_example_line("establish")
    assert "established" in line
