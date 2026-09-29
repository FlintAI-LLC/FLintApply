"""Discover ATS board candidates from SimplifyJobs listing JSON feeds."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
OUTPUT = BACKEND_ROOT / "data" / "job_corpus" / "candidates.jsonl"

from scripts.corpus.ats_url_parse import USER_AGENT, dedupe_key, parse_ats_url

SOURCES: tuple[tuple[str, str], ...] = (
    (
        "simplify_new_grad",
        "https://raw.githubusercontent.com/SimplifyJobs/New-Grad-Positions/dev/.github/scripts/listings.json",
    ),
    (
        "simplify_summer2026",
        "https://raw.githubusercontent.com/SimplifyJobs/Summer2026-Internships/dev/.github/scripts/listings.json",
    ),
    (
        "vanshb03_summer2026",
        "https://raw.githubusercontent.com/vanshb03/Summer2026-Internships/dev/.github/scripts/listings.json",
    ),
)


def _load_existing_keys(path: Path) -> set[tuple[str, str]]:
    if not path.is_file():
        return set()
    keys: set[tuple[str, str]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        ats = str(row.get("ats_type") or "")
        token = str(row.get("token") or "")
        if ats and token:
            keys.add((ats, token.lower()))
    return keys


def _append_rows(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def discover_from_listings(payload: object, *, source: str) -> list[dict]:
    if not isinstance(payload, list):
        return []
    now = datetime.now(timezone.utc).isoformat()
    by_key: dict[tuple[str, str], dict] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or item.get("apply_url") or "")
        parsed = parse_ats_url(url)
        if parsed is None:
            continue
        key = dedupe_key(parsed)
        row = by_key.get(key)
        if row is None:
            row = {
                "token": parsed.token,
                "ats_type": parsed.ats_type,
                "source": source,
                "discovered_at": now,
                "categories": [],
            }
            name = item.get("company_name") or item.get("company")
            if isinstance(name, str) and name.strip():
                row["name"] = name.strip()
            by_key[key] = row
        category = item.get("category")
        if isinstance(category, str) and category.strip():
            value = category.strip()
            if value not in row["categories"]:
                row["categories"].append(value)
    for row in by_key.values():
        if row["categories"]:
            row["category"] = row["categories"][0]
    return list(by_key.values())


async def fetch_json(client: httpx.AsyncClient, url: str) -> object | None:
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return None
        return resp.json()
    except (httpx.HTTPError, json.JSONDecodeError):
        return None


async def run(*, output: Path = OUTPUT) -> int:
    existing = _load_existing_keys(output)
    headers = {"User-Agent": USER_AGENT}
    added = 0
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0), headers=headers) as client:
        for source_id, url in SOURCES:
            payload = await fetch_json(client, url)
            if payload is None:
                # retry once
                payload = await fetch_json(client, url)
            if payload is None:
                print(f"[discover_simplifyjobs] skip unreachable: {source_id}", file=sys.stderr)
                continue
            batch: list[dict] = []
            for row in discover_from_listings(payload, source=source_id):
                key = (row["ats_type"], str(row["token"]).lower())
                if key in existing:
                    continue
                existing.add(key)
                batch.append(row)
            if batch:
                _append_rows(output, batch)
                added += len(batch)
            print(f"[discover_simplifyjobs] {source_id}: +{len(batch)} rows")
    print(f"[discover_simplifyjobs] total appended this run: {added}")
    return added


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover corpus candidates from SimplifyJobs JSON")
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT,
        help="JSONL output path",
    )
    args = parser.parse_args()
    import asyncio

    asyncio.run(run(output=args.output))


if __name__ == "__main__":
    main()
