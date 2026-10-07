"""DB operations for ``master_resumes`` + ``master_resume_chunks``.

Routers in ``backend/app/routers/profile.py`` and the retrieval service
both call into this module so that the underlying ORM never leaks into
the HTTP layer.  All functions are async — the project uses
SQLAlchemy 2.0 async sessions throughout.

Soft-delete contract:

- ``delete_chunk`` sets ``deleted_at = now()`` but never removes the
  row.  Older tailored resumes may still reference the chunk via
  ``selected_chunks`` traces — keeping the row preserves audit trail.
- ``get_chunks_for_user`` always filters ``deleted_at IS NULL`` so
  retrieval never re-surfaces a hidden chunk.
"""

from __future__ import annotations

import math
import re
import string
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

import structlog
from sqlalchemy import distinct, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.master_resume import (
    MasterResume,
    MasterResumeChunk,
    MasterResumeSectionType,
    MasterResumeSourceDoc,
)
from app.services.master_resume.chunking import (
    Chunk,
    chunk_parsed_sections,
    chunk_raw_text,
    count_tokens,
)
from app.services.retrieval.config import RETRIEVAL_EMBEDDING_MODEL
from app.services.master_resume.embedding import (
    EmbeddingConfigurationError,
    EmbeddingProviderError,
    embed_texts,
)

log = structlog.get_logger("master_resume.crud")

MAX_SOURCE_RESUMES = 5
_COSINE_DEDUP_THRESHOLD = 0.92


def _merge_fingerprint(
    section_type: MasterResumeSectionType,
    content: str,
    metadata: dict[str, Any] | None,
) -> str | None:
    """Stable key for project/education rows when text differs slightly across uploads."""
    meta = metadata or {}
    if section_type == MasterResumeSectionType.project:
        for key in ("title", "name"):
            value = meta.get(key)
            if isinstance(value, str) and value.strip():
                return f"project:{_normalize_chunk_text(value)[:96]}"
        first_line = (content or "").split("\n", 1)[0].strip()
        if first_line:
            return f"project:{_normalize_chunk_text(first_line)[:96]}"
        return None
    if section_type == MasterResumeSectionType.education:
        for key in ("institution", "school"):
            value = meta.get(key)
            if isinstance(value, str) and value.strip():
                return f"edu:{_normalize_chunk_text(value)[:96]}"
        head = (content or "").split("—", 1)[0].strip()
        if head:
            return f"edu:{_normalize_chunk_text(head)[:96]}"
        return None
    return None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_chunk_text(text: str) -> str:
    lowered = (text or "").lower()
    stripped = lowered.translate(str.maketrans("", "", string.punctuation))
    return " ".join(stripped.split())


def _cosine_vectors(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b, strict=False):
        x = float(x)
        y = float(y)
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


async def count_live_source_docs(db: AsyncSession, *, user_id: uuid.UUID) -> int:
    row = (
        await db.execute(
            select(func.count(distinct(MasterResumeChunk.source_doc_id))).where(
                MasterResumeChunk.user_id == user_id,
                MasterResumeChunk.deleted_at.is_(None),
                MasterResumeChunk.source_doc_id.is_not(None),
            )
        )
    ).scalar_one()
    return int(row or 0)


def _detect_role_conflicts(
    parsed_sections: dict[str, Any],
    existing_chunks: list[MasterResumeChunk],
) -> list[dict[str, str]]:
    """Report company/title mismatches (non-blocking)."""
    new_roles: list[tuple[str, str]] = []
    for entry in parsed_sections.get("experience") or []:
        if not isinstance(entry, dict):
            continue
        company = str(entry.get("company") or "").strip()
        title = str(entry.get("title") or "").strip()
        if company and title:
            new_roles.append((company.lower(), title))

    conflicts: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for chunk in existing_chunks:
        if chunk.section_type != MasterResumeSectionType.experience:
            continue
        meta = chunk.chunk_metadata or {}
        company = str(meta.get("company") or "").strip()
        title = str(meta.get("title") or "").strip()
        if not company or not title:
            continue
        for new_company, new_title in new_roles:
            if new_company == company.lower() and new_title.lower() != title.lower():
                key = (company.lower(), title.lower(), new_title.lower())
                if key in seen:
                    continue
                seen.add(key)
                conflicts.append(
                    {
                        "company": company,
                        "existing": title,
                        "new": new_title,
                    }
                )
    return conflicts


async def merge_upload_chunks(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    raw_text: str,
    parsed_sections: dict[str, Any] | None,
    filename: str | None = None,
) -> tuple[MasterResume, list[MasterResumeChunk], list[dict[str, str]]]:
    """Merge a new upload into existing live chunks (dedup + source doc)."""
    if await count_live_source_docs(db, user_id=user_id) >= MAX_SOURCE_RESUMES:
        raise ValueError("upload_limit_reached")

    if parsed_sections:
        chunks = chunk_parsed_sections(parsed_sections)
    else:
        chunks = chunk_raw_text(raw_text)

    resume = await _upsert_master_resume(
        db,
        user_id=user_id,
        raw_text=raw_text,
        parsed_sections=parsed_sections or {},
    )

    existing = await get_chunks_for_user(db, user_id=user_id)
    normalized_existing = {
        _normalize_chunk_text(c.content)
        for c in existing
        if c.content
    }
    merge_fingerprints: set[str] = set()
    for row in existing:
        fp = _merge_fingerprint(row.section_type, row.content, row.chunk_metadata)
        if fp:
            merge_fingerprints.add(fp)

    to_insert: list[Chunk] = []
    section_vectors: dict[MasterResumeSectionType, list[tuple[MasterResumeChunk, list[float]]]] = {}
    for row in existing:
        if row.embedding is None:
            continue
        section_vectors.setdefault(row.section_type, []).append(
            (row, list(row.embedding))
        )

    pending_vectors: list[list[float]] = []
    pending_chunks: list[Chunk] = []
    if chunks:
        try:
            pending_vectors = await embed_texts([c.content for c in chunks])
        except (EmbeddingConfigurationError, EmbeddingProviderError):
            from app.models.master_resume import EMBEDDING_DIM

            pending_vectors = [[0.0] * EMBEDDING_DIM for _ in chunks]

    for chunk, vector in zip(chunks, pending_vectors, strict=False):
        norm = _normalize_chunk_text(chunk.content)
        if norm in normalized_existing:
            continue
        fp = _merge_fingerprint(chunk.section_type, chunk.content, chunk.metadata)
        if fp and fp in merge_fingerprints:
            continue
        best = 0.0
        for _row, existing_vec in section_vectors.get(chunk.section_type, []):
            sim = _cosine_vectors(vector, existing_vec)
            best = max(best, sim)
        if best > _COSINE_DEDUP_THRESHOLD:
            continue
        to_insert.append(chunk)
        normalized_existing.add(norm)
        if fp:
            merge_fingerprints.add(fp)

    source_doc_id: uuid.UUID | None = None
    if to_insert:
        source_doc = MasterResumeSourceDoc(
            id=uuid.uuid4(),
            user_id=user_id,
            filename=(filename or "")[:512] or None,
            chunk_count=len(to_insert),
        )
        db.add(source_doc)
        await db.flush()
        source_doc_id = source_doc.id

    inserted = await _insert_chunks(
        db,
        resume=resume,
        user_id=user_id,
        chunks=to_insert,
        source_doc_id=source_doc_id,
    )
    resume.chunk_count = len(existing) + len(inserted)
    if inserted:
        resume.last_embedded_at = _utcnow()
    resume.updated_at = _utcnow()
    await db.flush()

    conflicts = _detect_role_conflicts(parsed_sections or {}, existing)
    return resume, inserted, conflicts


# ---------------------------------------------------------------------------
# MasterResume row helpers
# ---------------------------------------------------------------------------


async def get_raw_resume(
    db: AsyncSession, *, user_id: uuid.UUID
) -> MasterResume | None:
    """Return the user's master resume row (or ``None`` if not uploaded)."""
    return (
        await db.execute(
            select(MasterResume).where(MasterResume.user_id == user_id)
        )
    ).scalar_one_or_none()


async def _upsert_master_resume(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    raw_text: str,
    parsed_sections: dict[str, Any],
) -> MasterResume:
    """Insert or replace the user's ``MasterResume`` row.

    Replacement is done by mutating the existing row in-place so the FK
    cascade (chunks → master_resumes) does not blow away history before
    the new chunks have been written.  Caller is responsible for the
    chunk lifecycle (wipe + recreate vs. patch).
    """
    row = await get_raw_resume(db, user_id=user_id)
    now = _utcnow()
    if row is None:
        row = MasterResume(
            id=uuid.uuid4(),
            user_id=user_id,
            raw_text=raw_text,
            parsed_sections=parsed_sections or {},
            chunk_count=0,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        await db.flush()
        return row

    row.raw_text = raw_text
    row.parsed_sections = parsed_sections or {}
    row.updated_at = now
    await db.flush()
    return row


# ---------------------------------------------------------------------------
# Chunk listing
# ---------------------------------------------------------------------------


async def get_chunks_for_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    include_deleted: bool = False,
    section_type: MasterResumeSectionType | None = None,
) -> list[MasterResumeChunk]:
    """Return all live chunks for ``user_id`` ordered for determinism.

    Ordering ``(created_at ASC, id ASC)`` matches the tie-breaker used
    by the retrieval ANN query so the order seen by ``GET
    /api/profile/resume/chunks`` is consistent with the order seen by
    the retrieval trace.
    """
    stmt = select(MasterResumeChunk).where(MasterResumeChunk.user_id == user_id)
    if not include_deleted:
        stmt = stmt.where(MasterResumeChunk.deleted_at.is_(None))
    if section_type is not None:
        stmt = stmt.where(MasterResumeChunk.section_type == section_type)
    stmt = stmt.order_by(
        MasterResumeChunk.created_at.asc(),
        MasterResumeChunk.id.asc(),
    )
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


async def get_chunk(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    chunk_id: uuid.UUID,
    include_deleted: bool = False,
) -> MasterResumeChunk | None:
    stmt = select(MasterResumeChunk).where(
        MasterResumeChunk.id == chunk_id,
        MasterResumeChunk.user_id == user_id,
    )
    if not include_deleted:
        stmt = stmt.where(MasterResumeChunk.deleted_at.is_(None))
    return (await db.execute(stmt)).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Chunk write paths (create / update / delete)
# ---------------------------------------------------------------------------


async def replace_all_chunks(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    raw_text: str,
    parsed_sections: dict[str, Any] | None,
) -> tuple[MasterResume, list[MasterResumeChunk]]:
    """Full-replace flow used by POST /resume and PUT /resume.

    1. Upsert the ``master_resumes`` row.
    2. Soft-delete every existing chunk for the user.
    3. Re-chunk + embed the new payload.
    4. Insert one row per chunk inside the same transaction.

    Returns ``(master_resume, new_chunks)``.
    """
    if parsed_sections:
        chunks = chunk_parsed_sections(parsed_sections)
    else:
        chunks = chunk_raw_text(raw_text)

    resume = await _upsert_master_resume(
        db,
        user_id=user_id,
        raw_text=raw_text,
        parsed_sections=parsed_sections or {},
    )

    # Soft-delete prior chunks so they no longer participate in
    # retrieval but stay queryable for historical references.
    await db.execute(
        update(MasterResumeChunk)
        .where(
            MasterResumeChunk.user_id == user_id,
            MasterResumeChunk.deleted_at.is_(None),
        )
        .values(deleted_at=_utcnow())
    )
    await db.flush()

    rows = await _insert_chunks(db, resume=resume, user_id=user_id, chunks=chunks)
    resume.chunk_count = len(rows)
    resume.last_embedded_at = _utcnow()
    await db.flush()
    return resume, rows


async def create_chunk(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    section_type: MasterResumeSectionType,
    content: str,
    source_doc_id: uuid.UUID | None = None,
) -> MasterResumeChunk:
    """Insert one live chunk with embedding (brick CRUD POST)."""
    resume = await get_raw_resume(db, user_id=user_id)
    if resume is None:
        raise ValueError("master resume not found")

    cleaned = (content or "").strip()
    if not cleaned:
        raise ValueError("content must not be empty")

    chunk = Chunk(
        section_type=section_type,
        content=cleaned,
        token_count=count_tokens(cleaned),
        metadata={},
    )
    rows = await _insert_chunks(
        db,
        resume=resume,
        user_id=user_id,
        chunks=[chunk],
        source_doc_id=source_doc_id,
    )
    resume.chunk_count += len(rows)
    resume.last_embedded_at = _utcnow()
    resume.updated_at = _utcnow()
    await db.flush()
    return rows[0]


async def _insert_chunks(
    db: AsyncSession,
    *,
    resume: MasterResume,
    user_id: uuid.UUID,
    chunks: Sequence[Chunk],
    source_doc_id: uuid.UUID | None = None,
) -> list[MasterResumeChunk]:
    """Embed and insert ``chunks``; returns the inserted ORM rows.

    If the embedding service is unavailable (missing OpenAI key or provider
    error), chunks are saved with a zero-vector so the resume text is always
    persisted.  The caller can trigger a re-embed once the key is configured.
    """
    if not chunks:
        return []

    try:
        vectors = await embed_texts([c.content for c in chunks])
    except (EmbeddingConfigurationError, EmbeddingProviderError) as exc:
        log.warning(
            "master_resume.embed_failed_fallback",
            error=str(exc),
            chunk_count=len(chunks),
        )
        from app.models.master_resume import EMBEDDING_DIM
        vectors = [[0.0] * EMBEDDING_DIM for _ in chunks]
        resume.last_embedded_at = None  # signal that embeddings are not valid
    now = _utcnow()
    rows: list[MasterResumeChunk] = []
    for chunk, vector in zip(chunks, vectors):
        row = MasterResumeChunk(
            id=uuid.uuid4(),
            master_resume_id=resume.id,
            user_id=user_id,
            section_type=chunk.section_type,
            content=chunk.content,
            token_count=chunk.token_count,
            embedding=vector,
            embedding_model=RETRIEVAL_EMBEDDING_MODEL,
            chunk_metadata=dict(chunk.metadata or {}),
            source_doc_id=source_doc_id,
            created_at=now,
            updated_at=now,
        )
        db.add(row)
        rows.append(row)
    await db.flush()
    return rows


async def add_chunks(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    chunks: Sequence[Chunk],
) -> list[MasterResumeChunk]:
    """Append new chunks to the user's master resume (bulk insert).

    Used by ``PATCH /api/profile/resume/chunks`` when the fit UI adds
    suggested bullets.  Requires an existing ``MasterResume`` row.
    """
    if not chunks:
        return []

    resume = await get_raw_resume(db, user_id=user_id)
    if resume is None:
        raise ValueError("master resume not found")

    rows = await _insert_chunks(db, resume=resume, user_id=user_id, chunks=chunks)
    resume.chunk_count += len(rows)
    resume.last_embedded_at = _utcnow()
    resume.updated_at = _utcnow()
    await db.flush()
    return rows


async def update_chunk_content(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    chunk_id: uuid.UUID,
    new_content: str,
    new_section_type: MasterResumeSectionType | None = None,
    new_metadata: dict[str, Any] | None = None,
) -> MasterResumeChunk | None:
    """Edit a single chunk in place and re-embed it.

    Used by ``PATCH /api/profile/resume/chunks/{id}``.  Re-embedding
    only the touched chunk (instead of the full resume) matches §18.4
    "Re-embedding strategy".
    """
    chunk = await get_chunk(db, user_id=user_id, chunk_id=chunk_id)
    if chunk is None:
        return None

    cleaned = (new_content or "").strip()
    if not cleaned:
        # Empty content is the documented way to delete a chunk via PATCH;
        # callers that want delete semantics should use the DELETE
        # endpoint, but we tolerate the alias here.
        await delete_chunk(db, user_id=user_id, chunk_id=chunk_id)
        return None

    chunk.content = cleaned
    chunk.token_count = count_tokens(cleaned)
    if new_section_type is not None:
        chunk.section_type = new_section_type
    if new_metadata is not None:
        chunk.chunk_metadata = dict(new_metadata)
    chunk.updated_at = _utcnow()

    # Re-embed just this chunk (single-element batch).
    [vector] = await embed_texts([cleaned])
    chunk.embedding = vector
    chunk.embedding_model = RETRIEVAL_EMBEDDING_MODEL

    # Mirror the parent's bookkeeping.
    resume = await db.get(MasterResume, chunk.master_resume_id)
    if resume is not None:
        resume.last_embedded_at = _utcnow()
        resume.updated_at = _utcnow()

    await db.flush()
    return chunk


def _chunk_keep_score(chunk: MasterResumeChunk) -> tuple[int, int, float]:
    """Sort key — higher richness wins when deduping duplicates."""
    content = chunk.content or ""
    richness = len(content)
    if "\n" in content:
        richness += 50
    meta = chunk.chunk_metadata or {}
    for key in ("dates", "start_date", "end_date", "graduation_date", "year"):
        if meta.get(key):
            richness += 100
            break
    updated = chunk.updated_at or chunk.created_at or _utcnow()
    return (richness, chunk.token_count or 0, updated.timestamp())


def plan_master_resume_dedupe_ids(
    chunks: Sequence[MasterResumeChunk],
) -> list[uuid.UUID]:
    """Return chunk IDs to soft-delete: duplicate projects, education, and skills."""
    live = [c for c in chunks if c.deleted_at is None]
    to_delete: set[uuid.UUID] = set()

    by_fingerprint: dict[str, list[MasterResumeChunk]] = {}
    for chunk in live:
        if chunk.section_type not in (
            MasterResumeSectionType.project,
            MasterResumeSectionType.education,
        ):
            continue
        fp = _merge_fingerprint(
            chunk.section_type, chunk.content, chunk.chunk_metadata
        )
        if not fp:
            norm = _normalize_chunk_text(chunk.content)
            if not norm:
                continue
            fp = f"{chunk.section_type.value}:norm:{norm[:120]}"
        by_fingerprint.setdefault(fp, []).append(chunk)

    for group in by_fingerprint.values():
        if len(group) < 2:
            continue
        ordered = sorted(group, key=_chunk_keep_score, reverse=True)
        for loser in ordered[1:]:
            to_delete.add(loser.id)

    skills = [
        c
        for c in live
        if c.section_type == MasterResumeSectionType.skills and c.id not in to_delete
    ]
    by_norm: dict[str, list[MasterResumeChunk]] = {}
    for chunk in skills:
        norm = _normalize_chunk_text(chunk.content)
        if not norm:
            continue
        by_norm.setdefault(norm, []).append(chunk)
    for group in by_norm.values():
        if len(group) < 2:
            continue
        ordered = sorted(group, key=_chunk_keep_score, reverse=True)
        for loser in ordered[1:]:
            to_delete.add(loser.id)

    skills_remaining = [c for c in skills if c.id not in to_delete]
    keepers: list[MasterResumeChunk] = []
    for chunk in sorted(skills_remaining, key=_chunk_keep_score, reverse=True):
        vec = list(chunk.embedding) if chunk.embedding is not None else None
        if vec is None:
            keepers.append(chunk)
            continue
        is_dup = False
        for keeper in keepers:
            kvec = list(keeper.embedding) if keeper.embedding is not None else None
            if kvec is None:
                continue
            if _cosine_vectors(vec, kvec) > _COSINE_DEDUP_THRESHOLD:
                is_dup = True
                break
        if is_dup:
            to_delete.add(chunk.id)
        else:
            keepers.append(chunk)

    return list(to_delete)


async def dedupe_live_chunks(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> dict[str, Any]:
    """Soft-delete duplicate project, education, and near-duplicate skill chunks."""
    chunks = await get_chunks_for_user(db, user_id=user_id)
    doomed = plan_master_resume_dedupe_ids(chunks)
    if not doomed:
        return {
            "deleted_count": 0,
            "deleted_by_section": {},
            "live_chunk_count": len(chunks),
        }

    by_section: dict[str, int] = {}
    id_set = set(doomed)
    deleted_count = 0
    for chunk in chunks:
        if chunk.id not in id_set:
            continue
        if await delete_chunk(db, user_id=user_id, chunk_id=chunk.id):
            deleted_count += 1
            section = chunk.section_type.value
            by_section[section] = by_section.get(section, 0) + 1

    live_after = await get_chunks_for_user(db, user_id=user_id)
    log.info(
        "master_resume.dedupe",
        user_id=str(user_id),
        deleted=deleted_count,
        by_section=by_section,
    )
    return {
        "deleted_count": deleted_count,
        "deleted_by_section": by_section,
        "live_chunk_count": len(live_after),
    }


async def delete_chunk(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    chunk_id: uuid.UUID,
) -> bool:
    """Soft-delete ``chunk_id`` (no-op if already deleted or unknown).

    Returns ``True`` when a live chunk transitioned to deleted state.
    """
    chunk = await get_chunk(db, user_id=user_id, chunk_id=chunk_id)
    if chunk is None:
        return False
    chunk.deleted_at = _utcnow()
    chunk.updated_at = chunk.deleted_at

    resume = await db.get(MasterResume, chunk.master_resume_id)
    if resume is not None:
        # Drop the chunk-count cache by one so the UI shows the new
        # value without forcing a full recount.  Re-embedding window
        # stays as-is — deletion is not a re-embed.
        resume.chunk_count = max(0, resume.chunk_count - 1)
        resume.updated_at = _utcnow()

    await db.flush()
    return True


# ---------------------------------------------------------------------------
# Helpers used by the retrieval service
# ---------------------------------------------------------------------------


async def has_any_live_chunk(
    db: AsyncSession, *, user_id: uuid.UUID
) -> bool:
    """Cheap existence check used by the 409 ``master_resume_required`` gate."""
    row = (
        await db.execute(
            select(MasterResumeChunk.id)
            .where(MasterResumeChunk.user_id == user_id)
            .where(MasterResumeChunk.deleted_at.is_(None))
            .limit(1)
        )
    ).first()
    return row is not None


def iter_chunk_summaries(
    rows: Iterable[MasterResumeChunk],
) -> list[dict[str, Any]]:
    """Project ORM rows into the shape returned by the list endpoint."""
    out: list[dict[str, Any]] = []
    for r in rows:
        out.append(
            {
                "id": str(r.id),
                "section_type": r.section_type.value,
                "content": r.content,
                "token_count": r.token_count,
                "source_doc_id": str(r.source_doc_id) if r.source_doc_id else None,
                "metadata": r.chunk_metadata,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "updated_at": r.updated_at.isoformat() if r.updated_at else None,
                "deleted_at": r.deleted_at.isoformat() if r.deleted_at else None,
            }
        )
    return out


def brick_summary(row: MasterResumeChunk) -> dict[str, Any]:
    """Shape for GET/POST/PATCH /api/profile/bricks."""
    return {
        "id": str(row.id),
        "section_type": row.section_type.value,
        "content": row.content,
        "token_count": row.token_count,
        "source_doc_id": str(row.source_doc_id) if row.source_doc_id else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "metadata": dict(row.chunk_metadata or {}),
    }


__all__ = [
    "MAX_SOURCE_RESUMES",
    "add_chunks",
    "brick_summary",
    "count_live_source_docs",
    "create_chunk",
    "dedupe_live_chunks",
    "delete_chunk",
    "get_chunk",
    "plan_master_resume_dedupe_ids",
    "get_chunks_for_user",
    "get_raw_resume",
    "has_any_live_chunk",
    "iter_chunk_summaries",
    "merge_upload_chunks",
    "replace_all_chunks",
    "update_chunk_content",
]
