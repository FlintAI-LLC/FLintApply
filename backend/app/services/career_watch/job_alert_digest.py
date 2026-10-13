"""Daily job-alert email digest (one send per user per local calendar day)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notifications import (
    DigestMode,
    Notification,
    NotificationChannel,
    NotificationDeliveryStatus,
)
from app.models.user import User
from app.services.notifications.dispatcher import dispatch_notification
from app.services.notifications.factory import build_notification
from app.services.notifications.preferences import get_or_create_preferences

log = structlog.get_logger("career_watch.job_alert_digest")

_DIGEST_TYPE = "career_watch_daily_digest"
_MAX_ITEMS_PER_EMAIL = 50
_DIGEST_HOUR_LOCAL = 18
_DEFAULT_TZ = "America/Los_Angeles"


def _user_zone(prefs_tz: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(prefs_tz or _DEFAULT_TZ)
    except Exception:  # noqa: BLE001
        return ZoneInfo(_DEFAULT_TZ)


def local_digest_date(now: datetime, tz_name: str | None) -> str:
    return now.astimezone(_user_zone(tz_name)).date().isoformat()


def scheduled_digest_send_utc(now: datetime, tz_name: str | None) -> datetime:
    """6:00 PM local on the digest calendar day containing ``now`` (UTC)."""
    tz = _user_zone(tz_name)
    local = now.astimezone(tz)
    send_local = datetime.combine(local.date(), time(_DIGEST_HOUR_LOCAL, 0), tzinfo=tz)
    return send_local.astimezone(timezone.utc)


async def _find_pending_digest(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    digest_date: str,
) -> Notification | None:
    stmt = (
        select(Notification)
        .where(Notification.user_id == user_id)
        .where(Notification.channel == NotificationChannel.email)
        .where(Notification.type == _DIGEST_TYPE)
        .where(Notification.delivery_status == NotificationDeliveryStatus.pending)
        .where(Notification.data["digest_date"].astext == digest_date)
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def enqueue_job_alert_digest_item(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    now: datetime,
    title: str,
    company_name: str,
    apply_url: str,
    career_alert_id: uuid.UUID,
) -> None:
    """Append a match to the user's pending daily digest (no immediate email)."""
    prefs = await get_or_create_preferences(session, user_id)
    if prefs.digest_mode != DigestMode.daily:
        return

    digest_date = local_digest_date(now, prefs.timezone)
    scheduled_at = scheduled_digest_send_utc(now, prefs.timezone)
    item = {
        "title": title,
        "company": company_name,
        "apply_url": apply_url,
        "career_alert_id": str(career_alert_id),
    }

    row = await _find_pending_digest(session, user_id=user_id, digest_date=digest_date)
    if row is None:
        row = build_notification(
            user_id=user_id,
            type=_DIGEST_TYPE,
            channel=NotificationChannel.email,
            title="Your daily job matches",
            body="",
            category="job_alerts",
            data={"digest_date": digest_date, "items": [item]},
            scheduled_at=scheduled_at,
        )
        session.add(row)
    else:
        items: list[dict[str, Any]] = list((row.data or {}).get("items") or [])
        if len(items) >= _MAX_ITEMS_PER_EMAIL:
            return
        items.append(item)
        payload = dict(row.data or {})
        payload["items"] = items
        row.data = payload
        row.scheduled_at = scheduled_at
    await session.flush()


def _format_digest_body(items: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for entry in items[:_MAX_ITEMS_PER_EMAIL]:
        title = entry.get("title") or "Role"
        company = entry.get("company") or ""
        url = entry.get("apply_url") or ""
        prefix = f"{title}"
        if company:
            prefix = f"{title} — {company}"
        lines.append(f"• {prefix}\n  {url}")
    return "\n\n".join(lines)


@dataclass(frozen=True, slots=True)
class DigestSendStats:
    users_considered: int = 0
    digests_sent: int = 0


async def send_daily_job_alert_digests(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> DigestSendStats:
    """Send pending digests for users whose local time is ≥ 6 PM and digest is due."""
    now_dt = now or datetime.now(timezone.utc)
    pending_rows = (
        await session.execute(
            select(Notification)
            .where(Notification.type == _DIGEST_TYPE)
            .where(Notification.channel == NotificationChannel.email)
            .where(Notification.delivery_status == NotificationDeliveryStatus.pending)
            .where(Notification.scheduled_at <= now_dt)
        )
    ).scalars().all()

    users_considered = 0
    digests_sent = 0
    for row in pending_rows:
        users_considered += 1
        prefs = await get_or_create_preferences(session, row.user_id)
        if prefs.digest_mode != DigestMode.daily:
            row.delivery_status = NotificationDeliveryStatus.failed
            row.error = "digest_disabled"
            continue

        items = list((row.data or {}).get("items") or [])
        if not items:
            row.delivery_status = NotificationDeliveryStatus.failed
            row.error = "empty_digest"
            continue

        row.body = _format_digest_body(items)
        row.title = f"Your daily job matches ({len(items)})"
        row.scheduled_at = now_dt
        await session.flush()
        await dispatch_notification(session, row)
        if row.delivery_status in (
            NotificationDeliveryStatus.sent,
            NotificationDeliveryStatus.delivered,
        ):
            digests_sent += 1
            log.info(
                "career_watch.digest_sent",
                user_id=str(row.user_id),
                item_count=len(items),
            )

    await session.flush()
    return DigestSendStats(
        users_considered=users_considered,
        digests_sent=digests_sent,
    )


__all__ = [
    "DigestSendStats",
    "enqueue_job_alert_digest_item",
    "local_digest_date",
    "scheduled_digest_send_utc",
    "send_daily_job_alert_digests",
]
