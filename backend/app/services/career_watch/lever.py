"""Lever public postings API adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.config import settings
from app.models.career_watch import WatchedCompany
from app.parsers.jd_normalize import normalize_job_description
from app.services.career_watch.fetch import fetch_json
from app.services.career_watch.types import ParsedJob


def _normalize_description(raw: str) -> str:
    return normalize_job_description(raw or "", max_chars=settings.JD_TEXT_MAX_CHARS).text


def _lever_description(item: dict[str, Any]) -> str:
    plain = str(item.get("descriptionPlain") or "")
    html = str(item.get("description") or "")
    return _normalize_description(plain or html)


def _parse_ts(value: object) -> datetime | None:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)
    if isinstance(value, str) and value.isdigit():
        return datetime.fromtimestamp(int(value) / 1000.0, tz=timezone.utc)
    return None


def _build_api_url(board_token: str) -> str:
    return f"https://api.lever.co/v0/postings/{board_token}?mode=json"


class LeverAdapter:
    async def fetch_jobs(
        self,
        company: WatchedCompany,
        *,
        client: httpx.AsyncClient,
    ) -> list[ParsedJob]:
        token = company.ats_board_token
        if not token:
            raise ValueError("lever adapter requires ats_board_token")

        payload = await fetch_json(client, _build_api_url(token))
        if not isinstance(payload, list):
            return []

        parsed: list[ParsedJob] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            job_id = str(item.get("id") or "")
            if not job_id:
                continue
            categories = item.get("categories") or {}
            location = ""
            if isinstance(categories, dict):
                location = str(categories.get("location") or "")
            parsed.append(
                ParsedJob(
                    external_job_id=job_id,
                    title=str(item.get("text") or "Untitled"),
                    location=location,
                    apply_url=str(item.get("hostedUrl") or item.get("applyUrl") or ""),
                    description_text=_lever_description(item),
                    posted_at=_parse_ts(item.get("createdAt")),
                    raw_payload=item,
                )
            )
        return parsed


def parse_lever_payload(items: list[dict[str, Any]]) -> list[ParsedJob]:
    parsed: list[ParsedJob] = []
    for item in items:
        job_id = str(item.get("id") or "")
        if not job_id:
            continue
        categories = item.get("categories") or {}
        location = str(categories.get("location") or "") if isinstance(categories, dict) else ""
        parsed.append(
            ParsedJob(
                external_job_id=job_id,
                title=str(item.get("text") or "Untitled"),
                location=location,
                apply_url=str(item.get("hostedUrl") or ""),
                description_text=_lever_description(item),
                posted_at=_parse_ts(item.get("createdAt")),
                raw_payload=item,
            )
        )
    return parsed


__all__ = ["LeverAdapter", "parse_lever_payload"]
