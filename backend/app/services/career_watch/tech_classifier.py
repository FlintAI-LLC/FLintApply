"""Deterministic tech-company classification for corpus expansion (no network, no LLM)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

TECH_TITLE_RE = re.compile(
    r"\b("
    r"software|swe|sde|sdet|front-?end|back-?end|full[- ]?stack|devops|sre|platform|"
    r"data (engineer|scientist)|machine learning|ml engineer|ios|android|"
    r"security engineer|infrastructure|product (engineer|designer)|"
    r"engineering manager|staff engineer|principal engineer|qa engineer|quality engineer"
    r")\b",
    re.IGNORECASE,
)

# Values observed in the SimplifyJobs listings feed (verified against live data).
SIMPLIFY_TECH_CATEGORIES = frozenset(
    {
        "software",
        "software engineering",
        "ai/ml/data",
        "data science, ai & machine learning",
        "hardware",
        "hardware engineering",
        "quant",
    }
)

ACCEPT_RATIO = 0.30
QUARANTINE_RATIO = 0.15
MIN_TECH_TITLES = 4
TITLE_SAMPLE_LIMIT = 25


@dataclass(frozen=True)
class ClassificationResult:
    decision: str  # accept | omit | quarantine
    tech_ratio: float
    tech_titles: int


def _normalize_category(value: str | None) -> str:
    return (value or "").strip().casefold()


def auto_pass(
    *,
    slug: str,
    tier1_slugs: Iterable[str],
    categories: Iterable[str] | None = None,
    industries: Any = None,
    tags: Any = None,
    source: str | None = None,
) -> bool:
    if slug.lower() in {s.lower() for s in tier1_slugs}:
        return True
    if source == "pinned":
        return True
    if any(_normalize_category(c) in SIMPLIFY_TECH_CATEGORIES for c in categories or ()):
        return True
    blob = " ".join(
        str(x).casefold()
        for x in (
            *(industries if isinstance(industries, list) else []),
            *(tags if isinstance(tags, list) else []),
        )
    )
    if any(
        token in blob
        for token in ("software", "developer tools", "artificial intelligence", "machine learning")
    ):
        return True
    return False


def classify_titles(titles: list[str]) -> ClassificationResult:
    if not titles:
        return ClassificationResult(decision="quarantine", tech_ratio=0.0, tech_titles=0)
    sample = titles[:TITLE_SAMPLE_LIMIT]
    tech = sum(1 for title in sample if TECH_TITLE_RE.search(title))
    ratio = tech / len(sample)
    if ratio >= ACCEPT_RATIO or tech >= MIN_TECH_TITLES:
        return ClassificationResult(decision="accept", tech_ratio=ratio, tech_titles=tech)
    if ratio >= QUARANTINE_RATIO:
        return ClassificationResult(decision="quarantine", tech_ratio=ratio, tech_titles=tech)
    return ClassificationResult(decision="omit", tech_ratio=ratio, tech_titles=tech)


def classify_company(
    *,
    slug: str,
    tier1_slugs: Iterable[str],
    job_titles: list[str],
    categories: Iterable[str] | None = None,
    industries: Any = None,
    tags: Any = None,
    source: str | None = None,
) -> ClassificationResult:
    if auto_pass(
        slug=slug,
        tier1_slugs=tier1_slugs,
        categories=categories,
        industries=industries,
        tags=tags,
        source=source,
    ):
        return ClassificationResult(decision="accept", tech_ratio=1.0, tech_titles=len(job_titles))
    return classify_titles(job_titles)
