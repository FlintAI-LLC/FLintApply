"""Postgres advisory lock so overlapping corpus poll runs cannot double-poll.

The lock is session-level on a dedicated connection held for the whole run. The
polling session commits independently and must not be used for the lock, since a
commit can hand its connection back to the pool.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

LOCK_KEY = "flintapply_job_corpus_poll"

_TRY_LOCK = text("SELECT pg_try_advisory_lock(hashtext(:key))")
_UNLOCK = text("SELECT pg_advisory_unlock(hashtext(:key))")


@asynccontextmanager
async def try_poll_lock(engine: AsyncEngine) -> AsyncIterator[bool]:
    """Yield True when this run owns the lock, False when another run holds it."""
    async with engine.connect() as conn:
        acquired = bool((await conn.execute(_TRY_LOCK, {"key": LOCK_KEY})).scalar())
        try:
            yield acquired
        finally:
            if acquired:
                await conn.execute(_UNLOCK, {"key": LOCK_KEY})
