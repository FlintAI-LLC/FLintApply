"""Deterministic JD requirement line extraction for Phase 1 / Phase 1b."""

from __future__ import annotations

import re

_SECTION_MARKERS = (
    "required qualification",
    "minimum qualification",
    "must have",
    "must-have",
    "requirements:",
    "qualifications:",
    "what you'll need",
    "what you will need",
    "you have:",
    "you'll have:",
    "responsibilities:",
    "what you'll do",
)

_SECTION_EXIT_MARKERS = (
    "benefits",
    "perks",
    "compensation",
    "about us",
    "about the company",
    "about the team",
    "who we are",
    "equal opportunity",
    "eeo",
    "how to apply",
    "what we offer",
    "our culture",
    "why join",
)

_BULLET_PREFIX = re.compile(r"^\s*(?:\d+[\.)]\s+|[-•*]\s+)")
_HEADER_LINE = re.compile(r"^[A-Za-z][^:]{0,80}:$")


def _is_non_requirement_header(line: str) -> bool:
    stripped = line.strip()
    if not stripped.endswith(":") or len(stripped) > 80:
        return False
    lower = stripped.lower()
    if any(marker in lower for marker in _SECTION_MARKERS):
        return False
    return bool(_HEADER_LINE.match(stripped)) or any(
        marker in lower for marker in _SECTION_EXIT_MARKERS
    )


def extract_jd_requirements(jd_text: str, *, max_items: int = 40) -> list[str]:
    """Return deduped requirement clauses from JD bullets and qualification sections."""
    text = (jd_text or "").strip()
    if not text:
        return []

    in_requirements = False
    seen: set[str] = set()
    out: list[str] = []

    def _add(raw: str) -> None:
        cleaned = " ".join(raw.split()).strip()
        if len(cleaned) < 12:
            return
        key = cleaned.lower()
        if key in seen:
            return
        seen.add(key)
        out.append(cleaned[:480])

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        lower = stripped.lower()
        if _is_non_requirement_header(stripped):
            in_requirements = False
            continue
        if any(marker in lower for marker in _SECTION_EXIT_MARKERS):
            in_requirements = False
            continue
        if any(marker in lower for marker in _SECTION_MARKERS):
            in_requirements = True
            if len(stripped) > 20 and not stripped.endswith(":"):
                _add(_BULLET_PREFIX.sub("", stripped))
            continue

        if not in_requirements:
            continue

        is_bullet = bool(_BULLET_PREFIX.match(stripped)) or (
            stripped[0].isupper() and len(stripped) > 15
        )
        if is_bullet:
            clause = _BULLET_PREFIX.sub("", stripped)
            if any(
                m in lower
                for m in ("preferred", "nice to have", "bonus:", "plus:")
            ):
                continue
            _add(clause)
            if len(out) >= max_items:
                break

    if not out:
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            s = sentence.strip()
            if len(s) >= 20 and any(
                m in s.lower() for m in ("required", "must", "years", "experience")
            ):
                _add(s)
                if len(out) >= max_items:
                    break

    return out[:max_items]


def merge_requirement_lists(
    llm_requirements: list[str] | None,
    jd_text: str,
) -> list[str]:
    """Prefer LLM lines when present; always backfill from deterministic extraction."""
    merged: list[str] = []
    seen: set[str] = set()
    for source in (llm_requirements or [], extract_jd_requirements(jd_text)):
        for item in source:
            key = " ".join(item.split()).lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(item.strip()[:480])
    return merged[:40]


__all__ = ["extract_jd_requirements", "merge_requirement_lists"]
