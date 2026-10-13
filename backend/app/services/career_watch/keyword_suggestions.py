"""Suggest Career Watch keywords from the user's master resume."""

from __future__ import annotations

import re
import uuid
from collections import Counter
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.master_resume import MasterResumeSectionType
from app.services.master_resume.crud import get_chunks_for_user

_WORD_RE = re.compile(r"[a-z][a-z0-9+#.-]{1,48}", re.I)
_MAX_SUGGESTIONS = 6
_MIN_TOKEN_LEN = 3
_MAX_KEYWORD_PHRASE_LEN = 40

# Drop only filler tokens when mining free-text skills (not experience titles).
_SKILL_STOPWORDS = frozenset(
    {
        "and",
        "the",
        "for",
        "with",
        "team",
        "work",
        "experience",
        "years",
        "role",
        "skills",
    }
)

_SENIORITY_PREFIX_RE = re.compile(
    r"^(?:(?:senior|staff|principal|lead|director|manager|head|"
    r"vp|vice\s+president|junior|jr|intern|mid(?:-level)?|associate)\s+)+",
    re.I,
)


def _tokens_from_text(text: str) -> list[str]:
    return [m.group(0).lower() for m in _WORD_RE.finditer(text) if len(m.group(0)) >= _MIN_TOKEN_LEN]


def _normalize_phrase(raw: str) -> str:
    return re.sub(r"\s+", " ", raw.strip().lower())


def _title_role_phrases(raw: str) -> list[str]:
    """Full title plus de-senioritized role phrase (e.g. Senior SWE → software engineer)."""
    full = _normalize_phrase(raw.replace("—", " ").replace("–", "-"))
    if not full or len(full) < _MIN_TOKEN_LEN:
        return []
    out: list[str] = []
    if len(full) <= _MAX_KEYWORD_PHRASE_LEN:
        out.append(full)
    stripped = _SENIORITY_PREFIX_RE.sub("", full).strip()
    if (
        stripped
        and stripped != full
        and len(stripped) >= _MIN_TOKEN_LEN
        and len(stripped) <= _MAX_KEYWORD_PHRASE_LEN
    ):
        out.append(stripped)
    return out


def _title_bigrams(raw: str) -> list[str]:
    tokens = _tokens_from_text(raw.replace("—", " ").replace("–", "-"))
    bigrams: list[str] = []
    for i in range(len(tokens) - 1):
        phrase = f"{tokens[i]} {tokens[i + 1]}"
        if len(phrase) <= _MAX_KEYWORD_PHRASE_LEN:
            bigrams.append(phrase)
    return bigrams


def suggest_keywords_from_chunks(chunks: list[Any]) -> list[str]:
    """Derive keyword candidates from experience titles first, then skills."""
    if not chunks:
        return []

    counts: Counter[str] = Counter()
    ordered: list[str] = []

    def add_phrase(raw: str, weight: int = 1, *, allow_stopwords: bool = False) -> None:
        phrase = _normalize_phrase(raw)
        if not phrase or len(phrase) < _MIN_TOKEN_LEN:
            return
        if not allow_stopwords and phrase in _SKILL_STOPWORDS:
            return
        if len(phrase) > _MAX_KEYWORD_PHRASE_LEN:
            return
        if phrase not in counts:
            ordered.append(phrase)
        counts[phrase] += weight

    def add_experience_title(raw: str) -> None:
        for phrase in _title_role_phrases(raw):
            add_phrase(phrase, weight=25, allow_stopwords=True)
        for bigram in _title_bigrams(raw):
            add_phrase(bigram, weight=18, allow_stopwords=True)

    seen_titles: set[str] = set()
    for chunk in chunks:
        meta = chunk.chunk_metadata or {}
        if chunk.section_type == MasterResumeSectionType.experience:
            for key in ("job_title", "title", "role"):
                val = meta.get(key)
                if isinstance(val, str) and val.strip():
                    norm = _normalize_phrase(val)
                    if norm in seen_titles:
                        continue
                    seen_titles.add(norm)
                    add_experience_title(val)

    for chunk in chunks:
        if chunk.section_type != MasterResumeSectionType.skills:
            continue
        for part in re.split(r"[,;\n|/]+", chunk.content):
            add_phrase(part, weight=2)
        for tok in _tokens_from_text(chunk.content):
            if len(tok) >= 4 and tok not in _SKILL_STOPWORDS:
                add_phrase(tok, weight=1)

    ranked = sorted(ordered, key=lambda k: (-counts[k], -len(k), k))
    pruned: list[str] = []
    for phrase in ranked:
        if any(phrase != other and phrase in other for other in pruned):
            continue
        pruned.append(phrase)
        if len(pruned) >= _MAX_SUGGESTIONS:
            break
    return pruned


async def suggest_career_watch_keywords(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> list[str]:
    chunks = await get_chunks_for_user(session, user_id=user_id)
    return suggest_keywords_from_chunks(chunks)


__all__ = ["suggest_career_watch_keywords", "suggest_keywords_from_chunks"]
