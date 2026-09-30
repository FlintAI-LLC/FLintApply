"""Free ATS re-score: deterministic refresh of a prior Phase 4 output."""

from __future__ import annotations

from app.agent.phase4_deterministic import (
    MISSING_KEYWORD_PREFIX,
    candidate_keyword_terms,
    is_deterministic_issue,
)
from app.agent.phase4_rescore import rescore_qa_output
from app.models.qa import BlockingIssue, QAItem, QAOutput
from app.models.rewrite import (
    TailoredExperienceEntry,
    TailoredResumeOutput,
)

MUST_HAVE = ["Python", "Kubernetes"]
LLM_PROSE_ISSUE = "Lead with the strongest outcome in your first IdMe24 bullet."


def _resume(*, skills: list[str], bullet: str) -> TailoredResumeOutput:
    return TailoredResumeOutput(
        contact={"name": "Jane Doe", "email": "jane@example.com"},
        summary="Senior engineer.",
        skills=skills,
        experience=[
            TailoredExperienceEntry(
                title="Engineer", company="Acme", dates="2022-2025", bullets=[bullet]
            )
        ],
        education=[],
        projects=[],
        certifications=[],
    )


def _prior() -> QAOutput:
    return QAOutput(
        checklist=[QAItem(item="Tailored to one specific JD", status="pass")],
        overall_status="warn",
        user_action_required=["Confirm the 30% figure."],
        ats_score=40,
        score_ceiling=90,
        blocking_issues=[
            BlockingIssue(
                category="keyword",
                description=f"{MISSING_KEYWORD_PREFIX}Kubernetes",
                suggestion="Add 'Kubernetes' to the Skills section.",
                impact="high",
                fix_effort="one_click",
            ),
            BlockingIssue(
                category="keyword",
                description="Kubernetes is not in Experience",
                suggestion="Reinforce 'Kubernetes' in an Experience bullet.",
                impact="high",
                fix_effort="one_click",
            ),
            BlockingIssue(
                category="bullet",
                description="Weak opening",
                suggestion=LLM_PROSE_ISSUE,
                impact="medium",
                fix_effort="manual_rewrite",
            ),
        ],
    )


def _rescore(resume: TailoredResumeOutput) -> QAOutput:
    return rescore_qa_output(
        _prior(),
        tailored=resume,
        must_have_terms=MUST_HAVE,
        career_stage="mid",
        tone_profile=None,
        target_role="Platform Engineer",
    )


def test_rescore_is_deterministic() -> None:
    resume = _resume(skills=["Languages: Python"], bullet="Built Python services for 1M users")
    first, second = _rescore(resume), _rescore(resume)
    assert first.ats_score == second.ats_score
    assert first.model_dump() == second.model_dump()


def test_adding_missing_keyword_raises_score_and_drops_its_issues() -> None:
    before = _resume(skills=["Languages: Python"], bullet="Built Python services for 1M users")
    after = _resume(
        skills=["Languages: Python", "Platform: Kubernetes"],
        bullet="Ran Kubernetes clusters serving 1M users with Python tooling",
    )
    score_before = _rescore(before)
    score_after = _rescore(after)

    assert score_after.ats_score > score_before.ats_score
    descriptions = [i.description for i in score_after.blocking_issues]
    assert f"{MISSING_KEYWORD_PREFIX}Kubernetes" not in descriptions
    assert "Kubernetes is not in Experience" not in descriptions
    assert "Kubernetes" not in score_after.missing_keywords


def test_llm_prose_issue_and_checklist_are_carried_over() -> None:
    resume = _resume(skills=["Languages: Python"], bullet="Built Python services for 1M users")
    updated = _rescore(resume)
    suggestions = [i.suggestion for i in updated.blocking_issues]
    assert LLM_PROSE_ISSUE in suggestions
    assert updated.user_action_required == ["Confirm the 30% figure."]
    assert [c.item for c in updated.checklist] == ["Tailored to one specific JD"]


def test_headline_reflects_the_new_score_and_ceiling_invariant_holds() -> None:
    resume = _resume(skills=["Languages: Python"], bullet="Built Python services for 1M users")
    updated = _rescore(resume)
    assert f"{updated.ats_score}/100" in updated.headline
    assert updated.score_ceiling >= updated.ats_score
    assert updated.guidance is not None
    assert updated.guidance.recoverable_ceiling >= updated.ats_score


def test_payload_carries_every_field_the_ats_panel_renders() -> None:
    resume = _resume(skills=["Languages: Python"], bullet="Built Python services for 1M users")
    updated = _rescore(resume)
    assert updated.rank_label
    assert updated.headline
    assert updated.score_axes
    for axis in updated.score_axes:
        assert axis.key and axis.label
        assert axis.max > 0
        assert 0 <= axis.score <= axis.max
    assert updated.category_summaries
    for summary in updated.category_summaries:
        assert summary.label
        assert summary.issue_count >= 0
    assert updated.guidance is not None


def test_category_prose_survives_and_counts_are_recomputed() -> None:
    prior = _prior()
    prior.category_summaries = [
        summary.model_copy(update={"why_it_matters": "from full analysis"})
        for summary in _rescore(
            _resume(skills=["Languages: Python"], bullet="Built Python services")
        ).category_summaries
    ]
    updated = rescore_qa_output(
        prior,
        tailored=_resume(skills=["Languages: Python"], bullet="Built Python services"),
        must_have_terms=MUST_HAVE,
        career_stage="mid",
        tone_profile=None,
        target_role="Platform Engineer",
    )
    assert any(s.why_it_matters == "from full analysis" for s in updated.category_summaries)


def test_quick_wins_stay_a_subset_of_blocking_issues() -> None:
    resume = _resume(skills=["Languages: Python"], bullet="Built Python services for 1M users")
    updated = _rescore(resume)
    assert updated.quick_wins
    keys = {(i.category, i.description, i.suggestion) for i in updated.blocking_issues}
    assert all((q.category, q.description, q.suggestion) in keys for q in updated.quick_wins)
    assert all(q.impact == "high" and q.fix_effort == "one_click" for q in updated.quick_wins)


def test_candidate_terms_use_quotes_and_verbatim_must_haves() -> None:
    terms = candidate_keyword_terms("Add 'Terraform' and mention Python", ["Python", "Go"])
    assert terms == ["Terraform", "Python"]


def test_deterministic_issue_detection() -> None:
    engine = BlockingIssue(
        category="keyword",
        description="'Python' appears only in skills",
        suggestion="x",
        impact="high",
        fix_effort="one_click",
    )
    prose = BlockingIssue(
        category="bullet",
        description="Weak opening",
        suggestion="x",
        impact="low",
        fix_effort="manual_rewrite",
    )
    assert is_deterministic_issue(engine, frozenset())
    assert not is_deterministic_issue(prose, frozenset())
    assert is_deterministic_issue(prose, frozenset({"Weak opening"}))
