from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.services.launch_gate import (
    assert_signup_allowed,
    launch_is_open,
    preview_cookie_value,
)


def test_launch_is_open_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "LAUNCH_AT", "")
    assert launch_is_open() is True


def test_launch_closed_before_instant(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    monkeypatch.setattr(settings, "LAUNCH_AT", "2030-01-01T09:00:00-08:00")
    assert launch_is_open(datetime(2026, 1, 1, tzinfo=timezone.utc)) is False


def test_preview_cookie_blocks_signup_without_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings
    from fastapi import HTTPException

    monkeypatch.setattr(settings, "LAUNCH_AT", "2030-01-01T09:00:00-08:00")
    monkeypatch.setattr(settings, "LAUNCH_PREVIEW_SECRET", "test-secret")
    req = MagicMock()
    req.cookies = {}
    with pytest.raises(HTTPException) as exc:
        assert_signup_allowed(req)
    assert exc.value.status_code == 403


def test_preview_cookie_allows_signup(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings

    secret = "test-secret"
    monkeypatch.setattr(settings, "LAUNCH_AT", "2030-01-01T09:00:00-08:00")
    monkeypatch.setattr(settings, "LAUNCH_PREVIEW_SECRET", secret)
    req = MagicMock()
    req.cookies = {"sr_launch_preview": preview_cookie_value(secret)}
    assert_signup_allowed(req)
