"""Deterministic post-processing for Phase 3 tailored resume output.

LLM output is not always compliant with prompt rules (e.g. flat skills instead of
JobRight-style categories). These helpers enforce structure without touching UI
manual-edit flows.
"""

from __future__ import annotations

import re
from collections import defaultdict

from app.agent.phase3_invariants import enforce_resume_invariants
from app.agent.tone_lint import annotate_tone_alignment
from app.agent.tone_profile import JDToneProfile
from app.agent.phase3_truthfulness import TruthfulnessContext, apply_truthfulness_guards
from app.models.rewrite import TailoredExperienceEntry, TailoredResumeOutput

_CATEGORY_LINE_RE = re.compile(r"^([^:]+):\s*(.+)$")

# Order matters — most JD-relevant groups first when multiple rules match.
_CATEGORY_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "AI & Machine Learning",
        re.compile(
            r"\b(generative\s*ai|llm?s?|large\s+language|rag|retrieval-augmented|"
            r"nim|nemo|pytorch|tensorflow|machine\s+learning|deep\s+learning|"
            r"transformer|embedding|gpu|model\s+training|nlp)\b",
            re.I,
        ),
    ),
    (
        "Programming Languages & Frameworks",
        re.compile(
            r"\b(python|java|javascript|typescript|go\b|rust|c\+\+|c#|sql|"
            r"fastapi|django|flask|spring|node\.?js|rest\s*api|grpc)\b",
            re.I,
        ),
    ),
    (
        "Frontend & Mobile",
        re.compile(
            r"\b(react|react\s+native|vue|angular|svelte|next\.?js|swift|swiftui|"
            r"kotlin|flutter|android|ios|tailwind|redux)\b",
            re.I,
        ),
    ),
    (
        "Cloud & Architecture",
        re.compile(
            r"\b(aws|azure|gcp|cloud|microservices|serverless|saas|"
            r"cloud-native|distributed\s+systems|architecture)\b",
            re.I,
        ),
    ),
    (
        "DevOps & Infrastructure",
        re.compile(
            r"\b(kubernetes|docker|ci/?cd|mlops|terraform|ansible|jenkins|"
            r"helm|container|infrastructure|devops|pipeline|observability|"
            r"prometheus|grafana|opentelemetry)\b",
            re.I,
        ),
    ),
    (
        "Data Engineering",
        re.compile(
            r"\b(spark|kafka|airflow|etl|data\s+pipeline|warehouse|"
            r"snowflake|databricks|dbt|data\s+engineering|postgresql|mysql|"
            r"mongodb|redis|dynamodb)\b",
            re.I,
        ),
    ),
    (
        "Security & Identity",
        re.compile(
            r"\b(oauth|saml|identity|security|auth|iam|encryption|compliance)\b",
            re.I,
        ),
    ),
]

# Same-technology spellings. Used for category matching and evidence checks only;
# the user's own skill text is never rewritten.
_SKILL_SYNONYMS: dict[str, str] = {
    "k8s": "kubernetes",
    "postgres": "postgresql",
    "golang": "go",
    "node": "node.js",
    "nextjs": "next.js",
    "amazon web services": "aws",
}
# Ordinary English words: never accepted as evidence for a *different* spelling.
_AMBIGUOUS_SPELLINGS = frozenset({"go", "node"})

_FALLBACK_CATEGORY = "Engineering & Tools"
_MAX_CATEGORIES = 5
_MAX_SKILLS_PER_CATEGORY = 8
_CURRENT_ROLE_MAX_BULLETS = 5
_PRIOR_ROLE_MAX_BULLETS = 3
_PROJECT_MAX_BULLETS = 3
_MAX_SKILL_WORDS = 6


def is_category_skill_line(skill: str) -> bool:
    """True when skill follows ``Category: a, b, c`` format."""
    text = skill.strip()
    if not _CATEGORY_LINE_RE.match(text):
        return False
    _, items = text.split(":", 1)
    return bool(items.strip())


def skills_are_categorized(skills: list[str]) -> bool:
    if not skills:
        return True
    categorized = sum(1 for s in skills if is_category_skill_line(s))
    return categorized >= max(1, len(skills) // 2)


def flatten_skill_terms(skills: list[str]) -> list[str]:
    """Public version: expand "Category: a, b" lines into individual skill terms.

    Used by Phase 4 keyword detection. Unlike :func:`_flatten_skills` this
    keeps every term (no word-count filter) because callers only need
    substring-match coverage, not display-quality skills.
    """
    flat: list[str] = []
    seen: set[str] = set()
    for raw in skills or []:
        text = raw.strip()
        if not text:
            continue
        if is_category_skill_line(text):
            _, items = text.split(":", 1)
            for item in items.split(","):
                term = item.strip()
                key = term.lower()
                if term and key not in seen:
                    flat.append(term)
                    seen.add(key)
            continue
        key = text.lower()
        if key not in seen:
            flat.append(text)
            seen.add(key)
    return flat


def _flatten_skills(skills: list[str]) -> list[str]:
    """Expand category lines and drop sentence-style entries."""
    flat: list[str] = []
    seen: set[str] = set()
    for raw in skills:
        text = raw.strip()
        if not text:
            continue
        if is_category_skill_line(text):
            _, items = text.split(":", 1)
            for item in items.split(","):
                term = item.strip()
                key = term.lower()
                if term and key not in seen and len(term.split()) <= _MAX_SKILL_WORDS:
                    flat.append(term)
                    seen.add(key)
            continue
        if len(text.split()) > _MAX_SKILL_WORDS:
            continue
        key = text.lower()
        if key not in seen:
            flat.append(text)
            seen.add(key)
    return flat


def canonical_skill(term: str) -> str:
    """Lowercased canonical spelling for known same-technology synonyms."""
    key = term.strip().lower()
    return _SKILL_SYNONYMS.get(key, key)


def skill_spellings(term: str) -> frozenset[str]:
    """Spellings that count as evidence for ``term`` (its own plus safe synonyms)."""
    canon = canonical_skill(term)
    group = {canon, *(alias for alias, target in _SKILL_SYNONYMS.items() if target == canon)}
    return frozenset({term.strip().lower(), *(g for g in group if g not in _AMBIGUOUS_SPELLINGS)})


def _match_category(skill: str) -> str:
    text = canonical_skill(skill)
    for category, pattern in _CATEGORY_RULES:
        if pattern.search(text):
            return category
    return _FALLBACK_CATEGORY


def normalize_skills_to_categories(
    skills: list[str],
    must_have_keywords: list[str] | None = None,
) -> list[str]:
    """Group flat skills into JobRight-style category lines."""
    if skills_are_categorized(skills):
        return _trim_category_lines(skills)

    flat = _flatten_skills(skills)
    if not flat:
        return skills

    jd_text = " ".join(must_have_keywords or []).lower()
    buckets: dict[str, list[str]] = defaultdict(list)
    for skill in flat:
        category = _match_category(skill)
        if skill not in buckets[category]:
            buckets[category].append(skill)

    ordered_categories = _order_categories(buckets, jd_text)

    result: list[str] = []
    for cat in ordered_categories:
        items = buckets[cat][:_MAX_SKILLS_PER_CATEGORY]
        if items:
            result.append(f"{cat}: {', '.join(items)}")

    return result or skills


def _order_categories(buckets: dict[str, list[str]], jd_text: str) -> list[str]:
    """JD-relevant categories first; overflow beyond the line cap merges into the fallback.

    Skills are never silently dropped because a resume happens to span more than
    ``_MAX_CATEGORIES`` domains.
    """
    patterns = dict(_CATEGORY_RULES)
    named = [name for name, _ in _CATEGORY_RULES if name in buckets]

    def jd_rank(name: str) -> int:
        return 0 if jd_text and patterns[name].search(jd_text) else 1

    display = sorted(named, key=jd_rank)
    has_misc = _FALLBACK_CATEGORY in buckets
    if len(named) + int(has_misc) <= _MAX_CATEGORIES:
        return display + ([_FALLBACK_CATEGORY] if has_misc else [])

    rule_order = {name: i for i, name in enumerate(named)}
    keep = set(
        sorted(named, key=lambda n: (jd_rank(n), -len(buckets[n]), rule_order[n]))[
            : _MAX_CATEGORIES - 1
        ]
    )
    misc = list(buckets.get(_FALLBACK_CATEGORY, []))
    for name in display:
        if name in keep:
            continue
        misc.extend(skill for skill in buckets[name] if skill not in misc)
    buckets[_FALLBACK_CATEGORY] = misc
    return [name for name in display if name in keep] + [_FALLBACK_CATEGORY]


def _trim_category_lines(skills: list[str]) -> list[str]:
    trimmed: list[str] = []
    for line in skills[:_MAX_CATEGORIES]:
        if not is_category_skill_line(line):
            trimmed.append(line)
            continue
        name, items = line.split(":", 1)
        parts = [p.strip() for p in items.split(",") if p.strip()]
        trimmed.append(f"{name.strip()}: {', '.join(parts[:_MAX_SKILLS_PER_CATEGORY])}")
    return trimmed


def enforce_experience_bullet_limits(
    experience: list[TailoredExperienceEntry],
) -> list[TailoredExperienceEntry]:
    """Current role ≤5 bullets; prior roles ≤3."""
    if not experience:
        return experience

    updated: list[TailoredExperienceEntry] = []
    for idx, entry in enumerate(experience):
        limit = _CURRENT_ROLE_MAX_BULLETS if idx == 0 else _PRIOR_ROLE_MAX_BULLETS
        if len(entry.bullets) <= limit:
            updated.append(entry)
            continue
        trimmed = entry.model_copy(
            update={
                "bullets": entry.bullets[:limit],
                "removed_bullets": [
                    *entry.removed_bullets,
                    *entry.bullets[limit:],
                ],
            }
        )
        updated.append(trimmed)
    return updated


def enforce_project_bullet_limits(projects: list[dict]) -> list[dict]:
    """Each project ≤3 bullets."""
    updated: list[dict] = []
    for proj in projects:
        if not isinstance(proj, dict):
            updated.append(proj)
            continue
        bullets = proj.get("bullets") or []
        if not isinstance(bullets, list) or len(bullets) <= _PROJECT_MAX_BULLETS:
            updated.append(proj)
            continue
        copy = dict(proj)
        copy["bullets"] = bullets[:_PROJECT_MAX_BULLETS]
        updated.append(copy)
    return updated


def _apply_invariants(
    output: TailoredResumeOutput,
    truthfulness: TruthfulnessContext,
    must_have_keywords: list[str] | None,
) -> TailoredResumeOutput:
    had_skills = any(s.strip() for s in output.skills)
    restored = enforce_resume_invariants(
        output,
        resume_parsed=truthfulness.resume_parsed,
        prior_output=truthfulness.prior_output,
    )
    if had_skills or not restored.skills:
        return restored
    # Restored skills come back flat; group them like every other skills list.
    return restored.model_copy(
        update={
            "skills": normalize_skills_to_categories(restored.skills, must_have_keywords)
        }
    )


def postprocess_tailored_output(
    output: TailoredResumeOutput,
    must_have_keywords: list[str] | None = None,
    tone_profile: JDToneProfile | None = None,
    truthfulness: TruthfulnessContext | None = None,
    place_keywords: bool = True,
) -> TailoredResumeOutput:
    """Apply deterministic structure rules after LLM generation.

    ``tone_profile`` — when supplied and non-neutral — triggers a tone lint
    pass that appends non-mutating findings to ``rewrite_notes``. Bullets
    themselves are never rewritten here; auto-repair would just be
    fabrication pressure by another name.
    """
    skills = normalize_skills_to_categories(output.skills, must_have_keywords)
    experience = enforce_experience_bullet_limits(output.experience)
    projects = enforce_project_bullet_limits(output.projects)

    notes = list(output.rewrite_notes)
    if skills != output.skills and not any("skill categor" in n.lower() for n in notes):
        notes.append(
            "Skills grouped into JD-relevant categories for ATS readability "
            "(JobRight-style format)."
        )

    interim = output.model_copy(
        update={
            "skills": skills,
            "experience": experience,
            "projects": projects,
            "rewrite_notes": notes,
        }
    )

    if tone_profile is not None:
        interim = annotate_tone_alignment(interim, tone_profile)

    if truthfulness is not None:
        interim = apply_truthfulness_guards(interim, truthfulness)
        interim = _apply_invariants(interim, truthfulness, must_have_keywords)
        if place_keywords:
            # Deferred import: the placer builds on this module's skill helpers.
            from app.agent.phase3_keyword_placement import place_evidenced_keywords

            interim = place_evidenced_keywords(interim, must_have_keywords, truthfulness)

    return interim


__all__ = [
    "enforce_experience_bullet_limits",
    "enforce_project_bullet_limits",
    "flatten_skill_terms",
    "is_category_skill_line",
    "normalize_skills_to_categories",
    "postprocess_tailored_output",
    "skills_are_categorized",
]
