#!/usr/bin/env python3
"""Match Career Watch keywords and send pending alert notifications once.

Usage (from ``backend/``, or inside the backend container):

  uv run python scripts/run_career_watch_matcher_once.py
  uv run python scripts/run_career_watch_matcher_once.py --limit 500
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.db.engine import async_session_factory, engine
from app.services.career_watch.matcher import run_matcher


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Max watches / pending alerts to process (default: 200)",
    )
    return parser.parse_args()


async def main() -> None:
    args = _parse_args()
    if args.limit < 1:
        print("ERROR: --limit must be >= 1", file=sys.stderr)
        sys.exit(1)

    async with async_session_factory() as session:
        stats = await run_matcher(session, limit=args.limit)
        await session.commit()

    print("Career Watch matcher complete")
    print(f"  watches_scanned:      {stats.watches_scanned}")
    print(f"  alerts_created:       {stats.alerts_created}")
    print(f"  notifications_sent:   {stats.notifications_sent}")


if __name__ == "__main__":
    asyncio.run(main())
