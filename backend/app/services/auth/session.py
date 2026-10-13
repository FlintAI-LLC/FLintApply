"""Redis-backed refresh-token session metadata.

Each issued refresh token id is bound in Redis under
``refresh:{token_id}`` -> JSON ``{user_id, device_fingerprint, issued_at}``
with TTL matching the token's lifetime.  This gives the auth layer a fast,
cluster-wide revocation check that does not require a DB round-trip on
every API request.

We deliberately reuse the project's existing Redis client (initialised in
``app.services.session_store.init_redis``) so the connection pool is
shared and the in-memory fallback (used for ``USE_IN_MEMORY_STORE=true``
local dev) Just Works.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

from app.config import settings
from app.services import session_store

# Key namespaces -----------------------------------------------------------

_TOKEN_KEY_FMT = "refresh:{token_id}"
_USER_INDEX_KEY_FMT = "refresh_user:{user_id}"
_ACTIVE_SESSION_KEY_FMT = "active_session:{user_id}"
_ACTIVE_SESSIONS_SET_KEY_FMT = "active_sessions:{user_id}"
_COOKIE_BIND_KEY_FMT = "cookie_bind:{user_id}:{session_id}"

# In-memory fallback for local dev / unit tests --------------------------------
_memory_tokens: dict[str, dict[str, Any]] = {}
_memory_user_index: dict[str, set[str]] = {}
_memory_active_sessions: dict[str, dict[str, Any]] = {}
_memory_active_session_sets: dict[str, dict[str, Any]] = {}
_memory_cookie_bind_tickets: dict[str, float] = {}


def _redis() -> aioredis.Redis | None:
    """Return the shared Redis client if Redis mode is active."""
    return session_store._redis_client  # type: ignore[attr-defined]


def _token_key(token_id: uuid.UUID | str) -> str:
    return _TOKEN_KEY_FMT.format(token_id=str(token_id))


def _user_key(user_id: uuid.UUID | str) -> str:
    return _USER_INDEX_KEY_FMT.format(user_id=str(user_id))


def _active_session_key(user_id: uuid.UUID | str) -> str:
    return _ACTIVE_SESSION_KEY_FMT.format(user_id=str(user_id))


def _active_sessions_set_key(user_id: uuid.UUID | str) -> str:
    return _ACTIVE_SESSIONS_SET_KEY_FMT.format(user_id=str(user_id))


def _cookie_bind_key(user_id: uuid.UUID | str, session_id: uuid.UUID | str) -> str:
    return _COOKIE_BIND_KEY_FMT.format(user_id=str(user_id), session_id=str(session_id))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def bind_refresh_token_to_redis(
    token_id: uuid.UUID | str,
    user_id: uuid.UUID | str,
    device_fp: str,
    ttl: int | None = None,
    *,
    auth_session_id: uuid.UUID | str | None = None,
) -> None:
    """Persist a refresh token id with its metadata + TTL."""
    ttl_seconds = ttl if ttl is not None else settings.REFRESH_TOKEN_TTL_SECONDS
    payload_data: dict[str, Any] = {
        "user_id": str(user_id),
        "device_fingerprint": device_fp,
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    if auth_session_id is not None:
        payload_data["auth_session_id"] = str(auth_session_id)
    payload = json.dumps(payload_data)
    r = _redis()
    if r is not None:
        async with r.pipeline(transaction=False) as pipe:
            pipe.setex(_token_key(token_id), ttl_seconds, payload)
            pipe.sadd(_user_key(user_id), str(token_id))
            # Re-stamp the index TTL so it always >= the longest member.
            pipe.expire(_user_key(user_id), ttl_seconds)
            await pipe.execute()
        return

    _memory_tokens[_token_key(token_id)] = {
        "payload": payload,
        "expires_at": datetime.now(timezone.utc).timestamp() + ttl_seconds,
    }
    _memory_user_index.setdefault(_user_key(user_id), set()).add(str(token_id))


async def get_refresh_token_metadata(
    token_id: uuid.UUID | str,
) -> dict[str, Any] | None:
    """Return the metadata blob for a token id or ``None`` if missing/revoked."""
    r = _redis()
    if r is not None:
        raw = await r.get(_token_key(token_id))
        return json.loads(raw) if raw else None

    entry = _memory_tokens.get(_token_key(token_id))
    if entry is None:
        return None
    if entry["expires_at"] <= datetime.now(timezone.utc).timestamp():
        _memory_tokens.pop(_token_key(token_id), None)
        return None
    return json.loads(entry["payload"])


async def mark_refresh_token_revoked_in_redis(token_id: uuid.UUID | str) -> None:
    """Flag a refresh row as DB-revoked while keeping metadata for classify."""
    key = _token_key(token_id)
    r = _redis()
    if r is not None:
        raw = await r.get(key)
        if not raw:
            return
        try:
            data = json.loads(raw)
        except (TypeError, ValueError):  # pragma: no cover - defensive
            return
        data["db_revoked"] = True
        ttl = await r.ttl(key)
        if ttl is None or ttl < 1:
            ttl = settings.REFRESH_TOKEN_TTL_SECONDS
        await r.setex(key, ttl, json.dumps(data))
        return

    entry = _memory_tokens.get(key)
    if entry is None:
        return
    try:
        data = json.loads(entry["payload"])
    except (TypeError, ValueError):  # pragma: no cover - defensive
        return
    data["db_revoked"] = True
    entry["payload"] = json.dumps(data)


async def revoke_redis_token(token_id: uuid.UUID | str) -> None:
    """Drop a single token id from Redis (idempotent)."""
    r = _redis()
    if r is not None:
        meta = await r.get(_token_key(token_id))
        await r.delete(_token_key(token_id))
        if meta:
            try:
                user_id = json.loads(meta).get("user_id")
            except (TypeError, ValueError):  # pragma: no cover - defensive
                user_id = None
            if user_id:
                await r.srem(_user_key(user_id), str(token_id))
        return

    entry = _memory_tokens.pop(_token_key(token_id), None)
    if entry is not None:
        try:
            user_id = json.loads(entry["payload"]).get("user_id")
        except (TypeError, ValueError):
            user_id = None
        if user_id:
            _memory_user_index.get(_user_key(user_id), set()).discard(str(token_id))


async def revoke_all_user_tokens(user_id: uuid.UUID | str) -> int:
    """Revoke every refresh token bound to ``user_id``.  Returns the count."""
    r = _redis()
    if r is not None:
        members = await r.smembers(_user_key(user_id))
        if not members:
            return 0
        keys = [_token_key(m) for m in members]
        async with r.pipeline(transaction=False) as pipe:
            pipe.delete(*keys)
            pipe.delete(_user_key(user_id))
            await pipe.execute()
        await clear_all_auth_sessions(user_id)
        return len(members)

    members = list(_memory_user_index.pop(_user_key(user_id), set()))
    for m in members:
        _memory_tokens.pop(_token_key(m), None)
    count = len(members)
    await clear_all_auth_sessions(user_id)
    return count


async def list_user_token_ids(user_id: uuid.UUID | str) -> list[str]:
    """Return the live token-id set for ``user_id`` (for /sessions UI)."""
    r = _redis()
    if r is not None:
        members = await r.smembers(_user_key(user_id))
        return sorted(members)
    return sorted(_memory_user_index.get(_user_key(user_id), set()))


async def register_auth_session(
    user_id: uuid.UUID | str,
    session_id: uuid.UUID | str,
    *,
    ttl: int | None = None,
) -> None:
    """Register ``session_id`` as a valid login for ``user_id`` (multi-client)."""
    ttl_seconds = ttl if ttl is not None else settings.REFRESH_TOKEN_TTL_SECONDS
    sid = str(session_id)
    set_key = _active_sessions_set_key(user_id)
    legacy_key = _active_session_key(user_id)
    r = _redis()
    if r is not None:
        async with r.pipeline(transaction=False) as pipe:
            pipe.sadd(set_key, sid)
            pipe.expire(set_key, ttl_seconds)
            pipe.delete(legacy_key)
            await pipe.execute()
        return

    now = datetime.now(timezone.utc).timestamp()
    entry = _memory_active_session_sets.setdefault(
        set_key,
        {"sessions": set(), "expires_at": now + ttl_seconds},
    )
    entry["sessions"].add(sid)
    entry["expires_at"] = max(entry["expires_at"], now + ttl_seconds)
    _memory_active_sessions.pop(legacy_key, None)


async def set_active_auth_session(
    user_id: uuid.UUID | str,
    session_id: uuid.UUID | str,
    *,
    ttl: int | None = None,
) -> None:
    """Backward-compatible alias for :func:`register_auth_session`."""
    await register_auth_session(user_id, session_id, ttl=ttl)


async def unregister_auth_session(
    user_id: uuid.UUID | str,
    session_id: uuid.UUID | str,
) -> None:
    """Remove one auth session id (single-device logout)."""
    sid = str(session_id)
    set_key = _active_sessions_set_key(user_id)
    legacy_key = _active_session_key(user_id)
    r = _redis()
    if r is not None:
        await r.srem(set_key, sid)
        legacy = await r.get(legacy_key)
        legacy_str = legacy.decode("utf-8") if isinstance(legacy, bytes) else legacy
        if legacy_str == sid:
            await r.delete(legacy_key)
        return

    entry = _memory_active_session_sets.get(set_key)
    if entry is not None:
        entry["sessions"].discard(sid)
        if not entry["sessions"]:
            _memory_active_session_sets.pop(set_key, None)
    legacy = _memory_active_sessions.get(legacy_key)
    if legacy and legacy.get("session_id") == sid:
        _memory_active_sessions.pop(legacy_key, None)


async def clear_all_auth_sessions(user_id: uuid.UUID | str) -> None:
    """Drop every registered auth session id for ``user_id`` (logout-all)."""
    set_key = _active_sessions_set_key(user_id)
    legacy_key = _active_session_key(user_id)
    r = _redis()
    if r is not None:
        async with r.pipeline(transaction=False) as pipe:
            pipe.delete(set_key)
            pipe.delete(legacy_key)
            await pipe.execute()
        return
    _memory_active_session_sets.pop(set_key, None)
    _memory_active_sessions.pop(legacy_key, None)


async def clear_active_auth_session(user_id: uuid.UUID | str) -> None:
    """Alias for :func:`clear_all_auth_sessions` (logout-all / chain revoke)."""
    await clear_all_auth_sessions(user_id)


async def _legacy_active_session_id(user_id: uuid.UUID | str) -> str | None:
    key = _active_session_key(user_id)
    r = _redis()
    if r is not None:
        raw = await r.get(key)
        return raw.decode("utf-8") if isinstance(raw, bytes) else raw

    entry = _memory_active_sessions.get(key)
    if entry is None:
        return None
    if entry["expires_at"] <= datetime.now(timezone.utc).timestamp():
        _memory_active_sessions.pop(key, None)
        return None
    return entry["session_id"]


async def user_has_registered_auth_sessions(user_id: uuid.UUID | str) -> bool:
    """True when Redis tracks at least one login session for enforcement."""
    set_key = _active_sessions_set_key(user_id)
    r = _redis()
    if r is not None:
        if await r.scard(set_key) > 0:
            return True
        return await _legacy_active_session_id(user_id) is not None

    entry = _memory_active_session_sets.get(set_key)
    if entry is not None:
        if entry["expires_at"] <= datetime.now(timezone.utc).timestamp():
            _memory_active_session_sets.pop(set_key, None)
        elif entry["sessions"]:
            return True
    return await _legacy_active_session_id(user_id) is not None


async def is_auth_session_active(
    user_id: uuid.UUID | str,
    session_id: uuid.UUID | str,
) -> bool:
    """Whether ``session_id`` is still a valid login for ``user_id``."""
    sid = str(session_id)
    set_key = _active_sessions_set_key(user_id)
    r = _redis()
    if r is not None:
        if await r.sismember(set_key, sid):
            return True
        legacy = await _legacy_active_session_id(user_id)
        return legacy == sid if legacy else False

    entry = _memory_active_session_sets.get(set_key)
    if entry is not None:
        if entry["expires_at"] <= datetime.now(timezone.utc).timestamp():
            _memory_active_session_sets.pop(set_key, None)
        elif sid in entry["sessions"]:
            return True
    legacy = await _legacy_active_session_id(user_id)
    return legacy == sid if legacy else False


async def get_active_auth_session_id(user_id: uuid.UUID | str) -> str | None:
    """Return any registered auth session id (fallback for legacy refresh rows)."""
    set_key = _active_sessions_set_key(user_id)
    r = _redis()
    if r is not None:
        member = await r.srandmember(set_key)
        if member is not None:
            return member.decode("utf-8") if isinstance(member, bytes) else member
        return await _legacy_active_session_id(user_id)

    entry = _memory_active_session_sets.get(set_key)
    if entry is not None:
        if entry["expires_at"] <= datetime.now(timezone.utc).timestamp():
            _memory_active_session_sets.pop(set_key, None)
        elif entry["sessions"]:
            return next(iter(entry["sessions"]))
    return await _legacy_active_session_id(user_id)


async def user_has_other_refresh_tokens_for_session(
    user_id: uuid.UUID | str,
    auth_session_id: uuid.UUID | str,
) -> bool:
    """True when another live refresh token still references ``auth_session_id``."""
    target = str(auth_session_id)
    for token_id in await list_user_token_ids(user_id):
        meta = await get_refresh_token_metadata(token_id)
        if not meta or meta.get("db_revoked"):
            continue
        if str(meta.get("auth_session_id")) == target:
            return True
    return False


async def issue_cookie_bind_ticket(
    user_id: uuid.UUID | str,
    session_id: uuid.UUID | str,
    *,
    ttl: int,
) -> None:
    """Allow ONE browser refresh-cookie bind for this auth session.

    Sign-in issues the ticket; ``POST /api/auth/refresh-cookie`` spends it. This
    keeps a bare access token from minting a long-lived refresh credential.
    """
    key = _cookie_bind_key(user_id, session_id)
    r = _redis()
    if r is not None:
        await r.setex(key, ttl, "1")
        return
    _memory_cookie_bind_tickets[key] = datetime.now(timezone.utc).timestamp() + ttl


async def consume_cookie_bind_ticket(
    user_id: uuid.UUID | str,
    session_id: uuid.UUID | str,
) -> bool:
    """Atomically spend the bind ticket. ``False`` when absent, spent or expired."""
    key = _cookie_bind_key(user_id, session_id)
    r = _redis()
    if r is not None:
        return await r.getdel(key) is not None
    expires_at = _memory_cookie_bind_tickets.pop(key, None)
    return expires_at is not None and expires_at > datetime.now(timezone.utc).timestamp()


def _reset_for_tests() -> None:
    """Clear the in-memory store between unit tests."""
    _memory_tokens.clear()
    _memory_user_index.clear()
    _memory_active_sessions.clear()
    _memory_active_session_sets.clear()
    _memory_cookie_bind_tickets.clear()


__all__ = [
    "bind_refresh_token_to_redis",
    "clear_active_auth_session",
    "clear_all_auth_sessions",
    "consume_cookie_bind_ticket",
    "get_active_auth_session_id",
    "get_refresh_token_metadata",
    "is_auth_session_active",
    "issue_cookie_bind_ticket",
    "list_user_token_ids",
    "register_auth_session",
    "revoke_all_user_tokens",
    "mark_refresh_token_revoked_in_redis",
    "revoke_redis_token",
    "set_active_auth_session",
    "unregister_auth_session",
    "user_has_other_refresh_tokens_for_session",
    "user_has_registered_auth_sessions",
]
