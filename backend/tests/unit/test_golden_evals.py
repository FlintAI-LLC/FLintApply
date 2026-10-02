"""Golden eval cases for output linter."""

from __future__ import annotations

from app.agent.output_linter import BLOCKING_RULES, lint_bullets
from evals.golden_cases import GOLDEN_CASES


def test_golden_eval_cases() -> None:
    for case in GOLDEN_CASES:
        issues = lint_bullets(case.bullets, case.skills, case.jd)
        rules = {i.rule for i in issues}
        if case.expect_clean:
            assert len(issues) == 0, case.name
        else:
            assert case.expected_rules <= rules, f"{case.name}: {rules}"
