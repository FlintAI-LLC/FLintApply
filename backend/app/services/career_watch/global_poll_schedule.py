"""Tier-aware due selection for global seed polling."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.career_watch import WatchedCompany


def interval_minutes_for_tier(tier: int | None) -> int:
    """Map poll_priority_tier to interval minutes."""
    if tier == 1:
        return settings.GLOBAL_POLL_INTERVAL_TIER_1_MINUTES
    if tier == 2:
        return settings.GLOBAL_POLL_INTERVAL_TIER_2_MINUTES
    if tier == 3:
        return settings.GLOBAL_POLL_INTERVAL_TIER_3_MINUTES
    return settings.GLOBAL_POLL_INTERVAL_TIER_2_MINUTES


async def fetch_due_global_seeds(
    session: AsyncSession,
    *,
    limit: int = 50,
    now: datetime | None = None,
) -> list[WatchedCompany]:
    """Return active global seed companies due for tiered polling."""
    now_dt = now or datetime.now(timezone.utc)
    due: list[WatchedCompany] = []
    remaining = limit
    for tier in (1, 2, 3):
        if remaining <= 0:
            break
        interval = interval_minutes_for_tier(tier)
        cutoff = now_dt - timedelta(minutes=interval)
        stmt = (
            select(WatchedCompany)
            .where(WatchedCompany.is_active.is_(True))
            .where(WatchedCompany.is_global_seed.is_(True))
            .where(WatchedCompany.poll_priority_tier == tier)
            .where(
                or_(
                    WatchedCompany.last_polled_at.is_(None),
                    WatchedCompany.last_polled_at <= cutoff,
                )
            )
            .order_by(WatchedCompany.last_polled_at.asc().nullsfirst())
            .limit(remaining)
        )
        rows = list((await session.execute(stmt)).scalars())[:remaining]
        due.extend(rows)
        remaining -= len(rows)
    return due


__all__ = [
    "fetch_due_global_seeds",
    "interval_minutes_for_tier",
]
