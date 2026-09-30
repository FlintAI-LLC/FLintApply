"""Deterministic Phase 4 score + blocking-issue injection (shared by session QA and checkup)."""

from __future__ import annotations

import re

from app.agent.phase4_score import ResumeQualityResult, compute_ats_score
from app.agent.tone_profile import JDToneProfile
from app.models.keywords import Keyword
from app.models.qa import BlockingIssue, IssueAnchor

MISSING_KEYWORD_PREFIX = "Missing must-have keyword: "
SINGLE_SECTION_MARKER = " appears only in "

_QUOTED_TERM = re.compile(
    r"['\"\u2018\u2019\u201c\u201d]([^'\"\u2018\u2019\u201c\u201d]{2,80})['\"\u2018\u2019\u201c\u201d]"
)


def extract_quoted_terms(text: str) -> list[str]:
    """Phrases the suggestion wraps in quotes (e.g. Add 'Python' to Skills)."""
    return [m.strip() for m in _QUOTED_TERM.findall(text) if m.strip()]


def candidate_keyword_terms(suggestion: str, must_have_terms: list[str]) -> list[str]:
    """Terms a keyword suggestion advocates: quoted phrases plus verbatim must-haves."""
    terms = extract_quoted_terms(suggestion)
    lower = suggestion.lower()
    for term in must_have_terms:
        t = term.strip()
        if t and t.lower() in lower and t not in terms:
            terms.append(t)
    return terms


def is_deterministic_issue(issue: BlockingIssue, axis_labels: frozenset[str]) -> bool:
    """True when the issue was produced by the scoring engine, not the QA LLM."""
    description = issue.description
    if description.startswith(MISSING_KEYWORD_PREFIX):
        return True
    if description.startswith("'") and SINGLE_SECTION_MARKER in description:
        return True
    return description in axis_labels

_AXIS_TO_CATEGORY: dict[str, tuple[str, str, str]] = {
    "tone_alignment": ("bullet", "medium", "manual_rewrite"),
    "bullet_metrics": ("metric", "high", "user_input"),
    "action_verbs": ("bullet", "medium", "manual_rewrite"),
    "bullet_length": ("bullet", "medium", "manual_rewrite"),
    "resume_length": ("length", "medium", "manual_rewrite"),
    "weak_phrases": ("bullet", "high", "one_click"),
    "first_person": ("bullet", "high", "one_click"),
    "buzzwords": ("bullet", "medium", "manual_rewrite"),
    "section_completeness": ("section", "high", "user_input"),
    "contact_completeness": ("section", "high", "user_input"),
    "field_completeness": ("section", "high", "user_input"),
}


def issue_anchor_from_dict(anchor: dict[str, int | str] | None) -> IssueAnchor | None:
    if not anchor:
        return None
    section = anchor.get("section")
    entry_index = anchor.get("entry_index")
    if section not in ("experience", "projects", "education") or entry_index is None:
        return None
    bullet_index = anchor.get("bullet_index")
    return IssueAnchor(
        section=section,  # type: ignore[arg-type]
        entry_index=int(entry_index),
        bullet_index=int(bullet_index) if bullet_index is not None else None,
    )


def scoring_terms_from_keywords(keywords: list[Keyword]) -> list[str]:
    """Must-have atoms used for ATS keyword axes (drops unscorable context blobs)."""
    terms: list[str] = []
    seen: set[str] = set()
    for kw in keywords:
        if kw.tier != "must_have" or not kw.term.strip():
            continue
        key = kw.term.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        terms.append(kw.term.strip())
    return terms


def compute_score_result(
    tailored,
    must_have_terms: list[str],
    *,
    career_stage: str = "mid",
    tone_profile: JDToneProfile | None = None,
) -> ResumeQualityResult:
    keywords = [k for k in must_have_terms if k and k.strip()]
    return compute_ats_score(
        tailored,
        keywords,
        career_stage=career_stage,
        tone_profile=tone_profile,
    )


def build_blocking_issues_from_score(
    score_result: ResumeQualityResult,
    *,
    existing_issues: list[BlockingIssue] | None = None,
    flagged_keyword_terms: set[str] | None = None,
) -> list[BlockingIssue]:
    """Turn deterministic axis findings into blocking issues."""
    corrected_issues = list(existing_issues or [])
    flagged_terms = flagged_keyword_terms or set()

    for kw in score_result.missing_keywords:
        if kw.lower() in flagged_terms:
            continue
        corrected_issues.append(
            BlockingIssue(
                category="keyword",
                description=f"{MISSING_KEYWORD_PREFIX}{kw}",
                suggestion=(
                    f"Add '{kw}' to the Skills section AND reinforce it in an Experience bullet "
                    "or your Professional Summary. If you don't have this skill, dismiss to ignore."
                ),
                impact="high",
                fix_effort="one_click",
            )
        )

    for kw in score_result.single_section_keywords:
        if kw.lower() in flagged_terms:
            continue
        sections = score_result.keyword_section_map.get(kw, [])
        section_label = sections[0] if sections else "skills"
        other_targets = [s for s in ("experience", "summary") if s != section_label]
        target_str = " or ".join(other_targets) if other_targets else "experience"
        corrected_issues.append(
            BlockingIssue(
                category="keyword",
                description=f"'{kw}'{SINGLE_SECTION_MARKER}{section_label}",
                suggestion=(
                    f"Reinforce '{kw}' in your {target_str} so it appears in 2+ sections "
                    "(ATS keyword density rule)."
                ),
                impact="high",
                fix_effort="one_click",
            )
        )

    for axis in score_result.axes:
        if axis.status == "pass":
            continue
        mapping = _AXIS_TO_CATEGORY.get(axis.key)
        if mapping is None:
            continue
        category, impact, fix_effort = mapping
        if axis.anchored_issues:
            for anchored in axis.anchored_issues:
                corrected_issues.append(
                    BlockingIssue(
                        category=category,  # type: ignore[arg-type]
                        description=axis.label,
                        suggestion=anchored.text,
                        impact=impact,  # type: ignore[arg-type]
                        fix_effort=fix_effort,  # type: ignore[arg-type]
                        anchor=issue_anchor_from_dict(anchored.anchor),
                    )
                )
            continue
        for issue_text in axis.issues:
            corrected_issues.append(
                BlockingIssue(
                    category=category,  # type: ignore[arg-type]
                    description=axis.label,
                    suggestion=issue_text,
                    impact=impact,  # type: ignore[arg-type]
                    fix_effort=fix_effort,  # type: ignore[arg-type]
                )
            )

    return corrected_issues
