"""Rate-limit key helpers."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from app.limiter import (
    authenticated_user_rate_limit_key,
    refresh_cookie_rate_limit_key,
)

pytestmark = pytest.mark.unit


def _request(
    *,
    peer: str = "172.18.0.1",
    bearer: str | None = None,
    refresh_cookie: str | None = None,
) -> Mock:
    request = Mock()
    request.client = Mock(host=peer)
    headers: dict[str, str] = {}
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    request.headers = headers
    request.cookies = {"sr_refresh": refresh_cookie} if refresh_cookie else {}
    return request


def test_refresh_cookie_key_is_per_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.auth.client_ip.settings.TRUSTED_PROXY_IPS",
        ["172.16.0.0/12"],
    )
    a = refresh_cookie_rate_limit_key(_request(refresh_cookie="token-a"))
    b = refresh_cookie_rate_limit_key(_request(refresh_cookie="token-b"))
    assert a.startswith("refresh:")
    assert b.startswith("refresh:")
    assert a != b


def test_refresh_cookie_key_falls_back_to_ip_without_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.auth.client_ip.settings.TRUSTED_PROXY_IPS",
        ["172.16.0.0/12"],
    )
    key = refresh_cookie_rate_limit_key(_request(peer="172.18.0.1"))
    assert key == "172.18.0.1"


def test_authenticated_key_uses_user_sub_when_jwt_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.auth.tokens import create_access_token
    import uuid

    user_id = uuid.uuid4()
    token = create_access_token(user_id, ttl=900)
    key = authenticated_user_rate_limit_key(_request(bearer=token))
    assert key == f"user:{user_id}"
