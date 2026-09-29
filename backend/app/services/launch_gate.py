"""Pre-launch signup gate — blocks public registration until LAUNCH_AT."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone

from fastapi import HTTPException, Request, status

from app.config import settings

PREVIEW_COOKIE_NAME = "sr_launch_preview"
_PREVIEW_COOKIE_PAYLOAD = b"flintapply-launch-preview-v1"


def preview_cookie_value(secret: str) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        _PREVIEW_COOKIE_PAYLOAD,
        hashlib.sha256,
    ).hexdigest()[:32]


def _parse_launch_at(raw: str) -> datetime | None:
    text = raw.strip()
    if not text:
        return None
    try:
        # Accept ISO-8601 with Z or offset.
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def launch_is_open(now: datetime | None = None) -> bool:
    raw = settings.LAUNCH_AT.strip()
    if not raw:
        return True
    launch_at = _parse_launch_at(raw)
    if launch_at is None:
        return True
    if launch_at.tzinfo is None:
        launch_at = launch_at.replace(tzinfo=timezone.utc)
    current = now or datetime.now(timezone.utc)
    return current >= launch_at.astimezone(timezone.utc)


def has_launch_preview(request: Request) -> bool:
    secret = settings.LAUNCH_PREVIEW_SECRET.strip()
    if not secret:
        return False
    expected = preview_cookie_value(secret)
    return request.cookies.get(PREVIEW_COOKIE_NAME) == expected


def assert_signup_allowed(request: Request) -> None:
    if launch_is_open():
        return
    if has_launch_preview(request):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "launch_closed",
            "message": "Sign-up opens when FlintApply launches. Use your early-access invite if you have one.",
        },
    )


__all__ = [
    "assert_signup_allowed",
    "has_launch_preview",
    "launch_is_open",
    "preview_cookie_value",
]
