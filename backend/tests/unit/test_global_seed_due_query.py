"""Tier-aware due query: SQL shape, tier order, and limit fill."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from app.services.career_watch.global_poll_schedule import (
    fetch_due_global_seeds,
    interval_minutes_for_tier,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)


class _RecordingSession:
    def __init__(self, rows_by_call: list[list[object]]) -> None:
        self.statements: list[object] = []
        self._rows = rows_by_call

    async def execute(self, stmt: object) -> MagicMock:
        index = len(self.statements)
        self.statements.append(stmt)
        result = MagicMock()
        result.scalars.return_value = iter(self._rows[index] if index < len(self._rows) else [])
        return result


def _sql(stmt: object) -> str:
    return str(
        stmt.compile(  # type: ignore[attr-defined]
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )


@pytest.mark.asyncio
async def test_queries_tiers_in_order_with_interval_predicate() -> None:
    session = _RecordingSession([[], [], []])
    await fetch_due_global_seeds(session, limit=10, now=NOW)  # type: ignore[arg-type]

    assert len(session.statements) == 3
    for tier, stmt in zip((1, 2, 3), session.statements, strict=True):
        sql = _sql(stmt)
        cutoff = NOW - timedelta(minutes=interval_minutes_for_tier(tier))
        assert f"poll_priority_tier = {tier}" in sql
        assert "last_polled_at IS NULL" in sql
        assert cutoff.strftime("%Y-%m-%d %H:%M:%S") in sql
        assert "NULLS FIRST" in sql
        assert "is_global_seed IS true" in sql
        assert "is_active IS true" in sql


@pytest.mark.asyncio
async def test_tier1_rows_come_before_lower_tiers_and_limit_is_shared() -> None:
    t1 = [object(), object()]
    t2 = [object(), object(), object()]
    session = _RecordingSession([t1, t2, [object()]])
    due = await fetch_due_global_seeds(session, limit=4, now=NOW)  # type: ignore[arg-type]

    assert due == [*t1, t2[0], t2[1]]
    assert len(session.statements) == 2  # limit exhausted before tier 3
    assert "LIMIT 4" in _sql(session.statements[0])
    assert "LIMIT 2" in _sql(session.statements[1])


@pytest.mark.asyncio
async def test_zero_limit_runs_no_queries() -> None:
    session = _RecordingSession([])
    assert await fetch_due_global_seeds(session, limit=0, now=NOW) == []  # type: ignore[arg-type]
    assert session.statements == []
