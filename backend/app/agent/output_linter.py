"""Deterministic output lint for tailored resume bullets and skills."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

import structlog
from pydantic import BaseModel

from app.agent.phase3_hollow import make_hollow_rejector
from app.models.resume import ParsedResume
from app.models.rewrite import TailoredResumeOutput

log = structlog.get_logger()

BLOCKING_RULES = frozenset(
    {
        "trailing_truncation",
        "em_dash_chain",
        "skill_is_sentence",
        "skill_is_jd_substring",
    }
)

_TRAILING_TRUNCATION = re.compile(r"\d+[-–—]\s*$")
_EM_DASH_CHAIN = re.compile(r"(?:\s—\s|\s–\s)")
_TRAILING_PREP = re.compile(
    r"\b(for|with|and|to|of|in|by|or|the)\s*$",
    re.IGNORECASE,
)
_SKILL_FUNCTION_WORDS = re.compile(
    r"\b(with|of|in|the|a|to|that|which|for|and|or)\b",
    re.IGNORECASE,
)
_TERMINAL_PUNCT = frozenset(". ,;:!?")


@dataclass(frozen=True)
class LintIssue:
    field: str
    index: int
    rule: str
    original: str


def count_by_rule(issues: list[LintIssue]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue.rule] = counts.get(issue.rule, 0) + 1
    return counts


def lint_bullets(
    bullets: list[str],
    skills: list[str],
    jd_text: str,
) -> list[LintIssue]:
    issues: list[LintIssue] = []
    jd_lower = (jd_text or "").lower()

    for idx, bullet in enumerate(bullets):
        text = bullet or ""
        if _TRAILING_TRUNCATION.search(text):
            issues.append(
                LintIssue("bullets", idx, "trailing_truncation", text),
            )
        if _TRAILING_PREP.search(text.rstrip()):
            issues.append(
                LintIssue("bullets", idx, "trailing_preposition", text),
            )
        dash_hits = len(_EM_DASH_CHAIN.findall(text))
        if dash_hits >= 2:
            issues.append(LintIssue("bullets", idx, "em_dash_chain", text))
        if len(text.split()) < 5:
            issues.append(LintIssue("bullets", idx, "bullet_too_short", text))
        if _unbalanced_parens(text):
            issues.append(LintIssue("bullets", idx, "unbalanced_parens", text))

    flat_skills = _flatten_skill_lines(skills)
    for idx, skill in enumerate(flat_skills):
        if _skill_is_sentence(skill):
            issues.append(LintIssue("skills", idx, "skill_is_sentence", skill))
        elif _skill_is_jd_substring(skill, jd_lower):
            issues.append(
                LintIssue("skills", idx, "skill_is_jd_substring", skill),
            )

    return issues


def has_blocking_lint_issues(issues: list[LintIssue]) -> bool:
    return any(issue.rule in BLOCKING_RULES for issue in issues)


def _entry_bullets(entry) -> list[str]:
    if isinstance(entry, dict):
        raw = entry.get("bullets") or []
    else:
        raw = getattr(entry, "bullets", None) or []
    return [str(b) for b in raw]


def collect_tailored_bullets(bullets_source) -> list[str]:
    """Flatten experience (and project) bullets from a TailoredResumeOutput-like object."""
    bullets: list[str] = []
    for entry in getattr(bullets_source, "experience", None) or []:
        bullets.extend(_entry_bullets(entry))
    for entry in getattr(bullets_source, "projects", None) or []:
        bullets.extend(_entry_bullets(entry))
    return bullets


def _unbalanced_parens(text: str) -> bool:
    depth = 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                return True
    return depth != 0


def _flatten_skill_lines(skills: list[str]) -> list[str]:
    terms: list[str] = []
    for line in skills:
        payload = line.split(":", 1)[1] if ":" in line else line
        for part in payload.split(","):
            trimmed = part.strip()
            if trimmed:
                terms.append(trimmed)
    return terms


def _skill_is_sentence(skill: str) -> bool:
    candidate = skill.strip()
    if not candidate:
        return False
    if len(candidate) > 40:
        return True
    if candidate[-1] in _TERMINAL_PUNCT:
        return True
    if _SKILL_FUNCTION_WORDS.search(candidate):
        return True
    return False


def _skill_is_jd_substring(skill: str, jd_lower: str) -> bool:
    if not jd_lower:
        return False
    skill_n = skill.lower().strip()
    words = skill_n.split()
    if len(words) < 5:
        return False
    if skill_n in jd_lower:
        return True
    jd_words = jd_lower.split()
    if len(jd_words) < 5:
        return False
    for i in range(len(jd_words) - 4):
        window = " ".join(jd_words[i : i + 5])
        if skill_n == window:
            return True
    return False


def make_phase3_accept_result(
    jd_text: str,
    source: ParsedResume | None,
) -> Callable[[BaseModel], str | None]:
    """Combine hollow rejection with blocking output-lint rules for LLM retries."""
    hollow_reject = make_hollow_rejector(source)

    def _accept(output: BaseModel) -> str | None:
        rejection = hollow_reject(output)
        if rejection:
            return rejection
        if not isinstance(output, TailoredResumeOutput):
            return None
        bullets = collect_tailored_bullets(output)
        issues = lint_bullets(bullets, list(output.skills or []), jd_text)
        blocking = [issue for issue in issues if issue.rule in BLOCKING_RULES]
        if not blocking:
            return None
        rules = sorted({issue.rule for issue in blocking})
        log.warning("phase3_output_linter_blocking", rules=rules, count=len(blocking))
        return "Output lint failed: " + ", ".join(rules)

    return _accept


def annotate_postprocess_lint(
    output: TailoredResumeOutput,
    jd_text: str,
) -> TailoredResumeOutput:
    """Record lint findings after deterministic post-processing (no LLM retry)."""
    bullets = collect_tailored_bullets(output)
    issues = lint_bullets(bullets, list(output.skills or []), jd_text)
    if not issues:
        return output
    notes = list(output.rewrite_notes or [])
    for issue in issues:
        log.warning(
            "phase3_postprocess_lint",
            rule=issue.rule,
            field=issue.field,
            index=issue.index,
        )
        snippet = issue.original
        if len(snippet) > 120:
            snippet = snippet[:120] + "…"
        notes.append(
            f"Lint ({issue.rule}) on {issue.field}[{issue.index}]: {snippet}",
        )
    return output.model_copy(update={"rewrite_notes": notes})


class TailoredLintValidationError(Exception):
    """Raised when a save path hits blocking lint rules."""

    def __init__(self, issues: list[LintIssue]) -> None:
        self.issues = issues
        super().__init__("tailored output failed lint")


def blocking_lint_issues(
    output: TailoredResumeOutput,
    jd_text: str,
) -> list[LintIssue]:
    bullets = collect_tailored_bullets(output)
    issues = lint_bullets(bullets, list(output.skills or []), jd_text)
    return [issue for issue in issues if issue.rule in BLOCKING_RULES]


def ensure_tailored_passes_blocking_lint(
    output: TailoredResumeOutput,
    jd_text: str,
) -> None:
    blocking = blocking_lint_issues(output, jd_text)
    if blocking:
        raise TailoredLintValidationError(blocking)
