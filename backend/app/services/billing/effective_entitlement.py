"""Effective free vs paid entitlement (subscription + grants) and ``users.tier`` cache."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserTier
from app.services.billing.plan_code_resolver import resolve_plan_code_for_user


def user_tier_for_plan_code(plan_code: str) -> UserTier:
    return UserTier.pro if plan_code != "free" else UserTier.free


async def effective_user_tier(session: AsyncSession, user: User) -> UserTier:
    plan_code = await resolve_plan_code_for_user(session, user)
    return user_tier_for_plan_code(plan_code)


async def is_free_entitlement(session: AsyncSession, user: User) -> bool:
    return (await resolve_plan_code_for_user(session, user)) == "free"


async def sync_user_tier_cache(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> bool:
    """Align ``users.tier`` with billing truth. Returns True if the row changed."""
    user = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        return False
    desired = await effective_user_tier(session, user)
    if user.tier == desired:
        return False
    user.tier = desired
    await session.flush()
    return True


__all__ = [
    "effective_user_tier",
    "is_free_entitlement",
    "sync_user_tier_cache",
    "user_tier_for_plan_code",
]
