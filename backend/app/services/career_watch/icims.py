"""iCIMS careers board adapter (JSON probe + server-rendered HTML)."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx

from app.models.career_watch import WatchedCompany
from app.services.career_watch.fetch import fetch_json, fetch_text
from app.services.career_watch.ssrf_guard import CareerWatchSsrfError
from app.services.career_watch.generic_html import parse_jsonld_job_postings
from app.services.career_watch.types import ParsedJob

_ICIMS_ROW_RE = re.compile(
    r'<div[^>]+class="[^"]*iCIMS_JobsTable[^"]*"[^>]*>(?P<body>.*?)</div>',
    re.I | re.DOTALL,
)
_ICIMS_JOB_LINK_RE = re.compile(
    r'<a[^>]+href="(?P<href>[^"]+)"[^>]*>(?P<title>[^<]{3,200})</a>',
    re.I,
)
_JSON_LIST_KEYS = ("jobs", "results", "postings", "requisitions")


def _search_urls(poll_url: str, token: str | None) -> list[str]:
    parsed = urlparse(poll_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    paths = [
        poll_url,
        f"{base}/jobs/search?ss=1&searchRelation=keyword_all",
        f"{base}/jobs/search?in_iframe=1",
    ]
    if token:
        paths.append(f"https://{token}.icims.com/jobs/search?ss=1")
    seen: set[str] = set()
    ordered: list[str] = []
    for url in paths:
        if url not in seen:
            seen.add(url)
            ordered.append(url)
    return ordered


def _parse_icims_json_payload(payload: object) -> list[ParsedJob]:
    if not isinstance(payload, dict):
        return []
    jobs_raw: list[Any] = []
    for key in _JSON_LIST_KEYS:
        raw = payload.get(key)
        if isinstance(raw, list) and raw:
            jobs_raw = raw
            break
    if not jobs_raw:
        return []

    parsed: list[ParsedJob] = []
    for item in jobs_raw:
        if not isinstance(item, dict):
            continue
        job_id = str(
            item.get("id")
            or item.get("jobId")
            or item.get("requisitionId")
            or item.get("slug")
            or ""
        )
        title = str(item.get("title") or item.get("jobTitle") or item.get("name") or "")
        if not job_id or not title:
            continue
        apply_url = str(item.get("url") or item.get("link") or item.get("applyUrl") or "")
        location = str(
            item.get("location")
            or item.get("locationName")
            or item.get("city")
            or ""
        )
        if isinstance(item.get("location"), dict):
            location = str(item["location"].get("city") or location)
        parsed.append(
            ParsedJob(
                external_job_id=job_id,
                title=title,
                location=location,
                apply_url=apply_url,
                description_text=str(item.get("description") or ""),
                posted_at=None,
                raw_payload=item,
            )
        )
    return parsed


def parse_icims_html(html: str, *, base_url: str) -> list[ParsedJob]:
    jsonld = parse_jsonld_job_postings(html, base_url=base_url)
    if jsonld:
        return jsonld

    parsed: list[ParsedJob] = []
    seen: set[str] = set()
    bodies = [html]
    for match in _ICIMS_ROW_RE.finditer(html):
        bodies.append(match.group("body"))

    for body in bodies:
        for match in _ICIMS_JOB_LINK_RE.finditer(body):
            href = match.group("href").strip()
            title = re.sub(r"\s+", " ", match.group("title")).strip()
            if not href or not title:
                continue
            if "job" not in href.lower() and "requisition" not in href.lower():
                continue
            absolute = urljoin(base_url, href)
            key = absolute.lower()
            if key in seen:
                continue
            seen.add(key)
            parsed.append(
                ParsedJob(
                    external_job_id=absolute.rsplit("/", 1)[-1][:64] or key[:32],
                    title=title,
                    location="",
                    apply_url=absolute,
                    description_text="",
                    posted_at=None,
                    raw_payload={"href": absolute, "title": title},
                )
            )
    return parsed


class IcimsAdapter:
    async def fetch_jobs(
        self,
        company: WatchedCompany,
        *,
        client: httpx.AsyncClient,
    ) -> list[ParsedJob]:
        poll_url = company.effective_poll_url
        token = company.ats_board_token

        for url in _search_urls(poll_url, token):
            json_url = url if "json" in url else f"{url}{'&' if '?' in url else '?'}format=json"
            try:
                payload = await fetch_json(client, json_url)
            except CareerWatchSsrfError:
                raise
            except Exception:
                payload = None
            if payload is not None:
                jobs = _parse_icims_json_payload(payload)
                if isinstance(payload, list):
                    jobs = _parse_icims_json_payload({"jobs": payload})
                if jobs:
                    return jobs

            try:
                html = await fetch_text(client, url, accept="text/html")
            except CareerWatchSsrfError:
                raise
            except Exception:
                continue
            jobs = parse_icims_html(html, base_url=url)
            if jobs:
                return jobs

        return []


__all__ = ["IcimsAdapter", "parse_icims_html"]
