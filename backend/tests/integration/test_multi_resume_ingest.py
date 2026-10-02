"""Merge ingest behavior for POST /api/profile/resume (merge=True)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.master_resume import crud as master_crud
from app.services.master_resume.embedding import set_fake_embedder
from tests.conftest import verify_user_email
from tests.integration.test_profile_api import REGISTER_PAYLOAD, SAMPLE_TEXT
from tests.retrieval.fake_embedder import deterministic_embed

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _install_fake_embedder():
    set_fake_embedder(deterministic_embed)
    try:
        yield
    finally:
        set_fake_embedder(None)


async def _register_and_login(
    client: AsyncClient, db_session: AsyncSession, email: str
) -> str:
    payload = {**REGISTER_PAYLOAD, "email": email}
    r = await client.post("/api/auth/register", json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    await verify_user_email(db_session, uuid.UUID(body["user"]["id"]))
    return body["access_token"]


def _unique_resume(seed: int) -> str:
    return (
        f"Resume upload #{seed}: senior backend engineer with Python, FastAPI, "
        f"PostgreSQL, Redis, Kubernetes, observability, and CI/CD across product "
        f"teams. Unique marker {seed:04d} ensures distinct chunks for merge ingest "
        f"and satisfies the minimum resume length gate for profile uploads."
    )


async def _post_resume(
    client: AsyncClient, headers: dict, text: str, *, parsed: dict | None = None
) -> dict:
    with patch("app.routers.profile._structure_with_llm", new_callable=AsyncMock) as mock:
        mock.return_value = parsed or {}
        r = await client.post(
            "/api/profile/resume",
            headers=headers,
            data={"text": text},
        )
    assert r.status_code == 201, r.text
    return r.json()


async def test_identical_merge_adds_zero_chunks(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    access = await _register_and_login(
        app_client, db_session, "merge-identical@example.com"
    )
    headers = {"Authorization": f"Bearer {access}"}
    first = await _post_resume(app_client, headers, SAMPLE_TEXT)
    assert first["chunk_count"] >= 1

    second = await _post_resume(app_client, headers, SAMPLE_TEXT)
    assert second["chunks"] == []
    assert second["chunk_count"] == first["chunk_count"]


async def test_different_merge_adds_chunks(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    access = await _register_and_login(
        app_client, db_session, "merge-diff@example.com"
    )
    headers = {"Authorization": f"Bearer {access}"}
    first = await _post_resume(app_client, headers, SAMPLE_TEXT)
    before = first["chunk_count"]

    other = _unique_resume(99)
    second = await _post_resume(app_client, headers, other)
    assert len(second["chunks"]) >= 1
    assert second["chunk_count"] > before


async def test_sixth_source_doc_returns_upload_limit(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    email = "merge-limit@example.com"
    reg = await app_client.post(
        "/api/auth/register", json={**REGISTER_PAYLOAD, "email": email}
    )
    assert reg.status_code == 201, reg.text
    user_id = uuid.UUID(reg.json()["user"]["id"])
    await verify_user_email(db_session, user_id)
    access = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {access}"}

    for i in range(5):
        token_blob = " ".join(f"kw{i}{j}" for j in range(24))
        parsed = {
            "experience": [
                {
                    "company": f"Employer{i}",
                    "title": "Engineer",
                    "bullets": [
                        f"Scope {i}: {token_blob} — shipped systems with distinct ownership."
                    ],
                }
            ],
        }
        await _post_resume(app_client, headers, _unique_resume(i), parsed=parsed)
        docs = await master_crud.count_live_source_docs(db_session, user_id=user_id)
        assert docs == i + 1

    with patch("app.routers.profile._structure_with_llm", new_callable=AsyncMock) as mock:
        mock.return_value = {
            "experience": [
                {
                    "company": "Employer5",
                    "title": "Engineer",
                    "bullets": [
                        "Delivered product #05 with Python, FastAPI, PostgreSQL, "
                        "and Kubernetes for measurable reliability and scale."
                    ],
                }
            ],
        }
        r = await app_client.post(
            "/api/profile/resume",
            headers=headers,
            data={"text": _unique_resume(5)},
        )
    assert r.status_code == 422, r.text
    detail = r.json()["detail"]
    assert detail["error"] == "upload_limit_reached"


async def test_role_conflicts_non_blocking(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    access = await _register_and_login(
        app_client, db_session, "merge-conflict@example.com"
    )
    headers = {"Authorization": f"Bearer {access}"}
    bullet = (
        "Designed distributed payment services with Python, FastAPI, and PostgreSQL "
        "for high-volume transaction processing and operational reliability."
    )
    parsed_a = {
        "experience": [
            {
                "company": "Acme",
                "title": "Senior Engineer",
                "bullets": [bullet],
            }
        ],
    }
    first = await _post_resume(
        app_client, headers, _unique_resume(10), parsed=parsed_a
    )
    assert first["chunk_count"] >= 1

    parsed_b = {
        "experience": [
            {
                "company": "Acme",
                "title": "Staff Engineer",
                "bullets": [
                    "Owned staff-level architecture for payments platform scaling, "
                    "mentoring engineers and driving reliability improvements."
                ],
            }
        ],
    }
    second = await _post_resume(
        app_client, headers, _unique_resume(11), parsed=parsed_b
    )
    conflicts = second.get("conflicts") or []
    assert conflicts
    assert conflicts[0]["company"] == "Acme"
    assert second["chunk_count"] >= first["chunk_count"]
