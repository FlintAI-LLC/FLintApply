"""Keyword filter and lightweight ranking for Career Watch alerts."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.career_watch import (
    CareerAlert,
    CareerAlertStatus,
    CareerJobCache,
    UserWatchedCompany,
)
from app.services.career_watch.apply_url import normalize_apply_url
from app.services.career_watch.notifications import emit_career_watch_alert
from app.services.career_watch.seniority import title_matches_seniority_levels

log = structlog.get_logger("career_watch.matcher")

_WORD_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> set[str]:
    return set(_WORD_RE.findall(text.lower()))


def _keyword_hits(keywords: list[str], job: CareerJobCache) -> list[str]:
    haystack = " ".join(
        [job.title, job.location, job.description_text]
    ).lower()
    tokens = _tokenize(haystack)
    return [kw for kw in keywords if kw.lower() in haystack or kw.lower() in tokens]


def keyword_match_score(keywords: list[str], job: CareerJobCache) -> tuple[float, str]:
    """Return ``(score, reason)`` based on keyword overlap."""
    if not keywords:
        return 0.0, ""
    hits = _keyword_hits(keywords, job)
    if not hits:
        return 0.0, ""
    score = min(1.0, len(hits) / max(len(keywords), 1))
    return score, f"matched keywords: {', '.join(hits)}"


def passes_career_watch_keyword_match(
    keywords: list[str],
    job: CareerJobCache,
    *,
    score: float,
    min_score: float = 0.25,
) -> bool:
    """Stricter gate: no keywords → no alert; need 2+ hits or a title match."""
    if not keywords or score < min_score:
        return False
    hits = _keyword_hits(keywords, job)
    if not hits:
        return False
    title_l = job.title.lower()
    title_hit = any(h.lower() in title_l for h in hits)
    if len(hits) >= 2:
        return True
    return title_hit


def match_baseline_for_watch(watch: UserWatchedCompany) -> datetime:
    """Only consider jobs first seen after the watch existed and since the last matcher pass."""
    baseline = watch.created_at
    if watch.last_matched_at is not None and watch.last_matched_at > baseline:
        baseline = watch.last_matched_at
    return baseline


async def _user_has_alert_for_apply_url(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    normalized_url: str,
) -> bool:
    if not normalized_url:
        return False
    stmt = (
        select(CareerJobCache.apply_url)
        .join(CareerAlert, CareerAlert.career_job_cache_id == CareerJobCache.id)
        .where(CareerAlert.user_id == user_id)
        .where(CareerJobCache.apply_url != "")
    )
    urls = (await session.execute(stmt)).scalars().all()
    for url in urls:
        if normalize_apply_url(url) == normalized_url:
            return True
    return False


@dataclass(slots=True)
class MatchStats:
    watches_scanned: int = 0
    alerts_created: int = 0
    notifications_sent: int = 0


async def match_new_jobs_for_watch(
    session: AsyncSession,
    watch: UserWatchedCompany,
    *,
    since: datetime | None = None,
    min_score: float = 0.25,
) -> int:
    """Create alerts for newly seen jobs matching ``watch`` keywords."""
    baseline = since if since is not None else match_baseline_for_watch(watch)
    stmt = (
        select(CareerJobCache)
        .where(CareerJobCache.watched_company_id == watch.watched_company_id)
        .where(CareerJobCache.is_open.is_(True))
        .where(CareerJobCache.first_seen_at > baseline)
    )
    jobs = (await session.execute(stmt)).scalars().all()

    created = 0
    keywords = list(watch.keywords or [])
    seniority = list(watch.seniority_levels or [])
    for job in jobs:
        if not title_matches_seniority_levels(job.title, seniority):
            continue
        score, reason = keyword_match_score(keywords, job)
        if not passes_career_watch_keyword_match(
            keywords, job, score=score, min_score=min_score
        ):
            continue
        existing = (
            await session.execute(
                select(CareerAlert)
                .where(CareerAlert.user_id == watch.user_id)
                .where(CareerAlert.career_job_cache_id == job.id)
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue
        norm_url = normalize_apply_url(job.apply_url)
        if norm_url and await _user_has_alert_for_apply_url(
            session, user_id=watch.user_id, normalized_url=norm_url
        ):
            continue
        alert = CareerAlert(
            id=uuid.uuid4(),
            user_id=watch.user_id,
            user_watched_company_id=watch.id,
            career_job_cache_id=job.id,
            match_score=score,
            match_reason=reason,
            status=CareerAlertStatus.pending,
        )
        session.add(alert)
        created += 1
    if created:
        watch.last_matched_at = datetime.now(timezone.utc)
    await session.flush()
    return created


async def run_matcher(
    session: AsyncSession,
    *,
    limit: int = 200,
) -> MatchStats:
    """Scan active watches and enqueue alerts + notifications."""
    watches = list(
        (
            await session.execute(
                select(UserWatchedCompany)
                .where(UserWatchedCompany.is_active.is_(True))
                .limit(limit)
            )
        ).scalars()
    )
    stats = MatchStats()
    for watch in watches:
        stats.watches_scanned += 1
        created = await match_new_jobs_for_watch(session, watch)
        stats.alerts_created += created

    pending = list(
        (
            await session.execute(
                select(CareerAlert)
                .where(CareerAlert.status == CareerAlertStatus.pending)
                .limit(limit)
            )
        ).scalars()
    )
    for alert in pending:
        sent = await emit_career_watch_alert(session, alert)
        if sent:
            stats.notifications_sent += 1
    return stats


__all__ = [
    "MatchStats",
    "keyword_match_score",
    "match_baseline_for_watch",
    "match_new_jobs_for_watch",
    "passes_career_watch_keyword_match",
    "run_matcher",
]
