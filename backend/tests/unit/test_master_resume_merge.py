"""Unit tests for multi-source merge helpers."""

from __future__ import annotations

from app.services.master_resume import crud as master_crud


def test_normalize_chunk_text_dedup_key() -> None:
    a = master_crud._normalize_chunk_text("Hello, World!")
    b = master_crud._normalize_chunk_text("hello world")
    assert a == b


def test_detect_role_conflicts() -> None:
    parsed = {
        "experience": [{"company": "Acme", "title": "Staff Engineer"}],
    }
    from app.models.master_resume import MasterResumeChunk, MasterResumeSectionType
    import uuid

    chunk = MasterResumeChunk(
        id=uuid.uuid4(),
        master_resume_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        section_type=MasterResumeSectionType.experience,
        content="bullet",
        token_count=1,
        chunk_metadata={"company": "Acme", "title": "Senior Engineer"},
    )
    conflicts = master_crud._detect_role_conflicts(parsed, [chunk])
    assert conflicts
    assert conflicts[0]["company"] == "Acme"
