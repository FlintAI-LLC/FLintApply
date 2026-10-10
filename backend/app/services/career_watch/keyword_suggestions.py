"""Suggest Career Watch keywords from the user's master resume."""

from __future__ import annotations

import re
import uuid
from collections import Counter

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.master_resume import MasterResumeSectionType
from app.services.master_resume.crud import get_chunks_for_user

_WORD_RE = re.compile(r"[a-z][a-z0-9+#.-]{1,48}", re.I)
_MAX_SUGGESTIONS = 20
_MIN_TOKEN_LEN = 3


def _tokens_from_text(text: str) -> list[str]:
    return [m.group(0).lower() for m in _WORD_RE.finditer(text) if len(m.group(0)) >= _MIN_TOKEN_LEN]


async def suggest_career_watch_keywords(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> list[str]:
    """Derive keyword candidates from skills + experience titles (not full JD text)."""
    chunks = await get_chunks_for_user(session, user_id=user_id)
    if not chunks:
        return []

    counts: Counter[str] = Counter()
    ordered: list[str] = []

    def add_phrase(raw: str, weight: int = 1) -> None:
        phrase = raw.strip().lower()
        if not phrase or len(phrase) < _MIN_TOKEN_LEN:
            return
        if phrase not in counts:
            ordered.append(phrase)
        counts[phrase] += weight

    for chunk in chunks:
        meta = chunk.chunk_metadata or {}
        if chunk.section_type == MasterResumeSectionType.experience:
            for key in ("job_title", "title", "role"):
                val = meta.get(key)
                if isinstance(val, str) and val.strip():
                    add_phrase(val, weight=3)
        if chunk.section_type == MasterResumeSectionType.skills:
            for part in re.split(r"[,;\n|/]+", chunk.content):
                add_phrase(part, weight=2)
            for tok in _tokens_from_text(chunk.content):
                if len(tok) >= 4:
                    add_phrase(tok, weight=1)

    ranked = sorted(ordered, key=lambda k: (-counts[k], -len(k), k))
    return ranked[:_MAX_SUGGESTIONS]


__all__ = ["suggest_career_watch_keywords"]
