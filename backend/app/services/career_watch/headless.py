"""Headless render fallback for JS-only career pages (poll worker only).

Uses Playwright Chromium with SSRF re-checks before navigation. Never invoked
from live user API requests — only from the recurring poll path.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

import structlog

from app.models.career_watch import CareerAtsType, WatchedCompany
from app.services.career_watch.fetch import CAREER_WATCH_USER_AGENT
from app.services.career_watch.generic_html import parse_jsonld_job_postings
from app.services.career_watch.icims import parse_icims_html
from app.services.career_watch.job_filters import meaningful_jobs
from app.services.career_watch.ssrf_guard import assert_url_safe_async, CareerWatchSsrfError
from app.services.career_watch.types import ParsedJob

log = structlog.get_logger("career_watch.headless")

_PAGE_TIMEOUT_MS = 15_000
_COMPANY_BUDGET_SECONDS = 25.0
_BLOCKED_SCHEMES = frozenset({"file", "data", "javascript"})
_HEADLESS_CONCURRENCY = 2


class HeadlessBrowser(Protocol):
    async def render_html(self, url: str, *, user_agent: str, timeout_ms: int) -> str: ...


@dataclass
class _PlaywrightBrowser:
    """Thin wrapper so tests can replace Playwright entrypoints."""

    async def render_html(self, url: str, *, user_agent: str, timeout_ms: int) -> str:
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=True,
                args=["--disable-dev-shm-usage"],
            )
            try:
                context = await browser.new_context(
                    user_agent=user_agent,
                    accept_downloads=False,
                    java_script_enabled=True,
                    permissions=[],
                )
                context.set_default_navigation_timeout(timeout_ms)
                context.set_default_timeout(timeout_ms)

                async def _block_bad_route(route, request) -> None:
                    scheme = urlparse(request.url).scheme.lower()
                    if scheme in _BLOCKED_SCHEMES:
                        await route.abort()
                        return
                    try:
                        await assert_url_safe_async(request.url)
                    except CareerWatchSsrfError:
                        await route.abort()
                        return
                    await route.continue_()

                await context.route("**/*", _block_bad_route)
                page = await context.new_page()

                async def _dismiss_dialog(dialog) -> None:
                    await dialog.dismiss()

                page.on("dialog", _dismiss_dialog)

                await assert_url_safe_async(url)
                await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                content = await page.content()
                return content[:2_000_000]
            finally:
                await browser.close()


_headless_semaphore = asyncio.Semaphore(_HEADLESS_CONCURRENCY)
_default_browser = _PlaywrightBrowser()


def _extract_rendered_jobs(
    html: str,
    *,
    base_url: str,
    ats_type: CareerAtsType,
) -> list[ParsedJob]:
    jobs = parse_jsonld_job_postings(html, base_url=base_url)
    if jobs:
        return jobs
    if ats_type == CareerAtsType.icims:
        icims_jobs = parse_icims_html(html, base_url=base_url)
        if icims_jobs:
            return icims_jobs
    return parse_icims_html(html, base_url=base_url)


async def fetch_jobs_headless(
    company: WatchedCompany,
    *,
    browser: HeadlessBrowser | None = None,
) -> list[ParsedJob]:
    """Render ``company`` poll URL and extract jobs without LLM calls."""
    poll_url = company.effective_poll_url
    await assert_url_safe_async(poll_url)
    runner = browser or _default_browser
    async with _headless_semaphore:
        try:
            html = await asyncio.wait_for(
                runner.render_html(
                    poll_url,
                    user_agent=CAREER_WATCH_USER_AGENT,
                    timeout_ms=_PAGE_TIMEOUT_MS,
                ),
                timeout=_COMPANY_BUDGET_SECONDS,
            )
        except CareerWatchSsrfError:
            raise
        except TimeoutError:
            log.warning(
                "career_watch_headless_timeout",
                company_id=str(getattr(company, "id", "")),
            )
            return []
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "career_watch_headless_failed",
                company_id=str(getattr(company, "id", "")),
                error=str(exc),
            )
            return []

    jobs = _extract_rendered_jobs(
        html,
        base_url=poll_url,
        ats_type=company.ats_type,
    )
    return meaningful_jobs(company.ats_type, jobs)


__all__ = ["HeadlessBrowser", "fetch_jobs_headless"]
