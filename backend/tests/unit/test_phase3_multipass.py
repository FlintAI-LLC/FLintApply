"""Unit tests for multi-pass composition helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.agent.brief import SectionBrief, TailoringBrief
from app.agent.phase3_multipass import (
    AnchoredEdit,
    apply_anchored_edits,
    build_protected_tokens,
    bullet_id_for,
    run_section_composition,
)
from app.config import settings
from app.models.rewrite import TailoredExperienceEntry, TailoredResumeOutput


def test_build_protected_tokens_percent_and_keyword() -> None:
    output = TailoredResumeOutput(
        experience=[
            TailoredExperienceEntry(
                company="Acme",
                bullets=["Reduced latency by 40% using Kubernetes"],
            )
        ]
    )
    protected = build_protected_tokens(output, ["Kubernetes"])
    bid = bullet_id_for("experience", 0, 0)
    tokens = protected[bid]
    assert any("40%" in t for t in tokens)
    assert "Kubernetes" in tokens


def test_merge_discards_edit_removing_protected_token() -> None:
    bid = bullet_id_for("experience", 0, 0)
    original = "Reduced latency by 40% using Kubernetes"
    output = TailoredResumeOutput(
        experience=[TailoredExperienceEntry(company="Acme", bullets=[original])]
    )
    protected = build_protected_tokens(output, ["Kubernetes"])
    edits = [AnchoredEdit(bullet_id=bid, replacement="Improved systems performance.")]
    merged, modified = apply_anchored_edits(output, edits, protected)
    assert modified == set()
    assert merged.experience[0].bullets[0] == original


def test_merge_applies_valid_edit() -> None:
    bid = bullet_id_for("experience", 0, 0)
    original = "Reduced latency by 40% using Kubernetes"
    output = TailoredResumeOutput(
        experience=[TailoredExperienceEntry(company="Acme", bullets=[original])]
    )
    protected = build_protected_tokens(output, ["Kubernetes"])
    replacement = "Cut latency by 40% while operating Kubernetes clusters."
    edits = [AnchoredEdit(bullet_id=bid, replacement=replacement)]
    merged, modified = apply_anchored_edits(output, edits, protected)
    assert modified == {bid}
    assert merged.experience[0].bullets[0] == replacement


def test_merge_discards_unknown_bullet_id() -> None:
    output = TailoredResumeOutput(
        experience=[TailoredExperienceEntry(company="Acme", bullets=["Built APIs"])]
    )
    edits = [AnchoredEdit(bullet_id="experience:9:0", replacement="Hacked")]
    merged, modified = apply_anchored_edits(output, edits, {})
    assert modified == set()
    assert merged.experience[0].bullets[0] == "Built APIs"


def test_enable_multipass_flag_default_off() -> None:
    assert settings.ENABLE_MULTIPASS_COMPOSITION is False


@pytest.mark.asyncio
async def test_run_skips_multipass_when_flag_disabled(monkeypatch) -> None:
    import asyncio
    from unittest.mock import Mock

    from app.agent.phase3_rewrite import run
    from app.models.audit import AuditOutput, KeywordCoverage
    from app.models.keywords import KeywordExtractionOutput
    from app.models.session import PhaseStatus
    from app.services.session_store import create_session, update_session

    multipass_calls = 0

    async def forbidden_multipass(*_args, **_kwargs):
        multipass_calls += 1
        return TailoredResumeOutput(summary="multipass")

    complete_calls = 0

    async def fake_phase3_llm(*_args, **_kwargs):
        nonlocal complete_calls
        complete_calls += 1
        return TailoredResumeOutput(summary="monolithic")

    monkeypatch.setattr(
        "app.agent.phase3_multipass.run_multipass_composition",
        forbidden_multipass,
    )
    monkeypatch.setattr(
        "app.agent.phase3_rewrite._complete_phase3_llm",
        fake_phase3_llm,
    )
    monkeypatch.setattr(
        "app.agent.phase3_rewrite._ensure_company_intel",
        AsyncMock(return_value=None),
    )
    llm = Mock(model_name="gpt-4o", provider_name="openai")

    session = await create_session()
    session.phase1_output = KeywordExtractionOutput()
    session.phase2_output = AuditOutput(
        keyword_coverage=KeywordCoverage(present=["Python"]),
        overall_score=70,
        summary="Audit ok",
    )
    session.phase1_status = PhaseStatus.done
    session.phase2_status = PhaseStatus.done
    session.jd_raw = "Python backend role"
    session.resume_raw = "Jane Doe\nPython engineer with eight years of experience."
    await update_session(session)

    monkeypatch.setattr(settings, "ENABLE_MULTIPASS_COMPOSITION", False)
    await run(session, llm, asyncio.Queue())
    assert multipass_calls == 0
    assert complete_calls >= 1


@pytest.mark.asyncio
async def test_section_composition_fallback_to_bricks() -> None:
    from app.services.retrieval.retrieval_service import SelectedChunk

    section = SectionBrief(
        section_type="experience",
        chunks=[
            SelectedChunk(
                chunk_id="c1",
                section="experience",
                content="Brick text from upload.",
                score=0.9,
                tokens=10,
                metadata={},
            )
        ],
        must_place_keywords=[],
        bullet_cap=3,
        always_include=True,
    )
    llm = AsyncMock()
    with patch(
        "app.agent.phase3_multipass.complete_structured",
        side_effect=RuntimeError("llm down"),
    ):
        bullets = await run_section_composition(section, "jd", "ctx", llm)
    assert bullets == ["Brick text from upload."]
