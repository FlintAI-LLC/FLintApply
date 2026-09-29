#!/usr/bin/env python3
"""Delete expired job_cache rows not referenced by saved_jobs."""

from __future__ import annotations

import argparse
import asyncio
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.engine import async_session_factory
from app.models.jobs import JobCache, SavedJob

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


async def run(
    *,
    apply: bool,
    session_factory: SessionFactory = async_session_factory,
    now: datetime | None = None,
) -> int:
    """Return the number of deletable (dry-run) or deleted (apply) rows."""
    cutoff = now or datetime.now(timezone.utc)
    saved_ids = select(SavedJob.job_cache_id).where(SavedJob.job_cache_id.is_not(None))
    # Predicate-based delete: an id list would exceed the driver bind-parameter limit.
    deletable = (JobCache.expires_at < cutoff, JobCache.id.not_in(saved_ids))

    async with session_factory() as session:
        if not apply:
            count = await session.execute(
                select(func.count()).select_from(JobCache).where(*deletable)
            )
            return int(count.scalar_one())
        result = await session.execute(delete(JobCache).where(*deletable))
        await session.commit()
        return int(result.rowcount or 0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Perform deletes (default dry-run)")
    args = parser.parse_args()
    count = asyncio.run(run(apply=args.apply))
    print(f"expired_deletable={count} apply={args.apply}")


if __name__ == "__main__":
    main()
