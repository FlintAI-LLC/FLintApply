"""Amazon Jobs (amazon.jobs) public search.json adapter."""

from __future__ import annotations

import re
from datetime import datetime
from html import unescape
from urllib.parse import urlparse

import httpx

from app.models.career_watch import WatchedCompany
from app.services.career_watch.fetch import CareerWatchFetchError, fetch_json
from app.services.career_watch.types import ParsedJob

_AMAZON_HOSTS = frozenset({"amazon.jobs", "www.amazon.jobs"})
_LOCALE_SEGMENT_RE = re.compile(r"^[a-z]{2}(-[a-z]{2,4})?$", re.IGNORECASE)
_PAGE_SIZE = 100
_DEFAULT_MAX_JOBS = 500
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def amazon_locale_from_url(url: str) -> str:
    """Locale segment for ``/en/search.json`` (defaults to ``en``)."""
    segments = [segment for segment in urlparse(url).path.split("/") if segment]
    if segments and _LOCALE_SEGMENT_RE.match(segments[0]):
        return segments[0]
    return "en"


def amazon_search_api_url(poll_url: str, locale: str | None) -> str:
    loc = locale or amazon_locale_from_url(poll_url)
    return f"https://www.amazon.jobs/{loc}/search.json"


def _parse_posted_at(value: str | None) -> datetime | None:
    if not value:
        return None
    cleaned = " ".join(value.split())
    for fmt in ("%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
    return None


def _strip_html(value: str) -> str:
    text = _HTML_TAG_RE.sub(" ", value)
    return " ".join(unescape(text).split())


def _job_apply_url(job_path: str) -> str:
    path = job_path if job_path.startswith("/") else f"/{job_path}"
    return f"https://www.amazon.jobs{path}"


def parse_amazon_search_payload(payload: object) -> list[ParsedJob]:
    if not isinstance(payload, dict):
        return []
    error = payload.get("error")
    if error:
        raise CareerWatchFetchError(f"Amazon Jobs API error: {error}")

    jobs_raw = payload.get("jobs") or []
    if not isinstance(jobs_raw, list):
        return []

    parsed: list[ParsedJob] = []
    for item in jobs_raw:
        if not isinstance(item, dict):
            continue
        job_id = str(item.get("id") or "")
        title = str(item.get("title") or "").strip()
        job_path = str(item.get("job_path") or "")
        if not job_id or not title or not job_path:
            continue
        location = str(
            item.get("normalized_location")
            or item.get("location")
            or ""
        ).strip()
        description = _strip_html(str(item.get("description") or ""))
        if not description:
            description = str(item.get("description_short") or "")
        parsed.append(
            ParsedJob(
                external_job_id=job_id,
                title=title,
                location=location,
                apply_url=_job_apply_url(job_path),
                description_text=description,
                posted_at=_parse_posted_at(str(item.get("posted_date") or "") or None),
                raw_payload=item,
            )
        )
    return parsed


async def fetch_amazon_jobs(
    company: WatchedCompany,
    *,
    client: httpx.AsyncClient,
    max_jobs: int | None = None,
) -> list[ParsedJob]:
    poll_url = company.effective_poll_url
    locale = company.ats_board_token or amazon_locale_from_url(poll_url)
    api_url = amazon_search_api_url(poll_url, locale)
    cap = max_jobs if max_jobs is not None else _DEFAULT_MAX_JOBS

    collected: list[ParsedJob] = []
    offset = 0
    while len(collected) < cap:
        params = {
            "result_limit": str(min(_PAGE_SIZE, cap - len(collected))),
            "offset": str(offset),
            "sort": "recent",
        }
        payload = await fetch_json(client, api_url, params=params)
        page_jobs = parse_amazon_search_payload(payload)
        if not page_jobs:
            break
        collected.extend(page_jobs)
        offset += len(page_jobs)
        if len(page_jobs) < _PAGE_SIZE:
            break
    return collected[:cap]


class AmazonJobsAdapter:
    async def fetch_jobs(
        self,
        company: WatchedCompany,
        *,
        client: httpx.AsyncClient,
        max_jobs: int | None = None,
    ) -> list[ParsedJob]:
        host = urlparse(company.effective_poll_url).netloc.lower()
        if host not in _AMAZON_HOSTS:
            raise ValueError("amazon_jobs adapter requires an amazon.jobs URL")
        return await fetch_amazon_jobs(company, client=client, max_jobs=max_jobs)


__all__ = [
    "AmazonJobsAdapter",
    "amazon_locale_from_url",
    "amazon_search_api_url",
    "fetch_amazon_jobs",
    "parse_amazon_search_payload",
]
