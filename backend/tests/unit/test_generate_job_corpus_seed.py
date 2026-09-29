"""Seed generator: pool building, selection, meta, and the committed seed file."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.services.career_watch.corpus_verify import token_is_safe
from app.services.career_watch.job_corpus_seed import (
    MIN_CORPUS_SIZE,
    read_seed_json,
    tier_targets_for_total,
    validate_seed_records,
)
from scripts import generate_job_corpus_seed as gen

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "job_corpus"
CHECKED_AT = datetime(2026, 9, 29, tzinfo=timezone.utc).isoformat()


def _pinned_row(slug: str, ats: str = "greenhouse") -> dict[str, object]:
    return {
        "name": slug.title(),
        "slug": slug,
        "ats_type": ats,
        "ats_board_token": slug,
        "poll_priority_tier": 3,
        "careers_page_url": f"https://boards.greenhouse.io/{slug}",
    }


def _write_pinned(path: Path, slugs: list[str]) -> None:
    path.write_text(json.dumps([_pinned_row(s) for s in slugs]), encoding="utf-8")


def _cache_line(token: str, *, status: str = "accept", ats: str = "greenhouse", name: str | None = None) -> str:
    return json.dumps(
        {
            "ats_type": ats,
            "token": token,
            "status": status,
            "reason": "auto_pass",
            "checked_at": CHECKED_AT,
            "titles": [],
            "name": name,
        }
    )


def _candidate_line(token: str, *, ats: str = "greenhouse", source: str = "simplify_new_grad") -> str:
    return json.dumps(
        {
            "token": token,
            "ats_type": ats,
            "source": source,
            "discovered_at": CHECKED_AT,
            "categories": ["Software"],
            "name": token.title(),
        }
    )


def _pool(count: int, *, prefix: str = "co") -> dict[str, dict[str, object]]:
    return {
        f"{prefix}{i:04d}": {
            "name": f"Co {i}",
            "slug": f"{prefix}{i:04d}",
            "ats_type": "greenhouse",
            "ats_board_token": f"{prefix}{i:04d}",
            "source": "simplify_new_grad",
        }
        for i in range(count)
    }


# ------------------------------------------------------------- loading


def test_load_accepted_keeps_only_accepted_and_joins_provenance(tmp_path: Path) -> None:
    cache = tmp_path / "cache.jsonl"
    candidates = tmp_path / "cand.jsonl"
    cache.write_text(
        "\n".join(
            [
                _cache_line("goodco", name="Good Co"),
                _cache_line("quarantined", status="quarantine"),
                _cache_line("omitted", status="omit"),
            ]
        ),
        encoding="utf-8",
    )
    candidates.write_text(
        "\n".join(_candidate_line(t, source="vanshb03") for t in ("goodco", "quarantined", "omitted")),
        encoding="utf-8",
    )

    rows = gen.load_accepted(cache, candidates)

    assert [r["slug"] for r in rows] == ["goodco"]
    assert rows[0]["name"] == "Good Co"
    assert rows[0]["source"] == "vanshb03"
    assert rows[0]["discovered_at"] == CHECKED_AT


def test_load_accepted_records_tech_ratio_from_cached_titles(tmp_path: Path) -> None:
    cache = tmp_path / "cache.jsonl"
    strong = json.loads(_cache_line("strongco"))
    strong["titles"] = ["Software Engineer", "Backend Engineer", "Data Scientist", "ML Engineer"]
    weak = json.loads(_cache_line("weakco"))
    weak["titles"] = ["Recruiter", "Account Executive", "Office Manager", "Nurse"]
    bare = json.loads(_cache_line("bareco"))
    cache.write_text("\n".join(json.dumps(x) for x in (strong, weak, bare)), encoding="utf-8")

    ratios = {r["slug"]: r["tech_ratio"] for r in gen.load_accepted(cache, tmp_path / "none.jsonl")}

    assert ratios["strongco"] > ratios["weakco"]
    assert ratios["weakco"] == 0.0
    assert ratios["bareco"] == 0.0


def test_load_accepted_drops_unsafe_tokens(tmp_path: Path) -> None:
    cache = tmp_path / "cache.jsonl"
    cache.write_text(
        "\n".join(_cache_line(t) for t in ("ok-token", "../evil", "a b", "x/../../y", "trail\n", "")),
        encoding="utf-8",
    )
    rows = gen.load_accepted(cache, tmp_path / "missing.jsonl")
    assert [r["ats_board_token"] for r in rows] == ["ok-token"]


def test_load_accepted_tolerates_garbage_lines(tmp_path: Path) -> None:
    cache = tmp_path / "cache.jsonl"
    cache.write_text("not json\n" + _cache_line("fine") + "\n{}\n", encoding="utf-8")
    assert [r["slug"] for r in gen.load_accepted(cache, tmp_path / "none.jsonl")] == ["fine"]


def test_load_pinned_reads_rows_and_marks_source(tmp_path: Path) -> None:
    path = tmp_path / "seed.json"
    _write_pinned(path, ["alpha", "beta"])
    rows = gen.load_pinned(path)
    assert [r["slug"] for r in rows] == ["alpha", "beta"]
    assert {r["source"] for r in rows} == {"baseline"}


def test_load_pinned_keeps_only_baseline_rows_so_reruns_do_not_ratchet(tmp_path: Path) -> None:
    path = tmp_path / "seed.json"
    rows = [
        _pinned_row("legacy"),
        {**_pinned_row("explicit-baseline"), "source": "baseline"},
        {**_pinned_row("previously-generated"), "source": "simplify_new_grad"},
    ]
    path.write_text(json.dumps(rows), encoding="utf-8")

    assert [r["slug"] for r in gen.load_pinned(path)] == ["legacy", "explicit-baseline"]


def test_load_pinned_missing_file_is_empty(tmp_path: Path) -> None:
    assert gen.load_pinned(tmp_path / "nope.json") == []


# ------------------------------------------------------------- pool


def test_pool_prefers_pinned_on_slug_collision() -> None:
    pinned = [{**_pinned_row("acme", "lever"), "source": "baseline"}]
    accepted = [
        {"name": "Acme", "slug": "acme", "ats_type": "greenhouse", "ats_board_token": "acme", "source": "x"}
    ]
    pool = gen.build_pool(pinned, accepted)
    assert pool["acme"]["ats_type"] == "lever"


def test_pool_prefers_earlier_ats_between_accepted_duplicates() -> None:
    accepted = [
        {"name": "A", "slug": "a", "ats_type": "workable", "ats_board_token": "a", "source": "x"},
        {"name": "A", "slug": "a", "ats_type": "ashby", "ats_board_token": "a", "source": "x"},
    ]
    assert gen.build_pool([], accepted)["a"]["ats_type"] == "ashby"


# ------------------------------------------------------------- selection


def test_select_hits_target_with_exact_tier_split_and_valid_rows() -> None:
    result = gen.select_seed_records(_pool(700), target=MIN_CORPUS_SIZE)
    assert len(result.records) == MIN_CORPUS_SIZE
    assert result.tier_counts == tier_targets_for_total(MIN_CORPUS_SIZE)
    validate_seed_records(result.records)


def test_select_puts_named_tier1_slugs_in_tier_one() -> None:
    pool = _pool(700)
    for slug, ats in (("stripe", "greenhouse"), ("openai", "ashby")):
        pool[slug] = {"name": slug, "slug": slug, "ats_type": ats, "ats_board_token": slug, "source": "x"}
    result = gen.select_seed_records(pool, target=MIN_CORPUS_SIZE)
    tiers = {r["slug"]: r["poll_priority_tier"] for r in result.records}
    assert tiers["stripe"] == 1
    assert tiers["openai"] == 1


def test_select_keeps_pinned_before_new_candidates_when_over_target() -> None:
    pool = _pool(600, prefix="new")
    pool.update({s: {**r, "source": "baseline"} for s, r in _pool(500, prefix="zpin").items()})
    result = gen.select_seed_records(pool, target=MIN_CORPUS_SIZE)
    assert {r["slug"] for r in result.records} == {f"zpin{i:04d}" for i in range(500)}


def test_select_prefers_stronger_tech_ratio_among_new_candidates() -> None:
    weak = {
        f"a-weak{i:03d}": {**row, "slug": f"a-weak{i:03d}", "ats_board_token": f"a-weak{i:03d}", "tech_ratio": 0.0}
        for i, row in enumerate(_pool(300).values())
    }
    strong = {
        f"z-strong{i:03d}": {**row, "slug": f"z-strong{i:03d}", "ats_board_token": f"z-strong{i:03d}", "tech_ratio": 0.8}
        for i, row in enumerate(_pool(300).values())
    }
    result = gen.select_seed_records({**weak, **strong}, target=MIN_CORPUS_SIZE)
    picked = {r["slug"] for r in result.records}
    assert all(s in picked for s in strong)
    assert sum(1 for s in picked if s.startswith("a-weak")) == MIN_CORPUS_SIZE - len(strong)


def test_select_fails_hard_when_pool_smaller_than_target() -> None:
    with pytest.raises(RuntimeError, match="pool"):
        gen.select_seed_records(_pool(600), target=800)


def test_select_allow_partial_returns_whole_pool() -> None:
    result = gen.select_seed_records(_pool(600), target=800, allow_partial=True)
    assert len(result.records) == 600
    validate_seed_records(result.records)


def test_select_rejects_pool_below_minimum_even_when_partial() -> None:
    with pytest.raises(RuntimeError):
        gen.select_seed_records(_pool(100), target=MIN_CORPUS_SIZE, allow_partial=True)


def test_selection_is_deterministic() -> None:
    pool = _pool(700)
    first = gen.select_seed_records(pool, target=MIN_CORPUS_SIZE).records
    second = gen.select_seed_records(dict(reversed(list(pool.items()))), target=MIN_CORPUS_SIZE).records
    assert first == second


def test_selected_rows_carry_provenance_and_no_internal_fields() -> None:
    row = gen.select_seed_records(_pool(600), target=MIN_CORPUS_SIZE).records[0]
    assert row["source"] == "simplify_new_grad"
    assert set(row) <= {
        "name", "slug", "ats_type", "ats_board_token", "poll_priority_tier",
        "careers_page_url", "source", "discovered_at",
    }


# ------------------------------------------------------------- meta / io


def test_meta_matches_written_seed_bytes(tmp_path: Path) -> None:
    records = gen.select_seed_records(_pool(600), target=MIN_CORPUS_SIZE).records
    seed_path = tmp_path / "seed.json"
    gen.write_seed(seed_path, records)

    meta = gen.build_meta(records, seed_path, pool_size=600, target=MIN_CORPUS_SIZE)

    assert meta["total"] == MIN_CORPUS_SIZE
    assert meta["pool_size"] == 600
    assert meta["sha256"] == hashlib.sha256(seed_path.read_bytes()).hexdigest()
    assert sum(meta["tier_counts"].values()) == MIN_CORPUS_SIZE
    assert meta["ats_counts"] == {"greenhouse": MIN_CORPUS_SIZE}
    assert meta["source_counts"] == {"simplify_new_grad": MIN_CORPUS_SIZE}


def test_phase_b_selection_uses_ten_twenty_seventy_split() -> None:
    result = gen.select_seed_records(_pool(2600), target=2600)
    assert result.tier_counts == {1: 260, 2: 520, 3: 1820}
    validate_seed_records(result.records)


def test_write_outputs_single_file_mode(tmp_path: Path) -> None:
    result = gen.select_seed_records(_pool(600), target=MIN_CORPUS_SIZE)
    out = tmp_path / "seed.json"

    written = gen.write_outputs(result, output=out, shards_dir=None, target=MIN_CORPUS_SIZE)

    assert out in written
    assert out.with_suffix(".meta.json") in written
    assert json.loads(out.read_text())[0]["slug"] == result.records[0]["slug"]


def test_write_outputs_shard_mode_round_trips(tmp_path: Path) -> None:
    from app.services.career_watch.job_corpus_seed import read_seed_manifest

    result = gen.select_seed_records(_pool(2600), target=2600)
    out = tmp_path / "seed.json"
    shards = tmp_path / "seed"

    written = gen.write_outputs(result, output=out, shards_dir=shards, target=2600)

    assert not out.exists()
    assert shards / "seed_manifest.json" in written
    loaded = read_seed_manifest(shards / "seed_manifest.json")
    assert {r["slug"] for r in loaded} == {r["slug"] for r in result.records}
    meta = json.loads((shards / "seed_manifest.meta.json").read_text())
    assert meta["total"] == 2600 and meta["tier_counts"] == {"1": 260, "2": 520, "3": 1820}


def test_curated_token_tuples_are_gone_from_the_module() -> None:
    assert not hasattr(gen, "GREENHOUSE_TOKENS")
    assert not hasattr(gen, "verify_token")


# ------------------------------------------------------------- committed data


@pytest.mark.skipif(not (DATA_DIR / "seed_2000.json").is_file(), reason="seed file absent")
def test_committed_seed_file_is_valid_and_safe() -> None:
    records = read_seed_json(DATA_DIR / "seed_2000.json")
    assert len(records) == 2000
    validate_seed_records(records)
    by_slug = {r["slug"]: r for r in records}
    assert by_slug["stripe"]["ats_type"] == "greenhouse"
    assert by_slug["openai"]["ats_type"] == "ashby"
    unsafe = [r["slug"] for r in records if not token_is_safe(r["ats_type"], r["ats_board_token"])]
    assert unsafe == []
    assert len({r["ats_board_token"].lower() + r["ats_type"] for r in records}) == len(records)


def test_load_pinned_skips_non_object_elements(tmp_path: Path) -> None:
    path = tmp_path / "pinned.json"
    path.write_text(json.dumps([_pinned_row("good"), "oops", None, [1], 7]), encoding="utf-8")
    rows = gen.load_pinned(path)
    assert [r["slug"] for r in rows] == ["good"]
