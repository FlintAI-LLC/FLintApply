"""PATCH /tailored save path returns 422 field_errors for blocking linter rules."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.rewrite import TailoredExperienceEntry, TailoredResumeOutput
from app.services.session_store import (
    create_session,
    reset_redis_keys_for_tests,
    update_session,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def _clean_sessions() -> None:
    await reset_redis_keys_for_tests()


async def test_patch_tailored_rejects_trailing_truncation_with_field_errors() -> None:
    session = await create_session()
    session.phase3_output = TailoredResumeOutput(
        summary="Engineer",
        experience=[
            TailoredExperienceEntry(
                title="Engineer",
                company="Acme",
                dates="2020",
                bullets=["Owned APIs and improved latency for core services by 10–"],
            ),
        ],
    )
    await update_session(session)

    payload = session.phase3_output.model_dump()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.patch(
            f"/api/sessions/{session.session_id}/tailored",
            json={"tailored_output": payload},
        )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "field_errors" in detail
    rules = {item["rule"] for item in detail["field_errors"]}
    assert "trailing_truncation" in rules
    bullet_errors = [e for e in detail["field_errors"] if e["field"].startswith("bullets[")]
    assert any(e["field"] == "bullets[0]" for e in bullet_errors)
