"""Deterministic tailoring brief assembly for Phase 3 (P1 slice 3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import tiktoken

from app.agent.keyword_match import normalize_haystack
from app.models.keywords import KeywordExtractionOutput
from app.models.resume import ParsedResume
from app.services.retrieval import config as retrieval_cfg
from app.services.retrieval.retrieval_service import RetrievalResult, SelectedChunk

RetrievalChunk = SelectedChunk
Phase1Output = KeywordExtractionOutput

# Brief token budget: 60% of retrieval chunk budget (§6a analogue for PHASE3_MAX_TOKENS).
_BRIEF_TOKENIZER = tiktoken.get_encoding("cl100k_base")
_BRIEF_TOKEN_FRACTION = 0.6
_BRIEF_SCHEMA_VERSION = "v1"

_SKILL_CATEGORIES = frozenset({"tool", "language", "framework"})
_BRIEF_TOKEN_MAX_LEN = 80


def _sanitize_brief_label(text: str) -> str:
    """Single-line label safe for bracketed brief headers (anti prompt-injection)."""
    cleaned = " ".join((text or "").split())
    for ch in "[]\n\r\t":
        cleaned = cleaned.replace(ch, "")
    return cleaned[:_BRIEF_TOKEN_MAX_LEN].strip()


@dataclass
class SectionBrief:
    section_type: str
    chunks: list[RetrievalChunk]
    must_place_keywords: list[str]
    bullet_cap: int
    always_include: bool


@dataclass
class TailoringBrief:
    sections: list[SectionBrief]
    global_token_budget: int
    schema_version: str
    retrieval_meta: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "global_token_budget": self.global_token_budget,
            "retrieval_meta": dict(self.retrieval_meta),
            "sections": [
                {
                    "section_type": s.section_type,
                    "must_place_keywords": list(s.must_place_keywords),
                    "bullet_cap": s.bullet_cap,
                    "always_include": s.always_include,
                    "chunks": [c.to_trace() | {"content": c.content} for c in s.chunks],
                }
                for s in self.sections
            ],
        }


def _chunk_tokens(text: str) -> int:
    return len(_BRIEF_TOKENIZER.encode(text or ""))


def _global_brief_budget() -> int:
    base = retrieval_cfg.RETRIEVAL_TOKEN_BUDGET
    return int(base * _BRIEF_TOKEN_FRACTION)


def _bullet_cap_for_role_index(idx: int) -> int:
    if idx == 0:
        return 5
    if idx == 1:
        return 3
    return 2


def _company_key(chunk: SelectedChunk) -> str:
    meta = chunk.metadata or {}
    for key in ("company", "title", "role"):
        val = meta.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip().lower()
    return ""


def _match_company(role_company: str, chunk: SelectedChunk) -> bool:
    key = _company_key(chunk)
    if not key:
        return False
    norm = role_company.strip().lower()
    return norm in key or key in norm


def _all_scored_chunks(result: RetrievalResult) -> list[SelectedChunk]:
    """Selected chunks plus skipped rows that still carry content (for fallback top-1)."""
    by_id: dict[str, SelectedChunk] = {s.chunk_id: s for s in result.selected}
    for sk in result.skipped:
        if sk.chunk_id in by_id:
            continue
        if not sk.content:
            continue
        by_id[sk.chunk_id] = SelectedChunk(
            chunk_id=sk.chunk_id,
            section=sk.section,
            score=sk.score,
            tokens=_chunk_tokens(sk.content),
            content=sk.content,
            metadata={},
        )
    return sorted(by_id.values(), key=lambda c: (-c.score, c.chunk_id))


def _assign_keywords(
    phase1: KeywordExtractionOutput,
    experience_roles: list[str],
    chunks_by_section: dict[str, list[SelectedChunk]],
) -> dict[str, list[str]]:
    """Map section key -> keywords owned by that section (each keyword once)."""
    assignments: dict[str, list[str]] = {}
    used: set[str] = set()

    def _claim(section_key: str, term: str) -> None:
        safe = _sanitize_brief_label(term)
        if not safe:
            return
        low = safe.lower()
        if low in used:
            return
        used.add(low)
        assignments.setdefault(section_key, []).append(safe)

    must = [k for k in (phase1.must_have_keywords or []) if k.term.strip()]
    exp_chunks = chunks_by_section.get("experience", [])

    for kw in must:
        term = kw.term.strip()
        if kw.category in _SKILL_CATEGORIES:
            _claim("skills", term)
            continue

        placed = False
        for idx, company in enumerate(experience_roles):
            section_key = f"experience:{company}"
            role_chunks = [c for c in exp_chunks if _match_company(company, c)]
            haystacks = [normalize_haystack(c.content) for c in role_chunks]
            if any(term.lower() in h for h in haystacks):
                _claim(section_key, term)
                placed = True
                break
        if placed:
            continue

        if experience_roles:
            _claim(f"experience:{experience_roles[0]}", term)

    return assignments


def _chunks_above_threshold(chunks: list[SelectedChunk]) -> list[SelectedChunk]:
    thr = retrieval_cfg.RETRIEVAL_PRIMARY_THRESHOLD
    return [c for c in chunks if c.score >= thr]


def _trim_to_token_budget(sections: list[SectionBrief], budget: int) -> list[SectionBrief]:
    """Drop lowest-scored chunks globally until total content tokens fit budget."""
    pool: list[tuple[float, int, int, SelectedChunk]] = []
    for s_idx, section in enumerate(sections):
        for c_idx, chunk in enumerate(section.chunks):
            pool.append((chunk.score, s_idx, c_idx, chunk))

    total = sum(_chunk_tokens(c.content) for _, _, _, c in pool)
    if total <= budget:
        return sections

    pool.sort(key=lambda item: (item[0], item[3].chunk_id))
    mutable: list[SectionBrief] = [
        SectionBrief(
            section_type=s.section_type,
            chunks=list(s.chunks),
            must_place_keywords=list(s.must_place_keywords),
            bullet_cap=s.bullet_cap,
            always_include=s.always_include,
        )
        for s in sections
    ]

    for score, s_idx, _c_idx, chunk in pool:
        if total <= budget:
            break
        section = mutable[s_idx]
        if section.always_include and len(section.chunks) <= 1:
            continue
        if chunk not in section.chunks:
            continue
        section.chunks.remove(chunk)
        total -= _chunk_tokens(chunk.content)

    return [s for s in mutable if s.chunks or s.always_include]


def _allocate_section_token_budgets(sections: list[SectionBrief], budget: int) -> None:
    cap_sum = sum(max(1, s.bullet_cap) for s in sections)
    if cap_sum <= 0:
        return
    for section in sections:
        share = max(1, section.bullet_cap) / cap_sum
        section_budget = int(budget * share)
        kept: list[SelectedChunk] = []
        running = 0
        for chunk in sorted(section.chunks, key=lambda c: (-c.score, c.chunk_id)):
            need = _chunk_tokens(chunk.content)
            if running + need > section_budget and kept:
                continue
            kept.append(chunk)
            running += need
        section.chunks = kept


def assemble_tailoring_ingredients(
    retrieval_result: RetrievalResult,
    phase1_output: Phase1Output,
    resume_parsed: ParsedResume,
    target_pages: int,
) -> TailoringBrief:
    """Build a deterministic section brief from retrieval + Phase 1 keywords."""
    _ = max(1, target_pages)  # reserved for future page-aware caps
    global_budget = _global_brief_budget()

    experience_roles: list[str] = []
    for entry in resume_parsed.experience or []:
        company = _sanitize_brief_label(entry.company or "")
        if company:
            experience_roles.append(company)

    all_chunks = _all_scored_chunks(retrieval_result)
    by_section: dict[str, list[SelectedChunk]] = {}
    for chunk in all_chunks:
        by_section.setdefault(chunk.section, []).append(chunk)

    keyword_map = _assign_keywords(phase1_output, experience_roles, by_section)

    sections: list[SectionBrief] = []

    # Skills
    skill_chunks = _chunks_above_threshold(by_section.get("skills", []))
    skills_keywords = keyword_map.get("skills", [])
    if skill_chunks or skills_keywords:
        sections.append(
            SectionBrief(
                section_type="skills",
                chunks=skill_chunks,
                must_place_keywords=skills_keywords,
                bullet_cap=6,
                always_include=False,
            )
        )

    # Experience — one brief per role on the parsed resume
    exp_pool = by_section.get("experience", [])
    for idx, company in enumerate(experience_roles):
        section_key = f"experience:{company}"
        role_chunks = [c for c in exp_pool if _match_company(company, c)]
        above = _chunks_above_threshold(role_chunks)
        chunks = above
        if not chunks and role_chunks:
            best = max(role_chunks, key=lambda c: (c.score, c.chunk_id))
            chunks = [best]
        elif not chunks and exp_pool:
            best = max(exp_pool, key=lambda c: (c.score, c.chunk_id))
            chunks = [best]

        must_kw = keyword_map.get(section_key, [])
        if not chunks and not must_kw:
            continue

        sections.append(
            SectionBrief(
                section_type=section_key,
                chunks=chunks,
                must_place_keywords=must_kw,
                bullet_cap=_bullet_cap_for_role_index(idx),
                always_include=False,
            )
        )

    # Education & certifications — always include
    for section_name, always in (("education", True), ("cert", True)):
        pool = by_section.get(section_name, [])
        above = _chunks_above_threshold(pool)
        chunks = above if above else (pool[:1] if pool else [])
        if not always and not chunks:
            continue
        sections.append(
            SectionBrief(
                section_type=section_name,
                chunks=chunks,
                must_place_keywords=[],
                bullet_cap=3 if section_name == "education" else 2,
                always_include=always,
            )
        )

    # Other sections (projects, etc.)
    for section_name in ("project", "summary", "other"):
        pool = by_section.get(section_name, [])
        above = _chunks_above_threshold(pool)
        if not above:
            continue
        sections.append(
            SectionBrief(
                section_type=section_name,
                chunks=above,
                must_place_keywords=[],
                bullet_cap=retrieval_cfg.section_cap(section_name),
                always_include=False,
            )
        )

    _allocate_section_token_budgets(sections, global_budget)
    sections = _trim_to_token_budget(sections, global_budget)

    return TailoringBrief(
        sections=sections,
        global_token_budget=global_budget,
        schema_version=_BRIEF_SCHEMA_VERSION,
        retrieval_meta=dict(retrieval_result.meta),
    )


def render_brief_for_prompt(brief: TailoringBrief) -> str:
    lines = [
        "TAILORING BRIEF (compose ONLY from these bricks):",
    ]
    for section in brief.sections:
        safe_type = _sanitize_brief_label(section.section_type.replace("\n", " "))
        header = f"[{safe_type.upper()}"
        if section.must_place_keywords:
            header += f" — must place: {', '.join(section.must_place_keywords)}"
        if section.section_type.startswith("experience:"):
            header += f" — cap: {section.bullet_cap}"
        header += "]"
        lines.append(header)
        for chunk in section.chunks:
            lines.append(chunk.content)
        lines.append("")
    return "\n".join(lines).strip()


__all__ = [
    "Phase1Output",
    "RetrievalChunk",
    "SectionBrief",
    "TailoringBrief",
    "assemble_tailoring_ingredients",
    "render_brief_for_prompt",
]
