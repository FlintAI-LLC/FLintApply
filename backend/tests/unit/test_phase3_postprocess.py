"""Unit tests for Phase 3 post-processing."""

from __future__ import annotations

from app.agent.phase3_postprocess import (
    enforce_experience_bullet_limits,
    enforce_project_bullet_limits,
    flatten_skill_terms,
    is_category_skill_line,
    normalize_skills_to_categories,
    postprocess_tailored_output,
    skills_are_categorized,
)
from app.models.rewrite import TailoredExperienceEntry, TailoredResumeOutput


def test_is_category_skill_line() -> None:
    assert is_category_skill_line("AI & ML: Python, LLMs, RAG")
    assert not is_category_skill_line("Python")
    assert not is_category_skill_line("Write production-quality code for teams")


def test_normalize_flat_skills_to_categories() -> None:
    flat = [
        "Python",
        "Generative AI",
        "LLMs",
        "RAG",
        "FastAPI",
        "Kubernetes",
        "Docker",
        "MLOps",
        "Backend Engineering",
    ]
    result = normalize_skills_to_categories(flat, must_have_keywords=["Generative AI", "LLMs"])
    assert skills_are_categorized(result)
    assert all(":" in line for line in result)
    assert any("AI" in line for line in result)
    assert any("Python" in line or "FastAPI" in line for line in result)


def test_normalize_preserves_existing_categories() -> None:
    categorized = [
        "AI & Machine Learning: LLMs, RAG",
        "DevOps: Kubernetes, Docker",
    ]
    assert normalize_skills_to_categories(categorized) == categorized


def test_enforce_experience_bullet_limits() -> None:
    experience = [
        TailoredExperienceEntry(company="Current", bullets=[f"b{i}" for i in range(7)]),
        TailoredExperienceEntry(company="Prior", bullets=[f"p{i}" for i in range(5)]),
    ]
    trimmed = enforce_experience_bullet_limits(experience)
    assert len(trimmed[0].bullets) == 5
    assert len(trimmed[1].bullets) == 3
    assert len(trimmed[0].removed_bullets) == 2


def test_enforce_project_bullet_limits() -> None:
    projects = [{"name": "P1", "bullets": ["a", "b", "c", "d"]}]
    trimmed = enforce_project_bullet_limits(projects)
    assert len(trimmed[0]["bullets"]) == 3


def test_flatten_skill_terms_handles_categories_and_flat() -> None:
    skills = [
        "AI & Machine Learning: Python, LLMs, RAG",
        "DevOps: Kubernetes",
        "Standalone Skill",
    ]
    flat = flatten_skill_terms(skills)
    assert flat == ["Python", "LLMs", "RAG", "Kubernetes", "Standalone Skill"]


def test_flatten_skill_terms_dedupes_case_insensitive() -> None:
    skills = ["AI: Python, LLMs", "ML: python, RAG"]
    flat = flatten_skill_terms(skills)
    assert [t.lower() for t in flat] == ["python", "llms", "rag"]


def test_postprocess_tailored_output_integration() -> None:
    output = TailoredResumeOutput(
        skills=["Python", "LLMs", "Kubernetes"],
        experience=[
            TailoredExperienceEntry(company="Acme", bullets=["b1", "b2", "b3", "b4", "b5", "b6"]),
        ],
        projects=[{"name": "Proj", "bullets": ["x", "y", "z", "w"]}],
    )
    processed = postprocess_tailored_output(output, must_have_keywords=["LLMs"])
    assert skills_are_categorized(processed.skills)
    assert len(processed.experience[0].bullets) == 5
    assert len(processed.projects[0]["bullets"]) == 3


import pytest

from app.agent.phase3_postprocess import _match_category, canonical_skill

_TYPICAL_TECH_SKILLS = [
    "Python", "Go", "TypeScript", "React", "Node.js", "PostgreSQL", "Redis",
    "AWS", "Docker", "Kubernetes", "Terraform", "Kafka", "Spark", "OAuth",
    "PyTorch", "Excel", "Communication", "Figma",
]


def _category_names(lines: list[str]) -> list[str]:
    return [line.split(":", 1)[0] for line in lines]


def test_jd_boost_does_not_push_unrelated_skills_into_cloud() -> None:
    skills = ["Python", "Excel", "Figma", "Communication", "Docker"]
    result = normalize_skills_to_categories(skills, must_have_keywords=["AWS", "Kubernetes"])
    by_name = {line.split(":", 1)[0]: line.split(":", 1)[1] for line in result}
    misc = by_name["Engineering & Tools"]
    for unrelated in ("Excel", "Figma", "Communication"):
        assert unrelated in misc
        assert unrelated not in by_name.get("Cloud & Architecture", "")


def test_unmatched_skills_stay_in_fallback_without_any_jd_keywords() -> None:
    result = normalize_skills_to_categories(["Python", "Excel", "Docker"], must_have_keywords=None)
    assert any(line.startswith("Engineering & Tools:") and "Excel" in line for line in result)


@pytest.mark.parametrize(
    "must_have",
    [None, [], ["AWS"], ["Kubernetes", "Terraform"], ["LLMs", "PyTorch", "RAG"], ["React", "GraphQL"]],
)
def test_typical_tech_resume_yields_three_to_five_lines(must_have: list[str] | None) -> None:
    result = normalize_skills_to_categories(list(_TYPICAL_TECH_SKILLS), must_have_keywords=must_have)
    names = _category_names(result)
    assert 3 <= len(result) <= 5, names
    assert len(set(names)) == len(names)


def test_overflow_categories_never_silently_drop_skills() -> None:
    result = normalize_skills_to_categories(list(_TYPICAL_TECH_SKILLS))
    kept = {t.lower() for t in flatten_skill_terms(result)}
    assert {s.lower() for s in _TYPICAL_TECH_SKILLS} <= kept


def test_categories_matching_the_jd_are_ordered_first() -> None:
    skills = ["Python", "AWS", "Docker", "Kafka"]
    result = normalize_skills_to_categories(skills, must_have_keywords=["Kafka", "Spark"])
    assert _category_names(result)[0] == "Data Engineering"
    plain = normalize_skills_to_categories(skills)
    assert _category_names(plain)[0] == "Programming Languages & Frameworks"


@pytest.mark.parametrize(
    ("skill", "category"),
    [
        ("React", "Frontend & Mobile"),
        ("React Native", "Frontend & Mobile"),
        ("Vue", "Frontend & Mobile"),
        ("Swift", "Frontend & Mobile"),
        ("Kotlin", "Frontend & Mobile"),
        ("Next.js", "Frontend & Mobile"),
        ("Prometheus", "DevOps & Infrastructure"),
        ("Observability", "DevOps & Infrastructure"),
        ("gRPC", "Programming Languages & Frameworks"),
        ("PostgreSQL", "Data Engineering"),
        ("Python", "Programming Languages & Frameworks"),
        ("Excel", "Engineering & Tools"),
    ],
)
def test_category_rules(skill: str, category: str) -> None:
    assert _match_category(skill) == category


@pytest.mark.parametrize(
    ("alias", "category"),
    [
        ("k8s", "DevOps & Infrastructure"),
        ("postgres", "Data Engineering"),
        ("golang", "Programming Languages & Frameworks"),
        ("nextjs", "Frontend & Mobile"),
        ("amazon web services", "Cloud & Architecture"),
        ("Node", "Programming Languages & Frameworks"),
    ],
)
def test_skill_synonyms_resolve_before_category_matching(alias: str, category: str) -> None:
    assert _match_category(alias) == category


def test_canonical_skill_maps_only_known_synonyms() -> None:
    assert canonical_skill("K8s") == "kubernetes"
    assert canonical_skill(" Amazon Web Services ") == "aws"
    assert canonical_skill("Rust") == "rust"


def test_synonym_matching_does_not_rewrite_the_users_skill_text() -> None:
    result = normalize_skills_to_categories(["k8s", "golang", "Python"])
    flat = flatten_skill_terms(result)
    assert "k8s" in flat and "golang" in flat
    assert "kubernetes" not in [t.lower() for t in flat]
