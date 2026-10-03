"""Unit tests for one-click master resume dedupe."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.models.master_resume import MasterResumeChunk, MasterResumeSectionType
from app.services.master_resume import crud as master_crud


def _chunk(
    *,
    section_type: MasterResumeSectionType,
    content: str,
    metadata: dict | None = None,
    embedding: list[float] | None = None,
) -> MasterResumeChunk:
    now = datetime.now(timezone.utc)
    return MasterResumeChunk(
        id=uuid.uuid4(),
        master_resume_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        section_type=section_type,
        content=content,
        token_count=len(content.split()),
        chunk_metadata=metadata or {},
        embedding=embedding,
        created_at=now,
        updated_at=now,
    )


def test_dedupe_projects_same_title_keeps_longer() -> None:
    short = _chunk(
        section_type=MasterResumeSectionType.project,
        content="Flint\nBuilt desktop app",
    )
    long = _chunk(
        section_type=MasterResumeSectionType.project,
        content="Flint\nBuilt desktop app\nShipped v1 with Rust + React",
    )
    doomed = master_crud.plan_master_resume_dedupe_ids([short, long])
    assert short.id in doomed
    assert long.id not in doomed


def test_dedupe_education_same_school() -> None:
    no_dates = _chunk(
        section_type=MasterResumeSectionType.education,
        content="MIT — Computer Science",
    )
    with_dates = _chunk(
        section_type=MasterResumeSectionType.education,
        content="MIT — Computer Science\nGPA 3.9",
        metadata={"institution": "MIT", "dates": "2018–2022"},
    )
    doomed = master_crud.plan_master_resume_dedupe_ids([no_dates, with_dates])
    assert no_dates.id in doomed
    assert with_dates.id not in doomed


def test_dedupe_skills_exact_normalized() -> None:
    a = _chunk(section_type=MasterResumeSectionType.skills, content="Python, FastAPI")
    b = _chunk(section_type=MasterResumeSectionType.skills, content="python fastapi")
    doomed = master_crud.plan_master_resume_dedupe_ids([a, b])
    assert len(doomed) == 1


def test_dedupe_skills_near_duplicate_embedding() -> None:
    base = [1.0, 0.0, 0.0]
    near = [0.99, 0.01, 0.0]
    far = [0.0, 1.0, 0.0]
    dup = _chunk(
        section_type=MasterResumeSectionType.skills,
        content="Kubernetes orchestration",
        embedding=near,
    )
    keeper = _chunk(
        section_type=MasterResumeSectionType.skills,
        content="Kubernetes — cluster ops, Helm, production SRE",
        embedding=base,
    )
    other = _chunk(
        section_type=MasterResumeSectionType.skills,
        content="PostgreSQL",
        embedding=far,
    )
    doomed = master_crud.plan_master_resume_dedupe_ids([dup, keeper, other])
    assert dup.id in doomed
    assert keeper.id not in doomed
    assert other.id not in doomed
