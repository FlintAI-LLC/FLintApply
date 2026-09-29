#!/usr/bin/env python3
"""Harvest ATS board tokens from the Internet Archive CDX index (Phase B discovery).

Usage (from ``backend/``, laptop-side only):

  uv run python scripts/corpus/harvest_wayback.py
  uv run python scripts/corpus/harvest_wayback.py --max-seconds 600 --hosts jobs.lever.co

One request at a time, paced, honoring ``Retry-After``. Time-boxed (default 3 hours) and
resumable: progress lives in ``wayback_raw/state.json`` so a re-run continues where it
stopped. New tokens are appended to ``candidates.jsonl`` with ``source=wayback``; they still
have to pass ``verify_candidates.py`` before they can reach the seed.
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import os
import sys
import tempfile
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.career_watch.job_corpus_seed import token_is_safe  # noqa: E402
from scripts.corpus.ats_url_parse import USER_AGENT, ParsedAtsUrl, parse_ats_url  # noqa: E402

DATA_DIR = BACKEND_ROOT / "data" / "job_corpus"
DEFAULT_RAW_DIR = DATA_DIR / "wayback_raw"
DEFAULT_CANDIDATES = DATA_DIR / "candidates.jsonl"

CDX_URL = "https://web.archive.org/cdx/search/cdx"
DEFAULT_HOSTS: tuple[str, ...] = (
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "jobs.ashbyhq.com",
    "jobs.lever.co",
    "careers.smartrecruiters.com",
    "apply.workable.com",
)
SOURCE = "wayback"
DEFAULT_MAX_SECONDS = 3 * 3600
DEFAULT_MIN_INTERVAL = 1.5
DEFAULT_MAX_RAW_BYTES = 2 * 1024**3
PAGE_LIMIT = 50_000
REQUEST_TIMEOUT_SECONDS = 180.0
MAX_ATTEMPTS = 3
MAX_RETRY_AFTER_SECONDS = 300.0
MIN_RETRY_SECONDS = 1.0
BACKOFF_BASE_SECONDS = 5.0
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

# Path segments on ATS hosts that are assets or app routes, never a company board.
_RESERVED_TOKENS = frozenset(
    {
        "embed", "static", "assets", "robots.txt", "favicon.ico", "widget", "v1", "api",
        "health", "sitemap.xml", "jobs", "job", "apply", "cdn-cgi", "login", "signin",
    }
)
_GREENHOUSE_HOSTS = frozenset({"boards.greenhouse.io", "job-boards.greenhouse.io"})

Sleep = Callable[[float], Awaitable[None]]
Clock = Callable[[], float]


def parse_cdx_page(text: str) -> tuple[list[str], str | None]:
    """Split a CDX text page into URLs and the optional resume key (after a blank line)."""
    urls: list[str] = []
    resume_key: str | None = None
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            if not urls:
                continue
            following = [x.strip() for x in lines[index + 1 :] if x.strip()]
            resume_key = following[0] if following else None
            break
        urls.append(line.strip())
    return urls, resume_key


def extract_token(url: str) -> ParsedAtsUrl | None:
    """Board token from an archived URL, or None for noise and unsafe tokens."""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    segments = [s for s in parts.path.split("/") if s]

    if host in _GREENHOUSE_HOSTS and segments and segments[0].lower() == "embed":
        values = parse_qs(parts.query).get("for") or []
        token = values[0].strip() if values else ""
        if token and token.lower() not in _RESERVED_TOKENS and token_is_safe("greenhouse", token):
            return ParsedAtsUrl(ats_type="greenhouse", token=token)
        return None

    parsed = parse_ats_url(url)
    if parsed is None or parsed.token.lower() in _RESERVED_TOKENS:
        return None
    if not token_is_safe(parsed.ats_type, parsed.token):
        return None
    return parsed


@dataclass
class _DeadlineReached(Exception):
    """Raised inside a retry wait when the time-box runs out."""


@dataclass
class HarvestReport:
    pages: int = 0
    urls_seen: int = 0
    new_tokens: int = 0
    stopped_reason: str = "complete"
    host_status: dict[str, str] = field(default_factory=dict)


class WaybackHarvester:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient,
        raw_dir: Path = DEFAULT_RAW_DIR,
        candidates_path: Path = DEFAULT_CANDIDATES,
        hosts: tuple[str, ...] = DEFAULT_HOSTS,
        max_seconds: float = DEFAULT_MAX_SECONDS,
        min_interval: float = DEFAULT_MIN_INTERVAL,
        max_raw_bytes: int = DEFAULT_MAX_RAW_BYTES,
        page_limit: int = PAGE_LIMIT,
        sleep: Sleep = asyncio.sleep,
        clock: Clock = time.monotonic,
    ) -> None:
        self._client = client
        self._raw_dir = raw_dir
        self._candidates_path = candidates_path
        self._hosts = hosts
        self._max_seconds = max_seconds
        self._min_interval = min_interval
        self._max_raw_bytes = max_raw_bytes
        self._page_limit = page_limit
        self._sleep = sleep
        self._clock = clock
        self._last_request_at: float | None = None
        self._started_at = 0.0
        self._state: dict[str, dict[str, object]] = {}
        self._known: set[tuple[str, str]] = set()
        self._raw_bytes = 0

    # ------------------------------------------------------------ state

    @property
    def _state_path(self) -> Path:
        return self._raw_dir / "state.json"

    def _load_state(self) -> None:
        try:
            raw = json.loads(self._state_path.read_text(encoding="utf-8"))
            self._state = raw if isinstance(raw, dict) else {}
        except (OSError, ValueError):
            self._state = {}

    def _save_state(self) -> None:
        self._raw_dir.mkdir(parents=True, exist_ok=True)
        handle, tmp_name = tempfile.mkstemp(dir=self._raw_dir, suffix=".tmp")
        with os.fdopen(handle, "w", encoding="utf-8") as fh:
            json.dump(self._state, fh)
        os.replace(tmp_name, self._state_path)

    def _load_known(self) -> None:
        self._known = set()
        if not self._candidates_path.is_file():
            return
        for line in self._candidates_path.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and row.get("ats_type") and row.get("token"):
                self._known.add((str(row["ats_type"]), str(row["token"]).lower()))

    # ------------------------------------------------------------ http

    def _deadline_hit(self) -> bool:
        return self._clock() - self._started_at >= self._max_seconds

    async def _pace(self) -> None:
        if self._last_request_at is not None:
            wait = self._min_interval - (self._clock() - self._last_request_at)
            if wait > 0:
                await self._sleep(wait)

    @staticmethod
    def _retry_after(response: httpx.Response, attempt: int) -> float:
        header = response.headers.get("Retry-After", "").strip()
        try:
            seconds = float(header)
        except ValueError:
            try:
                seconds = (parsedate_to_datetime(header) - datetime.now(timezone.utc)).total_seconds()
            except (TypeError, ValueError):
                seconds = BACKOFF_BASE_SECONDS * (2**attempt)
        return max(MIN_RETRY_SECONDS, min(seconds, MAX_RETRY_AFTER_SECONDS))

    async def _bounded_sleep(self, seconds: float) -> None:
        """Sleep without ever running past the time-box; raise once it is exhausted."""
        remaining = self._max_seconds - (self._clock() - self._started_at)
        if remaining <= 0:
            raise _DeadlineReached
        await self._sleep(min(seconds, remaining))
        if self._deadline_hit():
            raise _DeadlineReached

    async def _fetch(self, host: str, resume_key: str | None) -> str | None:
        params = {
            "url": host,
            "matchType": "domain",
            "collapse": "urlkey",
            "fl": "original",
            "filter": "statuscode:200",
            "showResumeKey": "true",
            "limit": str(self._page_limit),
        }
        if resume_key:
            params["resumeKey"] = resume_key

        for attempt in range(MAX_ATTEMPTS):
            try:
                response = await self._client.get(
                    CDX_URL,
                    params=params,
                    headers={"User-Agent": USER_AGENT},
                    timeout=REQUEST_TIMEOUT_SECONDS,
                )
            except httpx.HTTPError:
                self._last_request_at = self._clock()
                if attempt + 1 < MAX_ATTEMPTS:
                    await self._bounded_sleep(BACKOFF_BASE_SECONDS * (2**attempt))
                continue
            self._last_request_at = self._clock()
            if response.status_code == 200:
                return response.text
            if response.status_code in RETRYABLE_STATUS and attempt + 1 < MAX_ATTEMPTS:
                await self._bounded_sleep(self._retry_after(response, attempt))
                self._last_request_at = self._clock()
                continue
            if response.status_code not in RETRYABLE_STATUS:
                return None
        return None

    # ------------------------------------------------------------ processing

    def _cache_raw(self, host: str, page: int, text: str) -> None:
        self._raw_dir.mkdir(parents=True, exist_ok=True)
        path = self._raw_dir / f"{host}_{page:06d}.txt.gz"
        payload = gzip.compress(text.encode("utf-8"))
        path.write_bytes(payload)
        self._raw_bytes += len(payload)

    def _append_candidates(self, urls: list[str]) -> int:
        fresh: list[dict[str, str]] = []
        now = datetime.now(timezone.utc).isoformat()
        for url in urls:
            parsed = extract_token(url)
            if parsed is None:
                continue
            key = (parsed.ats_type, parsed.token.lower())
            if key in self._known:
                continue
            self._known.add(key)
            fresh.append(
                {
                    "token": parsed.token,
                    "ats_type": parsed.ats_type,
                    "source": SOURCE,
                    "discovered_at": now,
                }
            )
        if fresh:
            self._candidates_path.parent.mkdir(parents=True, exist_ok=True)
            with self._candidates_path.open("a", encoding="utf-8") as fh:
                for row in fresh:
                    fh.write(json.dumps(row) + "\n")
        return len(fresh)

    def _entry_for(self, host: str) -> dict[str, object]:
        raw = self._state.get(host)
        valid = (
            isinstance(raw, dict)
            and isinstance(raw.get("pages", 0), int)
            and (raw.get("resume_key") is None or isinstance(raw.get("resume_key"), str))
        )
        if not valid:
            raw = {"resume_key": None, "pages": 0, "done": False}
        entry: dict[str, object] = raw  # type: ignore[assignment]
        self._state[host] = entry
        return entry

    async def _harvest_host(self, host: str, report: HarvestReport) -> str | None:
        """Return a stop reason ("deadline" / "disk_cap") or None when the host is finished."""
        entry = self._entry_for(host)
        if entry.get("done"):
            report.host_status[host] = "complete"
            return None

        # A key we have already requested means the index is not advancing; stop rather than
        # re-download the same page until the time-box or disk cap runs out.
        seen_keys: set[str] = {entry["resume_key"]} if entry.get("resume_key") else set()

        while True:
            if self._deadline_hit():
                return "deadline"
            if self._raw_bytes >= self._max_raw_bytes:
                return "disk_cap"
            await self._pace()
            if self._deadline_hit():
                return "deadline"

            try:
                text = await self._fetch(host, entry.get("resume_key"))  # type: ignore[arg-type]
            except _DeadlineReached:
                return "deadline"
            if text is None:
                report.host_status[host] = "error"
                return None

            urls, next_key = parse_cdx_page(text)
            page_number = int(entry.get("pages", 0))
            self._cache_raw(host, page_number, text)
            report.urls_seen += len(urls)
            report.new_tokens += self._append_candidates(urls)
            report.pages += 1
            stalled = next_key is not None and next_key in seen_keys
            entry["pages"] = page_number + 1
            entry["resume_key"] = None if stalled else next_key
            entry["done"] = next_key is None or stalled
            self._save_state()

            if next_key is None or stalled:
                report.host_status[host] = "complete"
                return None
            seen_keys.add(next_key)

    async def run(self) -> HarvestReport:
        report = HarvestReport()
        self._started_at = self._clock()
        self._load_state()
        self._load_known()
        self._raw_bytes = sum(p.stat().st_size for p in self._raw_dir.glob("*.gz"))

        for host in self._hosts:
            reason = await self._harvest_host(host, report)
            if reason is not None:
                report.stopped_reason = reason
                report.host_status.setdefault(host, "stopped")
                break
        else:
            if any(status == "error" for status in report.host_status.values()):
                report.stopped_reason = "partial"
        return report


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hosts", nargs="+", default=list(DEFAULT_HOSTS))
    parser.add_argument("--max-seconds", type=float, default=DEFAULT_MAX_SECONDS)
    parser.add_argument("--min-interval", type=float, default=DEFAULT_MIN_INTERVAL)
    parser.add_argument("--max-raw-gb", type=float, default=DEFAULT_MAX_RAW_BYTES / 1024**3)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    return parser.parse_args(argv)


async def main() -> None:
    args = _parse_args()
    async with httpx.AsyncClient() as client:
        harvester = WaybackHarvester(
            client=client,
            raw_dir=args.raw_dir,
            candidates_path=args.candidates,
            hosts=tuple(args.hosts),
            max_seconds=args.max_seconds,
            min_interval=args.min_interval,
            max_raw_bytes=int(args.max_raw_gb * 1024**3),
        )
        report = await harvester.run()
    print(
        f"stopped={report.stopped_reason} pages={report.pages} urls={report.urls_seen} "
        f"new_tokens={report.new_tokens}"
    )
    for host, status in report.host_status.items():
        print(f"  {host:<32} {status}")


if __name__ == "__main__":
    asyncio.run(main())
