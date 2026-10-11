"""Shared ATS host detection from arbitrary URLs (resolver + detect)."""

from __future__ import annotations

import re
from urllib.parse import urlparse

# Host/path fragments that indicate a known ATS board (order: prefer API boards).
_ATS_HOST_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\.icims\.com", re.I), "icims"),
    (re.compile(r"\.myworkdayjobs\.com", re.I), "workday"),
    (re.compile(r"boards\.greenhouse\.io", re.I), "greenhouse"),
    (re.compile(r"job-boards\.greenhouse\.io", re.I), "greenhouse"),
    (re.compile(r"jobs\.lever\.co", re.I), "lever"),
    (re.compile(r"jobs\.ashbyhq\.com", re.I), "ashby"),
    (re.compile(r"smartrecruiters\.com", re.I), "smartrecruiters"),
    (re.compile(r"apply\.workable\.com", re.I), "workable"),
    (re.compile(r"\.workable\.com", re.I), "workable"),
    (re.compile(r"\.recruitee\.com", re.I), "recruitee"),
    (re.compile(r"\.breezy\.hr", re.I), "breezy"),
    (re.compile(r"\.jobs\.personio\.(com|de)", re.I), "personio"),
    (re.compile(r"\.bamboohr\.com", re.I), "bamboohr"),
    (re.compile(r"\.taleo\.net", re.I), "taleo"),
)


def normalize_http_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if not parsed.scheme:
        parsed = urlparse(f"https://{url.strip()}")
    return parsed.geturl()


def host_of(url: str) -> str:
    return (urlparse(normalize_http_url(url)).hostname or "").lower()


def is_known_ats_url(url: str) -> bool:
    hostname = host_of(url)
    return any(pat.search(hostname) for pat, _ in _ATS_HOST_PATTERNS)


def score_ats_url(url: str) -> int:
    """Higher = stronger ATS signal (used to pick canonical board)."""
    hostname = host_of(url)
    for index, (pat, _name) in enumerate(_ATS_HOST_PATTERNS):
        if pat.search(hostname):
            return 100 - index
    return 0


_HREF_RE = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.I)


def extract_candidate_urls(html: str, *, base_url: str) -> list[str]:
    from urllib.parse import urljoin

    found: list[str] = []
    seen: set[str] = set()
    for match in _HREF_RE.finditer(html or ""):
        href = match.group(1).strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href)
        if absolute not in seen:
            seen.add(absolute)
            found.append(absolute)
    return found


__all__ = [
    "extract_candidate_urls",
    "host_of",
    "is_known_ats_url",
    "normalize_http_url",
    "score_ats_url",
]
