"""Sharded seed manifest: write, read, and tamper detection."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.services.career_watch.job_corpus_seed import (
    SHARD_ROWS,
    careers_page_url,
    read_seed_manifest,
    tier_targets_for_total,
    validate_seed_records,
    write_seed_shards,
)

pytestmark = pytest.mark.unit

ATS_CYCLE = ("greenhouse", "ashby", "lever")


def _rows(total: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    index = 0
    for tier, target in tier_targets_for_total(total).items():
        for _ in range(target):
            ats = ATS_CYCLE[index % len(ATS_CYCLE)]
            token = f"tok{index:05d}"
            rows.append(
                {
                    "name": f"Co {index}",
                    "slug": token,
                    "ats_type": ats,
                    "ats_board_token": token,
                    "poll_priority_tier": tier,
                    "careers_page_url": careers_page_url(ats, token),
                }
            )
            index += 1
    return rows


def test_round_trip_preserves_every_row(tmp_path: Path) -> None:
    rows = _rows(2600)
    manifest_path = write_seed_shards(rows, tmp_path)

    loaded = read_seed_manifest(manifest_path)

    assert sorted(r["slug"] for r in loaded) == sorted(r["slug"] for r in rows)
    assert {r["slug"]: r for r in loaded} == {r["slug"]: r for r in rows}
    validate_seed_records(loaded)


def test_shards_are_grouped_by_ats_and_capped(tmp_path: Path) -> None:
    manifest_path = write_seed_shards(_rows(2600), tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["total"] == 2600
    assert all(s["rows"] <= SHARD_ROWS for s in manifest["shards"])
    assert sum(s["rows"] for s in manifest["shards"]) == 2600
    for shard in manifest["shards"]:
        rows = json.loads((tmp_path / shard["path"]).read_text(encoding="utf-8"))
        assert len({r["ats_type"] for r in rows}) == 1
        assert shard["path"].startswith(rows[0]["ats_type"] + "_shard_")


def test_manifest_records_version_and_generation_time(tmp_path: Path) -> None:
    manifest = json.loads(write_seed_shards(_rows(600), tmp_path).read_text(encoding="utf-8"))
    assert manifest["version"] == 1
    assert manifest["generated_at"]


def test_tampered_shard_is_rejected(tmp_path: Path) -> None:
    manifest_path = write_seed_shards(_rows(600), tmp_path)
    shard = tmp_path / json.loads(manifest_path.read_text())["shards"][0]["path"]
    rows = json.loads(shard.read_text())
    rows[0]["name"] = "Tampered"
    shard.write_text(json.dumps(rows), encoding="utf-8")

    with pytest.raises(ValueError, match="sha256"):
        read_seed_manifest(manifest_path)


def test_missing_shard_is_rejected(tmp_path: Path) -> None:
    manifest_path = write_seed_shards(_rows(600), tmp_path)
    (tmp_path / json.loads(manifest_path.read_text())["shards"][0]["path"]).unlink()
    with pytest.raises(ValueError, match="missing"):
        read_seed_manifest(manifest_path)


def test_total_mismatch_is_rejected(tmp_path: Path) -> None:
    manifest_path = write_seed_shards(_rows(600), tmp_path)
    manifest = json.loads(manifest_path.read_text())
    manifest["total"] += 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="total"):
        read_seed_manifest(manifest_path)


def test_row_count_mismatch_is_rejected(tmp_path: Path) -> None:
    manifest_path = write_seed_shards(_rows(600), tmp_path)
    manifest = json.loads(manifest_path.read_text())
    manifest["shards"][0]["rows"] += 1
    manifest["total"] += 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="rows"):
        read_seed_manifest(manifest_path)


@pytest.mark.parametrize("bad_path", ["../outside.json", "/etc/passwd", "sub/../../x.json"])
def test_shard_paths_cannot_escape_the_manifest_directory(tmp_path: Path, bad_path: str) -> None:
    manifest_path = write_seed_shards(_rows(600), tmp_path)
    manifest = json.loads(manifest_path.read_text())
    manifest["shards"][0]["path"] = bad_path
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="path"):
        read_seed_manifest(manifest_path)


def test_unsupported_version_is_rejected(tmp_path: Path) -> None:
    manifest_path = write_seed_shards(_rows(600), tmp_path)
    manifest = json.loads(manifest_path.read_text())
    manifest["version"] = 99
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="version"):
        read_seed_manifest(manifest_path)


def test_rewriting_removes_stale_shards(tmp_path: Path) -> None:
    write_seed_shards(_rows(2600), tmp_path)
    before = {p.name for p in tmp_path.glob("*_shard_*.json")}
    write_seed_shards(_rows(600), tmp_path)
    after = {p.name for p in tmp_path.glob("*_shard_*.json")}
    assert after and after < before


# ---- judge-accepted hardening (S9-SEC-001/003, S9-TEST-013) ----


def _one_row(**overrides: Any) -> list[dict[str, Any]]:
    row = _rows(500)[0]
    row.update(overrides)
    return [row]


@pytest.mark.parametrize("token", ["acme\n", " acme", "acme ", "acme\r\n"])
def test_tokens_with_surrounding_whitespace_are_rejected(token: str) -> None:
    rows = _one_row(ats_board_token=token, slug="acme", ats_type="greenhouse")
    rows[0]["careers_page_url"] = careers_page_url("greenhouse", "acme")
    with pytest.raises(ValueError, match="ats_board_token"):
        validate_seed_records(rows, require_full_corpus=False)


def test_name_longer_than_column_is_rejected() -> None:
    with pytest.raises(ValueError, match="name"):
        validate_seed_records(_one_row(name="x" * 501), require_full_corpus=False)


def test_name_at_column_limit_is_accepted() -> None:
    validate_seed_records(_one_row(name="x" * 500), require_full_corpus=False)


def test_slug_longer_than_column_is_rejected() -> None:
    slug = "s" * 256
    rows = _one_row(slug=slug, ats_board_token=slug[:100], ats_type="greenhouse")
    rows[0]["careers_page_url"] = careers_page_url("greenhouse", slug[:100])
    with pytest.raises(ValueError, match="slug"):
        validate_seed_records(rows, require_full_corpus=False)


def test_token_longer_than_column_is_rejected() -> None:
    token = "t" * 256
    rows = _one_row(slug="short", ats_board_token=token, ats_type="greenhouse")
    rows[0]["careers_page_url"] = careers_page_url("greenhouse", token)
    with pytest.raises(ValueError):
        validate_seed_records(rows, require_full_corpus=False)


@pytest.mark.parametrize("payload", ["[]", "null", '"x"', "1"])
def test_non_object_manifest_raises_value_error(tmp_path: Path, payload: str) -> None:
    manifest = tmp_path / "seed_manifest.json"
    manifest.write_text(payload, encoding="utf-8")
    with pytest.raises(ValueError):
        read_seed_manifest(manifest)


@pytest.mark.parametrize("entry", ['"greenhouse_shard_0.json"', "[]", "null", "3"])
def test_non_object_shard_entry_raises_value_error(tmp_path: Path, entry: str) -> None:
    manifest = tmp_path / "seed_manifest.json"
    manifest.write_text(f'{{"version": 1, "total": 1, "shards": [{entry}]}}', encoding="utf-8")
    with pytest.raises(ValueError):
        read_seed_manifest(manifest)
