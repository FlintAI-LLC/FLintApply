"""Career Watch keyword suggestions prioritize experience role titles."""

from types import SimpleNamespace

from app.models.master_resume import MasterResumeSectionType
from app.services.career_watch.keyword_suggestions import suggest_keywords_from_chunks


def _chunk(section_type: MasterResumeSectionType, content: str, metadata: dict | None = None):
    return SimpleNamespace(
        section_type=section_type,
        content=content,
        chunk_metadata=metadata or {},
    )


def test_suggestions_prioritize_software_engineering_title_over_consulting_skills() -> None:
    chunks = [
        _chunk(
            MasterResumeSectionType.experience,
            "Built platform services.",
            {"title": "Senior AI Software Engineer"},
        ),
        _chunk(
            MasterResumeSectionType.experience,
            "Led identity work.",
            {"job_title": "Staff Software Engineer"},
        ),
        _chunk(
            MasterResumeSectionType.skills,
            "Integration, Platform Identity, Security, Agenting, Consultant, Kubernetes",
        ),
    ]
    keywords = suggest_keywords_from_chunks(chunks)
    assert "software engineer" in keywords or "ai software engineer" in keywords
    assert "senior ai software engineer" in keywords or "staff software engineer" in keywords
    assert keywords[0] in {
        "senior ai software engineer",
        "staff software engineer",
        "ai software engineer",
        "software engineer",
    }
    assert "consultant" not in keywords[:3]


def test_empty_chunks_returns_empty() -> None:
    assert suggest_keywords_from_chunks([]) == []
