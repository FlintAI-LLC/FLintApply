"""Phase 1b — per-requirement chunk scoring (P1 slice 4).

Blends the JD-level retrieval score with the best cosine match against
embedded requirement clauses, plus a deterministic exact-token boost when
significant requirement terms appear verbatim in chunk text.
"""

from __future__ import annotations

import math
import re
from typing import Any, Sequence

import structlog

from app.services.retrieval import config as cfg
from app.services.retrieval.retrieval_service import RetrievalResult, SelectedChunk

log = structlog.get_logger("retrieval.phase1b")

_TOKEN_RE = re.compile(r"[A-Za-z0-9+#.]{2,}")
_STOP = frozenset(
    {
        "and",
        "or",
        "the",
        "with",
        "for",
        "you",
        "your",
        "our",
        "have",
        "has",
        "will",
        "must",
        "years",
        "year",
        "experience",
        "working",
        "strong",
        "ability",
        "including",
    }
)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return max(-1.0, min(1.0, dot / (na * nb)))


def significant_terms(requirement: str) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for match in _TOKEN_RE.finditer(requirement or ""):
        tok = match.group(0).lower()
        if tok in _STOP or len(tok) < 2:
            continue
        if tok in seen:
            continue
        seen.add(tok)
        terms.append(tok)
    return terms


def exact_term_boost(requirement: str, content: str) -> float:
    """Boost when at least two significant requirement tokens appear in chunk content."""
    terms = significant_terms(requirement)
    if len(terms) < 2:
        return 0.0
    hay = (content or "").lower()
    hits = sum(1 for t in terms if t in hay)
    if hits < 2:
        return 0.0
    ratio = hits / len(terms)
    return cfg.REQUIREMENT_EXACT_TERM_BOOST * ratio


def score_chunk_against_requirements(
    *,
    base_score: float,
    content: str,
    requirement_vectors: list[tuple[str, list[float]]],
    chunk_vector: list[float],
) -> tuple[float, dict[str, Any]]:
    best_sim = 0.0
    best_req = ""
    best_exact = 0.0
    for req_text, req_vec in requirement_vectors:
        sim = _cosine(chunk_vector, req_vec)
        boost = exact_term_boost(req_text, content)
        combined = sim + boost
        if combined > best_sim + best_exact:
            best_sim = sim
            best_exact = boost
            best_req = req_text

    overlay = cfg.REQUIREMENT_SCORE_BLEND * (best_sim + best_exact)
    blended = max(-1.0, min(1.0, base_score + overlay))
    detail = {
        "best_requirement": best_req[:120],
        "requirement_similarity": round(best_sim, 6),
        "exact_term_boost": round(best_exact, 6),
        "blended_score": round(blended, 6),
    }
    return blended, detail


async def apply_requirement_scoring(
    result: RetrievalResult,
    requirements: list[str],
    *,
    embedding_model: str,
) -> RetrievalResult:
    """Return a copy of ``result`` with adjusted chunk scores and trace metadata."""
    if not requirements or not result.selected:
        return result

    from app.services.master_resume.embedding import (
        EmbeddingConfigurationError,
        EmbeddingProviderError,
        embed_texts,
    )

    capped = requirements[: cfg.MAX_REQUIREMENTS_FOR_EMBEDDING]
    try:
        req_vectors_raw = await embed_texts(capped, model=embedding_model)
        chunk_vectors_raw = await embed_texts(
            [c.content for c in result.selected],
            model=embedding_model,
        )
    except (EmbeddingConfigurationError, EmbeddingProviderError) as exc:
        log.warning("phase1b_embed_skipped", error=str(exc))
        return result

    req_pairs = list(zip(capped, req_vectors_raw))
    boosted: list[SelectedChunk] = []
    chunk_traces: dict[str, Any] = {}

    for chunk, chunk_vec in zip(result.selected, chunk_vectors_raw):
        blended, detail = score_chunk_against_requirements(
            base_score=chunk.score,
            content=chunk.content,
            requirement_vectors=req_pairs,
            chunk_vector=chunk_vec,
        )
        chunk_traces[chunk.chunk_id] = detail
        boosted.append(
            SelectedChunk(
                chunk_id=chunk.chunk_id,
                section=chunk.section,
                score=blended,
                tokens=chunk.tokens,
                content=chunk.content,
                metadata={
                    **(chunk.metadata or {}),
                    "requirement_scoring": detail,
                },
            )
        )

    meta = dict(result.meta)
    meta["phase1b_requirement_scoring"] = {
        "requirements_used": len(capped),
        "requirements_total": len(requirements),
        "chunk_traces": chunk_traces,
    }

    return RetrievalResult(selected=boosted, skipped=list(result.skipped), meta=meta)


__all__ = [
    "apply_requirement_scoring",
    "exact_term_boost",
    "score_chunk_against_requirements",
    "significant_terms",
]
