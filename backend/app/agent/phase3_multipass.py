"""Multi-pass Phase 3 composition (feature-flagged)."""

from __future__ import annotations

import asyncio
import re
from typing import Any

import structlog
from pydantic import BaseModel, Field

from app.agent.brief import SectionBrief, TailoringBrief
from app.llm.base import LLMClient, LLMMessage
from app.llm.structured import complete_structured
from app.models.rewrite import TailoredExperienceEntry, TailoredResumeOutput

log = structlog.get_logger(__name__)

_SECTION_COMPOSITION_RETRIES = 2
_PROTECTED_NUMBER = re.compile(r"\d+\.?\d*[%xX]?", re.I)


class SectionBulletsOutput(BaseModel):
    bullets: list[str] = Field(default_factory=list)


class AnchoredEdit(BaseModel):
    bullet_id: str
    replacement: str


class CoherencePolishOutput(BaseModel):
    edits: list[AnchoredEdit] = Field(default_factory=list)


def bullet_id_for(section: str, entry_index: int, bullet_index: int) -> str:
    return f"{section}:{entry_index}:{bullet_index}"


def parse_bullet_id(bullet_id: str) -> tuple[str, int, int] | None:
    parts = bullet_id.split(":")
    if len(parts) != 3:
        return None
    try:
        return parts[0], int(parts[1]), int(parts[2])
    except ValueError:
        return None


def build_protected_tokens(
    output: TailoredResumeOutput,
    must_have_keywords: list[str],
    *,
    brick_company_names: list[str] | None = None,
) -> dict[str, list[str]]:
    """Collect strings that must survive coherence polish per bullet."""
    protected: dict[str, list[str]] = {}
    must_lower = [k.strip() for k in must_have_keywords if k.strip()]

    def add(bid: str, bullet: str) -> None:
        tokens: list[str] = []
        for match in _PROTECTED_NUMBER.findall(bullet):
            tokens.append(match)
        for kw in must_lower:
            if kw.lower() in bullet.lower():
                tokens.append(kw)
        for company in brick_company_names or []:
            if company and company.lower() in bullet.lower():
                tokens.append(company)
        if tokens:
            protected[bid] = list(dict.fromkeys(tokens))

    for ei, exp in enumerate(output.experience):
        for bi, bullet in enumerate(exp.bullets):
            add(bullet_id_for("experience", ei, bi), bullet)

    for pi, proj in enumerate(output.projects):
        bullets = proj.get("bullets") if isinstance(proj, dict) else []
        for bi, bullet in enumerate(bullets or []):
            add(bullet_id_for("projects", pi, bi), str(bullet))

    return protected


def apply_anchored_edits(
    output: TailoredResumeOutput,
    edits: list[AnchoredEdit],
    protected_tokens: dict[str, list[str]],
) -> tuple[TailoredResumeOutput, set[str]]:
    """Merge polish edits with protected-token enforcement."""
    modified: set[str] = set()
    result = output.model_copy(deep=True)

    for edit in edits:
        parsed = parse_bullet_id(edit.bullet_id)
        if parsed is None:
            continue
        section, entry_idx, bullet_idx = parsed
        required = protected_tokens.get(edit.bullet_id, [])
        replacement = edit.replacement or ""
        if required:
            repl_lower = replacement.lower()
            if not all(tok.lower() in repl_lower for tok in required):
                log.info(
                    "multipass.polish_discard_missing_protected",
                    bullet_id=edit.bullet_id,
                )
                continue

        if section == "experience":
            if entry_idx >= len(result.experience):
                continue
            exp = result.experience[entry_idx]
            if bullet_idx >= len(exp.bullets):
                continue
            new_bullets = list(exp.bullets)
            new_bullets[bullet_idx] = replacement.strip()
            result.experience[entry_idx] = exp.model_copy(update={"bullets": new_bullets})
            modified.add(edit.bullet_id)
        elif section == "projects":
            if entry_idx >= len(result.projects):
                continue
            proj = dict(result.projects[entry_idx])
            bullets = list(proj.get("bullets") or [])
            if bullet_idx >= len(bullets):
                continue
            bullets[bullet_idx] = replacement.strip()
            proj["bullets"] = bullets
            result.projects[entry_idx] = proj
            modified.add(edit.bullet_id)

    return result, modified


def _fallback_bullets(section: SectionBrief) -> list[str]:
    lines: list[str] = []
    for chunk in section.chunks:
        text = (chunk.content or "").strip()
        if text:
            lines.append(text)
    return lines


def _reject_empty_section(output: BaseModel) -> str | None:
    if isinstance(output, SectionBulletsOutput):
        if not any((b or "").strip() for b in output.bullets):
            return "section bullets empty"
    return None


async def run_section_composition(
    section_brief: SectionBrief,
    jd_text: str,
    shared_context: str,
    llm: LLMClient,
) -> list[str]:
    """One LLM call per section; returns bullet strings."""
    system = (
        "You compose resume bullets for ONE section only. "
        "Use ONLY facts from the provided bricks. "
        "Return JSON with a bullets array of complete achievement lines."
    )
    brick_block = "\n".join(f"- {c.content}" for c in section_brief.chunks)
    user = (
        f"CONTEXT: {shared_context}\n\n"
        f"SECTION: {section_brief.section_type}\n"
        f"MUST-PLACE KEYWORDS: {', '.join(section_brief.must_place_keywords)}\n"
        f"BULLET CAP: {section_brief.bullet_cap}\n\n"
        f"BRICKS:\n{brick_block}\n\n"
        f"JOB DESCRIPTION:\n{jd_text}"
    )
    messages = [
        LLMMessage(role="system", content=system),
        LLMMessage(role="user", content=user),
    ]

    last_error: Exception | None = None
    for attempt in range(_SECTION_COMPOSITION_RETRIES + 1):
        try:
            parsed = await complete_structured(
                llm,
                messages,
                SectionBulletsOutput,
                max_tokens=1200,
                accept_result=_reject_empty_section,
            )
            bullets = [b.strip() for b in parsed.bullets if b.strip()]
            if bullets:
                return bullets[: section_brief.bullet_cap]
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            log.warning(
                "multipass.section_failed",
                section=section_brief.section_type,
                attempt=attempt,
                error=str(exc),
            )
    log.warning(
        "multipass.section_fallback_bricks",
        section=section_brief.section_type,
        error=str(last_error) if last_error else None,
    )
    return _fallback_bullets(section_brief)


def assemble_multipass_output(
    brief: TailoringBrief,
    section_bullets: dict[str, list[str]],
    *,
    contact: dict[str, Any] | None = None,
) -> TailoredResumeOutput:
    """Map per-section bullet lists into TailoredResumeOutput."""
    output = TailoredResumeOutput(contact=contact or {})
    for section in brief.sections:
        bullets = section_bullets.get(section.section_type, [])
        if section.section_type == "summary" and bullets:
            output.summary = bullets[0]
        elif section.section_type == "skills" and bullets:
            output.skills = bullets
        elif section.section_type == "experience" and bullets:
            company = ""
            title = ""
            if section.chunks:
                meta = section.chunks[0].metadata or {}
                company = str(meta.get("company") or "")
                title = str(meta.get("title") or "")
            output.experience.append(
                TailoredExperienceEntry(
                    company=company,
                    title=title,
                    bullets=bullets,
                )
            )
    return output


async def run_coherence_polish(
    assembled: TailoredResumeOutput,
    jd_text: str,
    protected_tokens: dict[str, list[str]],
    llm: LLMClient,
) -> list[AnchoredEdit]:
    """Schema-obedient polish pass — anchored bullet edits only."""
    protected_lines = []
    for bid, tokens in protected_tokens.items():
        protected_lines.append(f"{bid}: {', '.join(tokens)}")
    system = (
        "Review the resume for voice consistency and prose flow. "
        "For bullets that read awkwardly, emit anchored edits. "
        "Do NOT change any string marked as protected. "
        "If a bullet is acceptable, do not emit an edit for it."
    )
    user = (
        f"RESUME JSON:\n{assembled.model_dump_json()}\n\n"
        f"PROTECTED TOKENS PER BULLET:\n" + "\n".join(protected_lines) + "\n\n"
        f"JOB DESCRIPTION:\n{jd_text}"
    )
    messages = [
        LLMMessage(role="system", content=system),
        LLMMessage(role="user", content=user),
    ]
    try:
        parsed = await complete_structured(
            llm,
            messages,
            CoherencePolishOutput,
            max_tokens=2000,
        )
        return list(parsed.edits)
    except Exception as exc:  # noqa: BLE001
        log.warning("multipass.coherence_polish_failed", error=str(exc))
        return []


async def run_multipass_composition(
    *,
    brief: TailoringBrief,
    jd_text: str,
    shared_context: str,
    section_llm: LLMClient,
    polish_llm: LLMClient,
    contact: dict[str, Any] | None = None,
) -> TailoredResumeOutput:
    """Parallel section drafting + coherence polish."""
    sem = asyncio.Semaphore(4)

    async def _one(section: SectionBrief) -> tuple[str, list[str]]:
        async with sem:
            bullets = await run_section_composition(
                section, jd_text, shared_context, section_llm
            )
            return section.section_type, bullets

    pairs = await asyncio.gather(*[_one(s) for s in brief.sections])
    section_bullets = dict(pairs)
    return assemble_multipass_output(brief, section_bullets, contact=contact)


__all__ = [
    "AnchoredEdit",
    "apply_anchored_edits",
    "assemble_multipass_output",
    "build_protected_tokens",
    "bullet_id_for",
    "run_coherence_polish",
    "run_multipass_composition",
    "run_section_composition",
]
