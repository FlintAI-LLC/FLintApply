"""poll_due_companies against a real database with the network patched out."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from sqlalchemy import func, select, text

from app.models.career_watch import (
    CareerAtsType,
    CareerJobCache,
    UserWatchedCompany,
    WatchedCompany,
)
from app.models.jobs import JobCache
from app.services.career_watch import poller
from app.models.user import AuthProvider, User, UserTier
from app.services.career_watch.fetch import CareerWatchFetchError
from app.services.career_watch.job_corpus_seed import STALE_FAIL_DEACTIVATE
from app.services.career_watch.types import ParsedJob

pytestmark = pytest.mark.integration

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
HTML_DESC = "<div><p>Build APIs</p><ul><li>Python</li></ul></div>"


def _job(ext_id: str, title: str = "Backend Engineer") -> ParsedJob:
    return ParsedJob(
        external_job_id=ext_id,
        title=title,
        location="Remote",
        apply_url=f"https://example.com/jobs/{ext_id}",
        description_text=HTML_DESC,
        posted_at=NOW,
        raw_payload={},
    )


async def _seed_company(db_session, slug: str, tier: int = 1) -> WatchedCompany:
    row = WatchedCompany(
        id=uuid.uuid4(),
        name=slug.title(),
        slug=slug,
        careers_page_url=f"https://boards.greenhouse.io/{slug}",
        ats_type=CareerAtsType.greenhouse,
        ats_board_token=slug,
        is_global_seed=True,
        is_active=True,
        poll_priority_tier=tier,
    )
    db_session.add(row)
    await db_session.flush()
    return row


def _gone_error() -> CareerWatchFetchError:
    request = httpx.Request("GET", "https://boards-api.greenhouse.io/v1/boards/x/jobs")
    cause = httpx.HTTPStatusError(
        "gone", request=request, response=httpx.Response(404, request=request)
    )
    err = CareerWatchFetchError("gone")
    err.__cause__ = cause
    return err


def _patched(fetch):
    return (
        patch.object(poller, "fetch_company_jobs", fetch),
        patch.object(poller, "poll_enabled_aggregators", AsyncMock(return_value=poller.PollStats())),
    )


async def _run(db_session, fetch):
    fetch_patch, agg_patch = _patched(fetch)
    with fetch_patch, agg_patch:
        stats = await poller.poll_due_companies(db_session, limit=50, now=NOW)
    await db_session.commit()
    return stats


async def _count(db_session, model) -> int:
    return int((await db_session.execute(select(func.count()).select_from(model))).scalar_one())


@pytest.mark.asyncio
async def test_poll_writes_normalized_jobs_and_isolates_a_fetch_failure(db_session) -> None:
    await _seed_company(db_session, "good-co")
    await _seed_company(db_session, "gone-co")
    await db_session.commit()

    async def fetch(company, client=None):
        if company.slug == "gone-co":
            raise _gone_error()
        return [_job("1"), _job("2")]

    stats = await _run(db_session, fetch)

    assert stats.companies_polled == 1
    assert stats.failures == 1
    assert stats.jobs_upserted == 2

    db_session.expire_all()
    good = (await db_session.execute(select(WatchedCompany).where(WatchedCompany.slug == "good-co"))).scalar_one()
    gone = (await db_session.execute(select(WatchedCompany).where(WatchedCompany.slug == "gone-co"))).scalar_one()
    assert good.last_polled_at == NOW and good.poll_fail_count == 0
    assert gone.poll_fail_count == 1 and gone.is_active is True

    cached = (await db_session.execute(select(CareerJobCache.description_text))).scalars().all()
    assert len(cached) == 2
    assert all("Build APIs" in d and "<" not in d for d in cached)
    for description in (await db_session.execute(select(JobCache.description))).scalars():
        assert "<" not in description


@pytest.mark.asyncio
async def test_repolling_is_idempotent_and_tombstones_removed_roles(db_session) -> None:
    await _seed_company(db_session, "steady-co")
    await db_session.commit()

    async def first(company, client=None):
        return [_job("1"), _job("2")]

    async def second(company, client=None):
        return [_job("1")]

    await _run(db_session, first)
    jobs_after_first = await _count(db_session, CareerJobCache)

    row = (await db_session.execute(select(WatchedCompany))).scalar_one()
    row.last_polled_at = NOW - timedelta(days=1)
    await db_session.commit()

    await _run(db_session, second)

    assert await _count(db_session, CareerJobCache) == jobs_after_first
    open_ids = (
        await db_session.execute(
            select(CareerJobCache.external_job_id).where(CareerJobCache.is_open.is_(True))
        )
    ).scalars().all()
    assert open_ids == ["1"]


@pytest.mark.asyncio
async def test_database_error_in_one_company_does_not_abort_the_run(db_session) -> None:
    await _seed_company(db_session, "aaa-poison")
    await _seed_company(db_session, "bbb-fine")
    await db_session.commit()

    async def fetch(company, client=None):
        return [_job(f"{company.slug}-1")]

    real_sync = poller.sync_polled_jobs_to_caches

    async def flaky_sync(session, company, jobs, *, now=None):
        if company.slug == "aaa-poison":
            await session.execute(text("SELECT 1/0"))
        return await real_sync(session, company, jobs, now=now)

    fetch_patch, agg_patch = _patched(fetch)
    with fetch_patch, agg_patch, patch.object(poller, "sync_polled_jobs_to_caches", flaky_sync):
        stats = await poller.poll_due_companies(db_session, limit=50, now=NOW)
    await db_session.commit()

    assert stats.failures == 1
    assert stats.companies_polled == 1
    db_session.expire_all()
    fine = (await db_session.execute(select(WatchedCompany).where(WatchedCompany.slug == "bbb-fine"))).scalar_one()
    poison = (await db_session.execute(select(WatchedCompany).where(WatchedCompany.slug == "aaa-poison"))).scalar_one()
    assert fine.last_polled_at == NOW
    assert poison.poll_fail_count == 1
    ids = (await db_session.execute(select(CareerJobCache.external_job_id))).scalars().all()
    assert ids == ["bbb-fine-1"]


async def _watch(db_session, company: WatchedCompany, *, active: bool) -> None:
    user = User(
        id=uuid.uuid4(),
        email=f"watch-{uuid.uuid4().hex[:8]}@example.com",
        auth_provider=AuthProvider.email,
        password_hash="x",
        display_name="Watcher",
        tier=UserTier.free,
        credit_balance=0,
        accepted_tos_version="2026-06",
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        UserWatchedCompany(
            id=uuid.uuid4(),
            user_id=user.id,
            watched_company_id=company.id,
            keywords=[],
            is_active=active,
        )
    )
    await db_session.flush()


async def _poll_dying_seed(db_session, slug: str, *, watcher: str) -> WatchedCompany:
    company = await _seed_company(db_session, slug)
    company.poll_fail_count = STALE_FAIL_DEACTIVATE - 1
    if watcher != "none":
        await _watch(db_session, company, active=(watcher == "active"))
    await db_session.commit()
    company_id = company.id

    async def fetch(company, client=None):
        raise _gone_error()

    await _run(db_session, fetch)
    db_session.expire_all()
    return await db_session.get(WatchedCompany, company_id)


@pytest.mark.asyncio
async def test_dead_unwatched_seed_is_deactivated_but_row_is_kept(db_session) -> None:
    row = await _poll_dying_seed(db_session, "dead-seed", watcher="none")
    assert row is not None
    assert row.is_active is False


@pytest.mark.asyncio
async def test_dead_seed_with_an_active_user_watch_stays_active(db_session) -> None:
    row = await _poll_dying_seed(db_session, "watched-seed", watcher="active")
    assert row.is_active is True
    assert row.poll_fail_count >= STALE_FAIL_DEACTIVATE


@pytest.mark.asyncio
async def test_dead_seed_with_only_an_inactive_watch_is_deactivated(db_session) -> None:
    row = await _poll_dying_seed(db_session, "orphan-watch-seed", watcher="inactive")
    assert row.is_active is False
