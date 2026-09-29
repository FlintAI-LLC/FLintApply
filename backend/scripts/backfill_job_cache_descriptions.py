#!/usr/bin/env python3
"""Normalize stale HTML job descriptions in job_cache / career_job_cache."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.engine import async_session_factory
from app.models.career_watch import CareerJobCache
from app.models.jobs import JobCache
from app.parsers.jd_normalize import normalize_job_description
from app.services.career_watch.corpus_sync import _description_hash

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]

# Postgres regex equivalent of "contains a tag or an HTML entity".
_HTML_HINT_SQL = r"<|&([a-zA-Z]+|#[0-9]+|#x[0-9a-fA-F]+);"


@dataclass
class BackfillStats:
    scanned: int = 0
    updated: int = 0
    unchanged: int = 0
    errors: int = 0


@dataclass(frozen=True)
class _Target:
    model: Any
    text_attr: str
    hash_attr: str | None = None


_JOB_CACHE = _Target(JobCache, "description")
_CAREER_JOB_CACHE = _Target(CareerJobCache, "description_text", "description_hash")


def _apply(row: Any, target: _Target, *, dry_run: bool, stats: BackfillStats) -> None:
    stats.scanned += 1
    current = getattr(row, target.text_attr) or ""
    try:
        normalized = normalize_job_description(
            current, max_chars=settings.JD_TEXT_MAX_CHARS
        ).text
    except Exception as exc:  # noqa: BLE001
        stats.errors += 1
        print(f"normalize failed id={row.id}: {exc!r}", file=sys.stderr)
        return
    if normalized == current:
        stats.unchanged += 1
        return
    stats.updated += 1
    if dry_run:
        return
    setattr(row, target.text_attr, normalized)
    if target.hash_attr:
        setattr(row, target.hash_attr, _description_hash(normalized))


async def _backfill_table(
    session: AsyncSession,
    target: _Target,
    *,
    dry_run: bool,
    limit: int | None,
    batch_size: int,
    scan_all: bool,
    stats: BackfillStats,
) -> None:
    """Keyset-paginate so memory stays bounded regardless of table size."""
    id_col = target.model.id
    text_col = getattr(target.model, target.text_attr)
    last_id = None
    remaining = limit
    while remaining is None or remaining > 0:
        page = batch_size if remaining is None else min(batch_size, remaining)
        stmt = select(target.model).order_by(id_col).limit(page)
        if last_id is not None:
            stmt = stmt.where(id_col > last_id)
        if not scan_all:
            stmt = stmt.where(text_col.op("~")(_HTML_HINT_SQL))
        rows = list((await session.execute(stmt)).scalars())
        if not rows:
            return
        last_id = rows[-1].id
        for row in rows:
            _apply(row, target, dry_run=dry_run, stats=stats)
        if not dry_run:
            await session.commit()
        if remaining is not None:
            remaining -= len(rows)


async def run(
    *,
    dry_run: bool,
    limit: int | None,
    batch_size: int,
    career: bool,
    scan_all: bool,
    session_factory: SessionFactory = async_session_factory,
) -> BackfillStats:
    stats = BackfillStats()
    targets = [_JOB_CACHE, *([_CAREER_JOB_CACHE] if career else [])]
    async with session_factory() as session:
        for target in targets:
            await _backfill_table(
                session,
                target,
                dry_run=dry_run,
                limit=limit,
                batch_size=batch_size,
                scan_all=scan_all,
                stats=stats,
            )
    return stats


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Write changes (default is a dry run)")
    mode.add_argument("--dry-run", action="store_true", help="Report only (this is the default)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch-size", type=int, default=200)
    parser.add_argument("--career-job-cache", action="store_true")
    parser.add_argument("--all", action="store_true", help="Normalize every row, not only HTML hints")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    dry_run = not args.apply
    stats = asyncio.run(
        run(
            dry_run=dry_run,
            limit=args.limit,
            batch_size=args.batch_size,
            career=args.career_job_cache,
            scan_all=args.all,
        )
    )
    print(
        f"scanned={stats.scanned} updated={stats.updated} unchanged={stats.unchanged} "
        f"errors={stats.errors} dry_run={dry_run}"
    )


if __name__ == "__main__":
    main()
