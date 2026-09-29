"""DB-backed tests for corpus maintenance: due query, poll lock, backfill, prune."""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import create_async_engine

from app.models.career_watch import CareerAtsType, CareerJobCache, WatchedCompany
from app.models.jobs import JobCache, SavedJob
from app.models.user import AuthProvider, User, UserTier
from app.services.career_watch.corpus_sync import _description_hash
from app.services.career_watch.global_poll_schedule import fetch_due_global_seeds
from app.services.career_watch.poll_lock import try_poll_lock
from scripts import backfill_job_cache_descriptions as backfill
from scripts import prune_job_cache as prune

pytestmark = pytest.mark.integration

NOW = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)
HTML_DESC = "<div><p>Build APIs</p><ul><li>Python</li></ul></div>"
PAGE_SIZE = 2


def _factory(db_session):
    @asynccontextmanager
    async def _open():
        yield db_session

    return _open


async def _company(
    db_session,
    slug: str,
    *,
    tier: int | None,
    last_polled: datetime | None,
    active: bool = True,
    seed: bool = True,
) -> WatchedCompany:
    row = WatchedCompany(
        id=uuid.uuid4(),
        name=slug,
        slug=slug,
        careers_page_url=f"https://boards.greenhouse.io/{slug}",
        ats_type=CareerAtsType.greenhouse,
        ats_board_token=slug,
        is_active=active,
        is_global_seed=seed,
        poll_priority_tier=tier,
        last_polled_at=last_polled,
    )
    db_session.add(row)
    await db_session.flush()
    return row


async def _job(
    db_session, *, description: str, expires_at: datetime, key: str | None = None
) -> JobCache:
    row = JobCache(
        id=uuid.uuid4(),
        sources=["corpus"],
        external_ids={"corpus": uuid.uuid4().hex},
        title="Engineer",
        company="Acme",
        company_normalized="acme",
        location="Remote",
        remote=True,
        employment_type="",
        posted_date=NOW,
        description=description,
        apply_url="https://example.com/j",
        raw_json={},
        cached_at=NOW,
        expires_at=expires_at,
        dedup_key=key or uuid.uuid4().hex,
        is_active=True,
    )
    db_session.add(row)
    await db_session.flush()
    return row


async def _user(db_session) -> User:
    user = User(
        id=uuid.uuid4(),
        email=f"maint-{uuid.uuid4().hex[:8]}@example.com",
        auth_provider=AuthProvider.email,
        password_hash="x",
        display_name="Maint",
        tier=UserTier.free,
        credit_balance=0,
        accepted_tos_version="2026-06",
    )
    db_session.add(user)
    await db_session.flush()
    return user


# ---------------------------------------------------------------- due query


@pytest.mark.asyncio
async def test_due_query_filters_and_orders_by_tier_then_staleness(db_session) -> None:
    long_ago = NOW - timedelta(days=30)
    a = await _company(db_session, "t1-null", tier=1, last_polled=None)
    b = await _company(db_session, "t1-old", tier=1, last_polled=long_ago)
    c = await _company(db_session, "t2-old", tier=2, last_polled=long_ago)
    d = await _company(db_session, "t3-old", tier=3, last_polled=long_ago)
    await _company(db_session, "fresh", tier=1, last_polled=NOW - timedelta(seconds=5))
    await _company(db_session, "inactive", tier=1, last_polled=None, active=False)
    await _company(db_session, "user-watch", tier=1, last_polled=None, seed=False)
    await db_session.commit()

    due = await fetch_due_global_seeds(db_session, limit=50, now=NOW)

    assert [x.slug for x in due] == [a.slug, b.slug, c.slug, d.slug]


@pytest.mark.asyncio
async def test_due_query_respects_shared_limit_across_tiers(db_session) -> None:
    for i in range(3):
        await _company(db_session, f"t1-{i}", tier=1, last_polled=None)
    await _company(db_session, "t2-x", tier=2, last_polled=None)
    await db_session.commit()

    due = await fetch_due_global_seeds(db_session, limit=2, now=NOW)

    assert len(due) == 2
    assert all(x.poll_priority_tier == 1 for x in due)


# ---------------------------------------------------------------- poll lock


@pytest.mark.asyncio
async def test_poll_lock_is_exclusive_and_released() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    try:
        async with try_poll_lock(engine) as first:
            assert first is True
            async with try_poll_lock(engine) as second:
                assert second is False
        async with try_poll_lock(engine) as again:
            assert again is True
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_poll_lock_released_when_body_raises() -> None:
    engine = create_async_engine(os.environ["DATABASE_URL"])
    try:
        with pytest.raises(RuntimeError):
            async with try_poll_lock(engine) as acquired:
                assert acquired
                raise RuntimeError("boom")
        async with try_poll_lock(engine) as after:
            assert after is True
    finally:
        await engine.dispose()


# ---------------------------------------------------------------- prune


@pytest.mark.asyncio
async def test_prune_deletes_only_expired_unsaved(db_session) -> None:
    past, future = NOW - timedelta(days=1), NOW + timedelta(days=30)
    expired_unsaved = await _job(db_session, description="x", expires_at=past)
    expired_saved = await _job(db_session, description="x", expires_at=past)
    live = await _job(db_session, description="x", expires_at=future)
    user = await _user(db_session)
    db_session.add(SavedJob(id=uuid.uuid4(), user_id=user.id, job_cache_id=expired_saved.id))
    await db_session.commit()
    unsaved_id, saved_id, live_id = expired_unsaved.id, expired_saved.id, live.id

    dry = await prune.run(apply=False, session_factory=_factory(db_session), now=NOW)
    assert dry == 1
    assert await db_session.get(JobCache, unsaved_id) is not None

    applied = await prune.run(apply=True, session_factory=_factory(db_session), now=NOW)
    assert applied == 1
    db_session.expire_all()
    assert await db_session.get(JobCache, unsaved_id) is None
    assert await db_session.get(JobCache, saved_id) is not None
    assert await db_session.get(JobCache, live_id) is not None

    again = await prune.run(apply=True, session_factory=_factory(db_session), now=NOW)
    assert again == 0


@pytest.mark.asyncio
async def test_prune_handles_more_rows_than_the_bind_parameter_limit(db_session) -> None:
    past = NOW - timedelta(days=1)
    await db_session.execute(
        JobCache.__table__.insert(),
        [
            {
                "id": uuid.uuid4(),
                "sources": ["corpus"],
                "external_ids": {},
                "title": "t",
                "company": "c",
                "company_normalized": "c",
                "location": "",
                "remote": False,
                "employment_type": "",
                "posted_date": NOW,
                "description": "",
                "apply_url": "",
                "raw_json": {},
                "cached_at": NOW,
                "expires_at": past,
                "dedup_key": f"bulk-{i}",
                "is_active": True,
            }
            for i in range(33_000)
        ],
    )
    await db_session.commit()

    deleted = await prune.run(apply=True, session_factory=_factory(db_session), now=NOW)

    assert deleted == 33_000
    total = (await db_session.execute(select(func.count()).select_from(JobCache))).scalar_one()
    assert total == 0


# ---------------------------------------------------------------- backfill


async def _run_backfill(db_session, **overrides):
    kwargs = {
        "dry_run": False,
        "limit": None,
        "batch_size": PAGE_SIZE,
        "career": False,
        "scan_all": False,
        "session_factory": _factory(db_session),
    }
    kwargs.update(overrides)
    return await backfill.run(**kwargs)


@pytest.mark.asyncio
async def test_backfill_dry_run_mutates_nothing(db_session) -> None:
    row = await _job(db_session, description=HTML_DESC, expires_at=NOW)
    await db_session.commit()
    row_id = row.id

    stats = await _run_backfill(db_session, dry_run=True)

    assert stats.updated == 1
    assert row.description == HTML_DESC
    db_session.expire_all()
    assert (await db_session.get(JobCache, row_id)).description == HTML_DESC


@pytest.mark.asyncio
async def test_backfill_apply_normalizes_html_only_and_is_idempotent(db_session) -> None:
    html_rows = [
        await _job(db_session, description=HTML_DESC, expires_at=NOW) for _ in range(5)
    ]
    plain = await _job(db_session, description="Already plain text", expires_at=NOW)
    await db_session.commit()
    html_ids, plain_id = [r.id for r in html_rows], plain.id

    stats = await _run_backfill(db_session)

    assert stats.updated == 5
    assert stats.errors == 0
    db_session.expire_all()
    for row_id in html_ids:
        text = (await db_session.get(JobCache, row_id)).description
        assert "Build APIs" in text and "- Python" in text
        assert "<" not in text
    assert (await db_session.get(JobCache, plain_id)).description == "Already plain text"

    second = await _run_backfill(db_session)
    assert second.updated == 0


@pytest.mark.asyncio
async def test_backfill_respects_limit(db_session) -> None:
    for _ in range(5):
        await _job(db_session, description=HTML_DESC, expires_at=NOW)
    await db_session.commit()

    stats = await _run_backfill(db_session, limit=3)

    assert stats.updated == 3
    remaining = (
        await db_session.execute(
            select(func.count()).select_from(JobCache).where(JobCache.description.like("<%"))
        )
    ).scalar_one()
    assert remaining == 2


@pytest.mark.asyncio
async def test_backfill_career_rows_update_text_and_hash(db_session) -> None:
    company = await _company(db_session, "acme", tier=1, last_polled=None)
    rows = []
    for i in range(3):
        row = CareerJobCache(
            id=uuid.uuid4(),
            watched_company_id=company.id,
            external_job_id=f"ext-{i}",
            title="Engineer",
            location="",
            apply_url="",
            description_text=HTML_DESC,
            description_hash="stale",
            first_seen_at=NOW,
            last_seen_at=NOW,
            is_open=True,
            raw_payload={},
        )
        db_session.add(row)
        rows.append(row)
    await db_session.commit()
    row_ids = [r.id for r in rows]

    stats = await _run_backfill(db_session, career=True)

    assert stats.updated == 3
    db_session.expire_all()
    for row_id in row_ids:
        fresh = await db_session.get(CareerJobCache, row_id)
        assert "Build APIs" in fresh.description_text and "<" not in fresh.description_text
        assert fresh.description_hash == _description_hash(fresh.description_text)
