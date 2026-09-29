"""TalioCV job corpus seed validation and idempotent loader."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.career_watch import CareerAtsType, WatchedCompany

VALID_ATS_TYPES: frozenset[str] = frozenset(
    {
        "greenhouse",
        "lever",
        "ashby",
        "smartrecruiters",
        "workable",
        "recruitee",
        "breezy",
        "personio",
        "bamboohr",
    }
)
MIN_CORPUS_SIZE = 500
MAX_CORPUS_SIZE = 10_000
# Mirror the watched_companies column sizes so a bad row fails before any batch commits.
MAX_NAME_CHARS = 500
MAX_SLUG_CHARS = 255
MAX_TOKEN_CHARS = 255
TOTAL_TARGET = 2000
PHASE_B_TARGET = 10_000
PHASE_A_MAX = 2000
SHARD_ROWS = 500
MANIFEST_VERSION = 1
MANIFEST_NAME = "seed_manifest.json"
_SHARD_GLOB = "*_shard_*.json"
PROBE_CACHE_TTL_DAYS = 7
STALE_FAIL_DEACTIVATE = 5
TIER1_RATIO = 0.20
TIER2_RATIO = 0.35
PHASE_B_TIER1_RATIO = 0.10
PHASE_B_TIER2_RATIO = 0.20
REQUIRED_FIELDS: tuple[str, ...] = (
    "name",
    "slug",
    "ats_type",
    "ats_board_token",
    "poll_priority_tier",
    "careers_page_url",
)


_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")
_LABEL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]{0,62}")


def token_is_safe(ats_type: str, token: str) -> bool:
    """Board tokens are interpolated into URLs, so only plain identifier characters pass."""
    if not _TOKEN_RE.fullmatch(token):
        return False
    if ats_type == "recruitee":
        return bool(_LABEL_RE.fullmatch(token))
    return True


def tier_targets_for_total(total: int) -> dict[int, int]:
    """Split ``total`` rows across poll tiers.

    Up to Phase A (2,000 rows) the split is 20/35/45. Larger corpora use 10/20/70 so the
    hot tiers stay affordable to poll.
    """
    if total < MIN_CORPUS_SIZE or total > MAX_CORPUS_SIZE:
        raise ValueError(
            f"corpus size must be between {MIN_CORPUS_SIZE} and {MAX_CORPUS_SIZE}, got {total}"
        )
    if total <= PHASE_A_MAX:
        tier1_ratio, tier2_ratio = TIER1_RATIO, TIER2_RATIO
    else:
        tier1_ratio, tier2_ratio = PHASE_B_TIER1_RATIO, PHASE_B_TIER2_RATIO
    tier1 = round(total * tier1_ratio)
    tier2 = round(total * tier2_ratio)
    return {1: tier1, 2: tier2, 3: total - tier1 - tier2}


# Default tier targets for a full 2,000-company corpus.
TIER_TARGETS: dict[int, int] = tier_targets_for_total(TOTAL_TARGET)


def careers_page_url(ats_type: str, board_token: str) -> str:
    """Build the public careers board URL for a supported ATS."""
    token = board_token.strip()
    if ats_type == "greenhouse":
        return f"https://boards.greenhouse.io/{token}"
    if ats_type == "lever":
        return f"https://jobs.lever.co/{token}"
    if ats_type == "ashby":
        return f"https://jobs.ashbyhq.com/{token}"
    if ats_type == "smartrecruiters":
        return f"https://careers.smartrecruiters.com/{token}"
    if ats_type == "workable":
        return f"https://apply.workable.com/{token}"
    if ats_type == "recruitee":
        return f"https://{token}.recruitee.com/"
    if ats_type == "breezy":
        return f"https://{token}.breezy.hr/"
    if ats_type == "personio":
        return f"https://{token}.jobs.personio.com/"
    if ats_type == "bamboohr":
        return f"https://{token}.bamboohr.com/careers"
    raise ValueError(f"unsupported ats_type: {ats_type}")


def read_seed_json(path: Path) -> list[dict[str, Any]]:
    """Load seed rows from ``path``."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("seed file must be a JSON array")
    return raw


def tier_counts(records: list[dict[str, Any]]) -> dict[int, int]:
    counts = {1: 0, 2: 0, 3: 0}
    for row in records:
        tier = row.get("poll_priority_tier")
        if tier in counts:
            counts[int(tier)] += 1
    return counts


def validate_seed_records(
    records: list[dict[str, Any]],
    *,
    require_full_corpus: bool = True,
) -> None:
    """Validate seed corpus invariants; raise ``ValueError`` on failure."""
    total = len(records)
    if require_full_corpus and (total < MIN_CORPUS_SIZE or total > MAX_CORPUS_SIZE):
        raise ValueError(
            f"corpus size must be between {MIN_CORPUS_SIZE} and {MAX_CORPUS_SIZE}, got {total}"
        )
    if not require_full_corpus and not records:
        raise ValueError("seed records must not be empty")

    if require_full_corpus:
        expected = tier_targets_for_total(total)
        counts = tier_counts(records)
        for tier, target in expected.items():
            if counts[tier] != target:
                raise ValueError(
                    f"tier {tier}: expected {target} rows, got {counts[tier]}"
                )

    slugs: set[str] = set()
    for index, row in enumerate(records):
        if not isinstance(row, dict):
            raise ValueError(f"row {index} is not an object")

        missing = [field for field in REQUIRED_FIELDS if field not in row]
        if missing:
            raise ValueError(f"row {index} missing fields: {', '.join(missing)}")

        slug = str(row["slug"]).strip().lower()
        if slug != row["slug"]:
            raise ValueError(f"row {index} slug must be lowercase: {row['slug']!r}")
        if len(slug) > MAX_SLUG_CHARS:
            raise ValueError(f"row {index} slug exceeds {MAX_SLUG_CHARS} chars")
        if len(str(row["name"])) > MAX_NAME_CHARS:
            raise ValueError(f"row {index} name exceeds {MAX_NAME_CHARS} chars")
        if slug in slugs:
            raise ValueError(f"duplicate slug: {slug}")
        slugs.add(slug)

        ats_type = row["ats_type"]
        if ats_type not in VALID_ATS_TYPES:
            raise ValueError(f"row {index} invalid ats_type: {ats_type!r}")

        tier = row["poll_priority_tier"]
        if tier not in (1, 2, 3):
            raise ValueError(f"row {index} invalid poll_priority_tier: {tier!r}")

        token = str(row["ats_board_token"])
        if not token.strip():
            raise ValueError(f"row {index} empty ats_board_token")
        # Validate the exact stored value; stripping first would let "acme\n" through.
        if len(token) > MAX_TOKEN_CHARS or not token_is_safe(ats_type, token):
            raise ValueError(f"row {index} unsafe ats_board_token: {token!r}")

        expected_url = careers_page_url(ats_type, token)
        if row["careers_page_url"] != expected_url:
            raise ValueError(
                f"row {index} careers_page_url mismatch for {slug}: "
                f"expected {expected_url!r}, got {row['careers_page_url']!r}"
            )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_seed_shards(
    records: list[dict[str, Any]],
    out_dir: Path,
    *,
    shard_rows: int = SHARD_ROWS,
) -> Path:
    """Write ``{ats}_shard_{n}.json`` files plus ``seed_manifest.json``; return the manifest path."""
    if shard_rows < 1:
        raise ValueError("shard_rows must be a positive integer")
    out_dir.mkdir(parents=True, exist_ok=True)
    for stale in out_dir.glob(_SHARD_GLOB):
        stale.unlink()

    by_ats: dict[str, list[dict[str, Any]]] = {}
    for row in sorted(records, key=lambda r: (r["ats_type"], r["slug"])):
        by_ats.setdefault(row["ats_type"], []).append(row)

    shards: list[dict[str, Any]] = []
    for ats_type, rows in by_ats.items():
        for number, offset in enumerate(range(0, len(rows), shard_rows)):
            chunk = rows[offset : offset + shard_rows]
            name = f"{ats_type}_shard_{number}.json"
            path = out_dir / name
            path.write_text(json.dumps(chunk, indent=2) + "\n", encoding="utf-8")
            shards.append({"path": name, "rows": len(chunk), "sha256": _sha256_file(path)})

    manifest = {
        "version": MANIFEST_VERSION,
        "total": len(records),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "shards": shards,
    }
    manifest_path = out_dir / MANIFEST_NAME
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def _shard_path(base: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or len(pure.parts) != 1:
        raise ValueError(f"invalid shard path in manifest: {relative!r}")
    return base / pure.name


def read_seed_manifest(manifest_path: Path) -> list[dict[str, Any]]:
    """Concatenate shards after verifying version, hashes, row counts, and totals."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be a JSON object")
    if manifest.get("version") != MANIFEST_VERSION:
        raise ValueError(f"unsupported manifest version: {manifest.get('version')!r}")
    shards = manifest.get("shards")
    if not isinstance(shards, list):
        raise ValueError("manifest shards must be a list")

    base = manifest_path.parent
    records: list[dict[str, Any]] = []
    for shard in shards:
        if not isinstance(shard, dict):
            raise ValueError("manifest shard entries must be objects")
        path = _shard_path(base, str(shard.get("path", "")))
        if not path.is_file():
            raise ValueError(f"shard file missing: {shard.get('path')!r}")
        if _sha256_file(path) != shard.get("sha256"):
            raise ValueError(f"sha256 mismatch for shard {shard.get('path')!r}")
        rows = read_seed_json(path)
        if len(rows) != shard.get("rows"):
            raise ValueError(f"rows mismatch for shard {shard.get('path')!r}")
        records.extend(rows)

    if len(records) != manifest.get("total"):
        raise ValueError(
            f"manifest total {manifest.get('total')} does not match {len(records)} shard rows"
        )
    return records


@dataclass(frozen=True)
class LoadStats:
    inserted: int = 0
    updated: int = 0


def _row_to_company(row: dict[str, Any], *, existing: WatchedCompany | None) -> WatchedCompany:
    if existing is None:
        company = WatchedCompany(
            name=str(row["name"]),
            slug=str(row["slug"]),
            careers_page_url=str(row["careers_page_url"]),
            ats_type=CareerAtsType(str(row["ats_type"])),
            ats_board_token=str(row["ats_board_token"]),
            poll_priority_tier=int(row["poll_priority_tier"]),
            is_global_seed=True,
            is_active=True,
        )
        return company

    existing.name = str(row["name"])
    existing.careers_page_url = str(row["careers_page_url"])
    existing.ats_type = CareerAtsType(str(row["ats_type"]))
    existing.ats_board_token = str(row["ats_board_token"])
    existing.poll_priority_tier = int(row["poll_priority_tier"])
    existing.is_global_seed = True
    return existing


async def _upsert_batch(session: AsyncSession, batch: list[dict[str, Any]]) -> LoadStats:
    inserted = 0
    updated = 0
    slugs = [str(row["slug"]) for row in batch]
    existing_by_slug: dict[str, WatchedCompany] = {}
    chunk_size = 500
    for offset in range(0, len(slugs), chunk_size):
        chunk = slugs[offset : offset + chunk_size]
        result = await session.execute(
            select(WatchedCompany).where(WatchedCompany.slug.in_(chunk))
        )
        for company in result.scalars():
            existing_by_slug[company.slug] = company

    for row in batch:
        existing = existing_by_slug.get(str(row["slug"]))
        if existing is None:
            session.add(_row_to_company(row, existing=None))
            inserted += 1
        else:
            if not existing.is_global_seed:
                continue
            _row_to_company(row, existing=existing)
            updated += 1
    return LoadStats(inserted=inserted, updated=updated)


async def load_seed_records(
    session: AsyncSession,
    records: list[dict[str, Any]],
    *,
    require_full_corpus: bool = True,
    commit_every: int | None = None,
) -> LoadStats:
    """Upsert seed rows into ``watched_companies`` by slug (idempotent).

    The whole set is validated before anything is written. With ``commit_every`` the load
    commits per batch so a 10k load never holds one huge transaction.
    """
    if commit_every is not None and commit_every < 1:
        raise ValueError("commit_every must be a positive integer")
    validate_seed_records(records, require_full_corpus=require_full_corpus)

    batch_size = commit_every or max(len(records), 1)
    inserted = updated = 0
    for offset in range(0, len(records), batch_size):
        stats = await _upsert_batch(session, records[offset : offset + batch_size])
        inserted += stats.inserted
        updated += stats.updated
        if commit_every is not None:
            await session.commit()
    return LoadStats(inserted=inserted, updated=updated)


async def load_seed_file(session: AsyncSession, path: Path) -> LoadStats:
    """Load ``path`` and upsert into ``watched_companies``."""
    records = read_seed_json(path)
    return await load_seed_records(session, records)


__all__ = [
    "LoadStats",
    "MANIFEST_NAME",
    "MAX_CORPUS_SIZE",
    "MIN_CORPUS_SIZE",
    "PHASE_B_TARGET",
    "SHARD_ROWS",
    "REQUIRED_FIELDS",
    "TIER_TARGETS",
    "TOTAL_TARGET",
    "PROBE_CACHE_TTL_DAYS",
    "STALE_FAIL_DEACTIVATE",
    "VALID_ATS_TYPES",
    "careers_page_url",
    "load_seed_file",
    "read_seed_manifest",
    "write_seed_shards",
    "load_seed_records",
    "read_seed_json",
    "tier_counts",
    "tier_targets_for_total",
    "validate_seed_records",
]
