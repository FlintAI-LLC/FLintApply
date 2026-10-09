"""Admin monitoring report endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import AdminRole
from app.models.user import AuthAuditEvent, AuthProvider, User
from app.services.auth.audit import record_auth_event
from tests.admin.conftest import issue_admin_session, make_admin

pytestmark = pytest.mark.asyncio


async def _admin_headers(session: AsyncSession) -> dict[str, str]:
    admin, _secret = await make_admin(
        session,
        email="reports-admin@example.com",
        role=AdminRole.read_only_analyst,
    )
    token, headers = await issue_admin_session(admin.id)
    return headers


async def test_monitoring_activity_and_funnel(
    app_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    headers = await _admin_headers(db_session)
    user = User(
        email="monitor-user@example.com",
        email_canonical="monitor-user@example.com",
        display_name="Monitor",
        password_hash="x",
        auth_provider=AuthProvider.email,
        email_verified_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        accepted_tos_version="test",
    )
    db_session.add(user)
    await db_session.flush()
    await record_auth_event(
        db_session,
        user_id=user.id,
        event=AuthAuditEvent.login_success,
        ip="1.2.3.4",
        user_agent="pytest",
        metadata={"source": "web"},
    )
    await db_session.commit()

    today = datetime.now(timezone.utc).date().isoformat()
    activity = await app_client.get(
        f"/api/admin/reports/activity?from_date={today}&to_date={today}",
        headers=headers,
    )
    assert activity.status_code == 200
    body = activity.json()
    assert body["metrics"]
    assert body["metrics"][-1]["dau"] >= 1
    assert body["metrics"][-1]["dau_web"] >= 1

    funnel = await app_client.get(
        f"/api/admin/reports/funnel?from_date={today}&to_date={today}",
        headers=headers,
    )
    assert funnel.status_code == 200
    assert funnel.json()["registered"] >= 1
    assert funnel.json()["email_verified"] >= 1


async def test_public_beacon_increments_summary(
    app_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    beacon = await app_client.post(
        "/api/public/metrics/beacon",
        json={"key": "landing_view"},
    )
    assert beacon.status_code == 200
    assert beacon.json()["ok"] is True

    headers = await _admin_headers(db_session)
    today = datetime.now(timezone.utc).date().isoformat()
    summary = await app_client.get(
        f"/api/admin/reports/monitoring-summary?from_date={today}&to_date={today}",
        headers=headers,
    )
    assert summary.status_code == 200
    assert summary.json()["landing_views"] >= 1
