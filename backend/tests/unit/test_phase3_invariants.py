"""Unit tests for deterministic Phase 3 section invariants."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.agent.phase3_experience_fallback import apply_experience_fallback
from app.agent.phase3_hollow import (
    make_hollow_rejector,
    phase3_is_hollow,
)
from app.agent.phase3_invariants import (
    enforce_resume_invariants,
    preserve_master_sections,
)
from app.agent.phase3_postprocess import (
    flatten_skill_terms,
    postprocess_tailored_output,
    skills_are_categorized,
)
from app.agent.phase3_truthfulness import TruthfulnessContext
from app.main import app
from app.models.resume import (
    EducationEntry,
    ExperienceEntry,
    ParsedResume,
    ProjectEntry,
)
from app.models.rewrite import (
    TailoredEducationEntry,
    TailoredExperienceEntry,
    TailoredResumeOutput,
)
from app.services.session_store import (
    create_session,
    get_session,
    reset_redis_keys_for_tests,
    update_session,
)

EDU_NOTE = (
    "Restored Education section — LLM output omitted it despite "
    "being present in the original resume."
)
SKILLS_NOTE = (
    "Restored Skills section — LLM output omitted it despite "
    "being present in the original resume."
)


def _parsed(**overrides: object) -> ParsedResume:
    base: dict[str, object] = {
        "summary": "Backend engineer with platform experience.",
        "skills": ["Python", "FastAPI", "Postgres"],
        "experience": [
            ExperienceEntry(
                title="Engineer", company="Acme", dates="2020-2024", bullets=["Built APIs."]
            )
        ],
        "education": [EducationEntry(degree="BS CS", institution="State U", year="2018")],
        "projects": [ProjectEntry(name="Side Project", bullets=["Shipped it."])],
    }
    base.update(overrides)
    return ParsedResume(**base)  # type: ignore[arg-type]


def _healthy(**overrides: object) -> TailoredResumeOutput:
    base: dict[str, object] = {
        "summary": "Tailored summary.",
        "skills": ["Languages: Python"],
        "experience": [
            TailoredExperienceEntry(
                title="Engineer", company="Acme", dates="2020-2024", bullets=["Owned APIs."]
            )
        ],
        "education": [TailoredEducationEntry(degree="BS CS", institution="State U", year="2018")],
        "projects": [{"name": "Side Project", "bullets": ["Shipped it."]}],
    }
    base.update(overrides)
    return TailoredResumeOutput(**base)  # type: ignore[arg-type]


def test_skills_restored_from_prior_before_parsed() -> None:
    prior = _healthy(skills=["Languages: Rust"])
    out = enforce_resume_invariants(
        _healthy(skills=[]), resume_parsed=_parsed(), prior_output=prior
    )
    assert out.skills == ["Languages: Rust"]
    assert out.rewrite_notes.count(SKILLS_NOTE) == 1


def test_skills_restored_from_parsed_when_no_prior() -> None:
    out = enforce_resume_invariants(
        _healthy(skills=[]), resume_parsed=_parsed(), prior_output=None
    )
    assert out.skills == ["Python", "FastAPI", "Postgres"]
    assert SKILLS_NOTE in out.rewrite_notes


def test_blank_skill_strings_count_as_empty() -> None:
    out = enforce_resume_invariants(
        _healthy(skills=["  ", ""]), resume_parsed=_parsed(), prior_output=None
    )
    assert out.skills == ["Python", "FastAPI", "Postgres"]


def test_current_output_wins_over_prior_and_parsed() -> None:
    current = _healthy(summary="Current summary.", skills=["Languages: Go"])
    out = enforce_resume_invariants(
        current,
        resume_parsed=_parsed(),
        prior_output=_healthy(summary="Prior summary.", skills=["Languages: Rust"]),
    )
    assert out.summary == "Current summary."
    assert out.skills == ["Languages: Go"]
    assert out.rewrite_notes == current.rewrite_notes


def test_summary_restored_from_prior_then_parsed() -> None:
    prior = _healthy(summary="Prior summary.")
    from_prior = enforce_resume_invariants(
        _healthy(summary=""), resume_parsed=_parsed(), prior_output=prior
    )
    assert from_prior.summary == "Prior summary."

    from_parsed = enforce_resume_invariants(
        _healthy(summary="  "), resume_parsed=_parsed(), prior_output=None
    )
    assert from_parsed.summary == "Backend engineer with platform experience."


def test_all_sources_empty_leaves_sections_empty_without_note() -> None:
    empty_source = ParsedResume()
    out = enforce_resume_invariants(
        TailoredResumeOutput(), resume_parsed=empty_source, prior_output=None
    )
    assert out.skills == []
    assert out.summary == ""
    assert out.experience == []
    assert out.education == []
    assert out.projects == []
    assert out.rewrite_notes == []


def test_no_sources_at_all_is_a_no_op() -> None:
    original = TailoredResumeOutput()
    assert (
        enforce_resume_invariants(original, resume_parsed=None, prior_output=None)
        == original
    )


def test_nothing_fabricated_only_source_text_is_copied() -> None:
    parsed = _parsed()
    out = enforce_resume_invariants(
        TailoredResumeOutput(), resume_parsed=parsed, prior_output=None
    )
    assert out.skills == parsed.skills
    assert out.summary == parsed.summary
    assert [b for e in out.experience for b in e.bullets] == ["Built APIs."]
    assert [e.institution for e in out.education] == ["State U"]
    assert [p["name"] for p in out.projects] == ["Side Project"]


def test_experience_entries_restored_from_prior_before_parsed() -> None:
    prior = _healthy()
    out = enforce_resume_invariants(
        _healthy(experience=[]), resume_parsed=_parsed(), prior_output=prior
    )
    assert out.experience[0].bullets == ["Owned APIs."]


def test_empty_role_gets_bullets_copied_and_current_roles_untouched() -> None:
    current = _healthy(
        experience=[
            TailoredExperienceEntry(title="Engineer", company="Acme", bullets=[]),
            TailoredExperienceEntry(title="Lead", company="Other", bullets=["Kept."]),
        ]
    )
    out = enforce_resume_invariants(
        current, resume_parsed=_parsed(), prior_output=_healthy()
    )
    assert out.experience[0].bullets == ["Owned APIs."]
    assert out.experience[1].bullets == ["Kept."]
    assert any("Restored bullets for Acme" in n for n in out.rewrite_notes)


def test_role_with_no_source_stays_empty() -> None:
    current = _healthy(
        experience=[TailoredExperienceEntry(company="Unknown Co", bullets=[])]
    )
    out = enforce_resume_invariants(
        current, resume_parsed=_parsed(), prior_output=None
    )
    assert out.experience[0].bullets == []


def test_education_and_projects_restored_when_dropped() -> None:
    out = enforce_resume_invariants(
        _healthy(education=[], projects=[]),
        resume_parsed=_parsed(),
        prior_output=None,
    )
    assert out.education[0].degree == "BS CS"
    assert out.projects[0]["name"] == "Side Project"


def test_invariants_are_idempotent_and_notes_deduplicated() -> None:
    once = enforce_resume_invariants(
        TailoredResumeOutput(), resume_parsed=_parsed(), prior_output=None
    )
    assert once.skills and once.summary and once.experience
    assert once.education and once.projects
    assert len(once.rewrite_notes) >= 4
    twice = enforce_resume_invariants(once, resume_parsed=_parsed(), prior_output=None)
    assert twice == once
    assert len(once.rewrite_notes) == len(set(once.rewrite_notes))


def test_preexisting_restore_note_is_not_duplicated() -> None:
    current = _healthy(education=[], rewrite_notes=[EDU_NOTE])
    out = enforce_resume_invariants(current, resume_parsed=_parsed(), prior_output=None)
    assert out.education[0].degree == "BS CS"
    assert out.rewrite_notes.count(EDU_NOTE) == 1


def test_postprocess_emits_one_education_and_one_projects_note() -> None:
    ctx = TruthfulnessContext(resume_parsed=_parsed())
    out = postprocess_tailored_output(
        _healthy(education=[], projects=[]), None, truthfulness=ctx
    )
    assert sum("Restored Education" in n for n in out.rewrite_notes) == 1
    assert sum("Restored Projects" in n for n in out.rewrite_notes) == 1


def test_postprocess_is_idempotent_across_two_runs() -> None:
    ctx = TruthfulnessContext(resume_parsed=_parsed())
    once = postprocess_tailored_output(_healthy(skills=[]), ["Python"], truthfulness=ctx)
    twice = postprocess_tailored_output(once, ["Python"], truthfulness=ctx)
    assert twice == once


def test_fallback_does_not_rebuild_when_only_skills_and_summary_are_missing() -> None:
    result = apply_experience_fallback(
        _healthy(skills=[], summary=""),
        resume_parsed=_parsed(),
        phase2_output=None,
        prior_output=None,
        must_have_keywords=None,
    )
    assert result.experience[0].bullets == ["Owned APIs."]
    assert not any("fallback" in n.lower() for n in result.rewrite_notes)


def test_scoped_shaped_partial_passes_sourceless_rejector_only() -> None:
    partial = _healthy(skills=[], summary="")
    assert make_hollow_rejector()(partial) is None
    assert make_hollow_rejector(_parsed())(partial) is not None


def test_whitespace_prior_fields_in_a_hollow_prior_fall_through_to_parsed() -> None:
    prior = _healthy(skills=[" "], summary=" ", experience=[], education=[])
    out = enforce_resume_invariants(
        _healthy(skills=[], summary="", education=[]),
        resume_parsed=_parsed(),
        prior_output=prior,
    )
    assert out.skills == ["Python", "FastAPI", "Postgres"]
    assert out.summary == "Backend engineer with platform experience."
    assert out.education[0].degree == "BS CS"


def test_hollow_treats_whitespace_skills_as_missing() -> None:
    assert phase3_is_hollow(_healthy(skills=[" "]), source=_parsed()) is True
    assert phase3_is_hollow(
        _healthy(skills=[], summary=""), source=_parsed(skills=[" "], summary="  ")
    ) is False


def test_prior_output_is_not_mutated_by_restoration() -> None:
    prior = _healthy()
    snapshot = prior.model_dump()
    restored = enforce_resume_invariants(
        _healthy(experience=[]), resume_parsed=_parsed(), prior_output=prior
    )
    restored.experience[0].bullets.append("mutation")
    assert prior.model_dump() == snapshot


def test_postprocess_runs_invariants_and_categorizes_restored_skills() -> None:
    ctx = TruthfulnessContext(resume_parsed=_parsed())
    out = postprocess_tailored_output(
        _healthy(skills=[]), ["Python"], truthfulness=ctx
    )
    assert skills_are_categorized(out.skills)
    assert {t.lower() for t in flatten_skill_terms(out.skills)} >= {
        "python",
        "fastapi",
        "postgres",
    }
    assert SKILLS_NOTE in out.rewrite_notes


def test_postprocess_without_truthfulness_context_does_not_restore() -> None:
    out = postprocess_tailored_output(_healthy(skills=[]), None)
    assert out.skills == []


@pytest.mark.asyncio
async def test_explicit_patch_to_empty_is_a_real_deletion() -> None:
    await reset_redis_keys_for_tests()
    session = await create_session()
    session.resume_parsed = _parsed()
    session.phase3_output = _healthy()
    await update_session(session)

    emptied = _healthy(skills=[]).model_dump()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.patch(
            f"/api/sessions/{session.session_id}/tailored",
            json={"tailored_output": emptied},
        )
    assert response.status_code == 200

    stored = await get_session(session.session_id)
    assert stored is not None and stored.phase3_output is not None
    assert stored.phase3_output.skills == []


def test_hollow_when_source_had_skills_and_output_does_not() -> None:
    source = _parsed()
    assert phase3_is_hollow(_healthy(skills=[])) is False
    assert phase3_is_hollow(_healthy(skills=[]), source=source) is True


def test_hollow_when_source_had_summary_and_output_does_not() -> None:
    assert phase3_is_hollow(_healthy(summary=""), source=_parsed()) is True


def test_not_hollow_when_source_never_had_the_sections() -> None:
    bare_source = _parsed(skills=[], summary=None)
    assert phase3_is_hollow(_healthy(skills=[], summary=""), source=bare_source) is False


def test_complete_output_is_not_hollow_with_source() -> None:
    assert phase3_is_hollow(_healthy(), source=_parsed()) is False


def test_rejector_uses_source_only_when_supplied() -> None:
    missing_skills = _healthy(skills=[])
    assert make_hollow_rejector()(missing_skills) is None
    message = make_hollow_rejector(_parsed())(missing_skills)
    assert message is not None and "skills" in message
    assert make_hollow_rejector(_parsed())(_healthy()) is None


def test_master_guard_keeps_stored_sections_for_a_degraded_tree() -> None:
    existing = {
        "skills": ["Python"],
        "summary": "Stored summary.",
        "experience": [{"company": "Acme", "bullets": ["Built."]}],
        "education": [{"degree": "BS"}],
        "projects": [{"name": "P"}],
    }
    degraded = {"skills": [], "summary": "", "experience": [], "education": [], "projects": []}
    merged = preserve_master_sections(degraded, existing)
    assert merged["skills"] == ["Python"]
    assert merged["summary"] == "Stored summary."
    assert merged["experience"] == existing["experience"]
    assert merged["education"] == existing["education"]
    assert merged["projects"] == existing["projects"]
    assert degraded["skills"] == []


def test_master_guard_honors_deliberate_empties_when_experience_is_real() -> None:
    existing = {"skills": ["Python"], "summary": "Stored summary."}
    edit = {
        "skills": [],
        "summary": "",
        "experience": [{"company": "Acme", "bullets": ["Built."]}],
    }
    assert preserve_master_sections(edit, existing) == edit


def test_master_guard_without_stored_resume_is_a_no_op() -> None:
    incoming = {"skills": [], "experience": []}
    assert preserve_master_sections(incoming, None) == incoming
    assert preserve_master_sections(incoming, {}) == incoming


def test_empty_section_in_a_healthy_prior_is_a_deliberate_deletion() -> None:
    prior = _healthy(skills=[], summary="", education=[], projects=[])
    out = enforce_resume_invariants(
        _healthy(skills=[], summary="", education=[], projects=[]),
        resume_parsed=_parsed(),
        prior_output=prior,
    )
    assert out.skills == []
    assert out.summary == ""
    assert out.education == []
    assert out.projects == []


def test_empty_section_in_a_hollow_prior_still_restores_from_parsed() -> None:
    hollow_prior = _healthy(skills=[], experience=[])
    out = enforce_resume_invariants(
        _healthy(skills=[]), resume_parsed=_parsed(), prior_output=hollow_prior
    )
    assert out.skills == ["Python", "FastAPI", "Postgres"]


def test_restored_projects_do_not_gain_synthesized_metadata() -> None:
    out = enforce_resume_invariants(
        _healthy(projects=[]), resume_parsed=_parsed(), prior_output=None
    )
    assert "relevant_to_jd" not in out.projects[0]


def test_restored_projects_are_deep_copies_of_the_prior() -> None:
    prior = _healthy(projects=[{"name": "P", "bullets": ["one"]}])
    snapshot = prior.model_dump()
    out = enforce_resume_invariants(
        _healthy(projects=[]), resume_parsed=None, prior_output=prior
    )
    out.projects[0]["bullets"].append("mutation")
    assert prior.model_dump() == snapshot


def test_company_names_with_braces_do_not_break_role_notes() -> None:
    current = _healthy(
        experience=[TailoredExperienceEntry(company="{Acme}", bullets=[])]
    )
    parsed = _parsed(
        experience=[
            ExperienceEntry(company="{Acme}", title="Engineer", bullets=["Built."])
        ]
    )
    out = enforce_resume_invariants(current, resume_parsed=parsed, prior_output=None)
    assert out.experience[0].bullets == ["Built."]
    assert any("{Acme}" in n for n in out.rewrite_notes)


def test_master_guard_treats_whitespace_summary_as_blank() -> None:
    existing = {"summary": "Stored.", "experience": [{"bullets": ["Built."]}]}
    merged = preserve_master_sections({"summary": "  ", "experience": []}, existing)
    assert merged["summary"] == "Stored."


def test_master_guard_honors_empties_when_stored_resume_has_no_experience() -> None:
    existing = {"skills": ["Python"], "experience": []}
    incoming = {"skills": [], "experience": []}
    assert preserve_master_sections(incoming, existing) == incoming


def test_master_guard_also_protects_contact_and_certifications() -> None:
    existing = {
        "contact": {"name": "A"},
        "certifications": ["AWS"],
        "experience": [{"bullets": ["Built."]}],
    }
    merged = preserve_master_sections(
        {"contact": {}, "certifications": [], "experience": []}, existing
    )
    assert merged["contact"] == {"name": "A"}
    assert merged["certifications"] == ["AWS"]


def test_postprocess_restores_education_and_projects_without_jd_flag() -> None:
    ctx = TruthfulnessContext(resume_parsed=_parsed())
    out = postprocess_tailored_output(
        _healthy(education=[], projects=[]), None, truthfulness=ctx
    )
    assert out.education[0].institution == "State U"
    assert out.projects[0]["name"] == "Side Project"
    assert "relevant_to_jd" not in out.projects[0]


def test_postprocess_respects_deleted_education_and_projects_in_healthy_prior() -> None:
    prior = _healthy(education=[], projects=[])
    ctx = TruthfulnessContext(resume_parsed=_parsed(), prior_output=prior)
    out = postprocess_tailored_output(
        _healthy(education=[], projects=[]), None, truthfulness=ctx
    )
    assert out.education == []
    assert out.projects == []
