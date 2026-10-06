"""Unit tests for story contact header helpers."""

from app.models.userinfo import UserInfo
from app.services.story_contact import (
    narrative_or_resume_is_tech,
    prepend_authoritative_contact_header,
    resume_starts_with_name,
)


def test_resume_starts_with_name() -> None:
    assert resume_starts_with_name("Ali Barzin\nPROFESSIONAL SUMMARY", "Ali Barzin")


def test_prepend_contact_when_name_missing() -> None:
    user = UserInfo(name="Ali Barzin", email="ali@example.com", phone="555-0100")
    draft = "PROFESSIONAL SUMMARY\nEngineer with cloud experience."
    out = prepend_authoritative_contact_header(
        draft,
        user_info=user,
        account_email="ali@example.com",
        narrative="I build APIs in Python.",
    )
    assert out.startswith("Ali Barzin")
    assert "ali@example.com" in out.splitlines()[1]


def test_narrative_or_resume_is_tech() -> None:
    assert narrative_or_resume_is_tech("I write React apps.", "")
    assert not narrative_or_resume_is_tech("I volunteer at the library.", "Volunteer role.")
