"""Normalize job apply URLs for deduplication."""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_STRIP_QUERY_PREFIXES = ("utm_", "fbclid", "gclid", "mc_", "ref", "source")


def normalize_apply_url(url: str) -> str:
    """Lowercase scheme/host/path; drop common tracking query params."""
    raw = (url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    kept = []
    for key, val in parse_qsl(parsed.query, keep_blank_values=True):
        kl = key.lower()
        if any(kl == p or kl.startswith(p) for p in _STRIP_QUERY_PREFIXES):
            continue
        kept.append((key, val))
    query = urlencode(kept)
    return urlunparse(
        (
            (parsed.scheme or "https").lower(),
            netloc,
            path,
            "",
            query,
            "",
        )
    )


__all__ = ["normalize_apply_url"]
