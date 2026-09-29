"""Unit tests for evidence-gated must-have keyword placement."""

from __future__ import annotations

import re

from app.agent.phase3_keyword_placement import place_evidenced_keywords
from app.agent.phase3_postprocess import (
    flatten_skill_terms,
    normalize_skills_to_categories,
    postprocess_tailored_output,
)
from app.agent.phase3_truthfulness import TruthfulnessContext
from app.agent.phase4_score import _axis_action_verbs
from app.models.resume import ExperienceEntry, ParsedResume
from app.models.rewrite import TailoredExperienceEntry, TailoredResumeOutput
from app.models.session import ApprovedMetric

NOTE_PREFIX = "Keywords not added (no evidence in your resume): "


def _output(**overrides: object) -> TailoredResumeOutput:
    base: dict[str, object] = {
        "summary": "Backend engineer.",
        "skills": ["Languages: Python"],
        "experience": [
            TailoredExperienceEntry(
                title="Engineer",
                company="Acme",
                bullets=["Led migration of services.", "Built payment APIs."],
            )
        ],
    }
    base.update(overrides)
    return TailoredResumeOutput(**base)  # type: ignore[arg-type]


def _ctx(**overrides: object) -> TruthfulnessContext:
    base: dict[str, object] = {
        "resume_raw": "Ran Kubernetes clusters and Docker builds on AWS.",
    }
    base.update(overrides)
    return TruthfulnessContext(**base)  # type: ignore[arg-type]


def _bullets(output: TailoredResumeOutput) -> list[str]:
    return [b for e in output.experience for b in e.bullets]


def test_evidenced_missing_keyword_is_added_to_skills_only() -> None:
    original = _output()
    out = place_evidenced_keywords(original, ["Kubernetes"], _ctx())
    assert "kubernetes" in {t.lower() for t in flatten_skill_terms(out.skills)}
    assert "python" in {t.lower() for t in flatten_skill_terms(out.skills)}
    assert _bullets(out) == _bullets(original)
    assert out.summary == original.summary


def test_bullets_are_never_prefixed_or_extended() -> None:
    out = place_evidenced_keywords(
        _output(), ["Kubernetes", "Docker", "AWS"], _ctx()
    )
    for bullet in _bullets(out):
        assert not re.match(r"^\w+:\s", bullet)
        assert "Kubernetes" not in bullet
    assert _bullets(out) == ["Led migration of services.", "Built payment APIs."]


def test_unevidenced_keyword_is_skipped_with_a_single_note() -> None:
    out = place_evidenced_keywords(
        _output(), ["Terraform", "Ansible", "Kubernetes"], _ctx()
    )
    terms = {t.lower() for t in flatten_skill_terms(out.skills)}
    assert "terraform" not in terms and "ansible" not in terms
    notes = [n for n in out.rewrite_notes if n.startswith(NOTE_PREFIX)]
    assert len(notes) == 1
    assert "Terraform" in notes[0] and "Ansible" in notes[0]
    assert "Kubernetes" not in notes[0]


def test_keywords_containing_digits_are_rejected_even_with_evidence() -> None:
    ctx = _ctx(resume_raw="Migrated to Python3 and managed 99.9 uptime.")
    out = place_evidenced_keywords(_output(), ["Python3", "99.9"], ctx)
    assert out.skills == _output().skills
    assert not any(n.startswith(NOTE_PREFIX) for n in out.rewrite_notes)


def test_keyword_already_in_skills_is_a_no_op() -> None:
    original = _output()
    assert place_evidenced_keywords(original, ["python"], _ctx()) == original


def test_evidence_can_come_from_each_source_kind() -> None:
    parsed = ParsedResume(
        experience=[ExperienceEntry(company="Acme", bullets=["Used Redis caches."])]
    )
    prior = _output(summary="Worked with Kafka streams.")
    ctx = TruthfulnessContext(
        resume_raw="",
        resume_parsed=parsed,
        prior_output=prior,
        user_claimed_keywords=["Terraform"],
        approved_metrics=[
            ApprovedMetric(scope="Acme", metric="Cut latency 30% with Elasticsearch")
        ],
    )
    out = place_evidenced_keywords(
        _output(), ["Redis", "Kafka", "Terraform", "Elasticsearch", "Ansible"], ctx
    )
    terms = {t.lower() for t in flatten_skill_terms(out.skills)}
    assert {"redis", "kafka", "terraform", "elasticsearch"} <= terms
    assert "ansible" not in terms


def test_evidence_match_respects_word_boundaries() -> None:
    ctx = _ctx(resume_raw="Worked on javascript tooling and gopher tools.")
    out = place_evidenced_keywords(_output(), ["Java", "Go"], ctx)
    terms = {t.lower() for t in flatten_skill_terms(out.skills)}
    assert "java" not in terms and "go" not in terms


def test_placement_is_idempotent_across_two_runs() -> None:
    keywords = ["Kubernetes", "Docker", "Terraform"]
    original = _output()
    once = place_evidenced_keywords(original, keywords, _ctx())
    once_terms = {t.lower() for t in flatten_skill_terms(once.skills)}
    assert {"kubernetes", "docker"} <= once_terms
    assert "terraform" not in once_terms
    assert _bullets(once) == _bullets(original)
    twice = place_evidenced_keywords(once, keywords, _ctx())
    thrice = place_evidenced_keywords(twice, keywords, _ctx())
    assert twice == once
    assert thrice == once
    assert twice.skills == once.skills
    assert sum(n.startswith(NOTE_PREFIX) for n in thrice.rewrite_notes) == 1


def test_no_keywords_returns_output_unchanged() -> None:
    original = _output()
    assert place_evidenced_keywords(original, None, _ctx()) is original
    assert place_evidenced_keywords(original, [" ", ""], _ctx()) is original


def test_postprocess_places_keywords_but_skips_when_disabled() -> None:
    ctx = _ctx()
    placed = postprocess_tailored_output(
        _output(), ["Kubernetes"], truthfulness=ctx
    )
    assert "kubernetes" in {t.lower() for t in flatten_skill_terms(placed.skills)}
    skipped = postprocess_tailored_output(
        _output(), ["Kubernetes"], truthfulness=ctx, place_keywords=False
    )
    assert "kubernetes" not in {t.lower() for t in flatten_skill_terms(skipped.skills)}


def test_prefixed_bullet_scores_zero_on_action_verbs_but_placed_keyword_does_not() -> None:
    prefixed = _output(
        experience=[
            TailoredExperienceEntry(
                company="Acme", bullets=["Kubernetes: Led migration of services."]
            )
        ]
    )
    assert _axis_action_verbs(_bullets(prefixed), prefixed).score == 0

    placed = place_evidenced_keywords(
        _output(
            experience=[
                TailoredExperienceEntry(
                    company="Acme", bullets=["Led migration of services."]
                )
            ]
        ),
        ["Kubernetes"],
        _ctx(),
    )
    assert "kubernetes" in {t.lower() for t in flatten_skill_terms(placed.skills)}
    assert _bullets(placed)[0].split()[0].lower() == "led"
    axis = _axis_action_verbs(_bullets(placed), placed)
    assert axis.score == axis.max_score


def test_empty_parsed_resume_does_not_evidence_schema_field_names() -> None:
    ctx = _ctx(resume_raw="Built payment APIs at Acme.", resume_parsed=ParsedResume())
    out = place_evidenced_keywords(
        _output(), ["GitHub", "LinkedIn", "Education", "Experience"], ctx
    )
    assert out.skills == _output().skills


def test_prior_run_notes_do_not_launder_unevidenced_keywords() -> None:
    ctx = _ctx()
    first = place_evidenced_keywords(_output(), ["Terraform", "Kubernetes"], ctx)
    assert any(n.startswith(NOTE_PREFIX) for n in first.rewrite_notes)
    second_ctx = _ctx(prior_output=first)
    second = place_evidenced_keywords(_output(), ["Terraform", "Kubernetes"], second_ctx)
    terms = {t.lower() for t in flatten_skill_terms(second.skills)}
    assert "terraform" not in terms
    assert any("Terraform" in n for n in second.rewrite_notes)


def test_prior_keywords_injected_is_not_evidence() -> None:
    prior = _output(
        experience=[
            TailoredExperienceEntry(
                company="Acme",
                bullets=["Built APIs."],
                keywords_injected=["Terraform", "Ansible"],
            )
        ]
    )
    out = place_evidenced_keywords(_output(), ["Terraform", "Ansible"], _ctx(prior_output=prior))
    terms = {t.lower() for t in flatten_skill_terms(out.skills)}
    assert "terraform" not in terms and "ansible" not in terms


def test_current_output_text_is_not_evidence() -> None:
    original = _output(
        summary="Used Terraform daily.",
        experience=[
            TailoredExperienceEntry(company="Acme", bullets=["Led Terraform migrations."])
        ],
    )
    out = place_evidenced_keywords(original, ["Terraform"], _ctx())
    assert "terraform" not in {t.lower() for t in flatten_skill_terms(out.skills)}
    assert any(n.startswith(NOTE_PREFIX) and "Terraform" in n for n in out.rewrite_notes)


def test_keyword_in_summary_or_bullets_is_still_added_to_skills() -> None:
    original = _output(
        summary="Backend engineer using Kubernetes.",
        experience=[
            TailoredExperienceEntry(company="Acme", bullets=["Led Kubernetes migration."])
        ],
    )
    out = place_evidenced_keywords(original, ["Kubernetes"], _ctx())
    assert "kubernetes" in {t.lower() for t in flatten_skill_terms(out.skills)}
    assert out.summary == original.summary
    assert _bullets(out) == _bullets(original)


def test_regex_metacharacter_keywords_match_literally() -> None:
    placed = place_evidenced_keywords(
        _output(), ["C++", "Node.js"], _ctx(resume_raw="Production C++ and Node.js services.")
    )
    terms = {t.lower() for t in flatten_skill_terms(placed.skills)}
    assert {"c++", "node.js"} <= terms

    skipped = place_evidenced_keywords(
        _output(), ["C++", "Node.js"], _ctx(resume_raw="Wrote C modules on NodeXjs.")
    )
    skipped_terms = {t.lower() for t in flatten_skill_terms(skipped.skills)}
    assert "c++" not in skipped_terms and "node.js" not in skipped_terms


def test_evidence_match_is_case_insensitive() -> None:
    out = place_evidenced_keywords(
        _output(), ["Kubernetes"], _ctx(resume_raw="ran KUBERNETES clusters")
    )
    assert "kubernetes" in {t.lower() for t in flatten_skill_terms(out.skills)}


def test_evidenced_keyword_survives_eight_per_category_cap() -> None:
    devops8 = [
        "Kubernetes", "Docker", "Terraform", "Ansible",
        "Jenkins", "Helm", "CI/CD", "MLOps",
    ]
    original = _output(skills=normalize_skills_to_categories(["Python", *devops8]))
    out = place_evidenced_keywords(
        original, ["pipeline"], _ctx(resume_raw="Owned the release pipeline.")
    )
    terms = {t.lower() for t in flatten_skill_terms(out.skills)}
    assert "pipeline" in terms
    assert {t.lower() for t in devops8} <= terms


def test_evidenced_keyword_survives_five_category_cap() -> None:
    skills = normalize_skills_to_categories(["Python", "AWS", "Docker", "Kafka", "PyTorch"])
    out = place_evidenced_keywords(
        _output(skills=skills), ["OAuth"], _ctx(resume_raw="Implemented OAuth.")
    )
    assert "oauth" in {t.lower() for t in flatten_skill_terms(out.skills)}


def test_placing_a_keyword_does_not_evict_an_existing_category() -> None:
    skills = normalize_skills_to_categories(["Python", "AWS", "Docker", "Kafka", "OAuth"])
    out = place_evidenced_keywords(
        _output(skills=skills), ["PyTorch"], _ctx(resume_raw="Trained PyTorch models.")
    )
    terms = {t.lower() for t in flatten_skill_terms(out.skills)}
    assert {"pytorch", "oauth"} <= terms


def test_capped_placement_is_stable_across_runs() -> None:
    skills = normalize_skills_to_categories(["Python", "AWS", "Docker", "Kafka", "OAuth"])
    ctx = _ctx(resume_raw="Trained PyTorch models.")
    once = place_evidenced_keywords(_output(skills=skills), ["PyTorch"], ctx)
    assert place_evidenced_keywords(once, ["PyTorch"], ctx) == once


def test_oversized_and_control_character_keywords_are_ignored() -> None:
    hostile = ["x" * 500, "line\nbreak", "tab\tkey"]
    ctx = _ctx(resume_raw=" ".join(hostile))
    out = place_evidenced_keywords(_output(), hostile, ctx)
    assert out == _output()


def test_unevidenced_note_is_bounded() -> None:
    many = [f"Tool{chr(65 + i)}{chr(97 + i)}" for i in range(20)]
    out = place_evidenced_keywords(_output(), many, _ctx())
    note = next(n for n in out.rewrite_notes if n.startswith(NOTE_PREFIX))
    assert "(+10 more)" in note
    assert note.count(",") == 9
