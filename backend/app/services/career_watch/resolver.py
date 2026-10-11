"""Resolve marketing careers URLs to canonical ATS poll targets."""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import structlog

from app.brand import PRODUCT_NAME, PRODUCT_SITE_URL
from app.services.career_watch.ats_hosts import (
    extract_candidate_urls,
    host_of,
    is_known_ats_url,
    normalize_http_url,
    score_ats_url,
)
from app.services.career_watch.detect import detect_ats_from_url
from app.services.career_watch.ssrf_guard import CareerWatchSsrfError
from app.services.career_watch.types import AtsDetectionResult

log = structlog.get_logger("career_watch.resolver")

_RESOLVER_HEADERS = {
    "User-Agent": f"{PRODUCT_NAME}-CareerWatch/1.0 (+{PRODUCT_SITE_URL})",
    "Accept": "text/html,application/xhtml+xml,*/*",
}


@dataclass(frozen=True, slots=True)
class BoardResolution:
    input_url: str
    canonical_poll_url: str
    detection: AtsDetectionResult
    resolved_away_from_input: bool


def _pick_canonical_url(input_url: str, candidates: list[str]) -> str | None:
    input_host = host_of(input_url)
    scored: list[tuple[int, str]] = []
    for url in candidates:
        if not is_known_ats_url(url):
            continue
        url_host = host_of(url)
        if url_host == input_host:
            continue
        scored.append((score_ats_url(url), normalize_http_url(url)))
    if not scored:
        return None
    scored.sort(key=lambda item: (-item[0], item[1]))
    return scored[0][1]


async def resolve_careers_board(
    careers_page_url: str,
    *,
    client: httpx.AsyncClient,
) -> BoardResolution:
    """Fetch ``careers_page_url`` and infer the canonical ATS poll URL if needed."""
    normalized_input = normalize_http_url(careers_page_url)
    input_detection = detect_ats_from_url(normalized_input)

    if input_detection.ats_type.value not in {"generic_html", "unknown"}:
        return BoardResolution(
            input_url=normalized_input,
            canonical_poll_url=normalized_input,
            detection=input_detection,
            resolved_away_from_input=False,
        )

    try:
        response = await client.get(
            normalized_input,
            headers=_RESOLVER_HEADERS,
        )
        response.raise_for_status()
    except CareerWatchSsrfError:
        raise
    except httpx.HTTPError as exc:
        log.warning(
            "career_watch_resolve_fetch_failed",
            host=host_of(normalized_input),
            error=type(exc).__name__,
        )
        return BoardResolution(
            input_url=normalized_input,
            canonical_poll_url=normalized_input,
            detection=input_detection,
            resolved_away_from_input=False,
        )

    chain_urls = [str(response.url)]
    chain_urls.extend(str(r.url) for r in response.history)
    chain_urls.extend(
        extract_candidate_urls(response.text, base_url=str(response.url))
    )

    canonical = _pick_canonical_url(normalized_input, chain_urls)
    if canonical is None:
        return BoardResolution(
            input_url=normalized_input,
            canonical_poll_url=normalized_input,
            detection=input_detection,
            resolved_away_from_input=False,
        )

    detection = detect_ats_from_url(canonical)
    return BoardResolution(
        input_url=normalized_input,
        canonical_poll_url=canonical,
        detection=detection,
        resolved_away_from_input=True,
    )


__all__ = ["BoardResolution", "resolve_careers_board"]
