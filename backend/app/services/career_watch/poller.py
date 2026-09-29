"""Poll watched companies and upsert career job cache rows."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
import structlog
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.career_watch import UserWatchedCompany, WatchedCompany
from app.services.career_watch.aggregators.registry import enabled_aggregator_sources
from app.services.career_watch.aggregators.sync import sync_aggregator_jobs_to_cache
from app.services.career_watch.corpus_sync import sync_polled_jobs_to_caches
from app.services.career_watch.fetch import is_gone_error
from app.services.career_watch.global_poll_schedule import fetch_due_global_seeds
from app.services.career_watch.job_corpus_seed import STALE_FAIL_DEACTIVATE
from app.services.career_watch.poll_budget import apply_daily_poll_budget, count_polls_today
from app.services.career_watch.poll_schedule import fetch_due_companies
from app.services.career_watch.registry import fetch_company_jobs
from app.services.career_watch.types import ParsedJob

log = structlog.get_logger("career_watch.poller")

_HOST_LIMITS: dict[str, int] = {
    "boards-api.greenhouse.io": 8,
    "api.lever.co": 6,
    "api.eu.lever.co": 6,
    "api.ashbyhq.com": 6,
    "api.smartrecruiters.com": 4,
    "apply.workable.com": 4,
}
_DEFAULT_HOST_LIMIT = 3
_HOST_DELAY_SECONDS = 0.1


@dataclass(frozen=True, slots=True)
class PollStats:
    companies_polled: int = 0
    jobs_upserted: int = 0
    failures: int = 0
    aggregators_polled: int = 0
    aggregator_jobs_upserted: int = 0
    aggregator_failures: int = 0


def _host_for_company(company: WatchedCompany) -> str:
    try:
        return urlparse(company.careers_page_url).netloc.lower() or "unknown"
    except Exception:
        return "unknown"


def _host_semaphore(host: str, semaphores: dict[str, asyncio.Semaphore]) -> asyncio.Semaphore:
    if host not in semaphores:
        limit = _HOST_LIMITS.get(host, _DEFAULT_HOST_LIMIT)
        semaphores[host] = asyncio.Semaphore(limit)
    return semaphores[host]


async def _fetch_company_jobs_bounded(
    company: WatchedCompany,
    *,
    client: httpx.AsyncClient,
    semaphores: dict[str, asyncio.Semaphore],
) -> tuple[WatchedCompany, list[ParsedJob] | Exception]:
    host = _host_for_company(company)
    sem = _host_semaphore(host, semaphores)
    try:
        async with sem:
            await asyncio.sleep(_HOST_DELAY_SECONDS)
            jobs = await fetch_company_jobs(company, client=client)
        return company, jobs
    except Exception as exc:  # noqa: BLE001
        return company, exc


_MAX_CAUSE_DEPTH = 5


def _is_gone(exc: BaseException) -> bool:
    """Walk the cause chain: fetch helpers wrap httpx errors in CareerWatchFetchError."""
    current: BaseException | None = exc
    for _ in range(_MAX_CAUSE_DEPTH):
        if current is None:
            return False
        if is_gone_error(current):
            return True
        current = current.__cause__ or current.__context__
    return False


async def _has_active_user_watch(session: AsyncSession, company: WatchedCompany) -> bool:
    """Seed rows are shared with user watches; deactivating would silence their alerts."""
    stmt = select(
        exists().where(
            UserWatchedCompany.watched_company_id == company.id,
            UserWatchedCompany.is_active.is_(True),
        )
    )
    return bool(await session.scalar(stmt))


async def _record_poll_failure(
    session: AsyncSession,
    company: WatchedCompany,
    exc: Exception,
    *,
    now: datetime,
) -> None:
    company.poll_fail_count += 1
    company.updated_at = now
    if (
        company.is_global_seed
        and _is_gone(exc)
        and company.poll_fail_count >= STALE_FAIL_DEACTIVATE
        and not await _has_active_user_watch(session, company)
    ):
        company.is_active = False
    await session.flush()
    log.warning(
        "career_watch_poll_failed",
        company_id=str(company.id),
        error=str(exc),
    )


async def poll_company(
    session: AsyncSession,
    company: WatchedCompany,
    *,
    client: httpx.AsyncClient | None = None,
    now: datetime | None = None,
) -> int:
    """Fetch jobs for ``company`` and upsert both cache tables. Returns new job count."""
    now = now or datetime.now(timezone.utc)
    try:
        jobs = await fetch_company_jobs(company, client=client)
    except Exception as exc:  # noqa: BLE001
        await _record_poll_failure(session, company, exc, now=now)
        raise

    inserted = await sync_polled_jobs_to_caches(session, company, jobs, now=now)
    company.last_polled_at = now
    company.poll_fail_count = 0
    company.updated_at = now
    await session.flush()
    return inserted


async def _due_companies_global_then_watchlist(
    session: AsyncSession,
    *,
    limit: int,
    now: datetime,
) -> list[WatchedCompany]:
    """Global seeds first, then user-watch due companies, deduped by id."""
    watch_reserve = max(1, limit // 5)
    global_limit = max(1, limit - watch_reserve)
    global_due = await fetch_due_global_seeds(session, limit=global_limit, now=now)
    watch_due = await fetch_due_companies(session, limit=limit, now=now)
    seen: set[uuid.UUID] = set()
    ordered: list[WatchedCompany] = []
    for company in (*global_due, *watch_due):
        if company.id in seen:
            continue
        seen.add(company.id)
        ordered.append(company)
        if len(ordered) >= limit:
            break
    polls_today = await count_polls_today(session, now=now)
    return apply_daily_poll_budget(ordered, polls_today=polls_today)


async def poll_enabled_aggregators(
    session: AsyncSession,
    *,
    client: httpx.AsyncClient,
    now: datetime | None = None,
) -> PollStats:
    """Fetch enabled free aggregators and upsert into shared job_cache."""
    now = now or datetime.now(timezone.utc)
    stats = PollStats()
    companies_polled = 0
    jobs_upserted = 0
    failures = 0
    for source in enabled_aggregator_sources():
        try:
            jobs = await source.fetch(client=client)
            count = await sync_aggregator_jobs_to_cache(
                session,
                source=source.id,
                jobs=jobs,
                now=now,
            )
            companies_polled += 1
            jobs_upserted += count
        except Exception as exc:  # noqa: BLE001
            failures += 1
            log.warning(
                "career_watch_aggregator_poll_failed",
                aggregator=source.id,
                error=str(exc),
            )
    return PollStats(
        aggregators_polled=companies_polled,
        aggregator_jobs_upserted=jobs_upserted,
        aggregator_failures=failures,
    )


async def poll_due_companies(
    session: AsyncSession,
    *,
    limit: int = 50,
    now: datetime | None = None,
) -> PollStats:
    """Poll global seeds first, then user-watch tier due companies."""
    now = now or datetime.now(timezone.utc)
    companies = await _due_companies_global_then_watchlist(
        session, limit=limit, now=now
    )
    companies_polled = 0
    jobs_upserted = 0
    failures = 0
    semaphores: dict[str, asyncio.Semaphore] = {}
    async with httpx.AsyncClient() as client:
        fetch_outcomes = await asyncio.gather(
            *[
                _fetch_company_jobs_bounded(company, client=client, semaphores=semaphores)
                for company in companies
            ]
        )
        for company, outcome in fetch_outcomes:
            if isinstance(outcome, Exception):
                failures += 1
                await _record_poll_failure(session, company, outcome, now=now)
                continue
            try:
                # Savepoint: a DB error must not poison the transaction for the
                # remaining companies in this run.
                async with session.begin_nested():
                    count = await sync_polled_jobs_to_caches(
                        session, company, outcome, now=now
                    )
                company.last_polled_at = now
                company.poll_fail_count = 0
                company.updated_at = now
                await session.flush()
                companies_polled += 1
                jobs_upserted += count
            except Exception as exc:  # noqa: BLE001
                failures += 1
                await _record_poll_failure(session, company, exc, now=now)

        agg_stats = await poll_enabled_aggregators(
            session, client=client, now=now
        )
        stats = PollStats(
            companies_polled=companies_polled,
            jobs_upserted=jobs_upserted,
            failures=failures,
            aggregators_polled=agg_stats.aggregators_polled,
            aggregator_jobs_upserted=agg_stats.aggregator_jobs_upserted,
            aggregator_failures=agg_stats.aggregator_failures,
        )
    return stats


__all__ = [
    "PollStats",
    "poll_company",
    "poll_due_companies",
    "poll_enabled_aggregators",
]
