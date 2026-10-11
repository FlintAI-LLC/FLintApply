"""Career Watch API integration tests."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notifications import Notification, NotificationChannel
from app.services.career_watch.probe import CareersPageProbe, ProbeStatus
from app.services.notifications.factory import build_notification
from tests.integration.test_auth import REGISTER_PAYLOAD

pytestmark = pytest.mark.integration


async def _register(client: AsyncClient) -> tuple[str, uuid.UUID]:
    payload = {
        **REGISTER_PAYLOAD,
        "email": f"cw-{uuid.uuid4().hex[:8]}@example.com",
    }
    r = await client.post("/api/auth/register", json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    return body["access_token"], uuid.UUID(body["user"]["id"])


@pytest.mark.asyncio
async def test_career_watch_detect_requires_auth(app_client: AsyncClient) -> None:
    resp = await app_client.post(
        "/api/career-watch/detect",
        json={"careers_page_url": "https://boards.greenhouse.io/acme"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_career_watch_create_and_list(app_client: AsyncClient) -> None:
    token, _user_id = await _register(app_client)
    headers = {"Authorization": f"Bearer {token}"}

    detect_resp = await app_client.post(
        "/api/career-watch/detect",
        json={"careers_page_url": "https://boards.greenhouse.io/acme"},
        headers=headers,
    )
    assert detect_resp.status_code == 200
    assert detect_resp.json()["ats_type"] == "greenhouse"

    ok_probe = CareersPageProbe(
        status=ProbeStatus.ok,
        job_count=1,
        message="Found 1 open job(s). This URL looks good for monitoring.",
    )
    with patch(
        "app.routers.career_watch.probe_careers_page",
        new=AsyncMock(return_value=ok_probe),
    ):
        create_resp = await app_client.post(
            "/api/career-watch/watches",
            json={
                "careers_page_url": "https://boards.greenhouse.io/acme",
                "company_name": "Acme Corp",
                "keywords": ["python", "backend"],
            },
            headers=headers,
        )
    assert create_resp.status_code == 201, create_resp.text
    body = create_resp.json()
    assert body["company_name"] == "Acme Corp"
    assert body["keywords"] == ["python", "backend"]

    list_resp = await app_client.get("/api/career-watch/watches", headers=headers)
    assert list_resp.status_code == 200
    watches = list_resp.json()
    assert len(watches) == 1
    assert watches[0]["id"] == body["id"]

    limits_resp = await app_client.get("/api/career-watch/limits", headers=headers)
    assert limits_resp.status_code == 200
    limits = limits_resp.json()
    assert limits["active_watches"] == 1
    assert limits["max_companies"] >= 1

    delete_resp = await app_client.delete(
        f"/api/career-watch/watches/{body['id']}",
        headers=headers,
    )
    assert delete_resp.status_code == 204, delete_resp.text

    list_after = await app_client.get("/api/career-watch/watches", headers=headers)
    assert list_after.status_code == 200
    assert list_after.json() == []

    limits_after = await app_client.get("/api/career-watch/limits", headers=headers)
    assert limits_after.json()["active_watches"] == 0


@pytest.mark.asyncio
async def test_career_watch_bulk_dismiss_requires_auth(app_client: AsyncClient) -> None:
    resp = await app_client.post(
        "/api/career-watch/alerts/dismiss",
        json={"alert_ids": [], "dismiss_all": False},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_career_watch_bulk_dismiss_validation(app_client: AsyncClient) -> None:
    token, _user_id = await _register(app_client)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await app_client.post(
        "/api/career-watch/alerts/dismiss",
        json={"alert_ids": [], "dismiss_all": False},
        headers=headers,
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_clear_in_app_notifications_deletes_job_alert_bell_rows(
    app_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    token, user_id = await _register(app_client)
    headers = {"Authorization": f"Bearer {token}"}
    alert_id = uuid.uuid4()

    db_session.add(
        build_notification(
            user_id=user_id,
            type="career_watch_match",
            channel=NotificationChannel.in_app,
            category="job_alerts",
            title="New role: Engineer",
            body="Match",
            data={"career_alert_id": str(alert_id)},
        )
    )
    db_session.add(
        build_notification(
            user_id=user_id,
            type="career_watch_match",
            channel=NotificationChannel.in_app,
            category="job_alerts",
            title="Already read",
            body="Old",
            data={"career_alert_id": str(uuid.uuid4())},
        )
    )
    db_session.add(
        build_notification(
            user_id=user_id,
            type="payment_recovered",
            channel=NotificationChannel.in_app,
            category="payment",
            title="Payment",
            body="Thanks",
        )
    )
    await db_session.commit()

    resp = await app_client.post(
        "/api/career-watch/alerts/clear-in-app-notifications",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["cleared"] == 2

    remaining = (
        await db_session.execute(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.user_id == user_id,
                Notification.channel == NotificationChannel.in_app,
            )
        )
    ).scalar_one()
    assert remaining == 1
