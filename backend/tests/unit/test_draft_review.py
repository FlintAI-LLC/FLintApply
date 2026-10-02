"""Draft review service unit tests."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.agent.phase3_multipass import bullet_id_for
from app.models.rewrite import TailoredExperienceEntry, TailoredResumeOutput
from app.services.draft_review import build_draft_review, remove_bullet_from_output
from app.services.master_resume.embedding import set_fake_embedder
from tests.retrieval.fake_embedder import deterministic_embed


@pytest.fixture(autouse=True)
def _fake_embed():
    set_fake_embedder(deterministic_embed)
    try:
        yield
    finally:
        set_fake_embedder(None)


@pytest.mark.asyncio
async def test_draft_review_lists_bullets() -> None:
    output = TailoredResumeOutput(
        experience=[
            TailoredExperienceEntry(
                company="Acme",
                bullets=["Built APIs in Python"],
            )
        ],
        skills=["Python"],
    )
    review = await build_draft_review(
        output, jd_text="Python engineer", must_have=["Python"]
    )
    assert len(review["bullets"]) == 1
    assert review["bullets"][0]["section"] == "experience"


@pytest.mark.asyncio
async def test_duplicate_candidates_near_identical() -> None:
    text = "Led platform migration reducing latency by forty percent"
    output = TailoredResumeOutput(
        experience=[
            TailoredExperienceEntry(
                company="A",
                bullets=[text, text + "."],
            )
        ]
    )
    vec = [1.0, 0.0, 0.5]
    with patch(
        "app.services.draft_review.embed_texts",
        new=AsyncMock(return_value=[vec, vec]),
    ):
        review = await build_draft_review(output, jd_text="", must_have=[])
    assert review["duplicate_candidates"]


def test_remove_bullet_does_not_touch_brick_store() -> None:
    bid = bullet_id_for("experience", 0, 0)
    output = TailoredResumeOutput(
        experience=[
            TailoredExperienceEntry(
                company="Acme",
                bullets=["First bullet", "Second bullet"],
            )
        ]
    )
    updated = remove_bullet_from_output(output, bid)
    assert len(updated.experience[0].bullets) == 1
    assert updated.experience[0].bullets[0] == "Second bullet"
