"""Parse ATS board tokens from public job-board URLs."""

from __future__ import annotations

import re
from dataclasses import dataclass

USER_AGENT = "FlintApplyCorpusBot/1.0"

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "greenhouse",
        re.compile(
            r"https?://(?:boards|job-boards)\.greenhouse\.io/(?P<token>[^/?#]+)",
            re.IGNORECASE,
        ),
    ),
    (
        "lever",
        re.compile(r"https?://jobs\.lever\.co/(?P<token>[^/?#]+)", re.IGNORECASE),
    ),
    (
        "ashby",
        re.compile(r"https?://jobs\.ashbyhq\.com/(?P<token>[^/?#]+)", re.IGNORECASE),
    ),
    (
        "workable",
        re.compile(r"https?://apply\.workable\.com/(?P<token>[^/?#]+)", re.IGNORECASE),
    ),
    (
        "smartrecruiters",
        re.compile(
            r"https?://careers\.smartrecruiters\.com/(?P<token>[^/?#]+)",
            re.IGNORECASE,
        ),
    ),
    (
        "recruitee",
        re.compile(
            r"https?://(?P<token>[^./]+)\.recruitee\.com",
            re.IGNORECASE,
        ),
    ),
)


@dataclass(frozen=True)
class ParsedAtsUrl:
    ats_type: str
    token: str


def parse_ats_url(url: str) -> ParsedAtsUrl | None:
    if not url or not isinstance(url, str):
        return None
    cleaned = url.strip()
    for ats_type, pattern in _PATTERNS:
        m = pattern.search(cleaned)
        if not m:
            continue
        token = m.group("token").strip()
        if not token or token.lower() in {"jobs", "job", "apply"}:
            continue
        return ParsedAtsUrl(ats_type=ats_type, token=token)
    return None


def dedupe_key(parsed: ParsedAtsUrl) -> tuple[str, str]:
    return (parsed.ats_type, parsed.token.lower())
