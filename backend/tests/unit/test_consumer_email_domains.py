"""Tests for B2C consumer email domain detection."""

from __future__ import annotations

import pytest

from app.services.auth.consumer_email_domains import (
    email_domain,
    is_consumer_email,
    is_signup_rate_limit_whitelisted,
)

pytestmark = pytest.mark.unit


def test_gmail_is_consumer() -> None:
    assert is_consumer_email("user@gmail.com") is True


def test_work_domain_is_not_consumer() -> None:
    assert is_consumer_email("ali@idme24.com") is False


def test_email_domain_extraction() -> None:
    assert email_domain("  User@Example.COM ") == "example.com"


def test_whitelist_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.auth.consumer_email_domains.settings.SIGNUP_RATE_LIMIT_WHITELIST_DOMAINS",
        ["acme-corp.com"],
    )
    assert is_signup_rate_limit_whitelisted("dev@acme-corp.com") is True
    assert is_signup_rate_limit_whitelisted("dev@gmail.com") is False
