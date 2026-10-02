"""Deterministic fixture linter for eval harness."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from app.agent.output_linter import BLOCKING_RULES, lint_bullets

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _load_fixtures() -> list[dict]:
    if not _FIXTURES_DIR.is_dir():
        return []
    fixtures: list[dict] = []
    for path in sorted(_FIXTURES_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as fh:
            fixtures.append(json.load(fh))
    return fixtures


def run_lint_suite() -> tuple[int, int]:
    """Run fixture + golden expectations; return (passed, failed)."""
    from evals.golden_cases import GOLDEN_CASES

    passed = 0
    failed = 0

    for case in GOLDEN_CASES:
        issues = lint_bullets(case.bullets, case.skills, case.jd)
        rules = {i.rule for i in issues}
        if case.expect_clean:
            blocking = rules & BLOCKING_RULES
            ok = blocking == set() and not (case.expected_rules - rules)
        else:
            ok = case.expected_rules <= rules
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"FAIL golden: {case.name} rules={rules}")

    for fixture in _load_fixtures():
        name = fixture.get("name", "unnamed")
        bullets = list(fixture.get("bullets") or [])
        skills = list(fixture.get("skills") or [])
        jd = str(fixture.get("jd") or "")
        issues = lint_bullets(bullets, skills, jd)
        rules = {i.rule for i in issues}
        if fixture.get("expected_clean"):
            ok = len(issues) == 0
        elif "expected_issues" in fixture:
            expected = set(fixture["expected_issues"])
            ok = rules == expected
        else:
            failed += 1
            print(f"FAIL fixture: {name} missing expected_clean or expected_issues")
            continue
        if ok:
            passed += 1
        else:
            failed += 1
            print(f"FAIL fixture: {name} rules={rules}")

    return passed, failed


def main() -> int:
    passed, failed = run_lint_suite()
    total = passed + failed
    print(f"lint_suite: {passed}/{total} passed, {failed} failed")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
