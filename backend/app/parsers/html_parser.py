"""HTML → plain-text converter used when JD URLs return raw HTML pages.

Uses only stdlib (html.parser) — no extra dependencies.
"""
from __future__ import annotations

from app.parsers.jd_normalize import normalize_job_description


def strip_html_to_text(raw: str, max_chars: int = 60_000) -> str:
    """Convert HTML or entity-encoded JD text to plain text."""
    return normalize_job_description(raw, max_chars=max_chars).text
