"""SSRF-guarded httpx client factory for Career Watch."""

from __future__ import annotations

import httpx

from app.services.career_watch.fetch import FETCH_TIMEOUT_SECONDS
from app.services.career_watch.ssrf_guard import assert_url_safe_async

_RESOLVER_TIMEOUT = httpx.Timeout(20.0, connect=10.0)


async def _ssrf_request_hook(request: httpx.Request) -> None:
    await assert_url_safe_async(str(request.url))


def create_career_watch_client(
    *,
    timeout: httpx.Timeout | float | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.AsyncClient:
    """Build an AsyncClient that validates every hop (including redirects)."""
    if timeout is None:
        timeout = FETCH_TIMEOUT_SECONDS
    if isinstance(timeout, (int, float)):
        timeout = httpx.Timeout(float(timeout), connect=min(10.0, float(timeout)))
    kwargs: dict = {
        "follow_redirects": True,
        "timeout": timeout,
        "event_hooks": {"request": [_ssrf_request_hook]},
        "trust_env": False,
    }
    if transport is not None:
        kwargs["transport"] = transport
    return httpx.AsyncClient(**kwargs)


__all__ = ["create_career_watch_client", "_RESOLVER_TIMEOUT"]
