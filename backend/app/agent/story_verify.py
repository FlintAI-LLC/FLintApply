"""Deterministic verification hints for story-generated resumes.

Compares spoken segment text against the generated resume draft so the
user can double-check names and dates before saving to their profile.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Literal

VerifyStatus = Literal["ok", "review"]

_EXPERIENCE_LINE = re.compile(
    r"^(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*$",
    re.MULTILINE,
)
_MONTH_YEAR = re.compile(
    r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
    r"\.?\s+\d{4}\b",
    re.IGNORECASE,
)
_YEAR_FULL = re.compile(r"\b(?:19|20)\d{2}\b")
_EMPLOYER_STOPLIST = frozenset(
    {
        "a",
        "about",
        "all",
        "and",
        "babysitting",
        "five",
        "for",
        "from",
        "home",
        "kids",
        "local",
        "my",
        "or",
        "programmer",
        "shops",
        "the",
        "tutor",
        "tutoring",
        "volunteering",
        "with",
        "your",
    }
)
_AT_COMPANY = re.compile(
    r"\b(?:at|for|from)\s+([A-Za-z][A-Za-z0-9&\-. ]{2,40}?)(?:\s+(?:since|from|in|I|we|they|that|there|where|when|and|or)\b|[,.]|$)",
    re.IGNORECASE,
)
_CALLED_COMPANY = re.compile(
    r"\bcalled\s+([A-Za-z][A-Za-z0-9&\-. ]{2,40}?)(?:\s+(?:in|I|it|that|there|where|and|or)\b|[,.]|$)",
    re.IGNORECASE,
)
_SCHOOL = re.compile(
    r"\b(University of [A-Za-z ]+|Portland Community College|[A-Za-z ]+ University)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class VerifyItem:
    field: str
    spoken: str
    resume: str
    status: VerifyStatus
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _tokens(text: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", _normalize(text)) if len(t) > 2}


def _names_match(spoken: str, resume: str) -> bool:
    s, r = _normalize(spoken), _normalize(resume)
    if s == r or s in r or r in s:
        return True
    s_tok, r_tok = _tokens(spoken), _tokens(resume)
    if not s_tok or not r_tok:
        return False
    overlap = len(s_tok & r_tok) / max(len(s_tok), len(r_tok))
    return overlap >= 0.6


def _extract_section_block(resume_text: str, header: str) -> str:
    upper = resume_text.upper()
    start = upper.find(header.upper())
    if start < 0:
        return ""
    end_candidates = [
        upper.find(h, start + len(header))
        for h in ("PROFESSIONAL SUMMARY", "SKILLS", "EXPERIENCE", "EDUCATION", "PROJECTS", "CERTIFICATIONS")
        if h != header.upper() and upper.find(h, start + len(header)) >= 0
    ]
    end = min(end_candidates) if end_candidates else len(resume_text)
    return resume_text[start:end]


def _extract_experience_block(resume_text: str) -> str:
    block = _extract_section_block(resume_text, "EXPERIENCE")
    return block if block else resume_text


def extract_resume_companies(resume_text: str) -> list[tuple[str, str, str]]:
    block = _extract_experience_block(resume_text)
    entries: list[tuple[str, str, str]] = []
    for line in block.splitlines():
        line = line.strip()
        if not line or line.upper() == "EXPERIENCE" or line.startswith("•"):
            continue
        m = _EXPERIENCE_LINE.match(line)
        if m:
            entries.append((m.group(1).strip(), m.group(2).strip(), m.group(3).strip()))
    return entries


def _is_plausible_employer(name: str) -> bool:
    key = _normalize(name)
    if len(key) < 3:
        return False
    tokens = [t for t in key.split() if t]
    if not tokens:
        return False
    if all(t in _EMPLOYER_STOPLIST for t in tokens):
        return False
    if tokens[0] in _EMPLOYER_STOPLIST and len(tokens) == 1:
        return False
    return True


def extract_spoken_companies(segments: list[str]) -> list[str]:
    text = " ".join(segments)
    found: list[str] = []
    seen: set[str] = set()
    for pattern in (_AT_COMPANY, _CALLED_COMPANY):
        for m in pattern.finditer(text):
            name = m.group(1).strip(" .,")
            key = _normalize(name)
            if len(key) < 3 or key in seen or not _is_plausible_employer(name):
                continue
            seen.add(key)
            found.append(name)
    for m in _SCHOOL.finditer(text):
        name = m.group(1).strip()
        key = _normalize(name)
        if key not in seen:
            seen.add(key)
            found.append(name)
    return found


def extract_spoken_date_phrases(segments: list[str]) -> list[str]:
    text = " ".join(segments)
    phrases: list[str] = []
    seen: set[str] = set()
    for m in _MONTH_YEAR.finditer(text):
        phrase = m.group(0)
        key = phrase.lower()
        if key not in seen:
            seen.add(key)
            phrases.append(phrase)
    for m in re.finditer(r"\b(summer|spring|fall|winter)\s+\d{4}\b", text, re.I):
        phrase = m.group(0)
        key = phrase.lower()
        if key not in seen:
            seen.add(key)
            phrases.append(phrase)
    for m in re.finditer(r"\b\d{4}\s*(?:to|–|-)\s*(?:\d{4}|present|now)\b", text, re.I):
        phrase = m.group(0)
        key = phrase.lower()
        if key not in seen:
            seen.add(key)
            phrases.append(phrase)
    return phrases


def extract_resume_date_phrases(resume_text: str) -> list[str]:
    block = _extract_experience_block(resume_text)
    phrases: list[str] = []
    seen: set[str] = set()
    for _, _, dates in extract_resume_companies(resume_text):
        key = dates.lower()
        if key not in seen:
            seen.add(key)
            phrases.append(dates)
    for m in _MONTH_YEAR.finditer(block):
        phrase = m.group(0)
        key = phrase.lower()
        if key not in seen:
            seen.add(key)
            phrases.append(phrase)
    for m in _YEAR_FULL.finditer(block):
        phrase = m.group(0)
        key = phrase.lower()
        if key not in seen and phrase not in phrases:
            seen.add(key)
            phrases.append(phrase)
    edu_block = _extract_section_block(resume_text, "EDUCATION")
    for m in _MONTH_YEAR.finditer(edu_block):
        phrase = m.group(0)
        key = phrase.lower()
        if key not in seen:
            seen.add(key)
            phrases.append(phrase)
    for m in _YEAR_FULL.finditer(edu_block):
        phrase = m.group(0)
        key = phrase.lower()
        if key not in seen:
            seen.add(key)
            phrases.append(phrase)
    return phrases


def _company_review_message(spoken: str, resume: str) -> str:
    if " " in resume and " " not in spoken.replace(" ", ""):
        pass
    s_words = spoken.split()
    r_words = resume.split()
    if len(s_words) >= 2 and len(r_words) >= 2:
        if s_words[0].lower() == r_words[0].lower() and s_words[-1].lower() == r_words[-1].lower():
            return "Speech may have split this name — confirm spelling (e.g. BrightCart vs Bright Card)."
    if _normalize(spoken) != _normalize(resume):
        return "Confirm employer or project name spelling matches your records."
    return "Review this name."


def _dates_related(spoken: str, resume: str) -> bool:
    if _names_match(spoken, resume) or spoken.lower() in resume.lower() or resume.lower() in spoken.lower():
        return True
    spoken_years = set(_YEAR_FULL.findall(spoken))
    resume_years = set(_YEAR_FULL.findall(resume))
    return bool(spoken_years & resume_years)


def _contact_line_present(resume_text: str, value: str) -> bool:
    if not value.strip():
        return True
    return value.strip().casefold() in resume_text.casefold()


def build_contact_verify_items(
    resume_text: str,
    *,
    profile_name: str | None = None,
    profile_email: str | None = None,
    profile_linkedin: str | None = None,
    profile_phone: str | None = None,
    profile_github: str | None = None,
    include_github: bool = False,
) -> list[VerifyItem]:
    items: list[VerifyItem] = []
    checks: list[tuple[str, str | None, str]] = [
        ("Contact — Name", profile_name, "Add your name at the top of the resume."),
        ("Contact — Email", profile_email, "Add your email in the contact header."),
        ("Contact — LinkedIn", profile_linkedin, "Add your LinkedIn URL in the contact header."),
        ("Contact — Phone", profile_phone, "Add your phone number if you want recruiters to call."),
    ]
    if include_github:
        checks.append(
            ("Contact — GitHub", profile_github, "Add your GitHub profile for technical roles."),
        )
    for field, profile_val, hint in checks:
        if not (profile_val or "").strip():
            continue
        present = _contact_line_present(resume_text, profile_val)
        items.append(
            VerifyItem(
                field=field,
                spoken=f"Profile: {profile_val.strip()}",
                resume=profile_val.strip() if present else "(not in resume header)",
                status="ok" if present else "review",
                message="Contact line present." if present else hint,
            )
        )
    if profile_name and not _contact_line_present(resume_text, profile_name):
        first = resume_text.strip().splitlines()[0] if resume_text.strip() else ""
        if first and not _contact_line_present(resume_text, profile_name):
            items.insert(
                0,
                VerifyItem(
                    field="Contact — Name",
                    spoken="(profile)",
                    resume=first[:80],
                    status="review",
                    message="Top line does not match your profile name — fix the header before saving.",
                ),
            )
    return items


def build_section_gap_items(segments: list[str], resume_text: str) -> list[VerifyItem]:
    from app.agent.story_completeness import completeness_warnings

    items: list[VerifyItem] = []
    narrative = " ".join(segments)
    for warning in completeness_warnings(narrative, resume_text):
        items.append(
            VerifyItem(
                field="Section completeness",
                spoken="(from your story)",
                resume="(draft)",
                status="review",
                message=warning,
            )
        )
    return items


def build_verify_items(
    segments: list[str],
    resume_text: str,
    *,
    profile_name: str | None = None,
    profile_email: str | None = None,
    profile_linkedin: str | None = None,
    profile_phone: str | None = None,
    profile_github: str | None = None,
    include_github: bool = False,
) -> list[VerifyItem]:
    items: list[VerifyItem] = []
    items.extend(
        build_contact_verify_items(
            resume_text,
            profile_name=profile_name,
            profile_email=profile_email,
            profile_linkedin=profile_linkedin,
            profile_phone=profile_phone,
            profile_github=profile_github,
            include_github=include_github,
        )
    )
    items.extend(build_section_gap_items(segments, resume_text))
    spoken_companies = extract_spoken_companies(segments)
    resume_entries = extract_resume_companies(resume_text)
    resume_companies = [c for c, _, _ in resume_entries]

    matched_resume: set[int] = set()
    for spoken in spoken_companies[:8]:
        best_idx = -1
        for i, resume_co in enumerate(resume_companies):
            if i in matched_resume:
                continue
            if _names_match(spoken, resume_co):
                best_idx = i
                break
        if best_idx >= 0:
            matched_resume.add(best_idx)
            resume_co = resume_companies[best_idx]
            if _normalize(spoken) == _normalize(resume_co):
                items.append(
                    VerifyItem(
                        field="Employer / organization",
                        spoken=spoken,
                        resume=resume_co,
                        status="ok",
                        message="Name matches your story.",
                    )
                )
            else:
                items.append(
                    VerifyItem(
                        field="Employer / organization",
                        spoken=spoken,
                        resume=resume_co,
                        status="review",
                        message=_company_review_message(spoken, resume_co),
                    )
                )
        else:
            items.append(
                VerifyItem(
                    field="Employer / organization",
                    spoken=spoken,
                    resume="(not found in resume)",
                    status="review",
                    message="Mentioned in your story but missing from Experience — add or remove.",
                )
            )

    for i, resume_co in enumerate(resume_companies):
        if i not in matched_resume:
            items.append(
                VerifyItem(
                    field="Employer / organization",
                    spoken="(not in story)",
                    resume=resume_co,
                    status="review",
                    message="In the resume but not clearly heard in your story — confirm it is correct.",
                )
            )

    spoken_dates = extract_spoken_date_phrases(segments)
    resume_dates = extract_resume_date_phrases(resume_text)
    for spoken_date in spoken_dates[:8]:
        matched = any(_dates_related(spoken_date, rd) for rd in resume_dates)
        if matched:
            resume_match = next(
                (rd for rd in resume_dates if _dates_related(spoken_date, rd)),
                spoken_date,
            )
            status: VerifyStatus = "ok"
            message = "Date aligns with your story."
            if re.search(r"\b(summer|spring|fall|winter)\b", spoken_date, re.I) and _MONTH_YEAR.search(resume_match):
                status = "review"
                message = "You said a season; resume uses a specific month — confirm the month is right."
            items.append(
                VerifyItem(
                    field="Dates",
                    spoken=spoken_date,
                    resume=resume_match,
                    status=status,
                    message=message,
                )
            )
        else:
            items.append(
                VerifyItem(
                    field="Dates",
                    spoken=spoken_date,
                    resume="(not matched)",
                    status="review",
                    message="Date from your story may be missing or changed in the resume.",
                )
            )

    return items
