"""Unit tests for output_linter count_by_rule."""

from __future__ import annotations

import pytest

from app.agent.output_linter import LintIssue, count_by_rule

pytestmark = pytest.mark.unit


def test_count_by_rule_aggregates_by_rule_name() -> None:
    issues = [
        LintIssue("bullets", 0, "em_dash_chain", "a — b — c"),
        LintIssue("bullets", 1, "em_dash_chain", "x — y — z"),
    ]
    assert count_by_rule(issues) == {"em_dash_chain": 2}
