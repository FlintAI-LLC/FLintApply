"""Evidence-gated must-have keyword placement for Phase 3 output.

Keywords are only ever added to the Skills section, and only when the
candidate's own source material already contains them. Bullets are never
rewritten, prefixed, or appended to: doing so corrupts the opening verb and
invents claims.
"""

from __future__ import annotations

import re

from app.agent.phase3_postprocess import (
    _match_category,
    flatten_skill_terms,
    is_category_skill_line,
    normalize_skills_to_categories,
    skill_spellings,
)
from app.agent.phase3_truthfulness import TruthfulnessContext
from app.models.resume import ParsedResume
from app.models.rewrite import TailoredResumeOutput

_UNEVIDENCED_NOTE_PREFIX = "Keywords not added (no evidence in your resume): "
_MAX_TERMS = 30
_MAX_TERM_CHARS = 60
_MAX_NOTE_TERMS = 10


def _evidence_pattern(term: str) -> re.Pattern[str]:
    """Match the term or a safe same-technology spelling (e.g. k8s for Kubernetes)."""
    alternatives = "|".join(re.escape(s) for s in sorted(skill_spellings(term)))
    return re.compile(rf"(?<!\w)(?:{alternatives})(?!\w)", re.IGNORECASE)


def _tailored_body_text(output: TailoredResumeOutput) -> list[str]:
    """Human-authored text only: never field names, notes, or injected-keyword lists."""
    parts: list[str] = [output.summary, *output.skills, *output.certifications]
    for entry in output.experience:
        parts.extend([entry.title, entry.company, *entry.bullets])
    for entry in output.education:
        parts.extend([entry.degree, entry.institution, *entry.bullets])
    for project in output.projects:
        parts.append(str(project.get("name") or ""))
        parts.extend(str(b) for b in project.get("bullets") or [])
    return parts


def _parsed_body_text(parsed: ParsedResume) -> list[str]:
    parts: list[str] = [parsed.summary or "", *parsed.skills, *parsed.certifications]
    parts.extend(str(v) for v in parsed.contact.model_dump().values() if v)
    for exp in parsed.experience:
        parts.extend([exp.title, exp.company, *exp.bullets])
    for proj in parsed.projects:
        parts.extend([proj.name, proj.description or "", *proj.bullets])
    for edu in parsed.education:
        parts.extend([edu.degree, edu.institution, edu.notes or ""])
    return parts


def _source_corpus(source: TruthfulnessContext) -> str:
    parts: list[str] = [source.resume_raw]
    if source.resume_parsed is not None:
        parts.extend(_parsed_body_text(source.resume_parsed))
    if source.prior_output is not None:
        parts.extend(_tailored_body_text(source.prior_output))
    parts.extend(source.user_claimed_keywords)
    parts.extend(m.metric for m in source.approved_metrics)
    return "\n".join(p for p in parts if p)


def _dedupe_terms(keywords: list[str]) -> list[str]:
    seen: set[str] = set()
    terms: list[str] = []
    for raw in keywords:
        term = raw.strip()
        key = term.lower()
        if (
            not term
            or key in seen
            or len(term) > _MAX_TERM_CHARS
            or re.search(r"[\d\r\n\t]", term)
        ):
            continue
        seen.add(key)
        terms.append(term)
        if len(terms) >= _MAX_TERMS:
            break
    return terms


def _append_without_caps(skills: list[str], terms: list[str]) -> list[str]:
    """Keep every existing line and add terms; used when category caps would drop one."""
    updated = list(skills)
    for term in terms:
        category = _match_category(term)
        for idx, line in enumerate(updated):
            if is_category_skill_line(line) and line.split(":", 1)[0].strip() == category:
                updated[idx] = f"{line.rstrip()}, {term}"
                break
        else:
            updated.append(f"{category}: {term}")
    return updated


def _add_terms(
    skills: list[str], to_add: list[str], must_have: list[str]
) -> list[str]:
    existing = flatten_skill_terms(skills)
    regrouped = normalize_skills_to_categories([*existing, *to_add], must_have)
    kept = {t.lower() for t in flatten_skill_terms(regrouped)}
    if all(t.lower() in kept for t in [*existing, *to_add]):
        return regrouped
    return _append_without_caps(skills, to_add)


def place_evidenced_keywords(
    output: TailoredResumeOutput,
    must_have: list[str] | None,
    source: TruthfulnessContext,
) -> TailoredResumeOutput:
    """Add evidenced, missing must-have keywords to Skills; idempotent."""
    terms = _dedupe_terms(must_have or [])
    if not terms:
        return output

    corpus = _source_corpus(source)
    skill_terms = {t.lower() for t in flatten_skill_terms(output.skills)}

    to_add: list[str] = []
    unevidenced: list[str] = []
    for term in terms:
        if term.lower() in skill_terms:
            continue
        if _evidence_pattern(term).search(corpus):
            to_add.append(term)
        else:
            unevidenced.append(term)

    notes = [n for n in output.rewrite_notes if not n.startswith(_UNEVIDENCED_NOTE_PREFIX)]
    if unevidenced:
        shown = unevidenced[:_MAX_NOTE_TERMS]
        extra = len(unevidenced) - len(shown)
        suffix = f" (+{extra} more)" if extra > 0 else ""
        notes.append(f"{_UNEVIDENCED_NOTE_PREFIX}{', '.join(shown)}{suffix}.")

    skills = _add_terms(output.skills, to_add, terms) if to_add else output.skills

    if skills == output.skills and notes == output.rewrite_notes:
        return output
    return output.model_copy(update={"skills": skills, "rewrite_notes": notes})


__all__ = ["place_evidenced_keywords"]
