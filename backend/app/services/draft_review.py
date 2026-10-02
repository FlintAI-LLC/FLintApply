"""Draft review payload for pre-export review gate."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any

from app.agent.output_linter import lint_bullets
from app.agent.phase3_multipass import bullet_id_for
from app.models.rewrite import TailoredResumeOutput
from app.services.master_resume.embedding import embed_texts

_CHARS_PER_PAGE = 3000
_DUPLICATE_THRESHOLD = 0.85

# Per-process cache: (session_id, phase3_hash) -> bullet embedding vectors.
_embed_cache: dict[tuple[str, str], list[list[float]]] = {}


def _phase3_output_hash(output: TailoredResumeOutput) -> str:
    payload = json.dumps(output.model_dump(mode="json"), sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _collect_bullets(output: TailoredResumeOutput) -> list[dict[str, Any]]:
    bullets: list[dict[str, Any]] = []
    brick_ids = list(output.source_brick_ids or [])
    for ei, exp in enumerate(output.experience):
        for bi, text in enumerate(exp.bullets):
            bullets.append(
                {
                    "id": bullet_id_for("experience", ei, bi),
                    "section": "experience",
                    "text": text,
                    "source_brick_ids": brick_ids,
                    "rewrite_notes": "",
                    "lint_issues": [],
                }
            )
    for pi, proj in enumerate(output.projects):
        if not isinstance(proj, dict):
            continue
        for bi, text in enumerate(proj.get("bullets") or []):
            bullets.append(
                {
                    "id": bullet_id_for("projects", pi, bi),
                    "section": "projects",
                    "text": str(text),
                    "source_brick_ids": brick_ids,
                    "rewrite_notes": "",
                    "lint_issues": [],
                }
            )
    return bullets


async def _embed_bullets_for_review(
    session_id: str | None,
    output: TailoredResumeOutput,
    texts: list[str],
) -> list[list[float]]:
    if len(texts) < 2:
        return []
    if session_id:
        key = (session_id, _phase3_output_hash(output))
        cached = _embed_cache.get(key)
        if cached is not None and len(cached) == len(texts):
            return cached
        vectors = await embed_texts(texts)
        _embed_cache[key] = vectors
        return vectors
    return await embed_texts(texts)


async def build_draft_review(
    output: TailoredResumeOutput,
    *,
    session_id: str | None = None,
    jd_text: str,
    must_have: list[str],
    target_pages: float = 1.0,
) -> dict[str, Any]:
    bullets = _collect_bullets(output)
    flat_bullet_texts = [b["text"] for b in bullets]
    lint_issues = lint_bullets(flat_bullet_texts, list(output.skills or []), jd_text)
    for issue in lint_issues:
        if issue.field == "bullets" and issue.index < len(bullets):
            bullets[issue.index]["lint_issues"].append(
                {
                    "rule": issue.rule,
                    "original": issue.original[:200],
                }
            )

    notes_blob = " ".join(output.rewrite_notes or [])
    for b in bullets:
        if notes_blob:
            b["rewrite_notes"] = notes_blob[:500]

    texts = [b["text"] for b in bullets]
    vectors = await _embed_bullets_for_review(session_id, output, texts)

    duplicates: list[dict[str, Any]] = []
    for i in range(len(vectors)):
        for j in range(i + 1, len(vectors)):
            sim = _cosine(vectors[i], vectors[j])
            if sim > _DUPLICATE_THRESHOLD:
                duplicates.append(
                    {
                        "bullet_id_a": bullets[i]["id"],
                        "bullet_id_b": bullets[j]["id"],
                        "similarity": round(sim, 4),
                    }
                )

    must_set = [k for k in must_have if k.strip()]
    haystack = (output.summary or "").lower()
    covered = [
        k
        for k in must_set
        if k.lower() in haystack
        or any(k.lower() in (b["text"] or "").lower() for b in bullets)
    ]
    missing = [k for k in must_set if k not in covered]

    char_count = sum(len(b["text"] or "") for b in bullets)
    pages = round(char_count / _CHARS_PER_PAGE, 2)

    return {
        "bullets": bullets,
        "skills": list(output.skills or []),
        "duplicate_candidates": duplicates,
        "keyword_coverage": {
            "must_have": must_set,
            "covered": covered,
            "missing": missing,
        },
        "length_estimate": {
            "pages": pages,
            "within_target": pages <= target_pages + 0.15,
        },
    }


def remove_bullet_from_output(
    output: TailoredResumeOutput, bullet_id: str
) -> TailoredResumeOutput:
    from app.agent.phase3_multipass import parse_bullet_id

    parsed = parse_bullet_id(bullet_id)
    if parsed is None:
        return output
    section, entry_idx, bullet_idx = parsed
    result = output.model_copy(deep=True)
    if section == "experience" and entry_idx < len(result.experience):
        exp = result.experience[entry_idx]
        if bullet_idx < len(exp.bullets):
            new_bullets = [
                b for i, b in enumerate(exp.bullets) if i != bullet_idx
            ]
            result.experience[entry_idx] = exp.model_copy(
                update={"bullets": new_bullets}
            )
    elif section == "projects" and entry_idx < len(result.projects):
        proj = dict(result.projects[entry_idx])
        bullets = list(proj.get("bullets") or [])
        if bullet_idx < len(bullets):
            proj["bullets"] = [b for i, b in enumerate(bullets) if i != bullet_idx]
            result.projects[entry_idx] = proj
    return result
