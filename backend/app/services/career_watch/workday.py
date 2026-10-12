"""Workday careers adapter (CXS JSON API + static HTML fallback)."""

from __future__ import annotations

import json
import re
from datetime import datetime
from html import unescape
from urllib.parse import urljoin, urlparse

import httpx

from app.models.career_watch import WatchedCompany
from app.services.career_watch.fetch import CareerWatchFetchError, fetch_text, post_json
from app.services.career_watch.types import ParsedJob

_EMBEDDED_JSON_RE = re.compile(
    r"window\.(?:workday|WD)\.(?:config|pageConfig)\s*=\s*(\{.*?\});",
    re.DOTALL,
)
_JOB_LINK_RE = re.compile(
    r'href="(/[^"]+/job/[^"]+)"[^>]*>([^<]+)</a>',
    re.IGNORECASE,
)
_WORKDAY_LOCALE_SEGMENT_RE = re.compile(r"^[a-z]{2}(-[a-z]{2,4})?$", re.IGNORECASE)
_CXS_PAGE_LIMIT = 20
_CXS_MAX_JOBS = 500


def _parse_posted_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def workday_cxs_api_url(poll_url: str, board_token: str | None) -> str | None:
    """Public Workday job-search API used by the careers SPA."""
    if not board_token or "/" not in board_token:
        return None
    parsed = urlparse(poll_url)
    if "myworkdayjobs.com" not in parsed.netloc.lower():
        return None
    tenant, site = board_token.split("/", 1)
    if not tenant or not site:
        return None
    return f"{parsed.scheme}://{parsed.netloc}/wday/cxs/{tenant}/{site}/jobs"


def _locale_from_poll_url(poll_url: str) -> str | None:
    segments = [segment for segment in urlparse(poll_url).path.split("/") if segment]
    if segments and _WORKDAY_LOCALE_SEGMENT_RE.match(segments[0]):
        return segments[0]
    return None


def _site_from_board_token(board_token: str | None) -> str | None:
    if not board_token or "/" not in board_token:
        return None
    return board_token.split("/", 1)[1]


def build_workday_job_url(
    *,
    origin: str,
    locale: str | None,
    site: str,
    external_path: str,
) -> str:
    path = external_path if external_path.startswith("/") else f"/{external_path}"
    base = origin.rstrip("/")
    if locale:
        return f"{base}/{locale}/{site}{path}"
    return f"{base}/{site}{path}"


def parse_workday_cxs_payload(
    payload: object,
    *,
    origin: str,
    locale: str | None,
    site: str,
) -> list[ParsedJob]:
    if not isinstance(payload, dict):
        return []
    postings = payload.get("jobPostings")
    if not isinstance(postings, list):
        return []

    parsed: list[ParsedJob] = []
    for item in postings:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        external_path = str(item.get("externalPath") or "").strip()
        if not title or not external_path:
            continue
        bullet = item.get("bulletFields")
        job_id = ""
        if isinstance(bullet, list) and bullet:
            job_id = str(bullet[0])
        if not job_id:
            job_id = external_path.rstrip("/").split("/")[-1]
        location = str(item.get("locationsText") or item.get("location") or "")
        apply_url = build_workday_job_url(
            origin=origin,
            locale=locale,
            site=site,
            external_path=external_path,
        )
        parsed.append(
            ParsedJob(
                external_job_id=job_id[:64],
                title=title,
                location=location,
                apply_url=apply_url,
                description_text="",
                posted_at=None,
                raw_payload=item,
            )
        )
    return parsed


async def fetch_workday_cxs_jobs(
    company: WatchedCompany,
    *,
    client: httpx.AsyncClient,
    max_jobs: int = _CXS_MAX_JOBS,
) -> list[ParsedJob]:
    poll_url = company.effective_poll_url
    api_url = workday_cxs_api_url(poll_url, company.ats_board_token)
    site = _site_from_board_token(company.ats_board_token)
    if not api_url or not site:
        return []

    origin = f"{urlparse(poll_url).scheme}://{urlparse(poll_url).netloc}"
    locale = _locale_from_poll_url(poll_url)
    collected: list[ParsedJob] = []
    offset = 0
    total = None

    cap = max(1, min(max_jobs, _CXS_MAX_JOBS))
    while len(collected) < cap:
        body = {
            "appliedFacets": {},
            "limit": _CXS_PAGE_LIMIT,
            "offset": offset,
            "searchText": "",
        }
        payload = await post_json(client, api_url, body)
        page_jobs = parse_workday_cxs_payload(
            payload,
            origin=origin,
            locale=locale,
            site=site,
        )
        if not page_jobs:
            break
        collected.extend(page_jobs)
        if isinstance(payload, dict) and total is None:
            raw_total = payload.get("total")
            if isinstance(raw_total, int):
                total = raw_total
        offset += len(page_jobs)
        if total is not None and offset >= total:
            break
        if len(page_jobs) < _CXS_PAGE_LIMIT:
            break

    return collected[:cap]


class WorkdayAdapter:
    async def fetch_jobs(
        self,
        company: WatchedCompany,
        *,
        client: httpx.AsyncClient,
        max_jobs: int | None = None,
    ) -> list[ParsedJob]:
        poll_url = company.effective_poll_url
        cap = max_jobs if max_jobs is not None else _CXS_MAX_JOBS
        try:
            jobs = await fetch_workday_cxs_jobs(company, client=client, max_jobs=cap)
        except CareerWatchFetchError:
            jobs = []
        if jobs:
            return jobs
        html = await fetch_text(client, poll_url, accept="text/html")
        return parse_workday_html(html, base_url=poll_url)


def parse_workday_html(html: str, *, base_url: str) -> list[ParsedJob]:
    """Extract job links from a Workday careers HTML page."""
    parsed: list[ParsedJob] = []
    seen: set[str] = set()

    for match in _JOB_LINK_RE.finditer(html):
        href, title = match.group(1), unescape(match.group(2).strip())
        if not title or href in seen:
            continue
        seen.add(href)
        job_id = href.rstrip("/").split("/")[-1]
        apply_url = urljoin(base_url, href)
        parsed.append(
            ParsedJob(
                external_job_id=job_id,
                title=title,
                location="",
                apply_url=apply_url,
                description_text="",
                posted_at=None,
                raw_payload={"href": href, "title": title},
            )
        )

    if parsed:
        return parsed

    embedded = _EMBEDDED_JSON_RE.search(html)
    if embedded:
        try:
            config = json.loads(embedded.group(1))
        except json.JSONDecodeError:
            config = {}
        postings = config.get("postings") or config.get("jobs") or []
        if isinstance(postings, list):
            for item in postings:
                if not isinstance(item, dict):
                    continue
                job_id = str(item.get("externalPath") or item.get("bulletFields", [""])[0])
                if not job_id:
                    continue
                parsed.append(
                    ParsedJob(
                        external_job_id=job_id,
                        title=str(item.get("title") or "Untitled"),
                        location=str(item.get("location") or ""),
                        apply_url=str(item.get("externalUrl") or base_url),
                        description_text=str(item.get("description") or ""),
                        posted_at=_parse_posted_at(str(item.get("postedOn") or "") or None),
                        raw_payload=item,
                    )
                )
    return parsed


__all__ = [
    "WorkdayAdapter",
    "build_workday_job_url",
    "fetch_workday_cxs_jobs",
    "parse_workday_cxs_payload",
    "parse_workday_html",
    "workday_cxs_api_url",
]
