"""HTTP tests for tailored-editor add/move on PATCH /resume/tailored."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.rewrite import TailoredEducationEntry, TailoredExperienceEntry, TailoredResumeOutput
from app.services.session_store import (
    create_session,
    get_session,
    reset_redis_keys_for_tests,
    update_session,
)


pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _clean_sessions() -> None:
    await reset_redis_keys_for_tests()


async def _client() -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def _session_with_tailored() -> str:
    session = await create_session()
    session.phase3_output = TailoredResumeOutput(
        summary="Engineer",
        experience=[
            TailoredExperienceEntry(title="A", company="Acme", dates="2020", bullets=["Did A."]),
            TailoredExperienceEntry(title="B", company="Beta", dates="2021", bullets=["Did B."]),
        ],
        education=[
            TailoredEducationEntry(degree="BS", institution="State U", year="2018", bullets=[]),
            TailoredEducationEntry(degree="MS", institution="Tech U", year="2020", bullets=[]),
        ],
    )
    await update_session(session)
    return session.session_id


async def test_snapshot_only_appends_version_without_mutating_resume() -> None:
    session_id = await _session_with_tailored()
    async with await _client() as client:
        before = await get_session(session_id)
        assert before is not None
        assert before.phase3_output is not None
        prior_summary = before.phase3_output.summary

        response = await client.patch(
            f"/api/sessions/{session_id}/resume/tailored",
            json={
                "snapshot_only": True,
                "snapshot_label": "Before re-tailor from scratch",
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["version"] == 1

        after = await get_session(session_id)
        assert after is not None
        assert after.phase3_output is not None
        assert after.phase3_output.summary == prior_summary
        assert len(after.phase3_versions) == 1
        snap = after.phase3_versions[0]
        assert snap.label == "Before re-tailor from scratch"
        assert snap.output.summary == prior_summary
        assert snap.output.experience[0].company == "Acme"

        ignored = await client.patch(
            f"/api/sessions/{session_id}/resume/tailored",
            json={
                "snapshot_only": True,
                "snapshot_label": "Before re-tailor from scratch",
                "section_id": "summary",
                "content": "Mutated summary",
            },
        )
        assert ignored.status_code == 200
        after_ignored = await get_session(session_id)
        assert after_ignored is not None
        assert after_ignored.phase3_output.summary == prior_summary
        assert snap.output.summary == prior_summary


async def test_patch_adds_and_moves_experience() -> None:
    session_id = await _session_with_tailored()
    async with await _client() as client:
        add = await client.patch(
            f"/api/sessions/{session_id}/resume/tailored",
            json={
                "section": "experience",
                "add_experience": {
                    "title": "Founder",
                    "company": "IdMe24",
                    "dates": "2024 – Present",
                    "bullets": ["Built identity platform."],
                },
            },
        )
        assert add.status_code == 200, add.text

        moved = await client.patch(
            f"/api/sessions/{session_id}/resume/tailored",
            json={
                "section": "experience",
                "move_index": 2,
                "move_direction": "up",
            },
        )
        assert moved.status_code == 200, moved.text

        oob = await client.patch(
            f"/api/sessions/{session_id}/resume/tailored",
            json={
                "section": "experience",
                "move_index": 0,
                "move_direction": "up",
            },
        )
        assert oob.status_code == 200, oob.text

    session = await get_session(session_id)
    assert session is not None
    companies = [entry.company for entry in session.phase3_output.experience]
    assert companies == ["Acme", "IdMe24", "Beta"]


async def test_patch_adds_and_moves_education() -> None:
    session_id = await _session_with_tailored()
    async with await _client() as client:
        add = await client.patch(
            f"/api/sessions/{session_id}/resume/tailored",
            json={
                "section": "education",
                "add_education": {
                    "degree": "PhD",
                    "institution": "Research U",
                    "year": "2024",
                    "bullets": ["Thesis."],
                },
            },
        )
        assert add.status_code == 200, add.text

        down = await client.patch(
            f"/api/sessions/{session_id}/resume/tailored",
            json={
                "section": "education",
                "move_index": 0,
                "move_direction": "down",
            },
        )
        assert down.status_code == 200, down.text

        oob = await client.patch(
            f"/api/sessions/{session_id}/resume/tailored",
            json={
                "section": "education",
                "move_index": 99,
                "move_direction": "down",
            },
        )
        assert oob.status_code == 200, oob.text

    session = await get_session(session_id)
    assert session is not None
    schools = [entry.institution for entry in session.phase3_output.education]
    assert schools == ["Tech U", "State U", "Research U"]
