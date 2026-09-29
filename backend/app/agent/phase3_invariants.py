"""Deterministic section invariants for Phase 3 tailored output.

The LLM sometimes omits whole sections (Skills, Summary, ...) that exist in the
candidate's source resume. These helpers copy the missing section back from the
best available source. They never generate text: precedence is current
non-empty output, then the prior tailored output, then the parsed resume. When
every source is empty the section stays empty.
"""

from __future__ import annotations

import copy
from collections.abc import Sequence
from typing import Any, TypeVar

from app.agent.phase3_truthfulness import _companies_match
from app.models.resume import ParsedResume
from app.models.rewrite import (
    TailoredEducationEntry,
    TailoredExperienceEntry,
    TailoredResumeOutput,
)

_T = TypeVar("_T")

_SECTION_NOTE = (
    "Restored {label} section — LLM output omitted it despite "
    "being present in the original resume."
)
_ENTRY_NOTE_PREFIX = "Restored bullets for "
_ENTRY_NOTE_SUFFIX = " — LLM output left this role empty."


def _has_text(values: Sequence[str] | None) -> bool:
    return any(v and v.strip() for v in values or [])


def _first_non_empty(*candidates: list[_T]) -> list[_T]:
    for candidate in candidates:
        if candidate:
            return candidate
    return []


def _parsed_education(parsed: ParsedResume | None) -> list[TailoredEducationEntry]:
    if parsed is None:
        return []
    return [
        TailoredEducationEntry(
            degree=e.degree, institution=e.institution, year=e.year or "", bullets=[]
        )
        for e in parsed.education
    ]


def _parsed_projects(parsed: ParsedResume | None) -> list[dict[str, Any]]:
    if parsed is None:
        return []
    return [
        {
            "name": p.name,
            "url": p.url,
            "description": p.description,
            "bullets": list(p.bullets or []),
        }
        for p in parsed.projects
    ]


def _parsed_experience(parsed: ParsedResume | None) -> list[TailoredExperienceEntry]:
    if parsed is None:
        return []
    return [
        TailoredExperienceEntry(
            title=e.title, company=e.company, dates=e.dates, bullets=list(e.bullets)
        )
        for e in parsed.experience
        if _has_text(e.bullets)
    ]


def _bullets_for_role(
    company: str,
    prior: TailoredResumeOutput | None,
    parsed: ParsedResume | None,
) -> list[str]:
    if prior is not None:
        for entry in prior.experience:
            if _companies_match(entry.company, company) and _has_text(entry.bullets):
                return [b.strip() for b in entry.bullets if b.strip()]
    if parsed is not None:
        for entry in parsed.experience:
            if _companies_match(entry.company, company) and _has_text(entry.bullets):
                return [b.strip() for b in entry.bullets if b.strip()]
    return []


def _restore_empty_roles(
    entries: list[TailoredExperienceEntry],
    prior: TailoredResumeOutput | None,
    parsed: ParsedResume | None,
) -> tuple[list[TailoredExperienceEntry], list[str]]:
    restored: list[TailoredExperienceEntry] = []
    notes: list[str] = []
    for entry in entries:
        if _has_text(entry.bullets):
            restored.append(entry)
            continue
        bullets = _bullets_for_role(entry.company, prior, parsed)
        if not bullets:
            restored.append(entry)
            continue
        notes.append(f"{_ENTRY_NOTE_PREFIX}{entry.company or 'role'}{_ENTRY_NOTE_SUFFIX}")
        restored.append(entry.model_copy(update={"bullets": bullets}))
    return restored, notes


def enforce_resume_invariants(
    output: TailoredResumeOutput,
    *,
    resume_parsed: ParsedResume | None,
    prior_output: TailoredResumeOutput | None,
) -> TailoredResumeOutput:
    """Copy back sections the LLM dropped; idempotent and copy-only."""
    updates: dict[str, Any] = {}
    section_notes: list[str] = []
    # A healthy prior with an empty section means the user cleared it; only a
    # hollow or missing prior may fall back to the parsed resume.
    prior_is_authoritative = (
        prior_output is not None
        and any(_has_text(e.bullets) for e in prior_output.experience)
    )
    parsed_for_sections = None if prior_is_authoritative else resume_parsed

    def restore(label: str, field: str, *sources: Any) -> None:
        for source in sources:
            if source:
                updates[field] = source
                section_notes.append(_SECTION_NOTE.format(label=label))
                return

    if not _has_text(output.skills):
        restore(
            "Skills",
            "skills",
            list(prior_output.skills) if prior_output and _has_text(prior_output.skills) else [],
            list(parsed_for_sections.skills)
            if parsed_for_sections and _has_text(parsed_for_sections.skills)
            else [],
        )

    if not output.summary.strip():
        restore(
            "Summary",
            "summary",
            prior_output.summary.strip() if prior_output else "",
            (parsed_for_sections.summary or "").strip() if parsed_for_sections else "",
        )

    experience = list(output.experience)
    if not experience:
        prior_experience = (
            [e.model_copy(deep=True) for e in prior_output.experience]
            if prior_output
            else []
        )
        source = _first_non_empty(prior_experience, _parsed_experience(resume_parsed))
        if source:
            experience = source
            section_notes.append(_SECTION_NOTE.format(label="Experience"))
    experience, role_notes = _restore_empty_roles(experience, prior_output, resume_parsed)
    if experience != list(output.experience):
        updates["experience"] = experience

    if not output.education:
        restore(
            "Education",
            "education",
            [e.model_copy(deep=True) for e in prior_output.education] if prior_output else [],
            _parsed_education(parsed_for_sections),
        )

    if not output.projects:
        restore(
            "Projects",
            "projects",
            copy.deepcopy(list(prior_output.projects)) if prior_output else [],
            _parsed_projects(parsed_for_sections),
        )

    new_notes = [*section_notes, *role_notes]
    if not updates and not new_notes:
        return output

    notes = list(output.rewrite_notes)
    seen = {n.strip() for n in notes}
    for note in new_notes:
        if note.strip() not in seen:
            notes.append(note)
            seen.add(note.strip())
    updates["rewrite_notes"] = notes
    return output.model_copy(update=updates)


_MASTER_SECTION_KEYS: tuple[str, ...] = (
    "skills",
    "summary",
    "experience",
    "education",
    "projects",
    "certifications",
    "contact",
)


def _experience_has_bullets(parsed_sections: dict[str, Any]) -> bool:
    return any(
        _has_text(list(entry.get("bullets") or []))
        for entry in parsed_sections.get("experience") or []
        if isinstance(entry, dict)
    )


def is_degraded_master_write(
    incoming: dict[str, Any], existing: dict[str, Any] | None
) -> bool:
    """True when a tree with no experience bullets would replace stored bullets."""
    return (
        bool(existing)
        and not _experience_has_bullets(incoming)
        and _experience_has_bullets(existing or {})
    )


def _is_blank(value: Any) -> bool:
    if isinstance(value, str):
        return not value.strip()
    return not value


def preserve_master_sections(
    incoming: dict[str, Any], existing: dict[str, Any] | None
) -> dict[str, Any]:
    """Keep the stored master resume from being overwritten by a degraded tree.

    A tree that lost every experience bullet the stored resume had is
    structurally degraded, so blank sections fall back to what is stored. A tree
    with real experience, or a stored resume that never had any, is a deliberate
    edit and is persisted as-is, including intentional empties.
    """
    if existing is None or not is_degraded_master_write(incoming, existing):
        return incoming
    merged: dict[str, Any] = dict(incoming)
    for key in _MASTER_SECTION_KEYS:
        if _is_blank(merged.get(key)) and not _is_blank(existing.get(key)):
            merged[key] = existing[key]
    return merged


__all__: list[str] = [
    "enforce_resume_invariants",
    "is_degraded_master_write",
    "preserve_master_sections",
]
