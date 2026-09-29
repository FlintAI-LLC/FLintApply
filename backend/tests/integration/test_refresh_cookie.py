"""POST /api/auth/refresh-cookie: bind an sr_refresh cookie after server-side OAuth.

OAuth sign-in runs ``/callback`` from the Next.js server, so the browser never
receives the refresh cookie and rotation 401s once the access token expires.
The signed-in browser calls this endpoint to obtain one for its CURRENT session,
spending the single-use ticket that sign-in issued for that session.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

import app.routers.auth as auth_router
from app.config import is_production_grade, settings
from app.limiter import limiter
from app.main import app
from app.models.user import RefreshToken, User
from app.routers.auth import REFRESH_COOKIE_NAME
from app.services.auth import session as redis_session
from app.services.auth.tokens import create_access_token, decode_access_token
from tests.integration.test_auth import REGISTER_PAYLOAD

pytestmark = pytest.mark.integration

URL = "/api/auth/refresh-cookie"


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _set_cookie(response: Response) -> str:
    return response.headers.get("set-cookie", "")


def _cookie_attributes(header: str) -> dict[str, str | None]:
    """Parse a Set-Cookie header into ``{lowercased-name: value-or-None}``."""
    parts = [part.strip() for part in header.split(";") if part.strip()]
    name, _, value = parts[0].partition("=")
    attrs: dict[str, str | None] = {"__name__": name, "__value__": value}
    for part in parts[1:]:
        key, sep, val = part.partition("=")
        attrs[key.lower()] = val if sep else None
    return attrs


async def _sso_like_session(client: AsyncClient) -> str:
    """Sign up, then drop the cookie: what the browser holds after Node consumed it."""
    r = await client.post("/api/auth/register", json=REGISTER_PAYLOAD)
    assert r.status_code == 201, r.text
    client.cookies.clear()
    return r.json()["access_token"]


async def _all_tokens(db: AsyncSession) -> list[RefreshToken]:
    return list((await db.execute(select(RefreshToken))).scalars().all())


async def _user(db: AsyncSession, email: str = REGISTER_PAYLOAD["email"]) -> User:
    return (await db.execute(select(User).where(User.email == email))).scalar_one()


async def _seed_ticket(user_id: uuid.UUID, access: str) -> None:
    await redis_session.issue_cookie_bind_ticket(
        user_id,
        decode_access_token(access)["sid"],
        ttl=settings.ACCESS_TOKEN_TTL_SECONDS,
    )


async def test_valid_bearer_sets_cookie_with_exact_attributes(
    app_client: AsyncClient,
) -> None:
    access = await _sso_like_session(app_client)

    r = await app_client.post(URL, headers=_bearer(access))

    assert r.status_code == 200, r.text
    assert r.json() == {"ok": True, "issued": True}
    attrs = _cookie_attributes(_set_cookie(r))
    assert attrs["__name__"] == REFRESH_COOKIE_NAME
    assert attrs["__value__"]
    assert attrs["path"] == "/api/auth"
    assert attrs["samesite"] is not None and attrs["samesite"].lower() == "lax"
    assert "httponly" in attrs
    assert ("secure" in attrs) == is_production_grade()
    assert attrs["max-age"] == str(settings.REFRESH_TOKEN_TTL_SECONDS)
    assert "domain" not in attrs


async def test_minted_cookie_rotates_within_the_same_auth_session(
    app_client: AsyncClient,
) -> None:
    access = await _sso_like_session(app_client)
    sid = decode_access_token(access)["sid"]

    bound = await app_client.post(URL, headers=_bearer(access))
    cookie = bound.cookies.get(REFRESH_COOKIE_NAME)
    assert cookie

    refreshed = await app_client.post(
        "/api/auth/refresh", cookies={REFRESH_COOKIE_NAME: cookie}
    )

    assert refreshed.status_code == 200, refreshed.text
    assert decode_access_token(refreshed.json()["access_token"])["sid"] == sid
    # The original access token is still honoured: no new auth session began.
    me = await app_client.get("/api/auth/me", headers=_bearer(access))
    assert me.status_code == 200


async def test_binds_token_to_the_current_auth_session_id(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    access = await _sso_like_session(app_client)
    sid = decode_access_token(access)["sid"]
    before = {t.id for t in await _all_tokens(db_session)}

    await app_client.post(URL, headers=_bearer(access))

    created = [t for t in await _all_tokens(db_session) if t.id not in before]
    assert len(created) == 1
    meta = await redis_session.get_refresh_token_metadata(created[0].id)
    assert meta is not None
    assert meta["auth_session_id"] == sid


async def test_does_not_mint_an_access_token(
    app_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    access = await _sso_like_session(app_client)
    calls: list[object] = []
    real = auth_router.create_access_token

    def counting(*args, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(auth_router, "create_access_token", counting)

    minted = await app_client.post(URL, headers=_bearer(access))
    cookie = minted.cookies.get(REFRESH_COOKIE_NAME)
    skipped = await app_client.post(
        URL, headers=_bearer(access), cookies={REFRESH_COOKIE_NAME: cookie}
    )

    assert minted.json()["issued"] is True
    assert skipped.json()["issued"] is False
    assert calls == []


async def test_rejects_missing_or_invalid_bearer_without_a_cookie(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    await _sso_like_session(app_client)
    before = len(await _all_tokens(db_session))

    missing = await app_client.post(URL)
    invalid = await app_client.post(URL, headers=_bearer("not-a-jwt"))

    for r in (missing, invalid):
        assert r.status_code == 401
        assert _set_cookie(r) == ""
    assert len(await _all_tokens(db_session)) == before


async def test_a_valid_bearer_without_a_ticket_cannot_mint(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    access = await _sso_like_session(app_client)
    first = await app_client.post(URL, headers=_bearer(access))
    assert first.status_code == 200
    app_client.cookies.clear()
    count = len(await _all_tokens(db_session))

    second = await app_client.post(URL, headers=_bearer(access))

    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "bind_unavailable"
    assert _set_cookie(second) == ""
    assert len(await _all_tokens(db_session)) == count


async def test_ticket_from_another_session_is_not_accepted(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    access = await _sso_like_session(app_client)
    user_id = (await _user(db_session)).id
    await redis_session.consume_cookie_bind_ticket(
        user_id, decode_access_token(access)["sid"]
    )
    await redis_session.issue_cookie_bind_ticket(
        user_id, uuid.uuid4(), ttl=settings.ACCESS_TOKEN_TTL_SECONDS
    )

    r = await app_client.post(URL, headers=_bearer(access))

    assert r.status_code == 409
    assert _set_cookie(r) == ""


async def test_revokes_nothing_and_keeps_existing_tokens_usable(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    r = await app_client.post("/api/auth/register", json=REGISTER_PAYLOAD)
    access = r.json()["access_token"]
    original_cookie = r.cookies.get(REFRESH_COOKIE_NAME)
    assert original_cookie
    app_client.cookies.clear()
    before = await _all_tokens(db_session)
    assert all(t.revoked_at is None for t in before)

    bound = await app_client.post(URL, headers=_bearer(access))
    assert bound.status_code == 200

    after = await _all_tokens(db_session)
    assert len(after) == len(before) + 1
    assert all(t.revoked_at is None for t in after), "no token may be revoked"
    still_works = await app_client.post(
        "/api/auth/refresh", cookies={REFRESH_COOKIE_NAME: original_cookie}
    )
    assert still_works.status_code == 200


async def test_skips_minting_without_spending_the_ticket_when_cookie_is_live(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    access = await _sso_like_session(app_client)
    first = await app_client.post(URL, headers=_bearer(access))
    cookie = first.cookies.get(REFRESH_COOKIE_NAME)
    assert cookie
    await _seed_ticket((await _user(db_session)).id, access)
    count = len(await _all_tokens(db_session))

    again = await app_client.post(
        URL, headers=_bearer(access), cookies={REFRESH_COOKIE_NAME: cookie}
    )

    assert again.status_code == 200
    assert again.json() == {"ok": True, "issued": False}
    assert _set_cookie(again) == ""
    assert len(await _all_tokens(db_session)) == count
    # The ticket survived the skip, so a cookieless retry can still mint.
    app_client.cookies.clear()
    later = await app_client.post(URL, headers=_bearer(access))
    assert later.json()["issued"] is True


async def test_mints_when_the_presented_cookie_is_revoked(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    access = await _sso_like_session(app_client)
    first = await app_client.post(URL, headers=_bearer(access))
    cookie = first.cookies.get(REFRESH_COOKIE_NAME)
    assert cookie
    await db_session.execute(update(RefreshToken).values(revoked_at=func.now()))
    await db_session.commit()
    user_id = (await _user(db_session)).id

    without_ticket = await app_client.post(
        URL, headers=_bearer(access), cookies={REFRESH_COOKIE_NAME: cookie}
    )
    assert without_ticket.status_code == 409

    await _seed_ticket(user_id, access)
    again = await app_client.post(
        URL, headers=_bearer(access), cookies={REFRESH_COOKIE_NAME: cookie}
    )
    assert again.status_code == 200
    assert again.json()["issued"] is True
    assert _set_cookie(again).startswith(f"{REFRESH_COOKIE_NAME}=")


async def test_cookie_bound_to_a_different_session_does_not_skip(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    access = await _sso_like_session(app_client)
    user_id = (await _user(db_session)).id
    first = await app_client.post(URL, headers=_bearer(access))
    cookie = first.cookies.get(REFRESH_COOKIE_NAME)
    assert cookie
    minted_id = (
        await db_session.execute(
            select(RefreshToken.id).order_by(RefreshToken.issued_at.desc()).limit(1)
        )
    ).scalar_one()
    await redis_session.bind_refresh_token_to_redis(
        minted_id, user_id, "fp", auth_session_id=uuid.uuid4()
    )

    without_ticket = await app_client.post(
        URL, headers=_bearer(access), cookies={REFRESH_COOKIE_NAME: cookie}
    )
    assert without_ticket.status_code == 409

    await _seed_ticket(user_id, access)
    with_ticket = await app_client.post(
        URL, headers=_bearer(access), cookies={REFRESH_COOKIE_NAME: cookie}
    )
    assert with_ticket.json()["issued"] is True


async def test_expired_refresh_row_does_not_skip(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    access = await _sso_like_session(app_client)
    user_id = (await _user(db_session)).id
    first = await app_client.post(URL, headers=_bearer(access))
    cookie = first.cookies.get(REFRESH_COOKIE_NAME)
    assert cookie
    await db_session.execute(
        update(RefreshToken).values(
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
        )
    )
    await db_session.commit()

    without_ticket = await app_client.post(
        URL, headers=_bearer(access), cookies={REFRESH_COOKIE_NAME: cookie}
    )
    assert without_ticket.status_code == 409

    await _seed_ticket(user_id, access)
    with_ticket = await app_client.post(
        URL, headers=_bearer(access), cookies={REFRESH_COOKIE_NAME: cookie}
    )
    assert with_ticket.json()["issued"] is True


async def test_does_not_accept_another_users_cookie_as_proof(
    app_client: AsyncClient, db_session: AsyncSession
) -> None:
    other = await app_client.post(
        "/api/auth/register",
        json={**REGISTER_PAYLOAD, "email": "other@example.com"},
    )
    other_cookie = other.cookies.get(REFRESH_COOKIE_NAME)
    assert other_cookie
    app_client.cookies.clear()

    me = await app_client.post("/api/auth/register", json=REGISTER_PAYLOAD)
    app_client.cookies.clear()
    r = await app_client.post(
        URL,
        headers=_bearer(me.json()["access_token"]),
        cookies={REFRESH_COOKIE_NAME: other_cookie},
    )

    assert r.status_code == 200
    assert r.json()["issued"] is True
    owner = await _user(db_session)
    minted = [t for t in await _all_tokens(db_session) if t.user_id == owner.id]
    assert len(minted) == 2


@pytest.mark.parametrize("case", ["expired", "session_replaced", "suspended", "no_sid"])
async def test_auth_gate_negatives_leave_no_cookie_and_no_row(
    case: str, app_client: AsyncClient, db_session: AsyncSession
) -> None:
    access = await _sso_like_session(app_client)
    user_id = (await _user(db_session)).id
    before = len(await _all_tokens(db_session))

    if case == "expired":
        token = create_access_token(
            user_id, ttl=-60, session_id=decode_access_token(access)["sid"]
        )
        expected = 401
    elif case == "session_replaced":
        token = create_access_token(user_id, session_id=uuid.uuid4())
        expected = 401
    elif case == "suspended":
        await db_session.execute(
            update(User).where(User.id == user_id).values(suspended_at=func.now())
        )
        token = access
        expected = 403
    else:
        token = create_access_token(user_id)
        expected = 401

    r = await app_client.post(URL, headers=_bearer(token))

    assert r.status_code == expected, r.text
    assert _set_cookie(r) == ""
    assert len(await _all_tokens(db_session)) == before


async def test_rate_limited_to_ten_per_minute_per_user(
    app_client: AsyncClient,
) -> None:
    access = await _sso_like_session(app_client)
    limiter.reset()
    limiter.enabled = True
    try:
        statuses = [
            (await app_client.post(URL, headers=_bearer(access))).status_code
            for _ in range(11)
        ]
    finally:
        limiter.enabled = False
        limiter.reset()

    assert 429 not in statuses[:10]
    assert statuses[10] == 429


async def test_extension_auth_keeps_body_tokens_and_ignores_the_web_cookie(
    app_client: AsyncClient,
) -> None:
    access = await _sso_like_session(app_client)
    bound = await app_client.post(URL, headers=_bearer(access))
    web_cookie = bound.cookies.get(REFRESH_COOKIE_NAME)
    assert web_cookie
    app_client.cookies.clear()

    login = await app_client.post(
        "/api/auth/extension/login",
        json={
            "email": REGISTER_PAYLOAD["email"],
            "password": REGISTER_PAYLOAD["password"],
        },
    )
    assert login.status_code == 200, login.text
    assert "refresh_token" in login.json()
    assert _set_cookie(login) == ""

    rotated = await app_client.post(
        "/api/auth/extension/refresh",
        json={"refresh_token": login.json()["refresh_token"]},
    )
    assert rotated.status_code == 200, rotated.text
    assert rotated.json()["refresh_token"] != login.json()["refresh_token"]
    assert _set_cookie(rotated) == ""

    # The web cookie is not an extension credential.
    smuggled = await app_client.post(
        "/api/auth/extension/refresh",
        json={"refresh_token": "not-a-real-token"},
        cookies={REFRESH_COOKIE_NAME: web_cookie},
    )
    assert smuggled.status_code == 401
    assert _set_cookie(smuggled) == ""


def test_extension_route_table_is_unchanged() -> None:
    extension_paths = sorted(
        {
            route.path  # type: ignore[attr-defined]
            for route in app.routes
            if "/extension" in getattr(route, "path", "")
            and getattr(route, "path", "").startswith("/api/auth")
        }
    )
    assert extension_paths == [
        "/api/auth/extension/callback",
        "/api/auth/extension/login",
        "/api/auth/extension/refresh",
    ]
