"""Integration tests for autofill payload endpoints."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dashboard import ResumeRecord, ResumeRecordStatus
from app.models.job_description import JobDescription
from app.models.rewrite import TailoredResumeOutput
from app.services.autofill import ensure_job_description_for_session
from app.services.dashboard.session_cache import build_session_cache
from app.services.session_store import (
    create_session,
    get_session,
    redis_delete,
    update_session,
)
from tests.integration.test_auth import REGISTER_PAYLOAD

pytestmark = pytest.mark.integration


async def _register(client: AsyncClient, suffix: str = "") -> tuple[str, str]:
    email = f"autofill-{suffix or uuid.uuid4().hex[:6]}@example.com"
    payload = {**REGISTER_PAYLOAD, "email": email}
    r = await client.post("/api/auth/register", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["access_token"], r.json()["user"]["id"]


@pytest.mark.asyncio
async def test_autofill_payload_requires_tailored_session(app_client: AsyncClient) -> None:
    token, _ = await _register(app_client, "409")

    save_r = await app_client.post(
        "/api/job-descriptions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "url": "https://boards.greenhouse.io/acme/jobs/123",
            "title": "Engineer",
            "company": "Acme",
            "text": "Build distributed systems with Rust and Kafka for this senior role opening.",
            "source": "extension",
        },
    )
    assert save_r.status_code == 200
    jd_id = save_r.json()["jd_id"]

    payload_r = await app_client.get(
        f"/api/job-descriptions/{jd_id}/autofill-payload",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert payload_r.status_code == 409
    assert payload_r.json()["detail"]["code"] == "resume_not_tailored_yet"


@pytest.mark.asyncio
async def test_autofill_payload_returns_greenhouse_fields(
    app_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    token, user_id = await _register(app_client, "ok")

    save_r = await app_client.post(
        "/api/job-descriptions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "url": "https://boards.greenhouse.io/acme/jobs/123",
            "title": "Senior Engineer",
            "company": "Acme",
            "text": "Build distributed systems with Rust and Kafka for this senior role opening.",
            "source": "extension",
        },
    )
    jd_id = save_r.json()["jd_id"]

    session = await create_session()
    session.user_id = user_id
    session.phase3_output = TailoredResumeOutput(
        contact={
            "name": "Alex Rivera",
            "email": "alex@example.com",
            "phone": "555-0100",
            "linkedin": "https://www.linkedin.com/in/alex",
        },
        summary="Tailored resume summary.",
    )
    await update_session(session)

    row = (
        await db_session.execute(select(JobDescription).where(JobDescription.id == uuid.UUID(jd_id)))
    ).scalar_one()
    row.session_id = session.session_id
    await db_session.commit()

    payload_r = await app_client.get(
        f"/api/job-descriptions/{jd_id}/autofill-payload",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert payload_r.status_code == 200, payload_r.text
    body = payload_r.json()
    assert body["platform"] == "greenhouse"
    keys = {field["key"] for field in body["fields"]}
    assert "email" in keys
    assert "resume" in keys
    assert all("summary" not in field["value"].lower() for field in body["fields"])


@pytest.mark.asyncio
async def test_autofill_payload_returns_lever_heuristic_fields(
    app_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    token, user_id = await _register(app_client, "lever")

    save_r = await app_client.post(
        "/api/job-descriptions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "url": "https://jobs.lever.co/acme/abc-123",
            "title": "Staff Engineer",
            "company": "Acme",
            "text": "Build platform APIs with Go and Kubernetes for our infrastructure team.",
            "source": "extension",
        },
    )
    jd_id = save_r.json()["jd_id"]

    session = await create_session()
    session.user_id = user_id
    session.phase3_output = TailoredResumeOutput(
        contact={"name": "Alex Rivera", "email": "alex@example.com"},
        summary="Tailored resume summary.",
    )
    await update_session(session)

    row = (
        await db_session.execute(select(JobDescription).where(JobDescription.id == uuid.UUID(jd_id)))
    ).scalar_one()
    row.session_id = session.session_id
    await db_session.commit()

    payload_r = await app_client.get(
        f"/api/job-descriptions/{jd_id}/autofill-payload",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert payload_r.status_code == 200, payload_r.text
    body = payload_r.json()
    assert body["platform"] == "lever"
    assert all(field["selector"] == "" for field in body["fields"])
    email = next(field for field in body["fields"] if field["key"] == "email")
    assert email["value"] == "alex@example.com"


@pytest.mark.asyncio
async def test_autofill_payload_returns_ashby_heuristic_fields(
    app_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    token, user_id = await _register(app_client, "ashby")

    save_r = await app_client.post(
        "/api/job-descriptions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "url": "https://jobs.ashbyhq.com/acme/abc-123",
            "title": "Staff Engineer",
            "company": "Acme",
            "text": "Build platform APIs with Go and Kubernetes for our infrastructure team.",
            "source": "extension",
        },
    )
    jd_id = save_r.json()["jd_id"]

    session = await create_session()
    session.user_id = user_id
    session.phase3_output = TailoredResumeOutput(
        contact={"name": "Alex Rivera", "email": "alex@example.com"},
        summary="Tailored resume summary.",
    )
    await update_session(session)

    row = (
        await db_session.execute(select(JobDescription).where(JobDescription.id == uuid.UUID(jd_id)))
    ).scalar_one()
    row.session_id = session.session_id
    await db_session.commit()

    payload_r = await app_client.get(
        f"/api/job-descriptions/{jd_id}/autofill-payload",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert payload_r.status_code == 200, payload_r.text
    body = payload_r.json()
    assert body["platform"] == "ashby"
    assert all(field["selector"] == "" for field in body["fields"])
    email = next(field for field in body["fields"] if field["key"] == "email")
    assert email["value"] == "alex@example.com"


@pytest.mark.asyncio
async def test_recent_tailored_sessions_lists_only_completed_tailoring(
    app_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    token, user_id = await _register(app_client, "recent")

    save_r = await app_client.post(
        "/api/job-descriptions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "url": "https://boards.greenhouse.io/acme/jobs/456",
            "title": "Platform Engineer",
            "company": "Beta Co",
            "text": "Own platform reliability and observability for customer-facing APIs and data.",
            "source": "extension",
        },
    )
    jd_id = save_r.json()["jd_id"]

    session = await create_session()
    session.user_id = user_id
    session.phase3_output = TailoredResumeOutput(
        contact={"name": "Sam", "email": "sam@example.com"},
        summary="Tailored.",
    )
    await update_session(session)

    row = (
        await db_session.execute(select(JobDescription).where(JobDescription.id == uuid.UUID(jd_id)))
    ).scalar_one()
    row.session_id = session.session_id
    await db_session.commit()

    list_r = await app_client.get(
        "/api/job-descriptions/recent-tailored",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_r.status_code == 200, list_r.text
    sessions = list_r.json()["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["jd_id"] == jd_id
    assert sessions[0]["company"] == "Beta Co"
    assert sessions[0]["url_host"] == "boards.greenhouse.io"


async def _tailored_session_with_record(
    db_session: AsyncSession,
    user_id: str,
    *,
    title: str = "Platform Engineer",
    company: str = "Web Co",
) -> tuple[str, ResumeRecord]:
    """A session tailored on the web: durable ResumeRecord snapshot, no JD row."""
    session = await create_session()
    session.user_id = user_id
    session.jd_raw = "Own platform reliability for customer-facing APIs and data pipelines."
    session.phase3_output = TailoredResumeOutput(
        contact={
            "name": "Dana Webb",
            "email": "dana@example.com",
            "phone": "555-0199",
        },
        summary="Tailored resume summary.",
    )
    await update_session(session)

    record = ResumeRecord(
        id=uuid.uuid4(),
        user_id=uuid.UUID(user_id),
        session_id=session.session_id,
        jd_title=title,
        jd_company=company,
        jd_text_hash=uuid.uuid4().hex,
        tags=[],
        current_ats_score=80,
        starting_ats_score=70,
        status=ResumeRecordStatus.draft,
        session_cache=build_session_cache(session),
    )
    db_session.add(record)
    await db_session.commit()
    return session.session_id, record


@pytest.mark.asyncio
async def test_autofill_payload_restores_from_expired_redis_session(
    app_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Autofill must survive the 24h Redis TTL via the durable snapshot."""
    token, user_id = await _register(app_client, "ttl")

    save_r = await app_client.post(
        "/api/job-descriptions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "url": "https://boards.greenhouse.io/acme/jobs/789",
            "title": "Senior Engineer",
            "company": "Acme",
            "text": "Build distributed systems with Rust and Kafka for this senior role opening.",
            "source": "extension",
        },
    )
    jd_id = save_r.json()["jd_id"]

    session_id, _ = await _tailored_session_with_record(db_session, user_id)
    row = (
        await db_session.execute(select(JobDescription).where(JobDescription.id == uuid.UUID(jd_id)))
    ).scalar_one()
    row.session_id = session_id
    await db_session.commit()

    # Simulate TTL expiry — the Redis key is the raw session_id. Each endpoint
    # is probed against a genuinely empty Redis, because a successful restore
    # repopulates the key and would mask the next call.
    await redis_delete(session_id)
    assert await get_session(session_id) is None

    list_r = await app_client.get(
        "/api/job-descriptions/recent-tailored",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_r.status_code == 200, list_r.text
    assert any(s["jd_id"] == jd_id for s in list_r.json()["sessions"])

    await redis_delete(session_id)
    assert await get_session(session_id) is None

    payload_r = await app_client.get(
        f"/api/job-descriptions/{jd_id}/autofill-payload",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert payload_r.status_code == 200, payload_r.text
    body = payload_r.json()
    assert body["platform"] == "greenhouse"
    email = next(f for f in body["fields"] if f["key"] == "email")
    assert email["value"] == "dana@example.com"
    assert email["selector"] == "[name='job_application[email]']"


@pytest.mark.asyncio
async def test_recent_tailored_web_session_survives_expired_redis_session(
    app_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """A web-tailored session must be listed and fetchable with Redis empty."""
    token, user_id = await _register(app_client, "webttl")
    session_id, _ = await _tailored_session_with_record(db_session, user_id)

    await redis_delete(session_id)
    assert await get_session(session_id) is None

    list_r = await app_client.get(
        "/api/job-descriptions/recent-tailored",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_r.status_code == 200, list_r.text
    sessions = list_r.json()["sessions"]
    assert len(sessions) == 1
    jd_id = sessions[0]["jd_id"]

    await redis_delete(session_id)
    assert await get_session(session_id) is None

    payload_r = await app_client.get(
        f"/api/job-descriptions/{jd_id}/autofill-payload",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert payload_r.status_code == 200, payload_r.text
    # No posting URL on a web-tailored row, so no platform selectors.
    assert payload_r.json()["platform"] == "unknown"
    assert all(f["selector"] == "" for f in payload_r.json()["fields"])


@pytest.mark.asyncio
async def test_ensure_job_description_for_session_is_idempotent(
    app_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Direct double-call: the listing endpoint's first pass hides repeats."""
    _, user_id = await _register(app_client, "ensure")
    session_id, record = await _tailored_session_with_record(db_session, user_id)

    first = await ensure_job_description_for_session(
        db_session,
        user_id=uuid.UUID(user_id),
        session_id=session_id,
        title=record.jd_title,
        company=record.jd_company,
        jd_text="Some JD text.",
    )
    second = await ensure_job_description_for_session(
        db_session,
        user_id=uuid.UUID(user_id),
        session_id=session_id,
        title="Changed Title",
        company="Changed Co",
        jd_text="Different text.",
    )
    await db_session.commit()

    assert second.id == first.id
    # The existing row must be returned untouched — never clobbered.
    assert second.title == record.jd_title
    assert second.company == record.jd_company

    rows = (
        await db_session.execute(
            select(JobDescription).where(JobDescription.session_id == session_id)
        )
    ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_recent_tailored_includes_web_session_without_jd_row(
    app_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """Tailoring on the web creates no JD row; it must still be autofillable."""
    token, user_id = await _register(app_client, "web")
    await _tailored_session_with_record(
        db_session, user_id, title="Data Engineer", company="Web Co"
    )

    list_r = await app_client.get(
        "/api/job-descriptions/recent-tailored",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert list_r.status_code == 200, list_r.text
    sessions = list_r.json()["sessions"]
    assert len(sessions) == 1
    entry = sessions[0]
    assert entry["company"] == "Web Co"
    # No posting URL exists for a web-tailored session — must stay empty so the
    # extension shows a picker instead of mis-matching on host.
    assert entry["url_host"] == ""

    # The listed jd_id must resolve: a picker row that 404s is worse than none.
    payload_r = await app_client.get(
        f"/api/job-descriptions/{entry['jd_id']}/autofill-payload",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert payload_r.status_code == 200, payload_r.text
    keys = {f["key"] for f in payload_r.json()["fields"]}
    assert {"first_name", "last_name", "email", "phone"} <= keys


@pytest.mark.asyncio
async def test_recent_tailored_web_upsert_is_idempotent(
    app_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    token, user_id = await _register(app_client, "idem")
    session_id, _ = await _tailored_session_with_record(db_session, user_id)

    first = await app_client.get(
        "/api/job-descriptions/recent-tailored",
        headers={"Authorization": f"Bearer {token}"},
    )
    second = await app_client.get(
        "/api/job-descriptions/recent-tailored",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert first.status_code == 200 and second.status_code == 200
    assert len(first.json()["sessions"]) == 1
    assert len(second.json()["sessions"]) == 1
    assert first.json()["sessions"][0]["jd_id"] == second.json()["sessions"][0]["jd_id"]

    rows = (
        await db_session.execute(
            select(JobDescription).where(JobDescription.session_id == session_id)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].source == "web"
    assert rows[0].url is None


@pytest.mark.asyncio
async def test_recent_tailored_web_upsert_isolated_between_users(
    app_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    owner_token, owner_id = await _register(app_client, "owner-web")
    other_token, other_id = await _register(app_client, "other-web")
    await _tailored_session_with_record(db_session, owner_id)

    # The owner sees it, which proves the second pass actually ran — otherwise
    # the other user's empty list would pass for the wrong reason.
    owner_list = await app_client.get(
        "/api/job-descriptions/recent-tailored",
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert owner_list.status_code == 200, owner_list.text
    owner_sessions = owner_list.json()["sessions"]
    assert len(owner_sessions) == 1
    owner_jd_id = owner_sessions[0]["jd_id"]

    other_list = await app_client.get(
        "/api/job-descriptions/recent-tailored",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert other_list.status_code == 200
    assert other_list.json()["sessions"] == []

    # The other user must not be able to fetch the lazily created row either.
    other_payload = await app_client.get(
        f"/api/job-descriptions/{owner_jd_id}/autofill-payload",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert other_payload.status_code == 404

    other_rows = (
        await db_session.execute(
            select(JobDescription).where(JobDescription.user_id == uuid.UUID(other_id))
        )
    ).scalars().all()
    assert other_rows == []


@pytest.mark.asyncio
async def test_autofill_payload_isolation_between_users(
    app_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    token_a, user_a = await _register(app_client, "iso-a")
    token_b, _ = await _register(app_client, "iso-b")

    save_r = await app_client.post(
        "/api/job-descriptions",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "title": "Private",
            "company": "Secret",
            "text": "Confidential job description text long enough for validation in this test case.",
            "source": "extension",
        },
    )
    jd_id = save_r.json()["jd_id"]

    session = await create_session()
    session.user_id = user_a
    session.phase3_output = TailoredResumeOutput(
        contact={"name": "Owner", "email": "owner@example.com"},
        summary="Private tailored resume.",
    )
    await update_session(session)

    row = (
        await db_session.execute(select(JobDescription).where(JobDescription.id == uuid.UUID(jd_id)))
    ).scalar_one()
    row.session_id = session.session_id
    await db_session.commit()

    forbidden = await app_client.get(
        f"/api/job-descriptions/{jd_id}/autofill-payload",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert forbidden.status_code == 404


@pytest.mark.asyncio
async def test_autofill_payload_unknown_jd_returns_404(app_client: AsyncClient) -> None:
    token, _ = await _register(app_client, "404")
    missing_id = str(uuid.uuid4())
    r = await app_client.get(
        f"/api/job-descriptions/{missing_id}/autofill-payload",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_job_description_by_id(app_client: AsyncClient) -> None:
    token, _ = await _register(app_client, "get-jd")

    save_r = await app_client.post(
        "/api/job-descriptions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "url": "https://boards.greenhouse.io/acme/jobs/789",
            "title": "Backend Engineer",
            "company": "Acme",
            "text": "Build APIs with FastAPI and PostgreSQL for our platform engineering team.",
            "source": "extension",
        },
    )
    assert save_r.status_code == 200
    jd_id = save_r.json()["jd_id"]

    get_r = await app_client.get(
        f"/api/job-descriptions/{jd_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_r.status_code == 200, get_r.text
    body = get_r.json()
    assert body["id"] == jd_id
    assert body["title"] == "Backend Engineer"
    assert body["company"] == "Acme"
