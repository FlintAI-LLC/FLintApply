"""Wayback CDX harvester: pagination, politeness, time-box, resume, token extraction."""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import httpx
import pytest

from scripts.corpus import harvest_wayback as hw

pytestmark = pytest.mark.unit

HOST = "jobs.lever.co"


def _page(urls: list[str], resume_key: str | None = None) -> str:
    body = "\n".join(urls) + "\n"
    if resume_key:
        body += f"\n{resume_key}\n"
    return body


class _Recorder:
    def __init__(self) -> None:
        self.sleeps: list[float] = []
        self.now = 0.0

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def clock(self) -> float:
        return self.now


def _harvester(tmp_path: Path, handler, *, recorder: _Recorder | None = None, **overrides):
    rec = recorder or _Recorder()
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    kwargs = {
        "client": client,
        "raw_dir": tmp_path / "raw",
        "candidates_path": tmp_path / "candidates.jsonl",
        "hosts": (HOST,),
        "sleep": rec.sleep,
        "clock": rec.clock,
        "min_interval": 1.0,
    }
    kwargs.update(overrides)
    return hw.WaybackHarvester(**kwargs), rec, client


def _candidates(tmp_path: Path) -> list[dict]:
    path = tmp_path / "candidates.jsonl"
    if not path.is_file():
        return []
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


# ------------------------------------------------------------- parsing


def test_parse_cdx_page_without_resume_key() -> None:
    urls, key = hw.parse_cdx_page("http://a/1\nhttp://a/2\n")
    assert urls == ["http://a/1", "http://a/2"] and key is None


def test_parse_cdx_page_with_resume_key() -> None:
    urls, key = hw.parse_cdx_page("http://a/1\nhttp://a/2\n\nabc%20def\n")
    assert urls == ["http://a/1", "http://a/2"]
    assert key == "abc%20def"


def test_parse_cdx_page_empty() -> None:
    assert hw.parse_cdx_page("") == ([], None)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://jobs.lever.co/acme/1234-abcd", ("lever", "acme")),
        ("http://boards.greenhouse.io/Stripe/jobs/1", ("greenhouse", "Stripe")),
        ("https://boards.greenhouse.io/embed/job_board?for=acme", ("greenhouse", "acme")),
        ("https://boards.greenhouse.io/embed/job_app?for=Acme&token=1", ("greenhouse", "Acme")),
        ("https://jobs.ashbyhq.com/openai", ("ashby", "openai")),
        ("https://apply.workable.com/acme/j/ABC", ("workable", "acme")),
    ],
)
def test_extract_token(url: str, expected: tuple[str, str]) -> None:
    got = hw.extract_token(url)
    assert got is not None and (got.ats_type, got.token) == expected


@pytest.mark.parametrize(
    "url",
    [
        "https://boards.greenhouse.io/embed/job_board",
        "https://boards.greenhouse.io/embed/job_board?for=../evil",
        "https://boards.greenhouse.io/embed/job_board?for=",
        "https://boards.greenhouse.io/robots.txt",
        "https://jobs.lever.co/static/app.js",
        "https://jobs.lever.co/acme%20corp/1",
        "https://jobs.lever.co/",
        "not a url",
    ],
)
def test_extract_token_rejects_noise_and_unsafe(url: str) -> None:
    assert hw.extract_token(url) is None


# ------------------------------------------------------------- request shape


@pytest.mark.asyncio
async def test_request_uses_polite_ua_and_required_cdx_params(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text=_page(["https://jobs.lever.co/acme/1"]))

    h, _, client = _harvester(tmp_path, handler)
    async with client:
        await h.run()

    req = seen[0]
    assert req.headers["user-agent"] == "FlintApplyCorpusBot/1.0"
    params = dict(req.url.params)
    assert params["url"] == HOST
    assert params["matchType"] == "domain"
    assert params["collapse"] == "urlkey"
    assert params["fl"] == "original"
    assert params["showResumeKey"] == "true"
    assert "resumeKey" not in params


# ------------------------------------------------------------- pagination


@pytest.mark.asyncio
async def test_follows_resume_keys_until_exhausted(tmp_path: Path) -> None:
    pages = {
        None: _page(["https://jobs.lever.co/aaa/1"], "K1"),
        "K1": _page(["https://jobs.lever.co/bbb/1"], "K2"),
        "K2": _page(["https://jobs.lever.co/ccc/1"]),
    }
    keys: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        key = request.url.params.get("resumeKey")
        keys.append(key)
        return httpx.Response(200, text=pages[key])

    h, _, client = _harvester(tmp_path, handler)
    async with client:
        report = await h.run()

    assert keys == [None, "K1", "K2"]
    assert {c["token"] for c in _candidates(tmp_path)} == {"aaa", "bbb", "ccc"}
    assert report.pages == 3
    assert report.stopped_reason == "complete"


@pytest.mark.asyncio
async def test_candidates_are_tagged_and_deduplicated(tmp_path: Path) -> None:
    (tmp_path / "candidates.jsonl").write_text(
        json.dumps({"token": "Existing", "ats_type": "lever", "source": "simplify_new_grad"}) + "\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=_page(
                [
                    "https://jobs.lever.co/existing/1",
                    "https://jobs.lever.co/Fresh/1",
                    "https://jobs.lever.co/fresh/2",
                    "https://jobs.lever.co/fresh/3",
                ]
            ),
        )

    h, _, client = _harvester(tmp_path, handler)
    async with client:
        report = await h.run()

    rows = _candidates(tmp_path)
    added = [r for r in rows if r.get("source") == "wayback"]
    assert [r["token"] for r in added] == ["Fresh"]
    assert added[0]["ats_type"] == "lever" and added[0]["discovered_at"]
    assert report.new_tokens == 1
    assert report.urls_seen == 4


@pytest.mark.asyncio
async def test_raw_pages_are_cached_gzipped(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_page(["https://jobs.lever.co/acme/1"]))

    h, _, client = _harvester(tmp_path, handler)
    async with client:
        await h.run()

    files = sorted((tmp_path / "raw").glob("*.gz"))
    assert len(files) == 1
    assert "jobs.lever.co/acme/1" in gzip.decompress(files[0].read_bytes()).decode()


# ------------------------------------------------------------- politeness


@pytest.mark.asyncio
async def test_requests_are_paced(tmp_path: Path) -> None:
    pages = {None: _page(["https://jobs.lever.co/a/1"], "K1"), "K1": _page(["https://jobs.lever.co/b/1"])}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=pages[request.url.params.get("resumeKey")])

    h, rec, client = _harvester(tmp_path, handler, min_interval=2.5)
    async with client:
        await h.run()

    assert sum(rec.sleeps) >= 2.5
    assert all(s >= 0 for s in rec.sleeps)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 503])
async def test_retry_after_is_honored(tmp_path: Path, status: int) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(status, headers={"Retry-After": "37"})
        return httpx.Response(200, text=_page(["https://jobs.lever.co/acme/1"]))

    h, rec, client = _harvester(tmp_path, handler)
    async with client:
        report = await h.run()

    assert calls["n"] == 2
    assert any(abs(s - 37) < 0.01 for s in rec.sleeps)
    assert report.stopped_reason == "complete"


@pytest.mark.asyncio
async def test_absurd_retry_after_is_capped(tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "999999"})
        return httpx.Response(200, text=_page([]))

    h, rec, client = _harvester(tmp_path, handler)
    async with client:
        await h.run()

    assert max(rec.sleeps) <= hw.MAX_RETRY_AFTER_SECONDS


@pytest.mark.asyncio
async def test_persistent_server_errors_stop_that_host_only(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["url"] == "jobs.lever.co":
            return httpx.Response(500)
        return httpx.Response(200, text=_page(["https://jobs.ashbyhq.com/openai"]))

    h, _, client = _harvester(tmp_path, handler, hosts=("jobs.lever.co", "jobs.ashbyhq.com"))
    async with client:
        report = await h.run()

    assert report.host_status["jobs.lever.co"] == "error"
    assert report.host_status["jobs.ashbyhq.com"] == "complete"
    assert {c["token"] for c in _candidates(tmp_path)} == {"openai"}


@pytest.mark.asyncio
async def test_retries_are_bounded(tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503)

    h, _, client = _harvester(tmp_path, handler)
    async with client:
        await h.run()

    assert calls["n"] == hw.MAX_ATTEMPTS


@pytest.mark.asyncio
async def test_network_errors_are_retried_then_recorded(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("slow", request=request)

    h, _, client = _harvester(tmp_path, handler)
    async with client:
        report = await h.run()

    assert report.host_status[HOST] == "error"


# ------------------------------------------------------------- time-box and resume


@pytest.mark.asyncio
async def test_deadline_stops_cleanly_and_state_allows_resume(tmp_path: Path) -> None:
    pages = {
        None: _page(["https://jobs.lever.co/aaa/1"], "K1"),
        "K1": _page(["https://jobs.lever.co/bbb/1"], "K2"),
        "K2": _page(["https://jobs.lever.co/ccc/1"]),
    }
    requested: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        key = request.url.params.get("resumeKey")
        requested.append(key)
        return httpx.Response(200, text=pages[key])

    rec = _Recorder()
    h, _, client = _harvester(tmp_path, handler, recorder=rec, max_seconds=1.5, min_interval=1.0)
    async with client:
        first = await h.run()

    assert first.stopped_reason == "deadline"
    assert first.pages < 3
    state = json.loads((tmp_path / "raw" / "state.json").read_text())
    assert state[HOST]["resume_key"] is not None

    requested.clear()
    h2, _, client2 = _harvester(tmp_path, handler, recorder=_Recorder())
    async with client2:
        second = await h2.run()

    assert second.stopped_reason == "complete"
    assert requested[0] is not None  # resumed mid-stream, not from the start
    assert {c["token"] for c in _candidates(tmp_path)} == {"aaa", "bbb", "ccc"}


@pytest.mark.asyncio
async def test_completed_hosts_are_not_refetched(tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, text=_page(["https://jobs.lever.co/acme/1"]))

    for _ in range(2):
        h, _, client = _harvester(tmp_path, handler)
        async with client:
            await h.run()

    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_disk_cap_stops_before_writing_more(tmp_path: Path) -> None:
    big = _page([f"https://jobs.lever.co/co{i}/1" for i in range(400)], "K")
    pages = {None: big, "K": big, "K2": big}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=pages.get(request.url.params.get("resumeKey"), big))

    h, _, client = _harvester(tmp_path, handler, max_raw_bytes=300)
    async with client:
        report = await h.run()

    assert report.stopped_reason == "disk_cap"
    total = sum(p.stat().st_size for p in (tmp_path / "raw").glob("*.gz"))
    assert total <= 300 + len(big)  # at most the page that crossed the cap


@pytest.mark.asyncio
async def test_corrupt_state_file_starts_fresh(tmp_path: Path) -> None:
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "state.json").write_text("{not json")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_page(["https://jobs.lever.co/acme/1"]))

    h, _, client = _harvester(tmp_path, handler)
    async with client:
        report = await h.run()

    assert report.stopped_reason == "complete"


def test_default_hosts_match_the_spec() -> None:
    assert set(hw.DEFAULT_HOSTS) == {
        "boards.greenhouse.io",
        "job-boards.greenhouse.io",
        "jobs.ashbyhq.com",
        "jobs.lever.co",
        "careers.smartrecruiters.com",
        "apply.workable.com",
    }
    assert hw.DEFAULT_MAX_SECONDS == 3 * 3600


# ---- judge-accepted hardening (S9-TEST-001/003/005/007/008/011) ----


def test_parse_cdx_page_leading_blank_line_does_not_swallow_urls() -> None:
    urls, key = hw.parse_cdx_page("\nhttps://jobs.lever.co/acme/1\n")
    assert urls == ["https://jobs.lever.co/acme/1"] and key is None


def test_parse_cdx_page_leading_blank_then_resume_key() -> None:
    urls, key = hw.parse_cdx_page("\nhttp://a/1\n\nKEY\n")
    assert urls == ["http://a/1"] and key == "KEY"


def test_parse_cdx_page_whitespace_only_separator() -> None:
    urls, key = hw.parse_cdx_page("http://a/1\n   \nKEY\n")
    assert urls == ["http://a/1"] and key == "KEY"


@pytest.mark.asyncio
async def test_request_pins_status_filter_and_page_limit(tmp_path: Path) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text=_page([]))

    h, _, client = _harvester(tmp_path, handler)
    async with client:
        await h.run()

    params = dict(seen[0].url.params)
    assert params["filter"] == "statuscode:200"
    assert params["limit"] == str(hw.PAGE_LIMIT)


@pytest.mark.asyncio
async def test_repeated_resume_key_terminates(tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, text=_page(["https://jobs.lever.co/acme/1"], "SAME"))

    h, _, client = _harvester(tmp_path, handler)
    async with client:
        report = await h.run()

    assert calls["n"] <= 3
    assert report.host_status[HOST] == "complete"
    state = json.loads((tmp_path / "raw" / "state.json").read_text())
    assert state[HOST]["done"] is True


@pytest.mark.asyncio
async def test_cyclic_resume_keys_terminate(tmp_path: Path) -> None:
    nxt = {None: "A", "A": "B", "B": "A"}
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        key = request.url.params.get("resumeKey")
        return httpx.Response(200, text=_page([f"https://jobs.lever.co/co{calls['n']}/1"], nxt[key]))

    h, _, client = _harvester(tmp_path, handler)
    async with client:
        report = await h.run()

    assert calls["n"] <= 4
    assert report.host_status[HOST] == "complete"


@pytest.mark.asyncio
@pytest.mark.parametrize("shape", ['"complete"', "[]", "null", "5"])
async def test_wrong_shaped_host_state_is_replaced(tmp_path: Path, shape: str) -> None:
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "state.json").write_text(f'{{"{HOST}": {shape}}}')

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=_page(["https://jobs.lever.co/acme/1"]))

    h, _, client = _harvester(tmp_path, handler)
    async with client:
        report = await h.run()

    assert report.host_status[HOST] == "complete"
    assert {c["token"] for c in _candidates(tmp_path)} == {"acme"}


@pytest.mark.asyncio
async def test_retry_after_http_date_is_honored_and_clamped(tmp_path: Path) -> None:
    from datetime import datetime, timedelta, timezone
    from email.utils import format_datetime

    when = datetime.now(timezone.utc) + timedelta(seconds=120)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": format_datetime(when, usegmt=True)})
        return httpx.Response(200, text=_page([]))

    h, rec, client = _harvester(tmp_path, handler)
    async with client:
        await h.run()

    assert any(100 <= s <= 121 for s in rec.sleeps)


@pytest.mark.asyncio
async def test_retry_after_past_http_date_waits_the_minimum(tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"})
        return httpx.Response(200, text=_page([]))

    h, rec, client = _harvester(tmp_path, handler)
    async with client:
        await h.run()

    assert any(abs(s - hw.MIN_RETRY_SECONDS) < 0.01 for s in rec.sleeps)


@pytest.mark.asyncio
async def test_garbage_retry_after_falls_back_to_backoff(tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "soon"})
        return httpx.Response(200, text=_page([]))

    h, rec, client = _harvester(tmp_path, handler)
    async with client:
        await h.run()

    assert any(abs(s - hw.BACKOFF_BASE_SECONDS) < 0.01 for s in rec.sleeps)


@pytest.mark.asyncio
async def test_retry_sleep_never_overruns_the_deadline(tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(429, headers={"Retry-After": "300"})

    h, rec, client = _harvester(tmp_path, handler, max_seconds=5.0, min_interval=0.0)
    async with client:
        report = await h.run()

    assert report.stopped_reason == "deadline"
    assert max(rec.sleeps) <= 5.0 + 1e-6
    assert calls["n"] == 1
    state_path = tmp_path / "raw" / "state.json"
    assert not state_path.exists() or json.loads(state_path.read_text()).get(HOST, {}).get("done") is not True


@pytest.mark.asyncio
async def test_non_retryable_status_is_one_call_and_host_error(tmp_path: Path) -> None:
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(403)

    h, _, client = _harvester(tmp_path, handler)
    async with client:
        report = await h.run()

    assert calls["n"] == 1
    assert report.host_status[HOST] == "error"
