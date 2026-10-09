"""Admin user tier/plan display aligns with resolve_plan_code_for_user."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.billing import (
    Subscription,
    SubscriptionBillingCycle,
    SubscriptionPlan,
    SubscriptionStatus,
)
from app.models.user import AuthProvider, User, UserTier
from app.services.billing.plan_code_resolver import admin_user_billing_snapshot_for_user


def _user() -> User:
    return User(
        id=uuid.uuid4(),
        email="paid@example.com",
        display_name="Paid",
        auth_provider=AuthProvider.email,
        password_hash="$2b$12$placeholder.placeholder.placeholder.placeholder.placeholder",
        tier=UserTier.free,
        accepted_tos_version="2026-06",
    )


def _active_sub(user_id: uuid.UUID) -> Subscription:
    now = datetime.now(timezone.utc)
    return Subscription(
        id=uuid.uuid4(),
        user_id=user_id,
        plan=SubscriptionPlan.monthly,
        billing_cycle=SubscriptionBillingCycle.recurring,
        status=SubscriptionStatus.active,
        period_start=now - timedelta(days=1),
        period_end=now + timedelta(days=29),
        resumes_used=2,
        stripe_customer_id="cus_test",
        stripe_subscription_id="sub_test",
        stripe_price_id="price_test",
    )


@pytest.mark.asyncio
async def test_admin_snapshot_shows_pro_when_plan_code_is_paid() -> None:
    user = _user()
    session = AsyncMock()

    with (
        patch(
            "app.services.billing.plan_code_resolver.resolve_plan_code_for_user",
            new_callable=AsyncMock,
            return_value="monthly_pro",
        ),
        patch(
            "app.services.billing.plan_code_resolver._active_subscription_for",
            new_callable=AsyncMock,
            return_value=_active_sub(user.id),
        ),
        patch(
            "app.services.billing.plan_code_resolver.get_active_tier_limits",
            new_callable=AsyncMock,
        ) as limits_mock,
    ):
        limits_mock.return_value.resumes_per_period = 25
        snap = await admin_user_billing_snapshot_for_user(session, user)

    assert snap.display_tier == "pro"
    assert snap.plan_label is not None
    assert "active" in snap.plan_label
    assert snap.resumes_used == 2
    assert snap.resumes_limit == 25


@pytest.mark.asyncio
async def test_admin_snapshot_stays_free_without_entitlement() -> None:
    user = _user()
    session = AsyncMock()

    with patch(
        "app.services.billing.plan_code_resolver.resolve_plan_code_for_user",
        new_callable=AsyncMock,
        return_value="free",
    ):
        snap = await admin_user_billing_snapshot_for_user(session, user)

    assert snap.display_tier == "free"
    assert snap.plan_label is None
