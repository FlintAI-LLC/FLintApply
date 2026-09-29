"""Signup rate limits keyed on IP, device fingerprint, and email domain class."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.services.auth.consumer_email_domains import (
    is_consumer_email,
    is_signup_rate_limit_whitelisted,
)


class SignupRateLimitError(Exception):
    """Signup refused because a network or domain-class limit was exceeded."""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


async def _count_signups(
    session: AsyncSession,
    *,
    since: datetime,
    signup_ip: str,
    device_fingerprint_hash: str | None = None,
) -> int:
    stmt = (
        select(func.count())
        .select_from(User)
        .where(User.created_at >= since)
        .where(User.signup_ip == signup_ip)
    )
    if device_fingerprint_hash is not None:
        stmt = stmt.where(User.signup_device_fingerprint_hash == device_fingerprint_hash)
    return int((await session.execute(stmt)).scalar() or 0)


async def _count_signups_matching_class(
    session: AsyncSession,
    *,
    since: datetime,
    signup_ip: str,
    device_fingerprint_hash: str,
    consumer_class: bool,
) -> int:
    emails = await _list_signup_emails(
        session,
        since=since,
        signup_ip=signup_ip,
        device_fingerprint_hash=device_fingerprint_hash,
    )
    if consumer_class:
        return sum(1 for email in emails if is_consumer_email(email))
    return sum(1 for email in emails if not is_consumer_email(email))


async def _list_signup_emails(
    session: AsyncSession,
    *,
    since: datetime,
    signup_ip: str,
    device_fingerprint_hash: str,
) -> list[str]:
    stmt = (
        select(User.email)
        .where(User.created_at >= since)
        .where(User.signup_ip == signup_ip)
        .where(User.signup_device_fingerprint_hash == device_fingerprint_hash)
    )
    return list((await session.execute(stmt)).scalars().all())


async def fingerprint_usable_for_narrow_limit(
    session: AsyncSession,
    *,
    signup_ip: str,
    device_fingerprint_hash: str | None,
    since: datetime,
) -> bool:
    if not device_fingerprint_hash:
        return False
    collisions = await _count_signups(
        session,
        since=since,
        signup_ip=signup_ip,
        device_fingerprint_hash=device_fingerprint_hash,
    )
    return collisions < settings.SIGNUP_FINGERPRINT_COLLISION_THRESHOLD


async def assert_signup_rate_limit_allowed(
    session: AsyncSession,
    *,
    signup_email: str,
    signup_ip: str,
    device_fingerprint_hash: str | None,
    now: datetime | None = None,
) -> None:
    """Raise ``SignupRateLimitError`` when signup caps are exceeded."""
    if not signup_ip:
        return

    if is_signup_rate_limit_whitelisted(signup_email):
        return

    now = now or datetime.now(timezone.utc)
    day_since = now - timedelta(days=1)

    ip_count = await _count_signups(session, since=day_since, signup_ip=signup_ip)
    if ip_count >= settings.SIGNUP_IP_DAILY_LIMIT:
        raise SignupRateLimitError("signup_ip_daily_limit")

    if not device_fingerprint_hash:
        return

    consumer = is_consumer_email(signup_email)
    if consumer:
        window_since = now - timedelta(days=30)
        limit = settings.SIGNUP_CONSUMER_IP_DEVICE_MONTHLY_LIMIT
        limit_reason = "signup_consumer_monthly_limit"
    else:
        window_since = day_since
        limit = settings.SIGNUP_CORPORATE_IP_DEVICE_DAILY_LIMIT
        limit_reason = "signup_corporate_daily_limit"

    if not await fingerprint_usable_for_narrow_limit(
        session,
        signup_ip=signup_ip,
        device_fingerprint_hash=device_fingerprint_hash,
        since=day_since,
    ):
        return

    class_count = await _count_signups_matching_class(
        session,
        since=window_since,
        signup_ip=signup_ip,
        device_fingerprint_hash=device_fingerprint_hash,
        consumer_class=consumer,
    )
    if class_count >= limit:
        raise SignupRateLimitError(limit_reason)


__all__ = [
    "SignupRateLimitError",
    "assert_signup_rate_limit_allowed",
    "fingerprint_usable_for_narrow_limit",
]
