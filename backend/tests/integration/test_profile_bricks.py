"""Brick CRUD at /api/profile/bricks."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.master_resume import MasterResumeChunk
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


async def _ensure_master_resume(client: AsyncClient, headers: dict) -> None:
    r = await client.post(
        "/api/profile/resume",
        headers=headers,
        data={"text": SAMPLE_TEXT},
    )
    assert r.status_code == 201, r.text


async def test_bricks_post_creates_chunk_with_embedding(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    access = await _register_and_login(
        app_client, db_session, "bricks-create@example.com"
    )
    headers = {"Authorization": f"Bearer {access}"}
    await _ensure_master_resume(app_client, headers)

    content = "Designed fault-tolerant payment APIs in Python and FastAPI."
    r = await app_client.post(
        "/api/profile/bricks",
        headers=headers,
        json={"section_type": "experience", "content": content},
    )
    assert r.status_code == 201, r.text
    brick = r.json()
    assert brick["content"] == content
    assert brick["token_count"] > 0

    row = (
        await db_session.execute(
            select(MasterResumeChunk).where(
                MasterResumeChunk.id == uuid.UUID(brick["id"])
            )
        )
    ).scalar_one()
    assert row.embedding is not None
    assert len(list(row.embedding)) > 0


async def test_bricks_get_scoped_to_current_user(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    access_a = await _register_and_login(
        app_client, db_session, "bricks-user-a@example.com"
    )
    headers_a = {"Authorization": f"Bearer {access_a}"}
    await _ensure_master_resume(app_client, headers_a)

    r = await app_client.post(
        "/api/profile/bricks",
        headers=headers_a,
        json={
            "section_type": "skills",
            "content": "Python, PostgreSQL, Redis, Kubernetes, FastAPI",
        },
    )
    assert r.status_code == 201
    brick_id_a = r.json()["id"]

    access_b = await _register_and_login(
        app_client, db_session, "bricks-user-b@example.com"
    )
    headers_b = {"Authorization": f"Bearer {access_b}"}
    await _ensure_master_resume(app_client, headers_b)

    r = await app_client.get("/api/profile/bricks", headers=headers_b)
    assert r.status_code == 200
    ids_b = {b["id"] for b in r.json()}
    assert brick_id_a not in ids_b

    r = await app_client.delete(
        f"/api/profile/bricks/{brick_id_a}",
        headers=headers_b,
    )
    assert r.status_code == 404


async def test_bricks_delete_soft_hides_from_get(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    access = await _register_and_login(
        app_client, db_session, "bricks-delete@example.com"
    )
    headers = {"Authorization": f"Bearer {access}"}
    await _ensure_master_resume(app_client, headers)

    r = await app_client.post(
        "/api/profile/bricks",
        headers=headers,
        json={"section_type": "project", "content": "Open-source CLI for resume linting."},
    )
    assert r.status_code == 201
    brick_id = r.json()["id"]

    r = await app_client.delete(
        f"/api/profile/bricks/{brick_id}", headers=headers
    )
    assert r.status_code == 204

    r = await app_client.get("/api/profile/bricks", headers=headers)
    assert r.status_code == 200
    assert brick_id not in {b["id"] for b in r.json()}
