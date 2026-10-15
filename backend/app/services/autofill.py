"""Autofill payload generation for the Flint browser extension."""

from __future__ import annotations

import uuid
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_description import JobDescription
from app.models.session import Session
from app.services.dashboard.session_cache import restore_session_from_record
from app.services.session_store import get_session

GREENHOUSE_FIELD_SELECTORS: dict[str, str] = {
    "first_name": "[name='job_application[first_name]']",
    "last_name": "[name='job_application[last_name]']",
    "email": "[name='job_application[email]']",
    "phone": "[name='job_application[phone]']",
    "resume": "[name='job_application[resume]']",
    "linkedin_url": "[name='job_application[urls][LinkedIn]']",
    "website_url": (
        "[name='job_application[urls][Website]'], "
        "[name='job_application[urls][Portfolio]']"
    ),
    "github_url": "[name='job_application[urls][GitHub]']",
    "work_authorization": "[name='job_application[answers][work_authorization]']",
}

RECENT_TAILORED_LIMIT = 20


def detect_platform(url: str | None) -> str:
    if not url:
        return "unknown"
    host = (urlparse(url).hostname or "").lower()
    if host.endswith("greenhouse.io"):
        return "greenhouse"
    if host.endswith("linkedin.com"):
        return "linkedin"
    if host.endswith("lever.co"):
        return "lever"
    if host.endswith("ashbyhq.com"):
        return "ashby"
    if host.endswith("myworkdayjobs.com") or host.endswith("myworkday.com"):
        return "workday"
    return "unknown"


def split_name(name: str) -> tuple[str, str]:
    cleaned = name.strip()
    if not cleaned:
        return "", ""
    parts = cleaned.split(None, 1)
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], parts[1]


def extract_contact(session: Session) -> dict[str, str]:
    if session.phase3_output and isinstance(session.phase3_output.contact, dict):
        return {str(k): str(v) for k, v in session.phase3_output.contact.items() if v}
    if session.resume_parsed and session.resume_parsed.contact:
        parsed = session.resume_parsed.contact.model_dump()
        return {str(k): str(v) for k, v in parsed.items() if v}
    if session.user_info:
        info = session.user_info.model_dump()
        return {str(k): str(v) for k, v in info.items() if v}
    return {}


def build_autofill_fields(contact: dict[str, str], platform: str) -> list[dict[str, str]]:
    # Only Greenhouse has known DOM selectors today; other platforms (linkedin,
    # unknown) still get concept-keyed fields so the extension can resolve
    # inputs via heuristics client-side.
    selectors = GREENHOUSE_FIELD_SELECTORS if platform == "greenhouse" else None

    first_name, last_name = split_name(str(contact.get("name") or ""))
    values: list[tuple[str, str]] = [
        ("first_name", first_name),
        ("last_name", last_name),
        ("email", str(contact.get("email") or "")),
        ("phone", str(contact.get("phone") or "")),
        ("linkedin_url", str(contact.get("linkedin") or "")),
        ("website_url", str(contact.get("website") or "")),
        ("github_url", str(contact.get("github") or "")),
    ]

    fields: list[dict[str, str]] = []
    for key, value in values:
        cleaned = value.strip()
        if not cleaned:
            continue
        fields.append(
            {
                "key": key,
                "selector": selectors[key] if selectors else "",
                "value": cleaned,
            }
        )

    # File inputs are surfaced for manual attachment — never claim they were filled.
    fields.append(
        {
            "key": "resume",
            "selector": selectors["resume"] if selectors else "",
            "value": "",
        }
    )
    return fields


def url_host(url: str | None) -> str:
    if not url:
        return ""
    return (urlparse(url).hostname or "").lower()


async def resolve_tailored_session(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    session_id: str,
) -> Session | None:
    """Tailored session from Redis, falling back to the durable dashboard snapshot.

    Redis sessions expire after SESSION_TTL_SECONDS, so autofill would otherwise
    stop working a day after tailoring even though the resume is still on file.
    """
    session = await get_session(session_id)
    if session is not None and session.phase3_output is not None:
        return session
    restored = await restore_session_from_record(
        db, session_id=session_id, user_id=user_id
    )
    if restored is None or restored.phase3_output is None:
        return None
    return restored


async def ensure_job_description_for_session(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    session_id: str,
    title: str,
    company: str,
    jd_text: str,
) -> JobDescription:
    """Return the JobDescription bound to this session, creating one if absent.

    Tailoring on the web never creates a row (only the extension's "Save job"
    does), but the extension can only fetch a payload by jd_id — so a row is the
    addressable handle. Idempotent, and never writes `url`: a web-tailored
    session has no posting URL here and a fabricated one would poison host
    matching in the extension's session picker.
    """
    existing = (
        await db.execute(
            select(JobDescription).where(
                JobDescription.user_id == user_id,
                JobDescription.session_id == session_id,
            )
        )
    ).scalars().first()
    if existing is not None:
        return existing

    row = JobDescription(
        user_id=user_id,
        url=None,
        title=title or None,
        company=company or None,
        text=jd_text or "",
        source="web",
        session_id=session_id,
    )
    db.add(row)
    # Commit stays owned by the get_db dependency; flush assigns row.id.
    await db.flush()
    return row
