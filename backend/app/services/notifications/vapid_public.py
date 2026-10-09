"""Expose the VAPID application server key for browser push subscription."""

from __future__ import annotations

import base64
import re

from app.config import settings

_URLSAFE_B64_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def application_server_key() -> str | None:
    """Return URL-safe base64 public key for ``PushManager.subscribe``, or None."""
    raw = (settings.WEB_PUSH_VAPID_PUBLIC_KEY or "").strip()
    if not raw:
        return None
    if _URLSAFE_B64_RE.fullmatch(raw) and len(raw) >= 80:
        return raw
    if raw.startswith("-----BEGIN"):
        from cryptography.hazmat.primitives import serialization
        from py_vapid import Vapid

        vapid = Vapid.from_pem(raw.encode())
        point = vapid.public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        return base64.urlsafe_b64encode(point).decode().rstrip("=")
    return None


__all__ = ["application_server_key"]
