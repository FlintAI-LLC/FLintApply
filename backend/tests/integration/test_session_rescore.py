"""POST /api/sessions/{id}/rescore — free deterministic ATS refresh."""

from __future__ import annotations

from contextlib import ExitStack
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

from app.models.keywords import Keyword, KeywordExtractionOutput
from app.models.qa import QAOutput
from app.models.rewrite import TailoredExperienceEntry, TailoredResumeOutput
from app.models.session import PhaseStatus
from app.services.session_store import create_session, get_session, update_session

pytestmark = pytest.mark.integration

STALE_SCORE = 40

# Every place the app can reach an LLM or charge quota; none may fire on rescore.
_FORBIDDEN_CALL_SITES = (
    "app.llm.structured.complete_structured",
    "app.agent.phase4_qa.complete_structured",
    "app.agent.phase4_narrative.complete_structured",
    "app.llm.factory.get_llm_client_for_step",
    "app.routers.sessions.get_llm_client_for_step",
    "app.services.billing.quota.check_and_increment_quota",
    "app.routers.phases.check_and_increment_quota",
)


def _keywords() -> KeywordExtractionOutput:
    return KeywordExtractionOutput(
        must_have_keywords=[
            Keyword(
                term="Kubernetes",
                source_sentence="Kubernetes required.",
                category="tool",
                tier="must_have",
                reason="core",
            )
        ]
    )


def _tailored() -> TailoredResumeOutput:
    return TailoredResumeOutput(
        contact={"name": "Jane Doe", "email": "jane@example.com"},
        summary="Senior engineer running Kubernetes platforms.",
        skills=["Platform: Kubernetes"],
        experience=[
            TailoredExperienceEntry(
                title="Engineer",
                company="Acme",
                dates="2022-2025",
                bullets=["Ran Kubernetes clusters serving 1M users"],
            )
        ],
        education=[],
        projects=[],
        certifications=[],
    )


async def scored_session(*, stale: bool):
    session = await create_session()
    session.phase1_status = PhaseStatus.done
    session.phase1_output = _keywords()
    session.phase3_status = PhaseStatus.done
    session.phase3_output = _tailored()
    session.phase4_status = PhaseStatus.done
    session.phase4_output = QAOutput(
        ats_score=STALE_SCORE, score_ceiling=90, blocking_issues=[]
    )
    if stale:
        session.phase4_stale_since = datetime.now(timezone.utc)
    await update_session(session)
    return session


def forbid_llm_and_quota(stack: ExitStack) -> list[MagicMock]:
    """Patch every LLM and quota entry point with a spy that fails if awaited."""
    spies: list[MagicMock] = []
    for target in _FORBIDDEN_CALL_SITES:
        spy = stack.enter_context(patch(target, new_callable=AsyncMock))
        spies.append(spy)
    return spies


@pytest.mark.asyncio
async def test_stale_session_is_rescored_without_llm_or_quota(
    app_client: AsyncClient,
) -> None:
    session = await scored_session(stale=True)

    with ExitStack() as stack:
        spies = forbid_llm_and_quota(stack)
        response = await app_client.post(f"/api/sessions/{session.session_id}/rescore")

    assert response.status_code == 200
    for spy in spies:
        spy.assert_not_called()

    body = response.json()
    assert body["ats_score"] > STALE_SCORE
    assert body["rank_label"]
    assert body["headline"]
    assert body["score_axes"]
    assert body["category_summaries"]
    assert body["guidance"]["recoverable_ceiling"] >= body["ats_score"]

    stored = await get_session(session.session_id)
    assert stored is not None
    assert stored.phase4_stale_since is None
    assert stored.phase4_output.ats_score == body["ats_score"]


@pytest.mark.asyncio
async def test_unchanged_resume_returns_stored_score(app_client: AsyncClient) -> None:
    session = await scored_session(stale=False)

    with ExitStack() as stack:
        spies = forbid_llm_and_quota(stack)
        response = await app_client.post(f"/api/sessions/{session.session_id}/rescore")

    assert response.status_code == 200
    assert response.json()["ats_score"] == STALE_SCORE
    for spy in spies:
        spy.assert_not_called()


@pytest.mark.asyncio
async def test_rescore_requires_a_prior_score(app_client: AsyncClient) -> None:
    session = await create_session()

    response = await app_client.post(f"/api/sessions/{session.session_id}/rescore")

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_rescore_requires_a_tailored_resume(app_client: AsyncClient) -> None:
    session = await scored_session(stale=True)
    session.phase3_output = None
    await update_session(session)

    response = await app_client.post(f"/api/sessions/{session.session_id}/rescore")

    assert response.status_code == 409


@pytest.mark.asyncio
async def test_unknown_session_is_404(app_client: AsyncClient) -> None:
    response = await app_client.post("/api/sessions/does-not-exist/rescore")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_scoring_failure_keeps_stale_flag_and_prior_score(
    app_client: AsyncClient,
) -> None:
    session = await scored_session(stale=True)

    with patch(
        "app.routers.sessions.rescore_qa_output", side_effect=RuntimeError("boom")
    ):
        with pytest.raises(RuntimeError):
            await app_client.post(f"/api/sessions/{session.session_id}/rescore")

    stored = await get_session(session.session_id)
    assert stored is not None
    assert stored.phase4_stale_since is not None
    assert stored.phase4_output.ats_score == STALE_SCORE


@pytest.mark.asyncio
async def test_edit_saved_during_scoring_is_not_overwritten(
    app_client: AsyncClient,
) -> None:
    session = await scored_session(stale=True)
    edited_copy = await get_session(session.session_id)
    assert edited_copy is not None
    edited_copy.phase3_output = _tailored().model_copy(
        update={"summary": "Edited while the rescore was running."}
    )

    with patch(
        "app.routers.sessions.get_session",
        new=AsyncMock(return_value=edited_copy),
    ):
        response = await app_client.post(f"/api/sessions/{session.session_id}/rescore")

    assert response.status_code == 409
    stored = await get_session(session.session_id)
    assert stored is not None
    assert stored.phase4_stale_since is not None
    assert stored.phase4_output.ats_score == STALE_SCORE
