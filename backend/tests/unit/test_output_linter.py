"""Unit tests for tailored resume output linter."""

from __future__ import annotations

from app.agent.output_linter import BLOCKING_RULES, lint_bullets


JD = (
    "We need a senior engineer who can lead platform migrations "
    "and mentor junior developers on the team."
)


def _rules(bullets: list[str], skills: list[str], jd: str = JD) -> set[str]:
    return {issue.rule for issue in lint_bullets(bullets, skills, jd)}


def test_trailing_truncation_fires() -> None:
    assert "trailing_truncation" in _rules(["improved performance by 10–"], [])


def test_em_dash_chain_fires() -> None:
    bullet = "Led — Built — Managed — Delivered"
    assert "em_dash_chain" in _rules([bullet], [])


def test_skill_is_jd_substring_fires() -> None:
    phrase = "senior engineer who can lead platform"
    skills = [f"Tools: {phrase}"]
    assert "skill_is_jd_substring" in _rules([], skills)


def test_clean_bullet_does_not_fire_blocking() -> None:
    bullet = "Led backend migration reducing latency by 40%"
    issues = lint_bullets([bullet], [], JD)
    blocking = {i.rule for i in issues if i.rule in BLOCKING_RULES}
    assert blocking == set()


def test_clean_skill_does_not_fire() -> None:
    issues = lint_bullets([], ["Languages: Kubernetes, Python"], JD)
    blocking = {i.rule for i in issues if i.rule in BLOCKING_RULES}
    assert blocking == set()
