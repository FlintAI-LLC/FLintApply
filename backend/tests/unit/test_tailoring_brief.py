"""Unit tests for assemble_tailoring_ingredients (P1 slice 3)."""

from __future__ import annotations

from app.agent.brief import assemble_tailoring_ingredients
from app.models.keywords import Keyword, KeywordExtractionOutput
from app.models.resume import EducationEntry, ExperienceEntry, ParsedResume
from app.services.retrieval import config as retrieval_cfg
from app.services.retrieval.retrieval_service import RetrievalResult, SelectedChunk, SkippedChunk


def _chunk(
    chunk_id: str,
    section: str,
    score: float,
    content: str,
    company: str | None = None,
) -> SelectedChunk:
    meta = {"company": company} if company else {}
    return SelectedChunk(
        chunk_id=chunk_id,
        section=section,
        score=score,
        tokens=10,
        content=content,
        metadata=meta,
    )


def _parsed_three_roles() -> ParsedResume:
    return ParsedResume(
        experience=[
            ExperienceEntry(company="Gamma", title="Staff", dates="2024", bullets=["Python APIs"]),
            ExperienceEntry(company="Beta", title="Sr", dates="2022", bullets=["microservices"]),
            ExperienceEntry(company="Acme", title="Eng", dates="2018", bullets=["Java"]),
        ],
        education=[EducationEntry(degree="BS", institution="State", year="2018")],
    )


def test_keyword_ownership_one_section_per_keyword() -> None:
    phase1 = KeywordExtractionOutput(
        must_have_keywords=[
            Keyword(
                term="Python",
                source_sentence="",
                category="language",
                tier="must_have",
                reason="",
            ),
            Keyword(
                term="microservices",
                source_sentence="",
                category="domain",
                tier="must_have",
                reason="",
            ),
        ]
    )
    result = RetrievalResult(
        selected=[
            _chunk("s1", "skills", 0.9, "Languages: Python, Go", None),
            _chunk("e1", "experience", 0.85, "Built microservices on Beta", "Beta"),
            _chunk("e2", "experience", 0.8, "Legacy Java monolith", "Acme"),
        ]
    )
    brief = assemble_tailoring_ingredients(result, phase1, _parsed_three_roles(), 1)
    owners: dict[str, str] = {}
    for section in brief.sections:
        for kw in section.must_place_keywords:
            owners[kw.lower()] = section.section_type
    assert owners["python"] == "skills"
    assert owners["microservices"].startswith("experience:")
    assert len(owners) == 2


def test_role_with_no_chunks_above_threshold_still_in_brief_cap_one() -> None:
    thr = retrieval_cfg.RETRIEVAL_PRIMARY_THRESHOLD
    low_score = thr - 0.05
    phase1 = KeywordExtractionOutput()
    parsed = ParsedResume(
        experience=[
            ExperienceEntry(company="Acme", title="Eng", dates="2020", bullets=["Did work"]),
        ]
    )
    result = RetrievalResult(
        selected=[],
        skipped=[
            SkippedChunk(
                chunk_id="low",
                section="experience",
                score=low_score,
                reason="below_threshold",
                content="Acme legacy bullet text",
            )
        ],
    )
    brief = assemble_tailoring_ingredients(result, phase1, parsed, 1)
    exp_sections = [s for s in brief.sections if s.section_type.startswith("experience:")]
    assert len(exp_sections) == 1
    assert exp_sections[0].bullet_cap >= 1
    assert len(exp_sections[0].chunks) == 1


def test_education_zero_score_always_include() -> None:
    phase1 = KeywordExtractionOutput()
    parsed = ParsedResume(
        education=[EducationEntry(degree="BS", institution="State", year="2018")]
    )
    result = RetrievalResult(
        selected=[
            _chunk("edu", "education", 0.0, "State University — BS 2018", None),
        ]
    )
    brief = assemble_tailoring_ingredients(result, phase1, parsed, 1)
    edu = next(s for s in brief.sections if s.section_type == "education")
    assert edu.always_include is True


def test_token_budget_trims_lowest_scored_chunks_first() -> None:
    phase1 = KeywordExtractionOutput()
    parsed = ParsedResume(
        experience=[ExperienceEntry(company="Acme", title="Eng", dates="2020", bullets=["x"])]
    )
    big = "word " * 800
    result = RetrievalResult(
        selected=[
            _chunk("high", "experience", 0.95, big, "Acme"),
            _chunk("low", "experience", 0.5, big, "Acme"),
        ]
    )
    brief = assemble_tailoring_ingredients(result, phase1, parsed, 1)
    exp = next(s for s in brief.sections if s.section_type.startswith("experience:"))
    ids = {c.chunk_id for c in exp.chunks}
    assert "high" in ids
    assert "low" not in ids
