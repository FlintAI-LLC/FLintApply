"""Trusted client IP resolution tests."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.services.auth.client_ip import resolve_client_ip

pytestmark = pytest.mark.unit


def _request(
    *, peer: str, xff: str | None = None, real_ip: str | None = None
) -> Mock:
    request = Mock()
    request.client = Mock(host=peer)
    headers: dict[str, str] = {}
    if xff is not None:
        headers["x-forwarded-for"] = xff
    if real_ip is not None:
        headers["x-real-ip"] = real_ip
    request.headers = headers
    return request


def test_direct_connection_ignores_xff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.auth.client_ip.settings.TRUSTED_PROXY_IPS",
        ["127.0.0.1"],
    )
    ip = resolve_client_ip(_request(peer="203.0.113.10", xff="198.51.100.20"))
    assert ip == "203.0.113.10"


def test_trusted_proxy_reads_first_untrusted_xff_hop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.auth.client_ip.settings.TRUSTED_PROXY_IPS",
        ["127.0.0.1"],
    )
    ip = resolve_client_ip(
        _request(peer="127.0.0.1", xff="198.51.100.20, 127.0.0.1")
    )
    assert ip == "198.51.100.20"


def test_trusted_proxy_uses_x_real_ip_when_xff_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.auth.client_ip.settings.TRUSTED_PROXY_IPS",
        ["172.16.0.0/12"],
    )
    ip = resolve_client_ip(
        _request(peer="172.18.0.1", real_ip="198.51.100.20")
    )
    assert ip == "198.51.100.20"
