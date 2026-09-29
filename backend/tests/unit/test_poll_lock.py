"""Advisory lock guard for overlapping corpus poll runs."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.career_watch.poll_lock import LOCK_KEY, try_poll_lock

pytestmark = pytest.mark.unit


class _FakeEngine:
    def __init__(self, *, lock_granted: bool) -> None:
        self.conn = MagicMock()
        self.calls: list[str] = []
        self.params: list[dict[str, object] | None] = []

        async def execute(stmt, params=None):
            sql = str(stmt)
            self.calls.append(sql)
            self.params.append(params)
            result = MagicMock()
            result.scalar.return_value = lock_granted
            return result

        self.conn.execute = AsyncMock(side_effect=execute)

    @asynccontextmanager
    async def connect(self):
        yield self.conn


@pytest.mark.asyncio
async def test_lock_acquired_then_released() -> None:
    engine = _FakeEngine(lock_granted=True)
    async with try_poll_lock(engine) as acquired:  # type: ignore[arg-type]
        assert acquired is True
        assert any("pg_try_advisory_lock" in c for c in engine.calls)
        assert not any("pg_advisory_unlock" in c for c in engine.calls)
    assert any("pg_advisory_unlock" in c for c in engine.calls)
    assert engine.params == [{"key": LOCK_KEY}, {"key": LOCK_KEY}]


@pytest.mark.asyncio
async def test_lock_held_by_other_run_yields_false_and_does_not_unlock() -> None:
    engine = _FakeEngine(lock_granted=False)
    async with try_poll_lock(engine) as acquired:  # type: ignore[arg-type]
        assert acquired is False
    assert not any("pg_advisory_unlock" in c for c in engine.calls)


@pytest.mark.asyncio
async def test_lock_released_when_body_raises() -> None:
    engine = _FakeEngine(lock_granted=True)
    with pytest.raises(RuntimeError):
        async with try_poll_lock(engine):  # type: ignore[arg-type]
            raise RuntimeError("poll blew up")
    assert any("pg_advisory_unlock" in c for c in engine.calls)


def test_lock_key_is_stable() -> None:
    assert LOCK_KEY == "flintapply_job_corpus_poll"
