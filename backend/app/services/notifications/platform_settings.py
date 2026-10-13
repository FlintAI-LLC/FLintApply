"""Platform-wide notification settings (admin UI)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notifications import NotificationPlatformSettings

_DEFAULT_DIGEST_HOUR = 18
_SINGLETON_KEY = "default"


async def get_notification_platform_settings(
    session: AsyncSession,
) -> NotificationPlatformSettings:
    row = (
        await session.execute(
            select(NotificationPlatformSettings).where(
                NotificationPlatformSettings.singleton_key == _SINGLETON_KEY
            )
        )
    ).scalar_one_or_none()
    if row is not None:
        return row
    row = NotificationPlatformSettings(
        id=uuid.uuid4(),
        singleton_key=_SINGLETON_KEY,
        job_alert_digest_hour_local=_DEFAULT_DIGEST_HOUR,
        updated_at=datetime.now(timezone.utc),
    )
    session.add(row)
    await session.flush()
    return row


async def get_job_alert_digest_hour_local(session: AsyncSession) -> int:
    """Hour (0–23) when daily job-alert digests send in each user's local timezone."""
    settings = await get_notification_platform_settings(session)
    hour = settings.job_alert_digest_hour_local
    if hour < 0 or hour > 23:
        return _DEFAULT_DIGEST_HOUR
    return hour


__all__ = [
    "get_job_alert_digest_hour_local",
    "get_notification_platform_settings",
]
