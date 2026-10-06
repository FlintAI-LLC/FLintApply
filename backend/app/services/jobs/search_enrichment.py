"""Post-search enrichment: seniority alignment, match reasons, off-ramp classification."""

from __future__ import annotations

import re
from typing import Literal

from app.services.jobs.job_service import tokenize_job_search_terms
from app.services.jobs.schemas import JobResult

RelevanceTier = Literal["strong", "good", "weak", "mismatch"]

_SENIOR_MARKERS = frozenset(
    {"senior", "staff", "principal", "lead", "manager", "director", "head", "sr"}
)
_JUNIOR_MARKERS = frozenset(
    {"junior", "associate", "entry", "intern", "internship", "graduate", "jr"}
)

_TECH_QUERY_TERMS = frozenset(
    {
        "engineer",
        "developer",
        "software",
        "data",
        "devops",
        "sre",
        "qa",
        "sdet",
        "frontend",
        "backend",
        "fullstack",
        "cloud",
        "platform",
        "security",
        "mobile",
        "ios",
        "android",
        "ml",
        "machine",
        "learning",
        "ai",
        "analyst",
        "scientist",
        "architect",
        "programmer",
        "programming",
        "automation",
        "kubernetes",
        "aws",
        "azure",
        "gcp",
        "typescript",
        "javascript",
        "python",
        "java",
        "golang",
        "rust",
        "product",
        "designer",
        "ux",
        "ui",
    }
)

_NON_TECH_QUERY_TERMS = frozenset(
    {
        "tutor",
        "tutoring",
        "teacher",
        "teaching",
        "nurse",
        "nursing",
        "retail",
        "cashier",
        "waiter",
        "waitress",
        "barista",
        "driver",
        "cleaner",
        "janitor",
        "receptionist",
        "babysitter",
        "caregiver",
        "warehouse",
        "forklift",
    }
)


def _title_tokens(title: str) -> set[str]:
    raw = re.findall(r"[a-z0-9]+", title.casefold())
    return {t for t in raw if len(t) > 1}


def seniority_from_text(text: str) -> str | None:
    tokens = _title_tokens(text)
    if tokens & _SENIOR_MARKERS:
        return "senior"
    if tokens & _JUNIOR_MARKERS:
        return "junior"
    return None


def query_seniority_intent(query: str) -> str | None:
    return seniority_from_text(query)


def _term_hits_title(term: str, title: str) -> bool:
    title_cf = title.casefold()
    if " " in term:
        return term in title_cf
    return bool(re.search(rf"(^|[^a-z0-9]){re.escape(term)}([^a-z0-9]|$)", title_cf))


def _term_hits_job(term: str, job: JobResult) -> tuple[bool, bool]:
    title_hit = _term_hits_title(term, job.title)
    if title_hit:
        return True, True
    blob = f"{job.company} {job.description}".casefold()
    if " " in term:
        return term in blob, False
    desc_hit = bool(
        re.search(rf"(^|[^a-z0-9]){re.escape(term)}([^a-z0-9]|$)", blob)
    )
    return desc_hit, False


def enrich_search_results(query: str, jobs: list[JobResult]) -> list[JobResult]:
    """Annotate jobs with match_reasons and relevance_tier; demote seniority mismatches."""
    terms = tokenize_job_search_terms(query)
    intent = query_seniority_intent(query)
    enriched: list[JobResult] = []

    for job in jobs:
        reasons: list[str] = []
        title_weight = 0
        for term in terms:
            hit, in_title = _term_hits_job(term, job)
            if hit:
                if in_title:
                    reasons.append(f'Title matches "{term}"')
                    title_weight += 2
                else:
                    reasons.append(f'Description mentions "{term}"')
                    title_weight += 1

        job_level = seniority_from_text(job.title)
        tier: RelevanceTier = "good"
        if title_weight >= 2:
            tier = "strong"
        elif title_weight == 0 and reasons:
            tier = "weak"
        elif not reasons:
            tier = "weak"

        if intent == "junior" and job_level == "senior":
            tier = "mismatch"
            reasons.append("Seniority mismatch: you searched for entry-level roles")
        elif intent == "senior" and job_level == "junior":
            tier = "mismatch"
            reasons.append("Seniority mismatch: role looks entry-level or intern")

        enriched.append(
            job.model_copy(
                update={
                    "match_reasons": reasons[:4],
                    "relevance_tier": tier,
                }
            )
        )

    tier_order = {"strong": 0, "good": 1, "weak": 2, "mismatch": 3}
    enriched.sort(key=lambda j: tier_order.get(j.relevance_tier or "weak", 2))
    return enriched


def is_likely_non_tech_query(terms: list[str]) -> bool:
    if not terms:
        return False
    has_non_tech = any(t in _NON_TECH_QUERY_TERMS for t in terms)
    has_tech = any(t in _TECH_QUERY_TERMS for t in terms)
    return has_non_tech and not has_tech


def classify_search_off_ramp(
    query: str,
    jobs: list[JobResult],
    *,
    terms: list[str] | None = None,
) -> str | None:
    """Return off-ramp reason code or None when results speak for themselves."""
    normalized = query.strip()
    if not normalized:
        return "empty_query"

    search_terms = terms if terms is not None else tokenize_job_search_terms(normalized)
    if is_likely_non_tech_query(search_terms):
        return "non_tech"

    if not jobs:
        return "empty_results"

    strong_or_good = sum(
        1 for j in jobs if j.relevance_tier in ("strong", "good")
    )
    if strong_or_good < 3 and len(jobs) < 5:
        return "low_relevance"

    return None
