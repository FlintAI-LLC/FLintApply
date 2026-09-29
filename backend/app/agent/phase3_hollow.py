"""Phase 3 hollow-output detection for structured LLM retries."""

from __future__ import annotations

from collections.abc import Callable

from pydantic import BaseModel

from app.models.resume import ParsedResume
from app.models.rewrite import TailoredResumeOutput

_BASE_HOLLOW_MESSAGE = (
    "Response is hollow: include experience entries with rewritten bullets. "
    "Each entry needs company, title, dates, and at least one bullet."
)
_MISSING_SECTIONS_MESSAGE = (
    "Response omitted sections present in the source resume: include a non-empty "
    "skills list and a professional summary alongside the experience entries."
)


def phase3_total_bullets(output: TailoredResumeOutput) -> int:
    return sum(len(e.bullets) for e in output.experience)


def phase3_drops_source_sections(
    output: TailoredResumeOutput, source: ParsedResume
) -> bool:
    """True when the source had skills or a summary that the output lost."""
    lost_skills = any(s.strip() for s in source.skills) and not any(
        s.strip() for s in output.skills
    )
    lost_summary = bool((source.summary or "").strip()) and not output.summary.strip()
    return lost_skills or lost_summary


def phase3_is_hollow(
    output: TailoredResumeOutput, *, source: ParsedResume | None = None
) -> bool:
    """Hollow means unusable as a tailored resume.

    Without ``source`` only the experience tree is checked. With ``source`` the
    output is also hollow when it dropped skills or a summary the source had.
    """
    if not output.experience:
        return True
    if phase3_total_bullets(output) == 0:
        return True
    return source is not None and phase3_drops_source_sections(output, source)


def make_hollow_rejector(
    source: ParsedResume | None = None,
) -> Callable[[BaseModel], str | None]:
    def _reject(output: BaseModel) -> str | None:
        if not isinstance(output, TailoredResumeOutput):
            return None
        if phase3_is_hollow(output):
            return _BASE_HOLLOW_MESSAGE
        if source is not None and phase3_drops_source_sections(output, source):
            return _MISSING_SECTIONS_MESSAGE
        return None

    return _reject


def reject_hollow_phase3(output: BaseModel) -> str | None:
    return make_hollow_rejector()(output)


__all__ = [
    "make_hollow_rejector",
    "phase3_drops_source_sections",
    "phase3_is_hollow",
    "phase3_total_bullets",
    "reject_hollow_phase3",
]
