"""Tracker notification helpers (Step 29 → Step 31 scheduler)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notifications import (
    Notification,
    NotificationChannel,
    NotificationDeliveryStatus,
)
from app.models.tracker import Application, ApplicationStatus, InterviewRound
from app.services.notifications.factory import build_notification

_INTERVIEW_REMINDER_TYPES = ("interview_reminder_24h", "interview_reminder_1h")


def _company(app: Application) -> str:
    return app.jd_company or "the company"


async def emit_status_change_notifications(
    session: AsyncSession,
    *,
    app: Application,
    old_status: ApplicationStatus,
    new_status: ApplicationStatus,
) -> None:
    if old_status == new_status:
        return

    company = _company(app)
    base_payload = {
        "application_id": str(app.id),
        "company": company,
        "title": app.jd_title,
        "old_status": old_status.value,
        "new_status": new_status.value,
        "url": f"/tracker/{app.id}",
    }

    if new_status == ApplicationStatus.offer:
        headline = f"Congratulations! Log your offer details for {company}"
        session.add(
            build_notification(
                user_id=app.user_id,
                type="application_offer_congrats",
                channel=NotificationChannel.in_app,
                category="application_offer",
                title=headline,
                data={**base_payload, "headline": headline},
            )
        )
        session.add(
            build_notification(
                user_id=app.user_id,
                type="application_offer_congrats",
                channel=NotificationChannel.email,
                category="application_offer",
                title=headline,
                data={**base_payload, "headline": headline},
            )
        )
        return

    if new_status == ApplicationStatus.applied:
        scheduled = datetime.now(timezone.utc)
        headline = f"Any updates on your application at {company}?"
        session.add(
            build_notification(
                user_id=app.user_id,
                type="application_follow_up_idle",
                channel=NotificationChannel.in_app,
                category="application_nudge",
                title=headline,
                scheduled_at=scheduled,
                data={**base_payload, "headline": headline, "idle_days": 14},
            )
        )


async def create_custom_reminder(
    session: AsyncSession,
    *,
    app: Application,
    scheduled_at: datetime,
    message: str,
) -> Notification:
    notification = build_notification(
        user_id=app.user_id,
        type="application_custom_reminder",
        channel=NotificationChannel.in_app,
        category="application_follow_up",
        title=message,
        scheduled_at=scheduled_at,
        data={
            "application_id": str(app.id),
            "company": _company(app),
            "title": app.jd_title,
            "headline": message,
            "url": f"/tracker/{app.id}",
        },
    )
    session.add(notification)
    await session.flush()
    return notification


async def schedule_follow_up_reminder(
    session: AsyncSession,
    *,
    app: Application,
    follow_up_date: datetime,
) -> None:
    headline = f"Time to follow up on your application at {_company(app)}"
    payload = {
        "application_id": str(app.id),
        "company": _company(app),
        "title": app.jd_title,
        "headline": headline,
        "url": f"/tracker/{app.id}",
    }
    session.add(
        build_notification(
            user_id=app.user_id,
            type="application_follow_up",
            channel=NotificationChannel.in_app,
            category="application_follow_up",
            title=headline,
            scheduled_at=follow_up_date,
            data=payload,
        )
    )
    session.add(
        build_notification(
            user_id=app.user_id,
            type="application_follow_up",
            channel=NotificationChannel.email,
            category="application_follow_up",
            title=headline,
            scheduled_at=follow_up_date,
            data=payload,
        )
    )


async def cancel_interview_round_reminders(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    round_id: uuid.UUID,
) -> None:
    await session.execute(
        delete(Notification).where(
            Notification.user_id == user_id,
            Notification.delivery_status == NotificationDeliveryStatus.pending,
            Notification.type.in_(_INTERVIEW_REMINDER_TYPES),
            Notification.data["interview_round_id"].astext == str(round_id),
        )
    )


def _format_interview_when(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%a %b %d, %Y %H:%M UTC")


async def sync_interview_round_reminders(
    session: AsyncSession,
    *,
    app: Application,
    rnd: InterviewRound,
) -> None:
    """Schedule in-app + email interview reminders (24h and 1h before). No SMS."""
    await cancel_interview_round_reminders(
        session, user_id=app.user_id, round_id=rnd.id
    )
    when = rnd.scheduled_at
    if when is None:
        return
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    company = _company(app)
    role = app.jd_title or "your role"
    when_label = _format_interview_when(when)
    base_payload = {
        "application_id": str(app.id),
        "interview_round_id": str(rnd.id),
        "company": company,
        "title": role,
        "round_name": rnd.name,
        "scheduled_at": when.isoformat(),
        "url": f"/tracker/{app.id}",
    }

    offsets: tuple[tuple[str, str, timedelta], ...] = (
        (
            "interview_reminder_24h",
            f"Interview tomorrow: {rnd.name} at {company}",
            timedelta(hours=24),
        ),
        (
            "interview_reminder_1h",
            f"Interview in 1 hour: {rnd.name} at {company}",
            timedelta(hours=1),
        ),
    )
    for ntype, headline, delta in offsets:
        fire_at = when - delta
        if fire_at <= now:
            continue
        body = (
            f"{headline}\n\n"
            f"Role: {role}\n"
            f"When: {when_label}\n"
            f"Open your application: /tracker/{app.id}"
        )
        payload = {**base_payload, "headline": headline}
        for channel in (NotificationChannel.in_app, NotificationChannel.email):
            session.add(
                build_notification(
                    user_id=app.user_id,
                    type=ntype,
                    channel=channel,
                    category="application_interview",
                    title=headline,
                    body=body,
                    scheduled_at=fire_at,
                    data=payload,
                )
            )
