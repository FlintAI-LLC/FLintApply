"""Load the committed seed into a real database and check loader guarantees."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.models.career_watch import CareerAtsType, WatchedCompany
from app.services.career_watch.job_corpus_seed import (
    load_seed_records,
    read_seed_json,
    tier_counts,
)

pytestmark = pytest.mark.integration

SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "job_corpus" / "seed_2000.json"
EXPECTED_TOTAL = 2000


async def _count(db_session, *conditions) -> int:
    stmt = select(func.count()).select_from(WatchedCompany).where(*conditions)
    return int((await db_session.execute(stmt)).scalar_one())


@pytest.mark.asyncio
async def test_full_seed_loads_and_reload_is_idempotent(db_session) -> None:
    records = read_seed_json(SEED_PATH)

    first = await load_seed_records(db_session, records)
    await db_session.commit()
    assert first.inserted == EXPECTED_TOTAL
    assert first.updated == 0
    assert await _count(db_session, WatchedCompany.is_global_seed.is_(True)) == EXPECTED_TOTAL

    tiers = tier_counts(records)
    for tier, expected in tiers.items():
        assert await _count(db_session, WatchedCompany.poll_priority_tier == tier) == expected

    second = await load_seed_records(db_session, records)
    await db_session.commit()
    assert second.inserted == 0
    assert second.updated == EXPECTED_TOTAL
    assert await _count(db_session) == EXPECTED_TOTAL


@pytest.mark.asyncio
async def test_reload_never_resurrects_deactivated_seed_rows(db_session) -> None:
    records = read_seed_json(SEED_PATH)
    await load_seed_records(db_session, records)
    await db_session.commit()

    victim_slug = records[0]["slug"]
    victim = (
        await db_session.execute(select(WatchedCompany).where(WatchedCompany.slug == victim_slug))
    ).scalar_one()
    victim.is_active = False
    await db_session.commit()

    await load_seed_records(db_session, records)
    await db_session.commit()

    db_session.expire_all()
    reloaded = (
        await db_session.execute(select(WatchedCompany).where(WatchedCompany.slug == victim_slug))
    ).scalar_one()
    assert reloaded.is_active is False


@pytest.mark.asyncio
async def test_seed_load_leaves_user_watched_companies_alone(db_session) -> None:
    user_row = WatchedCompany(
        id=uuid.uuid4(),
        name="My Watch",
        slug="my-personal-watch",
        careers_page_url="https://boards.greenhouse.io/mywatch",
        ats_type=CareerAtsType.greenhouse,
        ats_board_token="mywatch",
        is_global_seed=False,
        is_active=True,
    )
    db_session.add(user_row)
    await db_session.commit()

    await load_seed_records(db_session, read_seed_json(SEED_PATH))
    await db_session.commit()

    db_session.expire_all()
    kept = (
        await db_session.execute(
            select(WatchedCompany).where(WatchedCompany.slug == "my-personal-watch")
        )
    ).scalar_one()
    assert kept.is_global_seed is False
    assert kept.is_active is True
