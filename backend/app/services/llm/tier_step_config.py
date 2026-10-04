"""Admin tier step LLM pins — load and cache refresh."""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.model_registry import STEP_DEFAULTS, PipelineStep
from app.llm.tier_step_pin_cache import set_tier_step_pins
from app.models.llm_config import LLMProvider
from app.models.tier_step_llm_config import TierStepLLMConfig

log = structlog.get_logger()

# All editable steps for free-tier DeepSeek seeding.
# Excludes INHERITED_CLIENT_STEPS and GLOBAL_ONLY_STEPS from model_registry.py.
_FREE_TIER_DEEPSEEK_STEPS: list[str] = [
    "resume_structure",
    "phase1_keywords",
    "phase2_audit",
    "phase3_rewrite",
    "phase4_qa",
    "polish",
    "mechanical_fixes",
    "cover_letter",
    "job_fit",
    "job_title_suggestions",
    "story",
    "story_coach",
    "story_interview",
    "story_verify",
    "chat",
    "checkup",
]


def _coerce_step(step: str) -> PipelineStep:
    if step not in STEP_DEFAULTS:
        raise ValueError(f"unknown_pipeline_step:{step}")
    return step  # type: ignore[return-value]


async def load_active_tier_step_pins(session: AsyncSession) -> int:
    """Load active DB tier pins into the in-process cache. Returns pin count."""
    rows = (
        await session.execute(
            select(TierStepLLMConfig).where(TierStepLLMConfig.is_active.is_(True))
        )
    ).scalars().all()
    pins: dict[tuple[str, PipelineStep], tuple[str, str]] = {}
    for row in rows:
        try:
            step = _coerce_step(row.step)
        except ValueError:
            log.warning(
                "tier_step_llm_config.unknown_step_skipped",
                plan_code=row.plan_code,
                step=row.step,
                config_id=str(row.id),
            )
            continue
        pins[(row.plan_code, step)] = (row.provider.value, row.model_string)
    set_tier_step_pins(pins)
    log.info("tier_step_llm_config.cache_loaded", active_pins=len(pins))
    return len(pins)


async def refresh_tier_step_pin_cache(session: AsyncSession) -> int:
    """Reload tier pin cache after an admin write."""
    return await load_active_tier_step_pins(session)


async def seed_free_tier_deepseek_pins_if_empty(session: AsyncSession) -> int:
    """Seed tier_step_llm_configs for the free plan → deepseek-v4-flash.

    Runs at application startup (after migrations, on a fresh async connection
    where asyncpg has a current enum type cache). Skips all steps that already
    have an active row for the free plan, so it is safe to call on every boot.

    Returns the number of rows inserted.
    """
    _PLAN = "free"
    _PROVIDER = LLMProvider.deepseek
    _MODEL = "deepseek-v4-flash"
    _NOTES = "Bootstrapped: free tier cost reduction — DeepSeek over Gemini Flash"

    existing_count = (
        await session.execute(
            select(func.count()).select_from(TierStepLLMConfig).where(
                TierStepLLMConfig.plan_code == _PLAN,
                TierStepLLMConfig.is_active.is_(True),
            )
        )
    ).scalar() or 0

    if existing_count >= len(_FREE_TIER_DEEPSEEK_STEPS):
        log.info(
            "tier_step_llm_config.free_deepseek.already_seeded",
            existing=existing_count,
        )
        return 0

    inserted = 0
    for step in _FREE_TIER_DEEPSEEK_STEPS:
        has_row = (
            await session.execute(
                select(func.count()).select_from(TierStepLLMConfig).where(
                    TierStepLLMConfig.plan_code == _PLAN,
                    TierStepLLMConfig.step == step,
                    TierStepLLMConfig.is_active.is_(True),
                )
            )
        ).scalar() or 0
        if has_row:
            continue
        session.add(
            TierStepLLMConfig(
                id=uuid.uuid4(),
                plan_code=_PLAN,
                step=step,
                provider=_PROVIDER,
                model_string=_MODEL,
                is_active=True,
                notes=_NOTES,
                created_by_admin_id=None,
            )
        )
        inserted += 1

    if inserted:
        await session.flush()
        log.info(
            "tier_step_llm_config.free_deepseek.seeded",
            inserted=inserted,
            plan=_PLAN,
            provider=_PROVIDER.value,
            model=_MODEL,
        )
    return inserted


__all__ = [
    "load_active_tier_step_pins",
    "refresh_tier_step_pin_cache",
    "seed_free_tier_deepseek_pins_if_empty",
]
