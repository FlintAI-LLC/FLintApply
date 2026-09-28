"""Signup IP + device fingerprint rate limit tests."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import AuthProvider, User, UserTier
from app.services.auth.signup_rate_limit import (
    SignupRateLimitError,
    assert_signup_rate_limit_allowed,
    fingerprint_usable_for_narrow_limit,
)

pytestmark = pytest.mark.unit


async def _seed_signup(
    db_session: AsyncSession,
    *,
    email: str,
    signup_ip: str,
    fp_hash: str | None,
    created_at: datetime,
) -> None:
    user = User(
        id=uuid.uuid4(),
        email=email,
        email_canonical=email,
        display_name="Signup",
        auth_provider=AuthProvider.email,
        password_hash="hash",
        tier=UserTier.free,
        signup_ip=signup_ip,
        signup_device_fingerprint_hash=fp_hash,
        accepted_tos_version="2026-06",
        created_at=created_at,
    )
    db_session.add(user)
    await db_session.flush()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_consumer_monthly_limit_blocks_third_gmail_signup(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.auth.signup_rate_limit.settings.SIGNUP_CONSUMER_IP_DEVICE_MONTHLY_LIMIT",
        2,
    )
    monkeypatch.setattr(
        "app.services.auth.signup_rate_limit.settings.SIGNUP_IP_DAILY_LIMIT",
        15,
    )
    now = datetime.now(timezone.utc)
    ip = "198.51.100.44"
    fp = "abc123fingerprinthash"
    for idx in range(2):
        await _seed_signup(
            db_session,
            email=f"user{idx}@gmail.com",
            signup_ip=ip,
            fp_hash=fp,
            created_at=now - timedelta(days=5),
        )

    with pytest.raises(SignupRateLimitError) as exc:
        await assert_signup_rate_limit_allowed(
            db_session,
            signup_email="new@gmail.com",
            signup_ip=ip,
            device_fingerprint_hash=fp,
            now=now,
        )
    assert exc.value.reason == "signup_consumer_monthly_limit"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_corporate_daily_limit_blocks_third_work_signup(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.auth.signup_rate_limit.settings.SIGNUP_CORPORATE_IP_DEVICE_DAILY_LIMIT",
        2,
    )
    monkeypatch.setattr(
        "app.services.auth.signup_rate_limit.settings.SIGNUP_IP_DAILY_LIMIT",
        15,
    )
    now = datetime.now(timezone.utc)
    ip = "198.51.100.55"
    fp = "corp-device-fp"
    for idx in range(2):
        await _seed_signup(
            db_session,
            email=f"user{idx}@example.com",
            signup_ip=ip,
            fp_hash=fp,
            created_at=now - timedelta(hours=1),
        )

    with pytest.raises(SignupRateLimitError) as exc:
        await assert_signup_rate_limit_allowed(
            db_session,
            signup_email="new@example.com",
            signup_ip=ip,
            device_fingerprint_hash=fp,
            now=now,
        )
    assert exc.value.reason == "signup_corporate_daily_limit"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_ip_only_ceiling_blocks_sixteenth_signup(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.auth.signup_rate_limit.settings.SIGNUP_IP_DAILY_LIMIT",
        15,
    )
    now = datetime.now(timezone.utc)
    ip = "198.51.100.66"
    for idx in range(15):
        await _seed_signup(
            db_session,
            email=f"user{idx}@example.com",
            signup_ip=ip,
            fp_hash=f"device-{idx}",
            created_at=now - timedelta(hours=1),
        )

    with pytest.raises(SignupRateLimitError) as exc:
        await assert_signup_rate_limit_allowed(
            db_session,
            signup_email="rate@example.com",
            signup_ip=ip,
            device_fingerprint_hash="brand-new-device",
            now=now,
        )
    assert exc.value.reason == "signup_ip_daily_limit"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_whitelisted_domain_skips_narrow_limits(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.auth.signup_rate_limit.settings.SIGNUP_CONSUMER_IP_DEVICE_MONTHLY_LIMIT",
        2,
    )
    monkeypatch.setattr(
        "app.services.auth.consumer_email_domains.settings.SIGNUP_RATE_LIMIT_WHITELIST_DOMAINS",
        ["partner.edu"],
    )
    now = datetime.now(timezone.utc)
    ip = "198.51.100.77"
    fp = "partner-fp"
    for idx in range(5):
        await _seed_signup(
            db_session,
            email=f"user{idx}@partner.edu",
            signup_ip=ip,
            fp_hash=fp,
            created_at=now - timedelta(days=1),
        )

    await assert_signup_rate_limit_allowed(
        db_session,
        signup_email="another@partner.edu",
        signup_ip=ip,
        device_fingerprint_hash=fp,
        now=now,
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_fingerprint_collision_falls_back_to_ip_only(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.auth.signup_rate_limit.settings.SIGNUP_CORPORATE_IP_DEVICE_DAILY_LIMIT",
        2,
    )
    monkeypatch.setattr(
        "app.services.auth.signup_rate_limit.settings.SIGNUP_IP_DAILY_LIMIT",
        15,
    )
    monkeypatch.setattr(
        "app.services.auth.signup_rate_limit.settings.SIGNUP_FINGERPRINT_COLLISION_THRESHOLD",
        5,
    )
    now = datetime.now(timezone.utc)
    ip = "198.51.100.88"
    fp = "colliding-fingerprint"
    for idx in range(5):
        await _seed_signup(
            db_session,
            email=f"user{idx}@example.com",
            signup_ip=ip,
            fp_hash=fp,
            created_at=now - timedelta(hours=1),
        )

    assert (
        await fingerprint_usable_for_narrow_limit(
            db_session,
            signup_ip=ip,
            device_fingerprint_hash=fp,
            since=now - timedelta(days=1),
        )
        is False
    )

    await assert_signup_rate_limit_allowed(
        db_session,
        signup_email="new@example.com",
        signup_ip=ip,
        device_fingerprint_hash=fp,
        now=now,
    )
