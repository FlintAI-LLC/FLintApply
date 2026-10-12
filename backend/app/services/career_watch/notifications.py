"""Career Watch notification delivery (in-app + email/push outbox)."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.career_watch import (
    CareerAlert,
    CareerAlertStatus,
    CareerJobCache,
    UserWatchedCompany,
    WatchedCompany,
)
from app.models.notifications import Notification, NotificationChannel
from app.services.billing.free_tier_budget import user_on_paid_plan
from app.services.career_watch.job_alert_digest import enqueue_job_alert_digest_item
from app.services.notifications.factory import build_notification
from app.services.notifications.preferences import category_enabled, get_or_create_preferences

log = structlog.get_logger("career_watch.notifications")


async def emit_career_watch_alert(session: AsyncSession, alert: CareerAlert) -> bool:
    """Create in-app (+ optional push/email) notifications and mark alert sent."""
    job = await session.get(CareerJobCache, alert.career_job_cache_id)
    if job is None:
        alert.status = CareerAlertStatus.expired
        await session.flush()
        return False

    prefs = await get_or_create_preferences(session, alert.user_id)
    now = datetime.now(timezone.utc)

    title = f"New role: {job.title}"
    body = alert.match_reason or "A watched company posted a matching role."
    data = {
        "career_alert_id": str(alert.id),
        "career_job_cache_id": str(job.id),
        "apply_url": job.apply_url,
        "company_job_title": job.title,
    }

    if category_enabled(prefs, category="job_alerts", channel="in_app"):
        session.add(
            build_notification(
                user_id=alert.user_id,
                type="career_watch_match",
                channel=NotificationChannel.in_app,
                title=title,
                body=body,
                category="job_alerts",
                data=data,
            )
        )

    if prefs.web_push_enabled and category_enabled(
        prefs, category="job_alerts", channel="web_push"
    ):
        session.add(
            build_notification(
                user_id=alert.user_id,
                type="career_watch_match",
                channel=NotificationChannel.web_push,
                title=title,
                body=body,
                category="job_alerts",
                data=data,
            )
        )

    company_name = ""
    watch = await session.get(UserWatchedCompany, alert.user_watched_company_id)
    if watch is not None:
        company = await session.get(WatchedCompany, watch.watched_company_id)
        if company is not None:
            company_name = company.name

    paid_instant = (
        prefs.instant_job_alert_email
        and await user_on_paid_plan(session, user_id=alert.user_id)
    )
    if paid_instant and category_enabled(prefs, category="job_alerts", channel="email"):
        session.add(
            build_notification(
                user_id=alert.user_id,
                type="career_watch_match",
                channel=NotificationChannel.email,
                title=title,
                body=f"{body}\n\nApply: {job.apply_url}",
                category="job_alerts",
                data=data,
                scheduled_at=now,
            )
        )
    else:
        await enqueue_job_alert_digest_item(
            session,
            user_id=alert.user_id,
            now=now,
            title=job.title,
            company_name=company_name,
            apply_url=job.apply_url,
            career_alert_id=alert.id,
        )

    alert.status = CareerAlertStatus.sent
    alert.notified_at = now
    await session.flush()
    log.info(
        "career_watch_alert_sent",
        alert_id=str(alert.id),
        user_id=str(alert.user_id),
    )
    return True


def _in_app_job_alert_filters(user_id: uuid.UUID) -> list:
    """In-app rows shown under the bell for Career Watch / job alerts."""
    return [
        Notification.user_id == user_id,
        Notification.channel == NotificationChannel.in_app,
        Notification.category == "job_alerts",
    ]


async def _remove_in_app_job_alert_notifications(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    career_alert_ids: list[uuid.UUID] | None = None,
    all_job_alerts: bool = False,
) -> int:
    """Remove in-app bell rows when Career Watch alerts are cleared or dismissed."""
    filters = _in_app_job_alert_filters(user_id)
    if all_job_alerts:
        stmt = delete(Notification).where(*filters)
    elif career_alert_ids:
        id_strings = [str(aid) for aid in career_alert_ids]
        stmt = delete(Notification).where(
            *filters,
            Notification.data["career_alert_id"].astext.in_(id_strings),
        )
    else:
        return 0
    result = await session.execute(stmt)
    return int(result.rowcount or 0)


async def dismiss_alert(
    session: AsyncSession,
    *,
    user_id,
    alert_id,
) -> CareerAlert:
    alert = (
        await session.execute(
            select(CareerAlert)
            .where(CareerAlert.id == alert_id)
            .where(CareerAlert.user_id == user_id)
        )
    ).scalar_one_or_none()
    if alert is None:
        raise LookupError("alert not found")
    alert.status = CareerAlertStatus.dismissed
    await _remove_in_app_job_alert_notifications(
        session, user_id=user_id, career_alert_ids=[alert.id]
    )
    await session.flush()
    return alert


_MAX_BULK_DISMISS = 100
_ACTIVE_ALERT_STATUSES = (
    CareerAlertStatus.pending,
    CareerAlertStatus.sent,
)


async def dismiss_alerts(
    session: AsyncSession,
    *,
    user_id,
    alert_ids: list | None = None,
    dismiss_all: bool = False,
) -> int:
    """Dismiss active alerts for ``user_id``. Returns count updated."""
    if dismiss_all:
        stmt = (
            select(CareerAlert)
            .where(CareerAlert.user_id == user_id)
            .where(CareerAlert.status.in_(_ACTIVE_ALERT_STATUSES))
            .limit(_MAX_BULK_DISMISS + 1)
        )
        rows = list((await session.execute(stmt)).scalars().all())
        if len(rows) > _MAX_BULK_DISMISS:
            raise ValueError("too many alerts to dismiss at once")
        for alert in rows:
            alert.status = CareerAlertStatus.dismissed
        if rows:
            await _remove_in_app_job_alert_notifications(
                session,
                user_id=user_id,
                career_alert_ids=[a.id for a in rows],
            )
        await _remove_in_app_job_alert_notifications(
            session,
            user_id=user_id,
            all_job_alerts=True,
        )
        await session.flush()
        return len(rows)

    if not alert_ids:
        raise ValueError("alert_ids required when dismiss_all is false")
    if len(alert_ids) > _MAX_BULK_DISMISS:
        raise ValueError("too many alert_ids")

    unique_ids = list(dict.fromkeys(alert_ids))
    stmt = (
        select(CareerAlert)
        .where(CareerAlert.user_id == user_id)
        .where(CareerAlert.id.in_(unique_ids))
        .where(CareerAlert.status.in_(_ACTIVE_ALERT_STATUSES))
    )
    rows = list((await session.execute(stmt)).scalars().all())
    if len(rows) != len(unique_ids):
        raise LookupError("one or more alerts not found or already dismissed")
    for alert in rows:
        alert.status = CareerAlertStatus.dismissed
    await _remove_in_app_job_alert_notifications(
        session,
        user_id=user_id,
        career_alert_ids=[a.id for a in rows],
    )
    await session.flush()
    return len(rows)


async def clear_career_watch_in_app_notifications(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> int:
    """Remove all in-app job-alert notifications (bell sync)."""
    return await _remove_in_app_job_alert_notifications(
        session,
        user_id=user_id,
        all_job_alerts=True,
    )


__all__ = [
    "clear_career_watch_in_app_notifications",
    "dismiss_alert",
    "dismiss_alerts",
    "emit_career_watch_alert",
]
