"""Title-level seniority matching for Career Watch filters."""

from __future__ import annotations

import re

# Map watch filter values to title substrings (case-insensitive word boundaries).
_LEVEL_MARKERS: dict[str, tuple[str, ...]] = {
    "intern": ("intern", "internship"),
    "mid": ("mid-level", "mid level", "engineer ii", "software engineer ii"),
    "senior": ("senior", "sr.", "sr "),
    "staff": ("staff",),
    "principal": ("principal", "distinguished"),
    "manager": ("manager", "mgr"),
    "director": ("director",),
}

_WORD_BOUNDARY = re.compile(r"[a-z0-9]+")


def title_matches_seniority_levels(title: str, levels: list[str] | None) -> bool:
    """When levels is empty, all titles pass. Otherwise require one marker hit."""
    if not levels:
        return True
    title_l = title.casefold()
    tokens = set(_WORD_BOUNDARY.findall(title_l))
    for level in levels:
        markers = _LEVEL_MARKERS.get(level.strip().lower())
        if not markers:
            continue
        for marker in markers:
            if " " in marker:
                if marker in title_l:
                    return True
            elif marker.rstrip(".") in tokens or marker in title_l:
                return True
    return False


__all__ = ["title_matches_seniority_levels"]
