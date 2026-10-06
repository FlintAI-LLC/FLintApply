"""Deterministic section completeness checks for story-generated resumes."""

from __future__ import annotations

import re

_EDUCATION_SIGNAL = re.compile(
    r"\b("
    r"university|college|school|degree|b\.?s\.?|m\.?s\.?|bachelor|master|ph\.?d|"
    r"student|graduat|major in|minor in|gpa|coursework|campus"
    r")\b",
    re.IGNORECASE,
)

_CORE_SECTION_HEADERS = (
    "PROFESSIONAL SUMMARY",
    "SKILLS",
    "EXPERIENCE",
    "EDUCATION",
)

_TRAILING_TRUNCATION = re.compile(r"\d+[-–—]\s*$")
_TRAILING_PREP = re.compile(
    r"\b(for|with|and|to|of|in|by|or|the)\s*$",
    re.IGNORECASE,
)
_INCOMPLETE_METRIC_TAIL = re.compile(
    r"\b(?:approximately|about|roughly|over|under|nearly|around)\s+\d+\s*$",
    re.IGNORECASE,
)
_BULLET_LINE = re.compile(r"^\s*(?:[•\-*]|\d+[.)])\s+(.+)$")


def narrative_mentions_education(narrative: str) -> bool:
    return bool(_EDUCATION_SIGNAL.search(narrative))


def resume_has_section(resume_text: str, header: str) -> bool:
    return header.upper() in resume_text.upper()


def truncated_bullet_warnings(resume_text: str) -> list[str]:
    """Flag bullets that look cut off mid-sentence."""
    warnings: list[str] = []
    for line in resume_text.splitlines():
        match = _BULLET_LINE.match(line)
        if not match:
            continue
        text = match.group(1).strip()
        if (
            _TRAILING_TRUNCATION.search(text)
            or _TRAILING_PREP.search(text)
            or _INCOMPLETE_METRIC_TAIL.search(text)
        ):
            snippet = text if len(text) <= 48 else text[:45] + "…"
            warnings.append(f"Bullet may be incomplete: “{snippet}” — finish or remove it.")
            if len(warnings) >= 2:
                break
    return warnings


def completeness_warnings(narrative: str, resume_text: str) -> list[str]:
    """Human-readable warnings for Step 3 banner."""
    warnings: list[str] = []
    if narrative_mentions_education(narrative) and not resume_has_section(
        resume_text, "EDUCATION"
    ):
        warnings.append(
            "Your story mentions school or a degree, but the draft has no EDUCATION section. "
            "Add one before saving."
        )
    for header in ("PROFESSIONAL SUMMARY", "EXPERIENCE"):
        if not resume_has_section(resume_text, header):
            warnings.append(f"Missing {header.replace('_', ' ')} section — add it or regenerate.")
    warnings.extend(truncated_bullet_warnings(resume_text))
    return warnings[:5]
