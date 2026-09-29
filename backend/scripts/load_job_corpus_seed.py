#!/usr/bin/env python3
"""Load job corpus seed rows into ``watched_companies``.

Usage (from ``backend/``):

  uv run python scripts/load_job_corpus_seed.py
  uv run python scripts/load_job_corpus_seed.py --seed path/to/seed_2000.json
  uv run python scripts/load_job_corpus_seed.py --manifest data/job_corpus/seed/seed_manifest.json
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Any

from app.db.engine import async_session_factory
from app.services.career_watch.job_corpus_seed import (
    load_seed_records,
    read_seed_json,
    read_seed_manifest,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SEED = BACKEND_ROOT / "data" / "job_corpus" / "seed_2000.json"
FALLBACK_SEED = BACKEND_ROOT / "data" / "job_corpus" / "seed_500.json"
COMMIT_EVERY = 200


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--seed",
        type=Path,
        default=DEFAULT_SEED,
        help=f"Single seed JSON path (default: {DEFAULT_SEED})",
    )
    source.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Sharded seed manifest (Phase B); verifies shard hashes before loading",
    )
    return parser.parse_args(argv)


def read_records(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.manifest is not None:
        if not args.manifest.is_file():
            print(f"ERROR: manifest not found: {args.manifest}", file=sys.stderr)
            sys.exit(1)
        try:
            return read_seed_manifest(args.manifest)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            sys.exit(1)

    seed_path: Path = args.seed
    if seed_path == DEFAULT_SEED and not seed_path.is_file() and FALLBACK_SEED.is_file():
        seed_path = FALLBACK_SEED
    if not seed_path.is_file():
        print(f"ERROR: seed file not found: {seed_path}", file=sys.stderr)
        sys.exit(1)
    return read_seed_json(seed_path)


async def main() -> None:
    args = parse_args()
    records = read_records(args)

    async with async_session_factory() as session:
        stats = await load_seed_records(session, records, commit_every=COMMIT_EVERY)

    print("Job corpus seed load complete")
    print(f"  inserted: {stats.inserted}")
    print(f"  updated:  {stats.updated}")


if __name__ == "__main__":
    asyncio.run(main())
