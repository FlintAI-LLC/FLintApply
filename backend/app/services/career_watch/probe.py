"""Live probe: fetch jobs from a careers URL before the user saves a watch."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import httpx
import structlog

from app.models.career_watch import CareerAtsType, WatchedCompany
from app.services.career_watch.fetch import is_gone_error
from app.services.career_watch.http_client import _RESOLVER_TIMEOUT, create_career_watch_client
from app.services.career_watch.job_filters import meaningful_jobs
from app.services.career_watch.registry import fetch_company_jobs
from app.services.career_watch.resolver import resolve_careers_board
log = structlog.get_logger("career_watch.probe")


class ProbeStatus(str, Enum):
    ok = "ok"
    warning = "warning"
    error = "error"


@dataclass(frozen=True, slots=True)
class CareersPageProbe:
    status: ProbeStatus
    job_count: int
    message: str


def _company_for_probe(
    *,
    input_url: str,
    detection_url: str,
    ats_type: CareerAtsType,
    board_token: str | None,
    company_name: str | None,
    canonical_poll_url: str | None,
) -> WatchedCompany:
    return WatchedCompany(
        name=company_name or "Company",
        slug="probe",
        careers_page_url=detection_url,
        canonical_poll_url=canonical_poll_url,
        ats_type=ats_type,
        ats_board_token=board_token,
    )


def _resolution_note(resolved: bool, ats: CareerAtsType) -> str:
    if not resolved:
        return ""
    label = ats.value.replace("_", " ").title()
    if ats == CareerAtsType.icims:
        label = "iCIMS"
    if ats == CareerAtsType.workday:
        label = "Workday"
    return f"This page redirects to {label} — resolved and will be monitored there. "


async def probe_careers_page(careers_page_url: str) -> CareersPageProbe:
    """Fetch jobs once; classify whether this URL is safe to watch."""
    resolution_prefix = ""
    try:
        async with create_career_watch_client(timeout=_RESOLVER_TIMEOUT) as client:
            resolution = await resolve_careers_board(careers_page_url, client=client)
            detection = resolution.detection
            canonical = (
                resolution.canonical_poll_url
                if resolution.resolved_away_from_input
                else None
            )
            if resolution.resolved_away_from_input:
                resolution_prefix = _resolution_note(True, detection.ats_type)
            company = _company_for_probe(
                input_url=careers_page_url,
                detection_url=detection.careers_page_url,
                ats_type=detection.ats_type,
                board_token=detection.board_token,
                company_name=detection.company_name,
                canonical_poll_url=canonical,
            )
            ats = company.ats_type
            jobs = await fetch_company_jobs(
                company,
                client=client,
                allow_headless=False,
                workday_max_jobs=20,
            )
    except httpx.HTTPStatusError as exc:
        if is_gone_error(exc) or exc.response.status_code in {404, 410}:
            return CareersPageProbe(
                status=ProbeStatus.error,
                job_count=0,
                message=(
                    "We could not load job listings from this URL (not found). "
                    "Use the company's official job board link — often Greenhouse, Lever, "
                    "Ashby, or Workday — not a marketing careers landing page."
                ),
            )
        return CareersPageProbe(
            status=ProbeStatus.error,
            job_count=0,
            message=f"Could not read this careers page (HTTP {exc.response.status_code}).",
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("career_watch_probe_failed", error=type(exc).__name__)
        return CareersPageProbe(
            status=ProbeStatus.error,
            job_count=0,
            message=(
                "Could not fetch job listings from this URL. "
                "Check the link and try the direct ATS board URL from the company's job search page."
            ),
        )

    meaningful = meaningful_jobs(ats, jobs)
    count = len(meaningful)

    if ats == CareerAtsType.generic_html:
        if count == 0:
            return CareersPageProbe(
                status=ProbeStatus.warning,
                job_count=0,
                message=(
                    resolution_prefix
                    + "This page loaded, but we could not find readable job postings (often JavaScript-only). "
                    "Open the company's job search, copy the URL from the address bar when listings show "
                    "(e.g. boards.greenhouse.io/company, jobs.lever.co/company), and paste that here."
                ),
            )
        return CareersPageProbe(
            status=ProbeStatus.ok,
            job_count=count,
            message=(
                resolution_prefix
                + f"Found {count} job listing(s) on this page (limited detail for generic sites)."
            ),
        )

    if count == 0:
        if ats == CareerAtsType.workday:
            # Workday career sites are frequently client-rendered (the job
            # list loads via XHR after page load), so a quick synchronous
            # fetch here often finds nothing even for a correct URL. The
            # background poll worker uses a headless-render fallback that
            # this live probe intentionally skips (cost/latency/abuse
            # surface), so warn rather than block — the recurring poll may
            # still find jobs even though this check could not confirm it.
            return CareersPageProbe(
                status=ProbeStatus.warning,
                job_count=0,
                message=(
                    resolution_prefix
                    + "Detected Workday, but we could not confirm open jobs with a quick check "
                    "(Workday job lists often load after the page renders). This will be "
                    "monitored and checked more thoroughly on the next scan — if nothing turns "
                    "up after that, double-check the URL."
                ),
            )
        return CareersPageProbe(
            status=ProbeStatus.error,
            job_count=0,
            message=(
                resolution_prefix
                + f"Detected {ats.value}, but no open jobs were returned. "
                "The board slug may be wrong — paste the full careers URL from your browser "
                "(example: https://boards.greenhouse.io/stripe)."
            ),
        )

    return CareersPageProbe(
        status=ProbeStatus.ok,
        job_count=count,
        message=(
            resolution_prefix + f"Found {count} open job(s). This URL looks good for monitoring."
        ),
    )


__all__ = ["CareersPageProbe", "ProbeStatus", "probe_careers_page"]
