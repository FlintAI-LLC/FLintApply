"""Story coach credit timing and tier gates."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.billing.quota import (
    assert_story_coach_credit_affordable,
    has_active_subscription,
    story_coach_should_charge_credit,
)


@pytest.mark.asyncio
async def test_story_coach_should_not_charge_subscriber() -> None:
    mock_db = AsyncMock()
    mock_user = MagicMock(is_suspended=False, id="user-1")
    with patch(
        "app.services.billing.quota.has_active_subscription",
        new_callable=AsyncMock,
        return_value=True,
    ):
        assert not await story_coach_should_charge_credit(
            mock_db,
            user=mock_user,
            session_id="sess-1",
            history_len=0,
            coach_mode="whole_story",
        )


@pytest.mark.asyncio
async def test_story_coach_should_not_charge_follow_up_exchange() -> None:
    mock_db = AsyncMock()
    mock_user = MagicMock(is_suspended=False, id="user-1")
    with patch(
        "app.services.billing.quota.has_active_subscription",
        new_callable=AsyncMock,
        return_value=False,
    ):
        assert not await story_coach_should_charge_credit(
            mock_db,
            user=mock_user,
            session_id="sess-1",
            history_len=2,
            coach_mode="segment",
        )


@pytest.mark.asyncio
async def test_story_coach_should_charge_first_whole_story_call() -> None:
    mock_db = AsyncMock()
    mock_user = MagicMock(is_suspended=False, id="user-1")
    with patch(
        "app.services.billing.quota.has_active_subscription",
        new_callable=AsyncMock,
        return_value=False,
    ), patch(
        "app.services.billing.quota._story_coach_build_already_charged",
        new_callable=AsyncMock,
        return_value=False,
    ):
        assert await story_coach_should_charge_credit(
            mock_db,
            user=mock_user,
            session_id="sess-1",
            history_len=0,
            coach_mode="whole_story",
        )


@pytest.mark.asyncio
async def test_assert_story_coach_credit_affordable_raises_when_empty() -> None:
    from app.services.billing.exceptions import InsufficientCreditsError

    mock_db = AsyncMock()
    mock_user = MagicMock(id="user-1")
    with patch(
        "app.services.billing.quota.get_balance",
        new_callable=AsyncMock,
        return_value=0,
    ):
        with pytest.raises(InsufficientCreditsError):
            await assert_story_coach_credit_affordable(mock_db, user=mock_user)


@pytest.mark.asyncio
async def test_has_active_subscription_false_without_sub() -> None:
    mock_db = AsyncMock()
    mock_user = MagicMock(id="user-1")
    with patch(
        "app.services.billing.quota._active_subscription_for",
        new_callable=AsyncMock,
        return_value=None,
    ):
        assert not await has_active_subscription(mock_db, user=mock_user)
