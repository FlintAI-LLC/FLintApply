"""Board resolver unit tests."""

from __future__ import annotations

import httpx
import pytest

from app.models.career_watch import CareerAtsType
from app.services.career_watch.http_client import create_career_watch_client
from app.services.career_watch.resolver import resolve_careers_board
from app.services.career_watch.ssrf_guard import CareerWatchSsrfError

COSTCO_FIXTURE = """
<html><body>
  <a href="https://careers-costco.icims.com/jobs/search?ss=1">Search Jobs</a>
</body></html>
"""


def _mock_transport(handler) -> httpx.AsyncHTTPTransport:
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_resolver_finds_icims_from_costco_landing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "careers.costco.com"
        return httpx.Response(200, text=COSTCO_FIXTURE)

    async with create_career_watch_client(transport=_mock_transport(handler)) as client:
        result = await resolve_careers_board(
            "https://careers.costco.com/jobs",
            client=client,
        )
    assert result.resolved_away_from_input is True
    assert "icims.com" in result.canonical_poll_url
    assert result.detection.ats_type == CareerAtsType.icims


@pytest.mark.asyncio
async def test_greenhouse_url_unchanged() -> None:
    url = "https://boards.greenhouse.io/acme"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html></html>")

    async with create_career_watch_client(transport=_mock_transport(handler)) as client:
        result = await resolve_careers_board(url, client=client)
    assert result.resolved_away_from_input is False
    assert result.canonical_poll_url == url
    assert result.detection.ats_type == CareerAtsType.greenhouse


@pytest.mark.asyncio
async def test_redirect_to_private_ip_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_getaddrinfo(host, *args, **kwargs):
        if host == "careers.example.com":
            return [(2, 1, 6, "", ("93.184.216.34", 0))]
        if host == "127.0.0.1":
            return [(2, 1, 6, "", ("127.0.0.1", 0))]
        raise OSError("unexpected host")

    monkeypatch.setattr(
        "app.services.career_watch.ssrf_guard.socket.getaddrinfo",
        fake_getaddrinfo,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "careers.example.com":
            return httpx.Response(
                302,
                headers={"Location": "http://127.0.0.1/internal"},
            )
        raise AssertionError(f"unexpected request {request.url}")

    async with create_career_watch_client(transport=_mock_transport(handler)) as client:
        with pytest.raises(CareerWatchSsrfError, match="127.0.0.1"):
            await resolve_careers_board(
                "https://careers.example.com/jobs",
                client=client,
            )
