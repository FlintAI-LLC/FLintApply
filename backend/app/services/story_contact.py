"""Contact header helpers for story-generated plain-text resumes."""

from __future__ import annotations

import re
from typing import Any

from app.services.contact_authority import authoritative_contact
from app.models.userinfo import UserInfo

_TECH_SIGNAL = re.compile(
    r"\b(software|engineer|developer|devops|frontend|backend|full[\s-]?stack|"
    r"python|javascript|typescript|react|kubernetes|ml|machine learning)\b",
    re.IGNORECASE,
)


def narrative_or_resume_is_tech(narrative: str, resume_text: str) -> bool:
    blob = f"{narrative}\n{resume_text}".casefold()
    return bool(_TECH_SIGNAL.search(blob))


def format_contact_header(contact: dict[str, Any], *, include_github: bool) -> str:
    lines: list[str] = []
    name = (contact.get("name") or "").strip()
    if name:
        lines.append(name)
    detail_parts: list[str] = []
    for key in ("email", "phone", "linkedin", "website"):
        val = (contact.get(key) or "").strip()
        if val:
            detail_parts.append(val)
    if include_github:
        gh = (contact.get("github") or "").strip()
        if gh:
            detail_parts.append(gh)
    if detail_parts:
        lines.append(" | ".join(detail_parts))
    return "\n".join(lines).strip()


def resume_starts_with_name(resume_text: str, name: str) -> bool:
    if not name.strip():
        return False
    first_line = resume_text.strip().splitlines()[0].strip().casefold()
    return name.strip().casefold() in first_line or first_line == name.strip().casefold()


def prepend_authoritative_contact_header(
    resume_text: str,
    *,
    user_info: UserInfo | None,
    account_email: str | None,
    narrative: str,
) -> str:
    """Prepend a contact block from profile when the draft omits one."""
    merged = authoritative_contact(
        {},
        user_info=user_info,
        account_email=account_email,
    )
    include_github = narrative_or_resume_is_tech(narrative, resume_text)
    header = format_contact_header(merged, include_github=include_github)
    if not header:
        return resume_text
    if merged.get("name") and resume_starts_with_name(resume_text, str(merged["name"])):
        return resume_text
    body = resume_text.strip()
    if body.upper().startswith("PROFESSIONAL SUMMARY"):
        return f"{header}\n\n{body}"
    return f"{header}\n\n{body}"
