"""Phase 1b requirement scoring and brick provenance."""

from __future__ import annotations

import pytest

from app.agent.phase3_postprocess import attach_source_brick_provenance
from app.models.rewrite import TailoredExperienceEntry, TailoredResumeOutput
from app.services.master_resume.embedding import set_fake_embedder
from app.services.retrieval.requirement_scoring import (
    apply_requirement_scoring,
    exact_term_boost,
)
from app.services.retrieval.retrieval_service import RetrievalResult, SelectedChunk
from tests.retrieval.fake_embedder import deterministic_embed


@pytest.fixture(autouse=True)
def _fake_embedder():
    set_fake_embedder(deterministic_embed)
    yield
    set_fake_embedder(None)


def test_exact_term_boost_requires_two_significant_tokens() -> None:
    req = "Proficient in Python and Kubernetes"
    assert exact_term_boost(req, "Built Python services on Kubernetes") > 0
    assert exact_term_boost(req, "Python only") == 0.0


@pytest.mark.asyncio
async def test_apply_requirement_scoring_boosts_matching_chunk() -> None:
    req = "Experience with Python and distributed systems"
    chunk_a = SelectedChunk(
        chunk_id="a",
        section="experience",
        score=0.5,
        tokens=10,
        content="Led Python microservices for distributed systems at scale.",
        metadata={},
    )
    chunk_b = SelectedChunk(
        chunk_id="b",
        section="experience",
        score=0.9,
        tokens=10,
        content="Managed vendor contracts and procurement.",
        metadata={},
    )
    base = RetrievalResult(selected=[chunk_a, chunk_b], meta={"embedding_model": "test-model"})
    scored = await apply_requirement_scoring(
        base, [req], embedding_model="text-embedding-3-small"
    )
    by_id = {c.chunk_id: c for c in scored.selected}
    assert by_id["a"].score > chunk_a.score
    assert "phase1b_requirement_scoring" in scored.meta


def test_attach_source_brick_provenance_maps_bullets() -> None:
    chunks = [
        SelectedChunk(
            chunk_id="brick-1",
            section="experience",
            score=0.8,
            tokens=5,
            content="Optimized Python gRPC services and Redis caching.",
            metadata={},
        )
    ]
    output = TailoredResumeOutput(
        experience=[
            TailoredExperienceEntry(
                company="Acme",
                bullets=["Optimized Python gRPC services and Redis caching."],
            )
        ]
    )
    updated = attach_source_brick_provenance(output, chunks)
    assert updated.source_brick_ids == ["brick-1"]
