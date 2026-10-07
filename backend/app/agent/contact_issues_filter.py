"""Filter false-positive Phase 2 contact_issues from the LLM auditor."""

from __future__ import annotations

import re

# LLM phrasing for name↔email local-part mismatch (over-applied quality rule).
_NAME_MISMATCH_RE = re.compile(
    r"local part|does not match|full[- ]name professional|"
    r"name[- ]based email|professional name-based|"
    r"ali\.barzin@|name mismatch",
    re.IGNORECASE,
)

# PDF/header formatting — not ATS contact blockers.
_FORMATTING_RE = re.compile(
    r"labeled with ['\"]email|clickable url|plain text labels|"
    r"without urls|full clickable",
    re.IGNORECASE,
)

_UNPROFESSIONAL_LOCAL_RE = re.compile(
    r"^\d+$|^(kitty|cool|sexy|boss|hacker|ninja|guru|dev\d+)",
    re.IGNORECASE,
)


def _name_tokens(name: str) -> list[str]:
    return [t for t in re.split(r"[\s.\-_]+", name.strip().lower()) if len(t) >= 2]


def _local_part(email: str) -> str:
    addr = (email or "").strip().lower()
    if "@" not in addr:
        return addr
    return addr.split("@", 1)[0]


def _local_part_matches_name(local: str, name: str) -> bool:
    """True when local part reasonably matches any token in the display name."""
    if not local or not name:
        return False
    local = local.lower()
    tokens = _name_tokens(name)
    if local in tokens:
        return True
    for token in tokens:
        if len(token) >= 3 and (local.startswith(token) or token.startswith(local)):
            return True
        if len(token) >= 3 and token in local:
            return True
    full = name.strip().lower().replace(" ", "")
    if len(local) >= 3 and local in full:
        return True
    return False


def _is_clearly_unprofessional_local(local: str) -> bool:
    if not local or len(local) < 2:
        return True
    if _UNPROFESSIONAL_LOCAL_RE.search(local):
        return True
    digits = sum(1 for c in local if c.isdigit())
    return digits > len(local) // 2


def filter_contact_issues(
    issues: list[str],
    *,
    resume_name: str | None = None,
    contact_email: str | None = None,
) -> list[str]:
    """Drop LLM false positives; keep real nickname/joke email warnings."""
    kept: list[str] = []
    local = _local_part(contact_email or "")
    name = (resume_name or "").strip()

    for issue in issues:
        text = (issue or "").strip()
        if not text:
            continue

        if _FORMATTING_RE.search(text):
            continue

        if _NAME_MISMATCH_RE.search(text) and local and name:
            if _local_part_matches_name(local, name):
                continue
            if not _is_clearly_unprofessional_local(local) and "." in local:
                continue
            if not _is_clearly_unprofessional_local(local) and "@" in (contact_email or ""):
                domain = (contact_email or "").split("@", 1)[-1].lower()
                if domain and domain not in ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com"):
                    continue

        kept.append(text)

    return kept


def should_drop_contact_export_item(
    text: str,
    *,
    resume_name: str | None = None,
    contact_email: str | None = None,
) -> bool:
    """True when Phase 4 export QA should not block on email-name mismatch."""
    issue = (text or "").strip()
    if not issue:
        return True
    if _FORMATTING_RE.search(issue):
        return True
    if _NAME_MISMATCH_RE.search(issue) and contact_email:
        local = _local_part(contact_email)
        name = (resume_name or "").strip()
        if local and name:
            if _local_part_matches_name(local, name):
                return True
            if not _is_clearly_unprofessional_local(local):
                domain = contact_email.split("@", 1)[-1].lower()
                if domain and domain not in (
                    "gmail.com",
                    "yahoo.com",
                    "hotmail.com",
                    "outlook.com",
                ):
                    return True
    return False


def filter_contact_export_strings(
    items: list[str],
    *,
    resume_name: str | None = None,
    contact_email: str | None = None,
) -> list[str]:
    return [
        item
        for item in items
        if not should_drop_contact_export_item(
            item,
            resume_name=resume_name,
            contact_email=contact_email,
        )
    ]
