"""Unit tests for corpus discovery URL parsing."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from scripts.corpus.ats_url_parse import dedupe_key, parse_ats_url
from scripts.corpus.discover_simplifyjobs import discover_from_listings

FIXTURE = Path(__file__).resolve().parent.parent / "fixtures" / "simplify_listings_snippet.json"


def test_parse_greenhouse_preserves_token_case() -> None:
    parsed = parse_ats_url("https://boards.greenhouse.io/Stripe")
    assert parsed is not None
    assert parsed.ats_type == "greenhouse"
    assert parsed.token == "Stripe"


def test_parse_lever_and_ashby() -> None:
    lever = parse_ats_url("https://jobs.lever.co/flint-ai")
    assert lever and lever.ats_type == "lever" and lever.token == "flint-ai"
    ashby = parse_ats_url("https://jobs.ashbyhq.com/openai")
    assert ashby and ashby.ats_type == "ashby" and ashby.token == "openai"


@pytest.mark.parametrize(
    "url",
    [
        "https://boards.greenhouse.io/jobs",
        "https://example.com/careers",
        "not a url",
        "",
    ],
)
def test_parse_rejects_non_board_urls(url: str) -> None:
    assert parse_ats_url(url) is None


def test_dedupe_key_is_case_insensitive() -> None:
    a = parse_ats_url("https://boards.greenhouse.io/Acme")
    b = parse_ats_url("https://job-boards.greenhouse.io/acme")
    assert a and b
    assert dedupe_key(a) == dedupe_key(b)


def test_discover_from_listings_fixture() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    rows = discover_from_listings(payload, source="test")
    assert len(rows) >= 2
    tokens = {(r["ats_type"], r["token"]) for r in rows}
    assert ("greenhouse", "acme") in tokens


def test_categories_aggregate_across_listings_of_same_company() -> None:
    payload = [
        {"url": "https://boards.greenhouse.io/acme/jobs/1", "category": "Product"},
        {"url": "https://boards.greenhouse.io/Acme/jobs/2", "category": "Software"},
        {"url": "https://boards.greenhouse.io/acme/jobs/3", "category": "Software"},
    ]
    rows = discover_from_listings(payload, source="t")
    assert len(rows) == 1
    assert rows[0]["categories"] == ["Product", "Software"]
    assert rows[0]["token"] == "acme"  # first-seen case preserved
