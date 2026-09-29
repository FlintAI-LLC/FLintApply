#!/usr/bin/env python3
"""Generate the global job corpus seed JSON from verified sources.

The pool is the pinned baseline (already-seeded rows) plus every candidate that
``scripts/corpus/verify_candidates.py`` accepted. Nothing is probed here.

Usage (from ``backend/``):

  uv run python scripts/generate_job_corpus_seed.py
  uv run python scripts/generate_job_corpus_seed.py --target 2000
  uv run python scripts/generate_job_corpus_seed.py --allow-partial
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.career_watch.tech_classifier import classify_titles  # noqa: E402
from app.services.career_watch.job_corpus_seed import (  # noqa: E402
    MAX_CORPUS_SIZE,
    MIN_CORPUS_SIZE,
    TOTAL_TARGET,
    careers_page_url,
    tier_targets_for_total,
    token_is_safe,
    validate_seed_records,
    write_seed_shards,
)

DEFAULT_OUTPUT = BACKEND_ROOT / "data" / "job_corpus" / "seed_2000.json"
DATA_DIR = BACKEND_ROOT / "data" / "job_corpus"
PROBE_CACHE_PATH = DATA_DIR / "probe_cache.jsonl"
CANDIDATES_PATH = DATA_DIR / "candidates.jsonl"
BASELINE_SOURCE = "baseline"
ACCEPT_STATUS = "accept"
OUTPUT_FIELDS: tuple[str, ...] = (
    "name", "slug", "ats_type", "ats_board_token", "poll_priority_tier",
    "careers_page_url", "source", "discovered_at",
)

# Ordered tier-1 slugs (first tier-1 target matches in the pool become tier 1).
TIER1_SLUGS: tuple[str, ...] = (
    "stripe", "openai", "airbnb", "databricks", "coinbase", "figma", "discord",
    "roblox", "reddit", "lyft", "doordash", "instacart", "pinterest", "dropbox",
    "twilio", "block", "asana", "anthropic", "mongodb", "cloudflare", "datadog",
    "brex", "chime", "gusto", "scale-ai", "affirm", "checkr", "flexport", "gitlab",
    "hubspot", "intercom", "klaviyo", "netlify", "okta", "pagerduty", "toast",
    "vercel", "cockroach-labs", "planetscale", "mixpanel", "launchdarkly",
    "amplitude", "nuro", "fivetran", "spotify", "zscaler", "elastic", "notion",
    "linear", "ramp", "mercury", "posthog", "deel", "hightouch", "supabase", "neon",
    "confluent", "temporal", "snowflake", "sentry", "palantir", "plaid", "anduril",
    "spacex", "neuralink", "xai", "waymo", "weave", "webflow", "tailscale", "replit",
    "robinhood", "rubrik", "samsara", "verkada", "oscar-health", "lucid-motors",
    "lucid", "airtable", "sofi",
)

SLUG_OVERRIDES: dict[str, tuple[str, str]] = {
    "andurilindustries": ("anduril", "Anduril"),
    "doordashusa": ("doordash", "DoorDash"),
    "temporaltechnologies": ("temporal", "Temporal"),
    "lucidsoftware": ("lucid", "Lucid"),
    "lucidmotors": ("lucid-motors", "Lucid Motors"),
    "scaleai": ("scale-ai", "Scale AI"),
    "getscale": ("scale-ai", "Scale AI"),
    "cockroachlabs": ("cockroach-labs", "Cockroach Labs"),
    "grafanalabs": ("grafana", "Grafana Labs"),
    "layerzerolabs": ("layerzero", "LayerZero"),
    "weavehealth": ("weave-health", "Weave"),
    "moderntreasury": ("modern-treasury", "Modern Treasury"),
    "generalatlantic": ("general-atlantic", "General Atlantic"),
    "saasgroup": ("saas-group", "SaaS Group"),
    "insightpartners": ("insight-partners", "Insight Partners"),
    "khoslaventures": ("khosla-ventures", "Khosla Ventures"),
    "indexventures": ("index-ventures", "Index Ventures"),
}

DISPLAY_NAMES: dict[str, str] = {
    "a16z": "a16z",
    "xai": "xAI",
    "n26": "N26",
    "1password": "1Password",
    "openai": "OpenAI",
}

ATS_ORDER = {
    "greenhouse": 0,
    "ashby": 1,
    "lever": 2,
    "smartrecruiters": 3,
    "workable": 4,
    "recruitee": 5,
}


@dataclass
class GenerationResult:
    records: list[dict[str, Any]] = field(default_factory=list)
    omitted: list[str] = field(default_factory=list)
    tier_counts: dict[int, int] = field(default_factory=dict)
    pool_size: int = 0


def slug_and_name(token: str) -> tuple[str, str]:
    key = token.lower()
    if key in SLUG_OVERRIDES:
        return SLUG_OVERRIDES[key]
    slug = re.sub(r"[^a-z0-9]+", "-", key).strip("-")
    name = DISPLAY_NAMES.get(slug, slug.replace("-", " ").title())
    return slug, name


def _jsonl_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def load_pinned(path: Path) -> list[dict[str, Any]]:
    """Rows already seeded; kept ahead of new candidates so existing companies never churn."""
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"{path} must be a JSON array")
    rows: list[dict[str, Any]] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        # Rows generated from a candidate source are not baseline; pinning them
        # would freeze earlier selections on every re-run.
        if row.get("source", BASELINE_SOURCE) != BASELINE_SOURCE:
            continue
        token = str(row.get("ats_board_token", ""))
        if not token_is_safe(str(row.get("ats_type", "")), token):
            continue
        rows.append(
            {
                "name": row["name"],
                "slug": row["slug"],
                "ats_type": row["ats_type"],
                "ats_board_token": token,
                "source": BASELINE_SOURCE,
            }
        )
    return rows


def _tech_ratio(titles: Any) -> float:
    if not isinstance(titles, list) or not titles:
        return 0.0
    return classify_titles([str(t) for t in titles]).tech_ratio


def load_accepted(cache_path: Path, candidates_path: Path) -> list[dict[str, Any]]:
    """Accepted probe results joined with discovery provenance."""
    provenance = {
        (str(r.get("ats_type")), str(r.get("token", "")).lower()): r
        for r in _jsonl_rows(candidates_path)
    }
    rows: list[dict[str, Any]] = []
    for entry in _jsonl_rows(cache_path):
        if entry.get("status") != ACCEPT_STATUS:
            continue
        ats_type, token = str(entry.get("ats_type", "")), str(entry.get("token", ""))
        if not token_is_safe(ats_type, token):
            continue
        slug, derived_name = slug_and_name(token)
        if not slug:
            continue
        origin = provenance.get((ats_type, token.lower()), {})
        rows.append(
            {
                "name": entry.get("name") or derived_name,
                "slug": slug,
                "ats_type": ats_type,
                "ats_board_token": token,
                "source": origin.get("source") or "unknown",
                "discovered_at": origin.get("discovered_at") or entry.get("checked_at"),
                "tech_ratio": _tech_ratio(entry.get("titles")),
            }
        )
    return rows


def build_pool(
    pinned: list[dict[str, Any]], accepted: list[dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Slug-keyed pool. Pinned rows win; among new rows the earlier ATS wins."""
    pool: dict[str, dict[str, Any]] = {}
    for row in pinned:
        pool.setdefault(row["slug"], row)
    for row in accepted:
        existing = pool.get(row["slug"])
        if existing is None:
            pool[row["slug"]] = row
        elif (
            existing["source"] != BASELINE_SOURCE
            and ATS_ORDER[row["ats_type"]] < ATS_ORDER[existing["ats_type"]]
        ):
            pool[row["slug"]] = row
    return pool


def _selection_order(pool: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    tier1_first = [pool[s] for s in TIER1_SLUGS if s in pool]
    rest = [row for slug, row in pool.items() if slug not in TIER1_SLUGS]
    pinned = sorted((r for r in rest if r["source"] == BASELINE_SOURCE), key=lambda r: r["slug"])
    # A noisy signal (25 sampled titles), so it ranks rather than filters.
    fresh = sorted(
        (r for r in rest if r["source"] != BASELINE_SOURCE),
        key=lambda r: (-float(r.get("tech_ratio", 0.0)), r["slug"]),
    )
    return tier1_first + pinned + fresh


def select_seed_records(
    pool: dict[str, dict[str, Any]],
    *,
    target: int,
    allow_partial: bool = False,
) -> GenerationResult:
    """Select ``target`` rows with the proportional tier split; fail if the pool is short."""
    if target < MIN_CORPUS_SIZE or target > MAX_CORPUS_SIZE:
        raise ValueError(
            f"target must be between {MIN_CORPUS_SIZE} and {MAX_CORPUS_SIZE}, got {target}"
        )
    if len(pool) < MIN_CORPUS_SIZE:
        raise RuntimeError(
            f"pool has {len(pool)} unique companies; need at least {MIN_CORPUS_SIZE}"
        )
    if len(pool) < target and not allow_partial:
        raise RuntimeError(
            f"pool has {len(pool)} companies but target is {target}; "
            "run verify_candidates for more or pass --allow-partial"
        )

    select_count = min(len(pool), target)
    tier_targets = tier_targets_for_total(select_count)
    tiers: dict[int, list[dict[str, Any]]] = {1: [], 2: [], 3: []}
    for row in _selection_order(pool):
        tier = next((t for t in (1, 2, 3) if len(tiers[t]) < tier_targets[t]), None)
        if tier is None:
            break
        tiers[tier].append({**row, "poll_priority_tier": tier})

    records = [r for tier in (1, 2, 3) for r in tiers[tier]]
    if len(records) != select_count:
        raise RuntimeError(f"selected {len(records)} rows; expected {select_count}")

    finished = [
        {
            **{k: v for k, v in row.items() if k in OUTPUT_FIELDS},
            "careers_page_url": careers_page_url(row["ats_type"], row["ats_board_token"]),
        }
        for row in records
    ]
    selected = {row["slug"] for row in finished}
    return GenerationResult(
        records=finished,
        omitted=sorted(slug for slug in pool if slug not in selected),
        tier_counts={t: len(tiers[t]) for t in (1, 2, 3)},
        pool_size=len(pool),
    )


def generate_seed(
    *,
    pinned_path: Path,
    cache_path: Path,
    candidates_path: Path,
    target: int,
    allow_partial: bool,
) -> GenerationResult:
    pool = build_pool(load_pinned(pinned_path), load_accepted(cache_path, candidates_path))
    result = select_seed_records(pool, target=target, allow_partial=allow_partial)
    validate_seed_records(result.records)
    return result


def write_seed(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def build_meta(
    records: list[dict[str, Any]], seed_path: Path, *, pool_size: int, target: int
) -> dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target": target,
        "total": len(records),
        "pool_size": pool_size,
        "sha256": hashlib.sha256(seed_path.read_bytes()).hexdigest(),
        "tier_counts": dict(Counter(str(r["poll_priority_tier"]) for r in records)),
        "ats_counts": dict(Counter(r["ats_type"] for r in records)),
        "source_counts": dict(Counter(r.get("source", "unknown") for r in records)),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--pinned",
        type=Path,
        default=None,
        help="Existing seed whose rows are kept first (default: the output file)",
    )
    parser.add_argument(
        "--shards-dir",
        type=Path,
        default=None,
        help="Write sharded seed + seed_manifest.json here instead of a single file (Phase B)",
    )
    parser.add_argument("--cache", type=Path, default=PROBE_CACHE_PATH)
    parser.add_argument("--candidates", type=Path, default=CANDIDATES_PATH)
    parser.add_argument(
        "--target",
        type=int,
        default=TOTAL_TARGET,
        help=f"Corpus size target ({MIN_CORPUS_SIZE}-{MAX_CORPUS_SIZE}, default: {TOTAL_TARGET})",
    )
    parser.add_argument(
        "--allow-partial",
        action="store_true",
        help="Write a smaller corpus when the verified pool is short of the target",
    )
    return parser.parse_args()


def write_outputs(
    result: GenerationResult,
    *,
    output: Path,
    shards_dir: Path | None,
    target: int,
) -> list[Path]:
    """Write either a single seed file or shards plus manifest, and a meta file. Returns paths."""
    if shards_dir is None:
        write_seed(output, result.records)
        primary = output
        paths = [output]
    else:
        primary = write_seed_shards(result.records, shards_dir)
        paths = [primary]
    meta_path = primary.with_suffix(".meta.json")
    meta = build_meta(result.records, primary, pool_size=result.pool_size, target=target)
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return [*paths, meta_path]


def main() -> None:
    args = _parse_args()
    result = generate_seed(
        pinned_path=args.pinned or args.output,
        cache_path=args.cache,
        candidates_path=args.candidates,
        target=args.target,
        allow_partial=args.allow_partial,
    )
    written = write_outputs(
        result, output=args.output, shards_dir=args.shards_dir, target=args.target
    )
    print(f"Wrote {len(result.records)} rows (pool {result.pool_size}): {written[0]}")
    print("Tier counts: " + ", ".join(f"tier{t}={n}" for t, n in result.tier_counts.items()))
    print(f"Not selected (verified overflow): {len(result.omitted)}")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
