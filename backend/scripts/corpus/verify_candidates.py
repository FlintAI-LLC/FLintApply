#!/usr/bin/env python3
"""Verify discovered candidates and classify them as accept / omit / quarantine.

Usage (from ``backend/``):

  uv run python scripts/corpus/verify_candidates.py
  uv run python scripts/corpus/verify_candidates.py --include-yc --limit 500

Reads ``data/job_corpus/candidates.jsonl`` and writes ``probe_cache.jsonl`` and
``quarantine.json`` next to it. Accepted results are consumed by
``generate_job_corpus_seed.py``. YC-sourced slug probes are opt-in.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.career_watch.corpus_verify import (  # noqa: E402
    QUARANTINE,
    Candidate,
    ProbeCache,
    ProbeResult,
    verify_candidates,
)

DATA_DIR = BACKEND_ROOT / "data" / "job_corpus"
CANDIDATES = DATA_DIR / "candidates.jsonl"
PROBE_CACHE = DATA_DIR / "probe_cache.jsonl"
QUARANTINE_PATH = DATA_DIR / "quarantine.json"
PINNED_BASELINE = DATA_DIR / "seed_2000.json.bak"
SUPPORTED_ATS = frozenset({"greenhouse", "lever", "ashby", "smartrecruiters", "workable", "recruitee"})


def load_candidates(path: Path, *, include_yc: bool) -> list[Candidate]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict):
            continue
        ats, token = str(row.get("ats_type") or ""), str(row.get("token") or "")
        source = str(row.get("source") or "")
        if ats not in SUPPORTED_ATS or not token:
            continue
        if source == "yc_oss" and not include_yc:
            continue
        entry = merged.setdefault(
            (ats, token.lower()),
            {"token": token, "source": source, "name": row.get("name"), "categories": []},
        )
        for cat in row.get("categories") or ([row["category"]] if row.get("category") else []):
            if cat not in entry["categories"]:
                entry["categories"].append(cat)
        prov = row.get("provenance") or {}
        entry.setdefault("industries", prov.get("industries"))
        entry.setdefault("tags", prov.get("tags"))
    return [
        Candidate(
            ats_type=key[0],
            token=data["token"],
            source=data["source"],
            name=data.get("name"),
            categories=tuple(data["categories"]),
            industries=data.get("industries"),
            tags=data.get("tags"),
        )
        for key, data in merged.items()
    ]


def deadline_stop(
    max_seconds: float | None, clock: Callable[[], float] = time.monotonic
) -> Callable[[], bool]:
    """Return a should_stop predicate that turns true once max_seconds have elapsed."""
    if not max_seconds:
        return lambda: False
    started = clock()
    return lambda: clock() - started >= max_seconds


def pinned_keys(path: Path) -> set[tuple[str, str]]:
    if not path.is_file():
        return set()
    rows = json.loads(path.read_text(encoding="utf-8"))
    return {(r["ats_type"], str(r["ats_board_token"]).lower()) for r in rows}


def _tier1_slugs() -> tuple[str, ...]:
    from scripts.generate_job_corpus_seed import TIER1_SLUGS

    return TIER1_SLUGS


async def run(args: argparse.Namespace) -> None:
    candidates = load_candidates(args.candidates, include_yc=args.include_yc)
    if not args.reverify:
        pinned = pinned_keys(args.pinned)
        candidates = [c for c in candidates if c.key not in pinned]
    if args.limit:
        candidates = candidates[: args.limit]

    cache = ProbeCache(args.cache)
    now = datetime.now(timezone.utc)
    done = 0

    def progress(_: ProbeResult) -> None:
        nonlocal done
        done += 1
        if done % 250 == 0:
            print(f"  verified {done}/{len(candidates)}", flush=True)

    async with httpx.AsyncClient(follow_redirects=False) as client:
        results = await verify_candidates(
            client,
            candidates,
            cache,
            tier1_slugs=_tier1_slugs(),
            now=now,
            on_result=progress,
            on_chunk=cache.save,
            should_stop=deadline_stop(args.max_seconds),
        )
    cache.save()
    if len(results) < len(candidates):
        print(f"stopped at deadline: {len(results)}/{len(candidates)} processed; re-run to continue")

    quarantined = [r for r in results if r.status == QUARANTINE]
    args.quarantine.write_text(
        json.dumps(
            [{"ats_type": r.ats_type, "token": r.token, "reason": r.reason} for r in quarantined],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    by_status = Counter(r.status for r in results)
    reasons = Counter((r.status, r.reason) for r in results)
    print(f"verified={len(results)} {dict(by_status)} cache_hits={sum(r.from_cache for r in results)}")
    for (status, reason), count in reasons.most_common(15):
        print(f"  {status:<10} {reason:<24} {count}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=CANDIDATES)
    parser.add_argument("--cache", type=Path, default=PROBE_CACHE)
    parser.add_argument("--quarantine", type=Path, default=QUARANTINE_PATH)
    parser.add_argument("--pinned", type=Path, default=PINNED_BASELINE)
    parser.add_argument("--include-yc", action="store_true", help="Also probe YC slug guesses")
    parser.add_argument("--reverify", action="store_true", help="Re-probe pinned baseline rows too")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--max-seconds", type=float, default=0, help="Stop between chunks after this long (0 = no limit)"
    )
    args = parser.parse_args()
    if not args.candidates.is_file():
        print(f"ERROR: candidates file not found: {args.candidates}", file=sys.stderr)
        sys.exit(1)
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
