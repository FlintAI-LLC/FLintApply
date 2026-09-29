"""Tri-state candidate verification, rate-limit handling, and probe cache TTL."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest

from app.services.career_watch.corpus_verify import (
    ACCEPT,
    OMIT,
    QUARANTINE,
    Candidate,
    HostGate,
    ProbeCache,
    extract_titles,
    probe_candidate,
    verify_candidates,
)
from app.services.career_watch.job_corpus_seed import PROBE_CACHE_TTL_DAYS

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
TECH = ["Software Engineer", "Backend Engineer", "SRE", "Data Engineer", "ML Engineer"]


def _gh_payload(titles: list[str]) -> dict:
    return {"jobs": [{"title": t} for t in titles]}


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _cand(ats: str = "greenhouse", token: str = "acme", **kw) -> Candidate:
    return Candidate(ats_type=ats, token=token, source=kw.pop("source", "test"), **kw)


@pytest.mark.asyncio
async def test_valid_tech_board_is_accepted() -> None:
    async with _client(lambda r: httpx.Response(200, json=_gh_payload(TECH))) as c:
        res = await probe_candidate(c, _cand(), HostGate(), tier1_slugs=(), now=NOW)
    assert res.status == ACCEPT
    assert res.titles[:2] == TECH[:2]


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [404, 403, 410])
async def test_gone_or_forbidden_is_omitted(code: int) -> None:
    async with _client(lambda r: httpx.Response(code)) as c:
        res = await probe_candidate(c, _cand(), HostGate(), tier1_slugs=(), now=NOW)
    assert res.status == OMIT
    assert res.reason == f"http_{code}"


@pytest.mark.asyncio
async def test_invalid_json_is_omitted() -> None:
    async with _client(lambda r: httpx.Response(200, content=b"<html>nope</html>")) as c:
        res = await probe_candidate(c, _cand(), HostGate(), tier1_slugs=(), now=NOW)
    assert res.status == OMIT
    assert res.reason == "invalid_json"


@pytest.mark.asyncio
async def test_wrong_schema_is_omitted() -> None:
    async with _client(lambda r: httpx.Response(200, json={"unexpected": True})) as c:
        res = await probe_candidate(c, _cand(), HostGate(), tier1_slugs=(), now=NOW)
    assert res.status == OMIT
    assert res.reason == "bad_schema"


@pytest.mark.asyncio
@pytest.mark.parametrize("code", [500, 502, 503])
async def test_server_errors_are_quarantined(code: int) -> None:
    async with _client(lambda r: httpx.Response(code)) as c:
        res = await probe_candidate(c, _cand(), HostGate(), tier1_slugs=(), now=NOW)
    assert res.status == QUARANTINE


@pytest.mark.asyncio
async def test_timeout_is_quarantined() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    async with _client(handler) as c:
        res = await probe_candidate(c, _cand(), HostGate(), tier1_slugs=(), now=NOW)
    assert res.status == QUARANTINE
    assert res.reason == "network_error"


@pytest.mark.asyncio
async def test_empty_200_board_is_quarantined_even_for_tier1() -> None:
    async with _client(lambda r: httpx.Response(200, json=_gh_payload([]))) as c:
        res = await probe_candidate(
            c, _cand(token="stripe"), HostGate(), tier1_slugs=("stripe",), now=NOW
        )
    assert res.status == QUARANTINE
    assert res.reason == "empty_board"


@pytest.mark.asyncio
async def test_429_quarantines_and_blocks_host_for_rest_of_run() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(429, headers={"Retry-After": "120"})

    gate = HostGate()
    async with _client(handler) as c:
        first = await probe_candidate(c, _cand(token="a"), gate, tier1_slugs=(), now=NOW)
        second = await probe_candidate(c, _cand(token="b"), gate, tier1_slugs=(), now=NOW)
    assert first.status == QUARANTINE and first.reason == "rate_limited"
    assert first.retry_after == 120
    assert second.status == QUARANTINE and second.reason == "host_rate_limited_skip"
    assert len(calls) == 1  # second candidate never hit the network
    assert gate.is_blocked("greenhouse")


@pytest.mark.asyncio
async def test_rate_limit_on_one_host_does_not_block_another() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "greenhouse" in str(request.url):
            return httpx.Response(429)
        return httpx.Response(200, json=[{"text": t} for t in TECH])

    gate = HostGate()
    async with _client(handler) as c:
        await probe_candidate(c, _cand("greenhouse"), gate, tier1_slugs=(), now=NOW)
        lever = await probe_candidate(c, _cand("lever", "acme"), gate, tier1_slugs=(), now=NOW)
    assert lever.status == ACCEPT


@pytest.mark.asyncio
async def test_lever_falls_back_to_eu_host_once() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        if request.url.host == "api.lever.co":
            return httpx.Response(404)
        return httpx.Response(200, json=[{"text": t} for t in TECH])

    async with _client(handler) as c:
        res = await probe_candidate(c, _cand("lever", "eucorp"), HostGate(), tier1_slugs=(), now=NOW)
    assert res.status == ACCEPT
    assert res.host == "api.eu.lever.co"
    assert seen == ["api.lever.co", "api.eu.lever.co"]


@pytest.mark.asyncio
async def test_non_tech_board_is_omitted_and_sends_user_agent() -> None:
    agents: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        agents.append(request.headers.get("user-agent", ""))
        return httpx.Response(200, json=_gh_payload(["Recruiter", "Account Executive"] * 6))

    async with _client(handler) as c:
        res = await probe_candidate(c, _cand(), HostGate(), tier1_slugs=(), now=NOW)
    assert res.status == OMIT
    assert res.reason == "non_tech"
    assert agents == ["FlintApplyCorpusBot/1.0"]


@pytest.mark.asyncio
async def test_simplify_software_category_autopasses_non_tech_titles() -> None:
    async with _client(lambda r: httpx.Response(200, json=_gh_payload(["Recruiter"] * 5))) as c:
        res = await probe_candidate(
            c, _cand(categories=("Software",)), HostGate(), tier1_slugs=(), now=NOW
        )
    assert res.status == ACCEPT


def test_extract_titles_per_ats_shape() -> None:
    assert extract_titles("greenhouse", {"jobs": [{"title": "A"}]}) == ["A"]
    assert extract_titles("lever", [{"text": "B"}]) == ["B"]
    assert extract_titles("ashby", {"jobs": [{"title": "C"}]}) == ["C"]
    assert extract_titles("smartrecruiters", {"content": [{"name": "D"}]}) == ["D"]
    assert extract_titles("workable", {"jobs": [{"title": "E"}]}) == ["E"]
    assert extract_titles("recruitee", {"offers": [{"title": "F"}]}) == ["F"]
    assert extract_titles("greenhouse", {"jobs": [{"nope": 1}, "junk"]}) == []


def test_probe_cache_ttl_and_states(tmp_path: Path) -> None:
    path = tmp_path / "probe_cache.jsonl"
    cache = ProbeCache(path)
    fresh = NOW - timedelta(days=PROBE_CACHE_TTL_DAYS - 1)
    stale = NOW - timedelta(days=PROBE_CACHE_TTL_DAYS + 1)
    cache.put("greenhouse", "Fresh", ACCEPT, "ok", fresh, titles=["SWE"])
    cache.put("greenhouse", "Stale", OMIT, "http_404", stale)
    cache.put("greenhouse", "Flaky", QUARANTINE, "network_error", fresh)
    cache.save()

    reloaded = ProbeCache(path)
    assert reloaded.get("greenhouse", "fresh", now=NOW).status == ACCEPT  # case-insensitive
    assert reloaded.get("greenhouse", "Stale", now=NOW) is None  # expired
    assert reloaded.get("greenhouse", "Flaky", now=NOW) is None  # quarantine always retried
    assert reloaded.get("lever", "fresh", now=NOW) is None


@pytest.mark.asyncio
async def test_verify_candidates_uses_cache_and_never_reprobes_accept_or_omit(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json=_gh_payload(TECH))

    cache = ProbeCache(tmp_path / "probe_cache.jsonl")
    cache.put("greenhouse", "cached-ok", ACCEPT, "ok", NOW - timedelta(days=1), titles=TECH)
    cache.put("greenhouse", "cached-gone", OMIT, "http_404", NOW - timedelta(days=1))
    cands = [_cand(token="cached-ok"), _cand(token="cached-gone"), _cand(token="new-one")]

    async with _client(handler) as c:
        results = await verify_candidates(c, cands, cache, tier1_slugs=(), now=NOW)

    by_token = {r.token: r for r in results}
    assert by_token["cached-ok"].status == ACCEPT
    assert by_token["cached-gone"].status == OMIT
    assert by_token["new-one"].status == ACCEPT
    assert len(calls) == 1 and "new-one" in calls[0]


@pytest.mark.asyncio
async def test_verify_candidates_persists_cache_and_quarantine(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503) if "flaky" in str(request.url) else httpx.Response(200, json=_gh_payload(TECH))

    cache = ProbeCache(tmp_path / "probe_cache.jsonl")
    async with _client(handler) as c:
        results = await verify_candidates(
            c, [_cand(token="good"), _cand(token="flaky")], cache, tier1_slugs=(), now=NOW
        )
    cache.save()
    lines = [json.loads(x) for x in (tmp_path / "probe_cache.jsonl").read_text().splitlines()]
    assert {(r["token"], r["status"]) for r in lines} == {("good", ACCEPT), ("flaky", QUARANTINE)}
    assert [r.token for r in results if r.status == QUARANTINE] == ["flaky"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("ats", "token"),
    [
        ("greenhouse", "../../admin"),
        ("greenhouse", "a/b"),
        ("greenhouse", "a?x=1"),
        ("greenhouse", "a b"),
        ("greenhouse", "acme\n"),
        ("recruitee", "acme\n"),
        ("greenhouse", ""),
        ("greenhouse", "x" * 101),
        ("recruitee", "evil.com/x"),
        ("recruitee", "a.b"),
        ("lever", "%2e%2e"),
    ],
)
async def test_unsafe_tokens_are_omitted_without_any_request(ats: str, token: str) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json=_gh_payload(TECH))

    async with _client(handler) as c:
        res = await probe_candidate(c, _cand(ats, token), HostGate(), tier1_slugs=(), now=NOW)
    assert res.status == OMIT and res.reason == "invalid_token"
    assert calls == []


@pytest.mark.asyncio
async def test_preserves_greenhouse_token_case_in_request() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(200, json=_gh_payload(TECH))

    async with _client(handler) as c:
        await probe_candidate(c, _cand(token="AndurilIndustries"), HostGate(), tier1_slugs=(), now=NOW)
    assert seen == ["/v1/boards/AndurilIndustries/jobs"]


@pytest.mark.asyncio
async def test_verify_candidates_processes_in_chunks_and_persists_between_them(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_gh_payload(TECH))

    cache = ProbeCache(tmp_path / "probe_cache.jsonl")
    saved_sizes: list[int] = []

    def on_chunk() -> None:
        cache.save()
        saved_sizes.append(len((tmp_path / "probe_cache.jsonl").read_text().splitlines()))

    cands = [_cand(token=f"co{i}") for i in range(5)]
    async with _client(handler) as c:
        results = await verify_candidates(
            c, cands, cache, tier1_slugs=(), now=NOW, chunk_size=2, on_chunk=on_chunk
        )

    assert len(results) == 5
    assert saved_sizes == [2, 4, 5]


@pytest.mark.asyncio
async def test_verify_candidates_stops_between_chunks_when_asked(tmp_path: Path) -> None:
    probed: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        probed.append(str(request.url))
        return httpx.Response(200, json=_gh_payload(TECH))

    cache = ProbeCache(tmp_path / "probe_cache.jsonl")
    chunks_done = {"n": 0}

    def on_chunk() -> None:
        chunks_done["n"] += 1

    cands = [_cand(token=f"co{i}") for i in range(6)]
    async with _client(handler) as c:
        results = await verify_candidates(
            c,
            cands,
            cache,
            tier1_slugs=(),
            now=NOW,
            chunk_size=2,
            on_chunk=on_chunk,
            should_stop=lambda: chunks_done["n"] >= 1,
        )

    assert len(results) == 2
    assert len(probed) == 2
    # Unprocessed candidates stay unverified so the next run picks them up.
    assert cache.get("greenhouse", "co5", now=NOW) is None


@pytest.mark.asyncio
async def test_verify_candidates_rejects_non_positive_chunk_size(tmp_path: Path) -> None:
    cache = ProbeCache(tmp_path / "probe_cache.jsonl")
    async with _client(lambda r: httpx.Response(200)) as c:
        with pytest.raises(ValueError, match="chunk_size"):
            await verify_candidates(c, [_cand()], cache, tier1_slugs=(), now=NOW, chunk_size=0)


@pytest.mark.asyncio
async def test_verify_candidates_rate_limit_block_persists_across_chunks(tmp_path: Path) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(429, headers={"Retry-After": "60"})

    cache = ProbeCache(tmp_path / "probe_cache.jsonl")
    async with _client(handler) as c:
        results = await verify_candidates(
            c, [_cand(token=f"co{i}") for i in range(4)], cache, tier1_slugs=(), now=NOW, chunk_size=1
        )

    assert len(calls) == 1
    assert all(r.status == QUARANTINE for r in results)


def test_deadline_stop_flips_after_max_seconds() -> None:
    from scripts.corpus.verify_candidates import deadline_stop

    now = {"t": 100.0}
    stop = deadline_stop(10, clock=lambda: now["t"])
    assert stop() is False
    now["t"] = 109.9
    assert stop() is False
    now["t"] = 110.0
    assert stop() is True


def test_deadline_stop_without_limit_never_stops() -> None:
    from scripts.corpus.verify_candidates import deadline_stop

    now = {"t": 0.0}
    stop = deadline_stop(0, clock=lambda: now["t"])
    now["t"] = 1e9
    assert stop() is False


def test_load_candidates_skips_non_object_lines(tmp_path: Path) -> None:
    from scripts.corpus.verify_candidates import load_candidates

    path = tmp_path / "candidates.jsonl"
    path.write_text(
        "\n".join(
            [
                json.dumps({"ats_type": "greenhouse", "token": "ok", "source": "x"}),
                "[1, 2, 3]",
                "null",
                '"foo"',
                "true",
                "{broken",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    assert [c.token for c in load_candidates(path, include_yc=False)] == ["ok"]


def test_extract_titles_truncates_each_title() -> None:
    from app.services.career_watch.corpus_verify import MAX_TITLE_CHARS, extract_titles

    titles = extract_titles("greenhouse", {"jobs": [{"title": "T" * 5000}, {"title": "Engineer"}]})
    assert titles == ["T" * MAX_TITLE_CHARS, "Engineer"]
