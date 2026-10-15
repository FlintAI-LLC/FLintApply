"""Tier LLM launch cost policy — free lite+deepseek, paid gemini flash deliverables."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import uuid

from app.llm.tier_step_pin_cache import clear_tier_step_pins_for_tests
from app.models.llm_config import LLMProvider
from app.models.tier_step_llm_config import TierStepLLMConfig
from app.services.llm.tier_step_config import apply_tier_llm_cost_policy

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


@pytest.fixture(autouse=True)
def _clear_tier_cache() -> None:
    clear_tier_step_pins_for_tests()


async def test_cost_policy_free_rewrite_deepseek_chat_lite(
    db_session: AsyncSession,
) -> None:
    await apply_tier_llm_cost_policy(db_session)
    await db_session.commit()

    rows = (
        await db_session.execute(
            select(TierStepLLMConfig).where(
                TierStepLLMConfig.plan_code == "free",
                TierStepLLMConfig.is_active.is_(True),
            )
        )
    ).scalars().all()
    by_step = {r.step: r for r in rows}
    assert by_step["phase3_rewrite"].provider.value == "deepseek"
    assert by_step["phase3_rewrite"].model_string == "deepseek-v4-flash"
    assert by_step["chat"].provider.value == "gemini"
    assert by_step["chat"].model_string == "gemini-3.5-flash-lite"


async def test_cost_policy_paid_rewrite_and_polish_gemini_flash(
    db_session: AsyncSession,
) -> None:
    await apply_tier_llm_cost_policy(db_session)
    await db_session.commit()

    for plan in ("weekly", "monthly_pro"):
        rows = (
            await db_session.execute(
                select(TierStepLLMConfig).where(
                    TierStepLLMConfig.plan_code == plan,
                    TierStepLLMConfig.is_active.is_(True),
                )
            )
        ).scalars().all()
        by_step = {r.step: r for r in rows}
        assert by_step["phase3_rewrite"].model_string == "gemini-3.5-flash"
        assert by_step["polish"].model_string == "gemini-3.5-flash"
        assert by_step["chat"].provider.value == "deepseek"
        assert by_step["chat"].model_string == "deepseek-v4-flash"


async def test_cost_policy_upgrades_mismatched_paid_rewrite(
    db_session: AsyncSession,
) -> None:
    db_session.add(
        TierStepLLMConfig(
            id=uuid.uuid4(),
            plan_code="weekly",
            step="phase3_rewrite",
            provider=LLMProvider.deepseek,
            model_string="deepseek-v4-flash",
            is_active=True,
            notes="old",
        )
    )
    await db_session.flush()

    await apply_tier_llm_cost_policy(db_session)
    await db_session.commit()

    active = (
        await db_session.execute(
            select(TierStepLLMConfig).where(
                TierStepLLMConfig.plan_code == "weekly",
                TierStepLLMConfig.step == "phase3_rewrite",
                TierStepLLMConfig.is_active.is_(True),
            )
        )
    ).scalar_one()
    assert active.model_string == "gemini-3.5-flash"
