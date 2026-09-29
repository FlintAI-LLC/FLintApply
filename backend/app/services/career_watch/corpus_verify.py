"""Tri-state ATS board verification for corpus expansion.

accept      board reachable, schema valid, tech classifier passed
omit        definitively unusable (gone, invalid, non-tech); cached for the TTL
quarantine  inconclusive (timeout, 429, 5xx, empty board); retried next run and
            never enters the seed
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from app.services.career_watch.job_corpus_seed import PROBE_CACHE_TTL_DAYS, token_is_safe
from app.services.career_watch.tech_classifier import (
    TITLE_SAMPLE_LIMIT,
    auto_pass,
    classify_titles,
)

ACCEPT = "accept"
OMIT = "omit"
QUARANTINE = "quarantine"

USER_AGENT = "FlintApplyCorpusBot/1.0"
REQUEST_TIMEOUT_SECONDS = 8.0
VERIFY_CHUNK_SIZE = 300
MAX_TITLE_CHARS = 300
LEVER_US_HOST = "api.lever.co"
LEVER_EU_HOST = "api.eu.lever.co"

HOST_CONCURRENCY: dict[str, int] = {
    "greenhouse": 8,
    "ashby": 6,
    "lever": 6,
    "smartrecruiters": 4,
    "workable": 4,
}
DEFAULT_HOST_CONCURRENCY = 3

# Tokens end up in URL paths (and a hostname label for recruitee) on fixed hosts.
_GONE_CODES = frozenset({403, 404, 410})


@dataclass(frozen=True)
class Candidate:
    ats_type: str
    token: str
    source: str
    name: str | None = None
    categories: tuple[str, ...] = ()
    industries: Any = None
    tags: Any = None

    @property
    def key(self) -> tuple[str, str]:
        return (self.ats_type, self.token.lower())


@dataclass(frozen=True)
class ProbeResult:
    ats_type: str
    token: str
    status: str
    reason: str
    titles: list[str] = field(default_factory=list)
    host: str | None = None
    retry_after: int | None = None
    name: str | None = None
    source: str | None = None
    from_cache: bool = False


class HostGate:
    """Per-ATS concurrency limits plus a run-wide block after HTTP 429."""

    def __init__(self) -> None:
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._blocked: set[str] = set()

    def semaphore(self, ats_type: str) -> asyncio.Semaphore:
        if ats_type not in self._semaphores:
            limit = HOST_CONCURRENCY.get(ats_type, DEFAULT_HOST_CONCURRENCY)
            self._semaphores[ats_type] = asyncio.Semaphore(limit)
        return self._semaphores[ats_type]

    def block(self, ats_type: str) -> None:
        self._blocked.add(ats_type)

    def is_blocked(self, ats_type: str) -> bool:
        return ats_type in self._blocked


def verify_url(ats_type: str, token: str, *, host: str | None = None) -> str:
    if ats_type == "greenhouse":
        return f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    if ats_type == "lever":
        return f"https://{host or LEVER_US_HOST}/v0/postings/{token}?mode=json"
    if ats_type == "ashby":
        return f"https://api.ashbyhq.com/posting-api/job-board/{token}"
    if ats_type == "smartrecruiters":
        return f"https://api.smartrecruiters.com/v1/companies/{token}/postings?limit=1&offset=0"
    if ats_type == "workable":
        return f"https://apply.workable.com/api/v1/widget/accounts/{token}?details=true"
    if ats_type == "recruitee":
        return f"https://{token}.recruitee.com/api/offers/"
    raise ValueError(f"unsupported verify ats_type: {ats_type}")


def _job_list(ats_type: str, payload: Any) -> list[Any] | None:
    if ats_type == "lever":
        return payload if isinstance(payload, list) else None
    key = {
        "greenhouse": "jobs",
        "ashby": "jobs",
        "workable": "jobs",
        "smartrecruiters": "content",
        "recruitee": "offers",
    }.get(ats_type)
    if key is None or not isinstance(payload, dict):
        return None
    items = payload.get(key)
    return items if isinstance(items, list) else None


def extract_titles(ats_type: str, payload: Any) -> list[str]:
    items = _job_list(ats_type, payload) or []
    field_name = {"lever": "text", "smartrecruiters": "name"}.get(ats_type, "title")
    titles: list[str] = []
    for item in items:
        if isinstance(item, dict):
            value = item.get(field_name)
            if isinstance(value, str) and value.strip():
                titles.append(value.strip()[:MAX_TITLE_CHARS])
    return titles


def _parse_retry_after(response: httpx.Response) -> int | None:
    raw = response.headers.get("Retry-After", "")
    return int(raw) if raw.isdigit() else None


def _slug(token: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", token.lower()).strip("-")


def _result(cand: Candidate, status: str, reason: str, **kw: Any) -> ProbeResult:
    return ProbeResult(
        ats_type=cand.ats_type,
        token=cand.token,
        status=status,
        reason=reason,
        name=cand.name,
        source=cand.source,
        **kw,
    )


async def _get(client: httpx.AsyncClient, url: str) -> httpx.Response:
    return await client.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


async def probe_candidate(
    client: httpx.AsyncClient,
    cand: Candidate,
    gate: HostGate,
    *,
    tier1_slugs: Iterable[str],
    now: datetime,
) -> ProbeResult:
    if not token_is_safe(cand.ats_type, cand.token):
        return _result(cand, OMIT, "invalid_token")
    if gate.is_blocked(cand.ats_type):
        return _result(cand, QUARANTINE, "host_rate_limited_skip")

    hosts: list[str | None] = [None]
    if cand.ats_type == "lever":
        hosts = [LEVER_US_HOST, LEVER_EU_HOST]

    response: httpx.Response | None = None
    used_host: str | None = None
    async with gate.semaphore(cand.ats_type):
        for host in hosts:
            used_host = host
            try:
                response = await _get(client, verify_url(cand.ats_type, cand.token, host=host))
            except httpx.HTTPError:
                return _result(cand, QUARANTINE, "network_error", host=host)
            if response.status_code != 404 or host == hosts[-1]:
                break

    assert response is not None
    code = response.status_code
    if code == 429:
        gate.block(cand.ats_type)
        return _result(cand, QUARANTINE, "rate_limited", retry_after=_parse_retry_after(response))
    if code >= 500:
        return _result(cand, QUARANTINE, f"http_{code}", host=used_host)
    if code in _GONE_CODES or 400 <= code < 500:
        return _result(cand, OMIT, f"http_{code}", host=used_host)
    if code != 200:
        return _result(cand, OMIT, f"http_{code}", host=used_host)

    try:
        payload = response.json()
    except ValueError:
        return _result(cand, OMIT, "invalid_json", host=used_host)
    if _job_list(cand.ats_type, payload) is None:
        return _result(cand, OMIT, "bad_schema", host=used_host)

    titles = extract_titles(cand.ats_type, payload)
    if not titles:
        return _result(cand, QUARANTINE, "empty_board", host=used_host)

    sample = titles[:TITLE_SAMPLE_LIMIT]
    if auto_pass(
        slug=_slug(cand.token),
        tier1_slugs=tier1_slugs,
        categories=cand.categories,
        industries=cand.industries,
        tags=cand.tags,
        source=cand.source,
    ):
        return _result(cand, ACCEPT, "auto_pass", titles=sample, host=used_host)

    decision = classify_titles(sample).decision
    reason = {ACCEPT: "tech_titles", OMIT: "non_tech", QUARANTINE: "borderline_tech"}[decision]
    return _result(cand, decision, reason, titles=sample, host=used_host)


@dataclass
class CacheEntry:
    ats_type: str
    token: str
    status: str
    reason: str
    checked_at: datetime
    titles: list[str] = field(default_factory=list)
    name: str | None = None


class ProbeCache:
    """JSONL probe cache keyed by (ats_type, token.lower()) with a TTL."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._entries: dict[tuple[str, str], CacheEntry] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                entry = CacheEntry(
                    ats_type=row["ats_type"],
                    token=row["token"],
                    status=row["status"],
                    reason=row.get("reason", ""),
                    checked_at=datetime.fromisoformat(row["checked_at"]),
                    titles=list(row.get("titles") or []),
                    name=row.get("name"),
                )
            except (ValueError, KeyError, TypeError):
                continue
            self._entries[(entry.ats_type, entry.token.lower())] = entry

    def put(
        self,
        ats_type: str,
        token: str,
        status: str,
        reason: str,
        checked_at: datetime,
        *,
        titles: list[str] | None = None,
        name: str | None = None,
    ) -> None:
        self._entries[(ats_type, token.lower())] = CacheEntry(
            ats_type, token, status, reason, checked_at, list(titles or []), name
        )

    def get(self, ats_type: str, token: str, *, now: datetime) -> CacheEntry | None:
        """Return a definitive (accept/omit) entry inside the TTL; quarantine is never a hit."""
        entry = self._entries.get((ats_type, token.lower()))
        if entry is None or entry.status not in (ACCEPT, OMIT):
            return None
        if now - entry.checked_at > timedelta(days=PROBE_CACHE_TTL_DAYS):
            return None
        return entry

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            for entry in self._entries.values():
                fh.write(
                    json.dumps(
                        {
                            "ats_type": entry.ats_type,
                            "token": entry.token,
                            "status": entry.status,
                            "reason": entry.reason,
                            "checked_at": entry.checked_at.isoformat(),
                            "titles": entry.titles,
                            "name": entry.name,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        os.replace(tmp, self.path)


async def verify_candidates(
    client: httpx.AsyncClient,
    candidates: Iterable[Candidate],
    cache: ProbeCache,
    *,
    tier1_slugs: Iterable[str],
    now: datetime,
    on_result: Callable[[ProbeResult], None] | None = None,
    chunk_size: int = VERIFY_CHUNK_SIZE,
    on_chunk: Callable[[], None] | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> list[ProbeResult]:
    """Probe candidates chunk by chunk so long runs can persist progress and be time-boxed.

    ``should_stop`` is consulted before each chunk; candidates in chunks never started are
    left out of the result and out of the cache, so a re-run simply continues with them.
    """
    if chunk_size < 1:
        raise ValueError("chunk_size must be a positive integer")
    gate = HostGate()
    tier1 = tuple(tier1_slugs)
    unique: dict[tuple[str, str], Candidate] = {}
    for cand in candidates:
        unique.setdefault(cand.key, cand)

    async def run(cand: Candidate) -> ProbeResult:
        hit = cache.get(cand.ats_type, cand.token, now=now)
        if hit is not None:
            result = _result(cand, hit.status, hit.reason, titles=hit.titles, from_cache=True)
        else:
            result = await probe_candidate(client, cand, gate, tier1_slugs=tier1, now=now)
            cache.put(
                cand.ats_type,
                cand.token,
                result.status,
                result.reason,
                now,
                titles=result.titles,
                name=cand.name,
            )
        if on_result is not None:
            on_result(result)
        return result

    pending = list(unique.values())
    results: list[ProbeResult] = []
    for start in range(0, len(pending), chunk_size):
        if should_stop is not None and should_stop():
            break
        chunk = pending[start : start + chunk_size]
        results.extend(await asyncio.gather(*(run(c) for c in chunk)))
        if on_chunk is not None:
            on_chunk()
    return results
