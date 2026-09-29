"""Master-resume persist path must not be overwritten by a degraded tailored tree."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rewrite import TailoredExperienceEntry, TailoredResumeOutput
from app.models.user import AuthProvider, User, UserTier
from app.services.master_resume.crud import _upsert_master_resume, get_raw_resume
from app.services.tailored_persistence import _sync_master_resume_chunks

pytestmark = pytest.mark.asyncio

STORED = {
    "skills": ["Python"],
    "summary": "Stored summary.",
    "experience": [{"company": "Acme", "bullets": ["Built."]}],
    "education": [{"degree": "BS"}],
    "projects": [{"name": "P"}],
}


async def _seed_master(db: AsyncSession) -> uuid.UUID:
    user = User(
        id=uuid.uuid4(),
        email=f"master-{uuid.uuid4().hex[:8]}@example.com",
        auth_provider=AuthProvider.email,
        password_hash="x",
        display_name="Master",
        tier=UserTier.free,
        credit_balance=1,
        accepted_tos_version="2026-06",
        email_verified_at=datetime.now(timezone.utc),
    )
    db.add(user)
    await db.commit()
    user_id = user.id
    await _upsert_master_resume(
        db, user_id=user_id, raw_text="raw", parsed_sections=dict(STORED)
    )
    await db.commit()
    return user_id


async def test_degraded_tree_does_not_wipe_stored_master(db_session: AsyncSession) -> None:
    user_id = await _seed_master(db_session)
    await _sync_master_resume_chunks(
        db_session,
        user_id=user_id,
        tailored=TailoredResumeOutput(),
        raw_text="hollow render",
    )
    row = await get_raw_resume(db_session, user_id=user_id)
    assert row is not None
    assert row.parsed_sections["skills"] == ["Python"]
    assert row.parsed_sections["summary"] == "Stored summary."
    assert row.parsed_sections["experience"] == STORED["experience"]
    assert row.raw_text == "raw"


async def test_real_edit_with_empty_skills_is_persisted(db_session: AsyncSession) -> None:
    user_id = await _seed_master(db_session)
    edit = TailoredResumeOutput(
        summary="New summary.",
        experience=[TailoredExperienceEntry(company="Acme", bullets=["Owned."])],
    )
    await _sync_master_resume_chunks(
        db_session, user_id=user_id, tailored=edit, raw_text="raw"
    )
    row = await get_raw_resume(db_session, user_id=user_id)
    assert row is not None
    assert row.parsed_sections["skills"] == []
    assert row.parsed_sections["summary"] == "New summary."
