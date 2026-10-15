"""GET /api/sessions/{id} — job_posting_url from linked extension JD rows."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_description import JobDescription
from app.routers.sessions import _job_posting_url_for_session, _sanitize_job_posting_url
from app.services.session_store import create_session, update_session
from tests.integration.test_auth import REGISTER_PAYLOAD

pytestmark = pytest.mark.integration


async def _register(client: AsyncClient, suffix: str = "") -> tuple[str, str]:
    email = f"job-url-{suffix or uuid.uuid4().hex[:6]}@example.com"
    payload = {**REGISTER_PAYLOAD, "email": email}
    r = await client.post("/api/auth/register", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["access_token"], r.json()["user"]["id"]


async def _insert_jd(
    db_session: AsyncSession,
    *,
    user_id: str,
    session_id: str,
    url: str | None,
    created_at: datetime | None = None,
) -> None:
    row = JobDescription(
        user_id=uuid.UUID(user_id),
        url=url,
        title="Engineer",
        company="Acme",
        text="Job description text long enough for validation in other flows.",
        source="extension",
        session_id=session_id,
    )
    if created_at is not None:
        row.created_at = created_at
    db_session.add(row)
    await db_session.commit()


@pytest.mark.asyncio
async def test_linked_extension_jd_returns_url(
    app_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    token, user_id = await _register(app_client, "linked")
    session = await create_session()
    session.user_id = user_id
    await update_session(session)

    url = "https://boards.greenhouse.io/acme/jobs/123"
    await _insert_jd(db_session, user_id=user_id, session_id=session.session_id, url=url)

    r = await app_client.get(f"/api/sessions/{session.session_id}")
    assert r.status_code == 200
    assert r.json()["job_posting_url"] == url


@pytest.mark.asyncio
async def test_no_jd_row_returns_null(app_client: AsyncClient) -> None:
    session = await create_session()
    session.user_id = str(uuid.uuid4())
    await update_session(session)

    r = await app_client.get(f"/api/sessions/{session.session_id}")
    assert r.status_code == 200
    assert r.json()["job_posting_url"] is None


@pytest.mark.asyncio
async def test_jd_row_with_null_url_returns_null(
    app_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    token, user_id = await _register(app_client, "null-url")
    session = await create_session()
    session.user_id = user_id
    await update_session(session)

    await _insert_jd(db_session, user_id=user_id, session_id=session.session_id, url=None)

    r = await app_client.get(f"/api/sessions/{session.session_id}")
    assert r.status_code == 200
    assert r.json()["job_posting_url"] is None


@pytest.mark.asyncio
async def test_multiple_rows_newest_wins(
    app_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    token, user_id = await _register(app_client, "newest")
    session = await create_session()
    session.user_id = user_id
    await update_session(session)

    older = datetime.now(timezone.utc) - timedelta(days=2)
    newer = datetime.now(timezone.utc) - timedelta(days=1)
    await _insert_jd(
        db_session,
        user_id=user_id,
        session_id=session.session_id,
        url="https://jobs.lever.co/acme/old",
        created_at=older,
    )
    await _insert_jd(
        db_session,
        user_id=user_id,
        session_id=session.session_id,
        url="https://jobs.lever.co/acme/new",
        created_at=newer,
    )

    r = await app_client.get(f"/api/sessions/{session.session_id}")
    assert r.status_code == 200
    assert r.json()["job_posting_url"] == "https://jobs.lever.co/acme/new"


@pytest.mark.asyncio
async def test_cross_user_only_attacker_jd_returns_null(
    app_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _token_a, user_a = await _register(app_client, "attacker-only")
    _token_b, user_b = await _register(app_client, "victim-only")

    session = await create_session()
    session.user_id = user_b
    await update_session(session)

    await _insert_jd(
        db_session,
        user_id=user_a,
        session_id=session.session_id,
        url="https://boards.greenhouse.io/acme/jobs/999",
    )

    r = await app_client.get(f"/api/sessions/{session.session_id}")
    assert r.status_code == 200
    assert r.json()["job_posting_url"] is None


@pytest.mark.asyncio
async def test_cross_user_jd_not_leaked(
    app_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    _token_a, user_a = await _register(app_client, "owner-a")
    _token_b, user_b = await _register(app_client, "owner-b")

    session = await create_session()
    session.user_id = user_b
    await update_session(session)

    attacker_url = "https://boards.greenhouse.io/acme/jobs/999"
    owner_url = "https://jobs.lever.co/acme/owned"
    await _insert_jd(
        db_session,
        user_id=user_a,
        session_id=session.session_id,
        url=attacker_url,
    )
    await _insert_jd(
        db_session,
        user_id=user_b,
        session_id=session.session_id,
        url=owner_url,
    )

    r = await app_client.get(f"/api/sessions/{session.session_id}")
    assert r.status_code == 200
    assert r.json()["job_posting_url"] == owner_url
    assert r.json()["job_posting_url"] != attacker_url


@pytest.mark.asyncio
async def test_anonymous_session_skips_db_query(db_session: AsyncSession) -> None:
    session = await create_session()
    assert not session.user_id

    with patch.object(db_session, "execute", new_callable=AsyncMock) as mock_exec:
        result = await _job_posting_url_for_session(db_session, session)

    assert result is None
    mock_exec.assert_not_called()


@pytest.mark.asyncio
async def test_anonymous_session_returns_null_without_user_id(
    app_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    token, user_id = await _register(app_client, "anon-jd")
    session = await create_session()
    assert not session.user_id

    await _insert_jd(
        db_session,
        user_id=user_id,
        session_id=session.session_id,
        url="https://boards.greenhouse.io/acme/jobs/1",
    )

    r = await app_client.get(f"/api/sessions/{session.session_id}")
    assert r.status_code == 200
    assert r.json()["job_posting_url"] is None


@pytest.mark.parametrize(
    "url",
    [
        "https://boards.greenhouse.io/" + ("a" * 2100),
        "data:text/html,hello",
        "file:///etc/passwd",
        "https://user:pass@boards.greenhouse.io/jobs/1",
        "https://boards.greenhouse.io/jobs/1\r\nX: 1",
    ],
)
def test_sanitize_job_posting_url_rejects_unsafe_values(url: str) -> None:
    assert _sanitize_job_posting_url(url) is None


@pytest.mark.asyncio
async def test_javascript_scheme_sanitized_to_null(
    app_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    token, user_id = await _register(app_client, "js-scheme")
    session = await create_session()
    session.user_id = user_id
    await update_session(session)

    safe_url = "https://jobs.lever.co/acme/safe"
    await _insert_jd(
        db_session,
        user_id=user_id,
        session_id=session.session_id,
        url="javascript:alert(1)",
        created_at=datetime.now(timezone.utc),
    )
    await _insert_jd(
        db_session,
        user_id=user_id,
        session_id=session.session_id,
        url=safe_url,
        created_at=datetime.now(timezone.utc) - timedelta(days=1),
    )

    r = await app_client.get(f"/api/sessions/{session.session_id}")
    assert r.status_code == 200
    assert r.json()["job_posting_url"] is None

