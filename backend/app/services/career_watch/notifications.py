"""Career Watch notification delivery (in-app + email/push outbox)."""

from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.career_watch import CareerAlert, CareerAlertStatus, CareerJobCache
from app.models.notifications import NotificationChannel
from app.services.notifications.factory import build_notification

log = structlog.get_logger("career_watch.notifications")


async def emit_career_watch_alert(session: AsyncSession, alert: CareerAlert) -> bool:
    """Create in-app notification and mark alert sent."""
    job = await session.get(CareerJobCache, alert.career_job_cache_id)
    if job is None:
        alert.status = CareerAlertStatus.expired
        await session.flush()
        return False

    title = f"New role: {job.title}"
    body = alert.match_reason or "A watched company posted a matching role."
    notification = build_notification(
        user_id=alert.user_id,
        type="career_watch_match",
        channel=NotificationChannel.in_app,
        title=title,
        body=body,
        category="job_alerts",
        data={
            "career_alert_id": str(alert.id),
            "career_job_cache_id": str(job.id),
            "apply_url": job.apply_url,
            "company_job_title": job.title,
        },
    )
    session.add(notification)
    email_notification = build_notification(
        user_id=alert.user_id,
        type="career_watch_match",
        channel=NotificationChannel.email,
        title=title,
        body=f"{body}\n\nApply: {job.apply_url}",
        category="job_alerts",
        data=notification.data,
    )
    session.add(email_notification)
    push_notification = build_notification(
        user_id=alert.user_id,
        type="career_watch_match",
        channel=NotificationChannel.web_push,
        title=title,
        body=body,
        category="job_alerts",
        data=notification.data,
    )
    session.add(push_notification)
    alert.status = CareerAlertStatus.sent
    alert.notified_at = datetime.now(timezone.utc)
    await session.flush()
    log.info(
        "career_watch_alert_sent",
        alert_id=str(alert.id),
        user_id=str(alert.user_id),
    )
    return True


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
    await session.flush()
    return len(rows)


__all__ = ["dismiss_alert", "dismiss_alerts", "emit_career_watch_alert"]
