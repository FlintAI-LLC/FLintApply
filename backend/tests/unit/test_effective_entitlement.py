"""Effective entitlement helpers."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.user import AuthProvider, User, UserTier
from app.services.billing.effective_entitlement import (
    effective_user_tier,
    is_free_entitlement,
    sync_user_tier_cache,
    user_tier_for_plan_code,
)


def _user(tier: UserTier = UserTier.free) -> User:
    return User(
        id=uuid.uuid4(),
        email="u@example.com",
        email_canonical="u@example.com",
        display_name="U",
        auth_provider=AuthProvider.email,
        password_hash="x",
        tier=tier,
        accepted_tos_version="test",
    )


def test_user_tier_for_plan_code() -> None:
    assert user_tier_for_plan_code("free") == UserTier.free
    assert user_tier_for_plan_code("monthly_pro") == UserTier.pro


@pytest.mark.asyncio
async def test_is_free_entitlement_false_for_paid_plan() -> None:
    user = _user()
    session = AsyncMock()
    with patch(
        "app.services.billing.effective_entitlement.resolve_plan_code_for_user",
        new_callable=AsyncMock,
        return_value="monthly_pro",
    ):
        assert await is_free_entitlement(session, user) is False


@pytest.mark.asyncio
async def test_sync_user_tier_cache_updates_stale_free() -> None:
    user = _user(tier=UserTier.free)
    session = AsyncMock()
    row = MagicMock()
    row.scalar_one_or_none.return_value = user
    session.execute = AsyncMock(return_value=row)

    with patch(
        "app.services.billing.effective_entitlement.resolve_plan_code_for_user",
        new_callable=AsyncMock,
        return_value="monthly_pro",
    ):
        changed = await sync_user_tier_cache(session, user.id)

    assert changed is True
    assert user.tier == UserTier.pro
