"""Discover slug candidates from YC OSS company metadata (probe hints only)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.corpus.ats_url_parse import USER_AGENT

OUTPUT = BACKEND_ROOT / "data" / "job_corpus" / "candidates.jsonl"

YC_ALL = "https://yc-oss.github.io/api/companies/all.json"
YC_HIRING = "https://yc-oss.github.io/api/companies/hiring.json"

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify_name(name: str) -> str:
    return _SLUG_RE.sub("-", name.lower()).strip("-")


def domain_slug(website: str) -> str | None:
    if not website:
        return None
    parsed = urlparse(website if "://" in website else f"https://{website}")
    host = (parsed.netloc or parsed.path or "").lower()
    if host.startswith("www."):
        host = host[4:]
    base = host.split(".")[0] if host else ""
    return base or None


def probe_candidates(company: dict) -> list[tuple[str, str]]:
    """Return (ats_type, token) slug probes for GH/Ashby/Lever only."""
    name = str(company.get("name") or "").strip()
    website = str(company.get("website") or "").strip()
    slugs: list[str] = []
    if name:
        slugs.append(slugify_name(name))
    dom = domain_slug(website)
    if dom:
        slugs.append(dom)
    slugs = [s for s in dict.fromkeys(slugs) if s and len(s) >= 2]
    out: list[tuple[str, str]] = []
    for slug in slugs:
        for ats in ("greenhouse", "ashby", "lever"):
            out.append((ats, slug))
    return out


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


async def fetch_json(client: httpx.AsyncClient, url: str) -> list[dict]:
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return []
        data = resp.json()
        return data if isinstance(data, list) else []
    except (httpx.HTTPError, json.JSONDecodeError):
        return []


async def run(*, output: Path = OUTPUT) -> int:
    existing = _load_existing_keys(output)
    headers = {"User-Agent": USER_AGENT}
    now = datetime.now(timezone.utc).isoformat()
    added = 0
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0), headers=headers) as client:
        companies = await fetch_json(client, YC_ALL)
        hiring = await fetch_json(client, YC_HIRING)
        if hiring:
            hiring_ids = {str(c.get("id")) for c in hiring if isinstance(c, dict)}
            companies = [c for c in companies if str(c.get("id")) in hiring_ids] or companies
        batch: list[dict] = []
        for company in companies:
            if not isinstance(company, dict):
                continue
            provenance = {
                "batch": company.get("batch"),
                "industries": company.get("industries"),
                "tags": company.get("tags"),
            }
            name = str(company.get("name") or "").strip()
            for ats_type, token in probe_candidates(company):
                key = (ats_type, token.lower())
                if key in existing:
                    continue
                existing.add(key)
                row = {
                    "token": token,
                    "ats_type": ats_type,
                    "source": "yc_oss",
                    "discovered_at": now,
                    "name": name or None,
                    "provenance": provenance,
                }
                batch.append({k: v for k, v in row.items() if v is not None})
        if batch:
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("a", encoding="utf-8") as fh:
                for row in batch:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            added = len(batch)
    print(f"[discover_yc] appended {added} probe rows")
    return added


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover YC slug probe candidates")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    import asyncio

    asyncio.run(run(output=args.output))


if __name__ == "__main__":
    main()
