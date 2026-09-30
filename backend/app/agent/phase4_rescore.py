"""Free ATS re-score: recompute the deterministic score after resume edits.

The score number, axis breakdown, keyword findings and guidance are pure
functions of the resume, so no LLM call is needed. LLM-authored parts of the
previous Phase 4 output (checklist, user_action_required, issue prose) are
carried over and only pruned where the resume now visibly satisfies them.
"""

from __future__ import annotations

from app.agent.checkup_guidance import build_checkup_guidance
from app.agent.phase4_deterministic import (
    build_blocking_issues_from_score,
    candidate_keyword_terms,
    compute_score_result,
    is_deterministic_issue,
)
from app.agent.phase4_narrative import build_deterministic_narrative
from app.agent.phase4_qa import _collect_resume_text
from app.models.qa import BlockingIssue, QAOutput, ScoreAxis

_HIGH_IMPACT = "high"
_ONE_CLICK = "one_click"


def _prune_prior_issues(
    prior: list[BlockingIssue],
    *,
    axis_labels: frozenset[str],
    must_have_terms: list[str],
    resume_text: str,
) -> list[BlockingIssue]:
    kept: list[BlockingIssue] = []
    for issue in prior:
        if is_deterministic_issue(issue, axis_labels):
            continue
        if issue.category == "keyword":
            candidates = candidate_keyword_terms(issue.suggestion, must_have_terms)
            if candidates and all(term.lower() in resume_text for term in candidates):
                continue
        kept.append(issue)
    return kept


def rescore_qa_output(
    prior: QAOutput,
    *,
    tailored,
    must_have_terms: list[str],
    career_stage: str,
    tone_profile,
    target_role: str,
) -> QAOutput:
    """Return `prior` with score, axes, deterministic issues and guidance refreshed."""
    score_result = compute_score_result(
        tailored,
        must_have_terms,
        career_stage=career_stage,
        tone_profile=tone_profile,
    )
    axis_labels = frozenset(axis.label for axis in score_result.axes)
    kept = _prune_prior_issues(
        prior.blocking_issues,
        axis_labels=axis_labels,
        must_have_terms=must_have_terms,
        resume_text=_collect_resume_text(tailored).lower(),
    )
    flagged_terms = {
        term.lower()
        for issue in kept
        if issue.category == "keyword"
        for term in candidate_keyword_terms(issue.suggestion, must_have_terms)
    }
    issues = build_blocking_issues_from_score(
        score_result,
        existing_issues=kept,
        flagged_keyword_terms=flagged_terms,
    )
    narrative = build_deterministic_narrative(
        score_result=score_result,
        target_role=target_role,
        prior_categories=prior.category_summaries,
    )
    updated = prior.model_copy(
        update={
            "ats_score": score_result.ats_score,
            "score_ceiling": score_result.score_ceiling,
            "score_axes": [
                ScoreAxis.model_validate(axis.to_dict()) for axis in score_result.axes
            ],
            "missing_keywords": score_result.missing_keywords,
            "single_section_keywords": score_result.single_section_keywords,
            "blocking_issues": issues,
            "quick_wins": [
                i for i in issues if i.impact == _HIGH_IMPACT and i.fix_effort == _ONE_CLICK
            ],
            "guidance": build_checkup_guidance(score_result, blocking_issues=issues),
            "rank_label": narrative.rank_label,
            "headline": narrative.headline,
            "category_summaries": narrative.category_summaries,
        }
    )
    # Re-validate so ordering and quick_wins/score_ceiling invariants are enforced.
    return QAOutput.model_validate(updated.model_dump())
