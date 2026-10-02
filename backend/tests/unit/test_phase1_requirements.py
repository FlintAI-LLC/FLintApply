"""Phase 1 JD requirements extraction."""

from __future__ import annotations

from pathlib import Path

from app.agent.jd_requirements import extract_jd_requirements, merge_requirement_lists
from app.models.keywords import KeywordExtractionOutput
from tests.unit.test_jd_tone_profile import _CASUAL_SAAS_JD, _EXEC_FINANCE_JD


def test_extract_requirements_from_exec_jd() -> None:
    reqs = extract_jd_requirements(_EXEC_FINANCE_JD)
    assert len(reqs) >= 4
    joined = " ".join(reqs).lower()
    assert "quality engineering" in joined or "leadership" in joined


def test_extract_requirements_from_casual_jd() -> None:
    reqs = extract_jd_requirements(_CASUAL_SAAS_JD)
    assert len(reqs) >= 3
    assert any("react" in r.lower() or "ship" in r.lower() for r in reqs)


def test_merge_prefers_llm_and_dedupes() -> None:
    llm = ["Proficient in Python", "Proficient in Python"]
    merged = merge_requirement_lists(llm, "Required:\n- Proficient in Python\n- Kubernetes ops")
    assert merged[0] == "Proficient in Python"
    assert len(merged) == len({m.lower() for m in merged})


def test_keyword_output_defaults_requirements_empty() -> None:
    out = KeywordExtractionOutput()
    assert out.requirements == []


def test_requirements_stop_at_benefits_and_about_sections() -> None:
    jd = """
Required Qualifications:
- 5+ years of Python experience
- Strong communication skills

Benefits:
- Health insurance
- Unlimited PTO

About the company:
We are a fast growing startup changing how people work.
"""
    reqs = extract_jd_requirements(jd)
    joined = " ".join(reqs).lower()
    assert "python" in joined
    assert "health insurance" not in joined
    assert "fast growing startup" not in joined


def test_typical_fixture_jd_requirement_count_under_embedding_cap() -> None:
    """Average requirement count stays below MAX_REQUIREMENTS_FOR_EMBEDDING (no 4-layer gate)."""
    from app.services.retrieval.config import MAX_REQUIREMENTS_FOR_EMBEDDING

    fixture_dir = Path(__file__).parent.parent / "fixtures" / "tech_jds"
    counts: list[int] = []
    for path in fixture_dir.glob("*.txt"):
        body = path.read_text(encoding="utf-8")
        counts.append(len(extract_jd_requirements(body)))
    for jd in (_EXEC_FINANCE_JD, _CASUAL_SAAS_JD):
        counts.append(len(extract_jd_requirements(jd)))
    assert counts
    assert max(counts) <= MAX_REQUIREMENTS_FOR_EMBEDDING
