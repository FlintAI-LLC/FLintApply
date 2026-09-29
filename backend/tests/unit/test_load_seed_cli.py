"""Loader CLI: single-file and manifest modes."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.career_watch.job_corpus_seed import (
    careers_page_url,
    tier_targets_for_total,
    write_seed_shards,
)
from scripts import load_job_corpus_seed as loader

pytestmark = pytest.mark.unit


def _rows(total: int = 600) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    i = 0
    for tier, n in tier_targets_for_total(total).items():
        for _ in range(n):
            token = f"t{i:05d}"
            rows.append(
                {
                    "name": token,
                    "slug": token,
                    "ats_type": "greenhouse",
                    "ats_board_token": token,
                    "poll_priority_tier": tier,
                    "careers_page_url": careers_page_url("greenhouse", token),
                }
            )
            i += 1
    return rows


def test_seed_and_manifest_are_mutually_exclusive() -> None:
    with pytest.raises(SystemExit):
        loader.parse_args(["--seed", "a.json", "--manifest", "m.json"])


def test_default_is_single_file_mode() -> None:
    args = loader.parse_args([])
    assert args.manifest is None and args.seed == loader.DEFAULT_SEED


def test_commit_batch_size_is_two_hundred() -> None:
    assert loader.COMMIT_EVERY == 200


def test_manifest_mode_reads_all_shards(tmp_path: Path) -> None:
    manifest = write_seed_shards(_rows(), tmp_path)
    args = loader.parse_args(["--manifest", str(manifest)])
    assert len(loader.read_records(args)) == 600


def test_missing_manifest_is_a_clean_error(tmp_path: Path) -> None:
    args = loader.parse_args(["--manifest", str(tmp_path / "nope.json")])
    with pytest.raises(SystemExit) as exc:
        loader.read_records(args)
    assert exc.value.code == 1
