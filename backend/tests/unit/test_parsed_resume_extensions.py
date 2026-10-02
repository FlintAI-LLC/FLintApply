"""ParsedResume extended section models."""

from __future__ import annotations

from app.models.resume import (
    AwardEntry,
    LanguageEntry,
    ParsedResume,
    PublicationEntry,
    VolunteerEntry,
)


def test_parsed_resume_awards_volunteer_languages_publications() -> None:
    resume = ParsedResume(
        awards=[
            AwardEntry(
                title="Best Paper",
                issuer="ACM",
                date="2024",
                description="Distributed systems track.",
            )
        ],
        volunteer=[
            VolunteerEntry(
                organization="Code for Good",
                role="Mentor",
                dates="2023–2024",
            )
        ],
        languages=[LanguageEntry(language="English", proficiency="Native")],
        publications=[
            PublicationEntry(
                title="Scaling Event Pipelines",
                publisher="IEEE",
                url="https://example.com/paper",
            )
        ],
    )
    assert len(resume.awards) == 1
    assert resume.awards[0].title == "Best Paper"
    assert resume.volunteer[0].organization == "Code for Good"
    assert resume.languages[0].language == "English"
    assert resume.publications[0].publisher == "IEEE"
