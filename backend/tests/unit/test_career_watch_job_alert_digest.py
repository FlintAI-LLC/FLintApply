"""Daily job-alert digest tests (DB-backed; runs in integration CI job)."""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.integration
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notifications import DigestMode, NotificationChannel, NotificationDeliveryStatus
from app.services.career_watch.job_alert_digest import (
    enqueue_job_alert_digest_item,
    local_digest_date,
    scheduled_digest_send_utc,
    send_daily_job_alert_digests,
)


def test_local_digest_date_uses_timezone() -> None:
    utc = datetime(2026, 3, 15, 2, 0, tzinfo=timezone.utc)
    assert local_digest_date(utc, "America/Los_Angeles") == "2026-03-14"


def test_scheduled_digest_send_utc_is_6pm_local() -> None:
    utc = datetime(2026, 3, 15, 20, 0, tzinfo=timezone.utc)
    send_utc = scheduled_digest_send_utc(utc, "America/Los_Angeles")
    local = send_utc.astimezone(ZoneInfo("America/Los_Angeles"))
    assert local.hour == 18
    assert local.minute == 0


async def _user(db_session: AsyncSession) -> uuid.UUID:
    from app.models.user import AuthProvider, User

    user_id = uuid.uuid4()
    db_session.add(
        User(
            id=user_id,
            email=f"d-{user_id.hex[:8]}@example.com",
            email_canonical=f"d-{user_id.hex[:8]}@example.com",
            auth_provider=AuthProvider.email,
            password_hash="x",
            display_name="D",
        )
    )
    await db_session.flush()
    return user_id



@pytest.mark.asyncio
async def test_enqueue_appends_to_same_day_digest(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    prefs = MagicMock()
    prefs.digest_mode = DigestMode.daily
    prefs.timezone = "UTC"
    now = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)

    with patch(
        "app.services.career_watch.job_alert_digest.get_or_create_preferences",
        new=AsyncMock(return_value=prefs),
    ):
        await enqueue_job_alert_digest_item(
            db_session,
            user_id=user_id,
            now=now,
            title="Role A",
            company_name="Co",
            apply_url="https://jobs.example/a",
            career_alert_id=uuid.uuid4(),
        )
        await enqueue_job_alert_digest_item(
            db_session,
            user_id=user_id,
            now=now,
            title="Role B",
            company_name="Co",
            apply_url="https://jobs.example/b",
            career_alert_id=uuid.uuid4(),
        )

    await db_session.flush()
    from sqlalchemy import select
    from app.models.notifications import Notification

    rows = (
        await db_session.execute(
            select(Notification).where(Notification.user_id == user_id)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert len(rows[0].data.get("items") or []) == 2
    assert rows[0].channel == NotificationChannel.email


@pytest.mark.asyncio
async def test_three_matches_one_digest_email_send(db_session: AsyncSession) -> None:
    user_id = await _user(db_session)
    from app.services.notifications.preferences import get_or_create_preferences

    prefs = await get_or_create_preferences(db_session, user_id)
    prefs.digest_mode = DigestMode.daily
    prefs.timezone = "UTC"
    await db_session.flush()

    now = datetime(2026, 6, 1, 19, 0, tzinfo=timezone.utc)
    for i in range(3):
        await enqueue_job_alert_digest_item(
            db_session,
            user_id=user_id,
            now=now,
            title=f"Role {i}",
            company_name="Co",
            apply_url=f"https://jobs.example/{i}",
            career_alert_id=uuid.uuid4(),
        )
    await db_session.flush()

    mock_send = MagicMock(return_value={"id": "email_1"})
    with patch("resend.Emails.send", mock_send):
        with patch("app.services.notifications.email_adapter.settings") as cfg:
            cfg.RESEND_API_KEY = "re_test"
            cfg.RESEND_FROM_EMAIL = "noreply@test.com"
            cfg.FRONTEND_BASE_URL = "http://localhost:3100"
            stats = await send_daily_job_alert_digests(db_session, now=now)

    assert stats.digests_sent == 1
    mock_send.assert_called_once()
