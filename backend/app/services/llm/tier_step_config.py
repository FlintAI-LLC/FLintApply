"""Admin tier step LLM pins — load, cache refresh, and launch cost policy."""

from __future__ import annotations

import uuid
from typing import Final

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.llm.model_registry import STEP_DEFAULTS, PipelineStep
from app.llm.tier_step_pin_cache import set_tier_step_pins
from app.models.llm_config import LLMProvider
from app.models.tier_step_llm_config import TierStepLLMConfig
from app.services.billing.tier_limits import CANONICAL_PLAN_CODES

log = structlog.get_logger()

# All editable steps for tier pins (excludes inherited / global-only).
_FREE_TIER_EDITABLE_STEPS: list[str] = [
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

_GEMINI_FLASH_LITE: Final = ("gemini", "gemini-3.5-flash-lite")
_DEEPSEEK_V4_FLASH: Final = ("deepseek", "deepseek-v4-flash")
_GEMINI_FLASH: Final = ("gemini", "gemini-3.5-flash")

_POLICY_NOTES: Final = "Launch cost policy: free=lite+deepseek; paid=gemini flash on deliverables"

# Free: cheapest mix — Flash Lite for light steps, DeepSeek for deliverables.
_FREE_STEP_ROUTES: dict[str, tuple[str, str]] = {
    "resume_structure": _GEMINI_FLASH_LITE,
    "phase1_keywords": _GEMINI_FLASH_LITE,
    "phase2_audit": _GEMINI_FLASH_LITE,
    "phase4_qa": _GEMINI_FLASH_LITE,
    "mechanical_fixes": _GEMINI_FLASH_LITE,
    "job_fit": _GEMINI_FLASH_LITE,
    "job_title_suggestions": _GEMINI_FLASH_LITE,
    "story_verify": _GEMINI_FLASH_LITE,
    "chat": _GEMINI_FLASH_LITE,
    "checkup": _GEMINI_FLASH_LITE,
    "phase3_rewrite": _DEEPSEEK_V4_FLASH,
    "polish": _DEEPSEEK_V4_FLASH,
    "cover_letter": _DEEPSEEK_V4_FLASH,
    "story": _DEEPSEEK_V4_FLASH,
    "story_coach": _DEEPSEEK_V4_FLASH,
    "story_interview": _DEEPSEEK_V4_FLASH,
}

_PAID_PREMIUM_STEPS: frozenset[str] = frozenset({"phase3_rewrite", "polish"})

_PAID_PLAN_CODES: frozenset[str] = CANONICAL_PLAN_CODES - {"free"}


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


async def _active_tier_pin(
    session: AsyncSession,
    *,
    plan_code: str,
    step: str,
) -> TierStepLLMConfig | None:
    return (
        await session.execute(
            select(TierStepLLMConfig)
            .where(TierStepLLMConfig.plan_code == plan_code)
            .where(TierStepLLMConfig.step == step)
            .where(TierStepLLMConfig.is_active.is_(True))
        )
    ).scalars().first()


async def _upsert_tier_step_pin_policy(
    session: AsyncSession,
    *,
    plan_code: str,
    step: str,
    provider: str,
    model_string: str,
    notes: str,
) -> bool:
    """Set active tier pin when missing or wrong. Returns True if a new row was added."""
    try:
        provider_enum = LLMProvider(provider)
    except ValueError:
        log.warning(
            "tier_step_llm_config.invalid_provider",
            plan_code=plan_code,
            step=step,
            provider=provider,
        )
        return False

    current = await _active_tier_pin(session, plan_code=plan_code, step=step)
    if (
        current is not None
        and current.provider == provider_enum
        and current.model_string == model_string
    ):
        return False

    if current is not None:
        current.is_active = False

    session.add(
        TierStepLLMConfig(
            id=uuid.uuid4(),
            plan_code=plan_code,
            step=step,
            provider=provider_enum,
            model_string=model_string,
            is_active=True,
            notes=notes,
            created_by_admin_id=None,
        )
    )
    return True


async def apply_tier_llm_cost_policy(session: AsyncSession) -> int:
    """Apply free (lite + DeepSeek) and paid (Gemini Flash deliverables + DeepSeek) pins."""
    updated = 0
    for step, (provider, model) in _FREE_STEP_ROUTES.items():
        if await _upsert_tier_step_pin_policy(
            session,
            plan_code="free",
            step=step,
            provider=provider,
            model_string=model,
            notes=_POLICY_NOTES,
        ):
            updated += 1

    for plan_code in sorted(_PAID_PLAN_CODES):
        for step in _FREE_TIER_EDITABLE_STEPS:
            if step in _PAID_PREMIUM_STEPS:
                provider, model = _GEMINI_FLASH
            else:
                provider, model = _DEEPSEEK_V4_FLASH
            if await _upsert_tier_step_pin_policy(
                session,
                plan_code=plan_code,
                step=step,
                provider=provider,
                model_string=model,
                notes=_POLICY_NOTES,
            ):
                updated += 1

    if updated:
        await session.flush()
        log.info("tier_step_llm_config.cost_policy_applied", rows_written=updated)
    else:
        log.info("tier_step_llm_config.cost_policy_already_current")
    return updated


async def seed_free_tier_deepseek_pins_if_empty(session: AsyncSession) -> int:
    """Legacy entrypoint — applies full tier LLM cost policy (free + paid)."""
    return await apply_tier_llm_cost_policy(session)


__all__ = [
    "apply_tier_llm_cost_policy",
    "load_active_tier_step_pins",
    "refresh_tier_step_pin_cache",
    "seed_free_tier_deepseek_pins_if_empty",
]
