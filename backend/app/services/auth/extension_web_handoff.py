"""Single-use codes that let the browser extension adopt an existing web login."""

from __future__ import annotations

import json
import secrets
import uuid
from typing import Any

import redis.asyncio as aioredis

from app.services import session_store

_CODE_PREFIX = "extension_web_handoff:"
_HANDOFF_TTL_SECONDS = 60

_memory_handoff_codes: dict[str, dict[str, Any]] = {}


def _redis() -> aioredis.Redis | None:
    return session_store._redis_client  # type: ignore[attr-defined]


def _code_key(code: str) -> str:
    return f"{_CODE_PREFIX}{code}"


async def mint_web_handoff_code(
    user_id: uuid.UUID | str,
    web_auth_session_id: uuid.UUID | str,
) -> tuple[str, int]:
    """Create a one-time code the extension can exchange for its own tokens."""
    code = secrets.token_urlsafe(32)
    payload = json.dumps(
        {
            "user_id": str(user_id),
            "web_sid": str(web_auth_session_id),
        }
    )
    r = _redis()
    if r is not None:
        await r.setex(_code_key(code), _HANDOFF_TTL_SECONDS, payload)
    else:
        import time

        _memory_handoff_codes[_code_key(code)] = {
            "payload": payload,
            "expires_at": time.time() + _HANDOFF_TTL_SECONDS,
        }
    return code, _HANDOFF_TTL_SECONDS


async def consume_web_handoff_code(code: str) -> dict[str, str] | None:
    """Atomically redeem ``code`` or return ``None`` when invalid/expired."""
    if not code or len(code) > 128:
        return None
    key = _code_key(code)
    r = _redis()
    if r is not None:
        raw = await r.getdel(key)
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):
            return None
    else:
        import time

        entry = _memory_handoff_codes.pop(key, None)
        if entry is None or entry["expires_at"] <= time.time():
            return None
        try:
            data = json.loads(entry["payload"])
        except (TypeError, ValueError):
            return None

    user_id = data.get("user_id")
    web_sid = data.get("web_sid")
    if not user_id or not web_sid:
        return None
    return {"user_id": str(user_id), "web_sid": str(web_sid)}


def _reset_for_tests() -> None:
    _memory_handoff_codes.clear()


__all__ = [
    "consume_web_handoff_code",
    "mint_web_handoff_code",
    "_reset_for_tests",
]
