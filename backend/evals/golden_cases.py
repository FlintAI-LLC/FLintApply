"""Hardcoded golden lint cases (no user data)."""

from __future__ import annotations

from dataclasses import dataclass

JD = (
    "We need a senior engineer who can lead platform migrations "
    "and mentor junior developers on the team."
)


@dataclass(frozen=True)
class GoldenLintCase:
    name: str
    bullets: list[str]
    skills: list[str]
    jd: str
    expected_rules: set[str]
    expect_clean: bool = False


GOLDEN_CASES: tuple[GoldenLintCase, ...] = (
    GoldenLintCase(
        name="clean_bullet",
        bullets=["Led backend migration reducing latency by 40%"],
        skills=[],
        jd=JD,
        expected_rules=set(),
        expect_clean=True,
    ),
    GoldenLintCase(
        name="trailing_truncation",
        bullets=["improved performance 10–"],
        skills=[],
        jd=JD,
        expected_rules={"trailing_truncation"},
    ),
    GoldenLintCase(
        name="em_dash_chain",
        bullets=["Led — Built — Managed — Delivered"],
        skills=[],
        jd=JD,
        expected_rules={"em_dash_chain"},
    ),
    GoldenLintCase(
        name="skill_is_jd_substring",
        bullets=[],
        skills=["senior engineer who can lead platform"],
        jd=JD,
        expected_rules={"skill_is_jd_substring"},
    ),
    GoldenLintCase(
        name="bullet_too_short",
        bullets=["Worked"],
        skills=[],
        jd=JD,
        expected_rules={"bullet_too_short"},
    ),
)
