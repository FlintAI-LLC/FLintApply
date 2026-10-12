"""Career Watch emit notification policy tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.career_watch import (
    CareerAlert,
    CareerAlertStatus,
    CareerJobCache,
    UserWatchedCompany,
    WatchedCompany,
)
from app.models.notifications import Notification, NotificationChannel
from app.models.user import AuthProvider, User
from app.services.career_watch.notifications import emit_career_watch_alert


async def _fixture_alert(db_session: AsyncSession) -> CareerAlert:
    user_id = uuid.uuid4()
    db_session.add(
        User(
            id=user_id,
            email=f"cw-{user_id.hex[:8]}@example.com",
            email_canonical=f"cw-{user_id.hex[:8]}@example.com",
            auth_provider=AuthProvider.email,
            password_hash="x",
            display_name="CW",
        )
    )
    await db_session.flush()
    company_id = uuid.uuid4()
    db_session.add(
        WatchedCompany(
            id=company_id,
            name="Co",
            slug=f"co-{company_id.hex[:6]}",
            careers_page_url="https://example.com/careers",
        )
    )
    await db_session.flush()
    watch_id = uuid.uuid4()
    db_session.add(
        UserWatchedCompany(
            id=watch_id,
            user_id=user_id,
            watched_company_id=company_id,
            keywords=["python"],
        )
    )
    await db_session.flush()
    job_id = uuid.uuid4()
    db_session.add(
        CareerJobCache(
            id=job_id,
            watched_company_id=company_id,
            external_job_id="1",
            title="Python Engineer",
            location="Remote",
            description_text="python backend",
            description_hash="h",
            apply_url="https://jobs.example/1",
            first_seen_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
            is_open=True,
        )
    )
    await db_session.flush()
    alert = CareerAlert(
        id=uuid.uuid4(),
        user_id=user_id,
        user_watched_company_id=watch_id,
        career_job_cache_id=job_id,
        match_score=0.5,
        match_reason="matched",
        status=CareerAlertStatus.pending,
    )
    db_session.add(alert)
    await db_session.flush()
    return alert


@pytest.mark.asyncio
async def test_free_user_digest_email_not_immediate_match_email(
    db_session: AsyncSession,
) -> None:
    alert = await _fixture_alert(db_session)
    with patch(
        "app.services.career_watch.notifications.user_on_paid_plan",
        new=AsyncMock(return_value=False),
    ):
        await emit_career_watch_alert(db_session, alert)

    rows = (
        await db_session.execute(
            select(Notification).where(Notification.user_id == alert.user_id)
        )
    ).scalars().all()
    instant = [
        r
        for r in rows
        if r.channel == NotificationChannel.email and r.type == "career_watch_match"
    ]
    digest = [
        r
        for r in rows
        if r.channel == NotificationChannel.email
        and r.type == "career_watch_daily_digest"
    ]
    assert not instant
    assert len(digest) == 1


@pytest.mark.asyncio
async def test_paid_instant_opt_in_gets_immediate_email(
    db_session: AsyncSession,
) -> None:
    alert = await _fixture_alert(db_session)
    from app.services.notifications.preferences import get_or_create_preferences

    prefs = await get_or_create_preferences(db_session, alert.user_id)
    prefs.instant_job_alert_email = True
    prefs.email_enabled_categories = list(prefs.email_enabled_categories or []) + [
        "job_alerts"
    ]
    await db_session.flush()

    with patch(
        "app.services.career_watch.notifications.user_on_paid_plan",
        new=AsyncMock(return_value=True),
    ):
        await emit_career_watch_alert(db_session, alert)

    rows = (
        await db_session.execute(
            select(Notification).where(Notification.user_id == alert.user_id)
        )
    ).scalars().all()
    instant = [
        r
        for r in rows
        if r.channel == NotificationChannel.email and r.type == "career_watch_match"
    ]
    assert len(instant) == 1
