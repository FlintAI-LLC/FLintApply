"""Interview round reminders schedule email + in-app, not SMS."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.notifications import Notification, NotificationChannel
from app.models.tracker import Application, ApplicationStatus, InterviewFormat, InterviewRound
from app.models.user import AuthProvider, User, UserTier
from app.services.tracker.notifications import sync_interview_round_reminders


@pytest.mark.integration
@pytest.mark.asyncio
async def test_sync_interview_round_reminders_creates_email_and_in_app(
    db_session,
) -> None:
    user = User(
        id=uuid.uuid4(),
        email="interview@test.com",
        email_canonical="interview@test.com",
        display_name="Test",
        auth_provider=AuthProvider.email,
        password_hash="x",
        tier=UserTier.free,
        accepted_tos_version="test",
    )
    db_session.add(user)
    app = Application(
        id=uuid.uuid4(),
        user_id=user.id,
        jd_title="Engineer",
        jd_company="Acme",
        status=ApplicationStatus.interviewing,
    )
    db_session.add(app)
    await db_session.flush()

    when = datetime.now(timezone.utc) + timedelta(days=3)
    rnd = InterviewRound(
        id=uuid.uuid4(),
        application_id=app.id,
        round_number=1,
        name="Phone screen",
        format=InterviewFormat.video,
        scheduled_at=when,
    )
    db_session.add(rnd)
    await db_session.flush()

    await sync_interview_round_reminders(db_session, app=app, rnd=rnd)
    await db_session.flush()

    rows = (
        await db_session.execute(
            select(Notification).where(
                Notification.user_id == user.id,
                Notification.type.in_(("interview_reminder_24h", "interview_reminder_1h")),
            )
        )
    ).scalars().all()
    assert len(rows) == 4
    channels = {n.channel for n in rows}
    assert channels == {NotificationChannel.in_app, NotificationChannel.email}
    assert all(n.category == "application_interview" for n in rows)
    assert all(str(n.data.get("interview_round_id")) == str(rnd.id) for n in rows)
