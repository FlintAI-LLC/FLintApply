"""Pure helpers for admin reporting (no database)."""

from __future__ import annotations

import pytest

from app.services.admin.reporting import PUBLIC_METRIC_KEYS, _login_channel, _parse_report_dates


def test_parse_report_dates_valid() -> None:
    start, end = _parse_report_dates("2026-01-01", "2026-01-31")
    assert start.isoformat() == "2026-01-01"
    assert end.isoformat() == "2026-01-31"


def test_parse_report_dates_rejects_inverted() -> None:
    with pytest.raises(ValueError, match="to must be on or after from"):
        _parse_report_dates("2026-02-01", "2026-01-01")


def test_login_channel_extension() -> None:
    assert _login_channel({"source": "extension"}) == "extension"
    assert _login_channel({"source": "web"}) == "web"
    assert _login_channel(None) == "web"


def test_public_metric_keys_are_stable() -> None:
    assert "landing_view" in PUBLIC_METRIC_KEYS
    assert "extension_open" in PUBLIC_METRIC_KEYS
