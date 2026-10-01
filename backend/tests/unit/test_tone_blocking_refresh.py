"""Refresh pass for mirror-JD tone blocking issues."""

from __future__ import annotations

from app.agent.phase4_deterministic import (
    build_blocking_issues_from_score,
    refresh_qa_tone_guidance,
)
from app.agent.phase4_score import compute_ats_score
from app.agent.tone_issue_guidance import refresh_mirror_jd_blocking_issues
from app.agent.tone_profile import Formality, JDToneProfile, ReadingLevel
from app.models.qa import BlockingIssue, QAOutput
from app.models.rewrite import TailoredExperienceEntry, TailoredResumeOutput


def _exec_profile() -> JDToneProfile:
    return JDToneProfile(
        formality=Formality.executive,
        industry_register="financial services",
        dominant_verbs=["establish", "develop", "proven"],
        distinctive_phrases=[],
        sentence_length_median=18,
        reading_level=ReadingLevel.dense,
    )


def test_refresh_enriches_stale_llm_style_rows() -> None:
    jd = "We need you to establish platforms and develop APIs."
    stale = BlockingIssue(
        category="bullet",
        description="JD tone alignment",
        suggestion="Mirror JD vocabulary: 'establish'",
        impact="medium",
        fix_effort="manual_rewrite",
    )
    out = refresh_mirror_jd_blocking_issues([stale], jd)
    assert len(out) == 1
    assert "In the JD they use it like:" in out[0].suggestion
    assert "Example for your resume" in out[0].suggestion


def test_refresh_dedupes_llm_and_deterministic_same_term() -> None:
    jd = "Help us establish cloud governance."
    llm_row = BlockingIssue(
        category="bullet",
        description="Tone gap",
        suggestion="Mirror JD vocabulary: 'establish'",
        impact="medium",
        fix_effort="manual_rewrite",
    )
    enriched_row = BlockingIssue(
        category="bullet",
        description="JD tone alignment",
        suggestion=(
            "Mirror JD vocabulary: 'establish'\n\n"
            'In the JD they use it like: "Help us establish cloud governance."\n\n'
            "Example for your resume (only if accurate): Led and established secure "
            "architectural solutions across core products to drive platform scalability."
        ),
        impact="medium",
        fix_effort="manual_rewrite",
    )
    out = refresh_mirror_jd_blocking_issues([llm_row, enriched_row], jd)
    assert len(out) == 1
    assert "Example for your resume" in out[0].suggestion


def test_build_blocking_enriches_tone_axis_issues() -> None:
    resume = TailoredResumeOutput(
        contact={"name": "Jane Doe", "email": "jane@example.com"},
        skills=["Python"],
        experience=[
            TailoredExperienceEntry(
                title="Engineer",
                company="Acme",
                dates="2020-2024",
                bullets=["Built services."],
            )
        ],
    )
    score = compute_ats_score(resume, ["Python"], tone_profile=_exec_profile())
    jd = "You will establish and develop secure systems."
    issues = build_blocking_issues_from_score(score, jd_text=jd)
    mirror = [
        i
        for i in issues
        if i.description == "JD tone alignment"
        and "establish" in i.suggestion.lower()
    ]
    assert mirror
    assert "Example for your resume" in mirror[0].suggestion


def test_refresh_qa_tone_guidance_updates_blocking_list() -> None:
    qa = QAOutput(
        ats_score=70,
        score_ceiling=70,
        blocking_issues=[
            BlockingIssue(
                category="bullet",
                description="JD tone alignment",
                suggestion="Mirror JD vocabulary: 'develop'",
                impact="medium",
                fix_effort="manual_rewrite",
            )
        ],
    )
    refreshed = refresh_qa_tone_guidance(qa, "We develop platform APIs.")
    assert "Example for your resume" in refreshed.blocking_issues[0].suggestion
