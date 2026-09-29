"""Unit tests for extension auth routes (Strategy B Phase 2).

These tests rely on the shared ``app_client`` fixture which auto-skips
when ``DATABASE_URL`` is not configured.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import AuthProvider, CreditTransaction, User
from app.services.auth.oauth import NormalisedOAuthProfile
from tests.integration.test_auth import REGISTER_PAYLOAD


pytestmark = pytest.mark.integration


def _fake_profile(
    *, email: str, provider_id: str, display_name: str = "OAuth Person"
) -> NormalisedOAuthProfile:
    return {
        "email": email,
        "provider_id": provider_id,
        "display_name": display_name,
        "email_verified": True,
    }


def _patch_exchange(
    monkeypatch: pytest.MonkeyPatch,
    *,
    google: NormalisedOAuthProfile | None = None,
    github: NormalisedOAuthProfile | None = None,
    microsoft: NormalisedOAuthProfile | None = None,
) -> dict[str, list[tuple[str, str]]]:
    """Monkeypatch the code-exchange helpers imported into the router module.

    Returns a dict of call-log lists so tests can assert whether the
    (mocked) exchange function was actually invoked -- used to prove
    redirect_uri validation happens BEFORE any token exchange call.
    """
    calls: dict[str, list[tuple[str, str]]] = {
        "google": [],
        "github": [],
        "microsoft": [],
    }

    async def _fake_google(code: str, redirect_uri: str) -> NormalisedOAuthProfile:
        calls["google"].append((code, redirect_uri))
        assert google is not None
        return google

    async def _fake_github(code: str, redirect_uri: str) -> NormalisedOAuthProfile:
        calls["github"].append((code, redirect_uri))
        assert github is not None
        return github

    async def _fake_microsoft(code: str, redirect_uri: str) -> NormalisedOAuthProfile:
        calls["microsoft"].append((code, redirect_uri))
        assert microsoft is not None
        return microsoft

    monkeypatch.setattr(
        "app.routers.extension_auth.exchange_google_code", _fake_google
    )
    monkeypatch.setattr(
        "app.routers.extension_auth.exchange_github_code", _fake_github
    )
    monkeypatch.setattr(
        "app.routers.extension_auth.exchange_microsoft_code", _fake_microsoft
    )
    return calls


def _google_callback_uri() -> str:
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}/auth/extension/google/callback"


def _github_callback_uri() -> str:
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}/auth/extension/github/callback"


def _microsoft_callback_uri() -> str:
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}/auth/extension/microsoft/callback"


async def _register(client: AsyncClient, suffix: str = "") -> tuple[str, str]:
    """Register a user and return (access_token, email)."""
    email = f"ext-{suffix or 'test'}@example.com"
    payload = {**REGISTER_PAYLOAD, "email": email}
    r = await client.post("/api/auth/register", json=payload)
    assert r.status_code == 201, r.text
    return r.json()["access_token"], email


@pytest.mark.asyncio
async def test_extension_login_returns_tokens_in_body(app_client: AsyncClient) -> None:
    _, email = await _register(app_client, "login")
    r = await app_client.post(
        "/api/auth/extension/login",
        json={"email": email, "password": REGISTER_PAYLOAD["password"]},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["expires_in"] > 0
    assert body["user"]["email"] == email
    # Verify no Set-Cookie header (extension never uses cookies).
    assert "set-cookie" not in {k.lower() for k in r.headers}


@pytest.mark.asyncio
async def test_extension_login_invalid_credentials(app_client: AsyncClient) -> None:
    _, email = await _register(app_client, "badpw")
    r = await app_client.post(
        "/api/auth/extension/login",
        json={"email": email, "password": "wrongpassword1"},
    )
    assert r.status_code == 401
    assert r.json()["detail"]["code"] == "invalid_credentials"


@pytest.mark.asyncio
async def test_extension_login_unknown_email(app_client: AsyncClient) -> None:
    r = await app_client.post(
        "/api/auth/extension/login",
        json={"email": "nobody@example.com", "password": "somepassword1"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_extension_refresh_rotates_token(app_client: AsyncClient) -> None:
    _, email = await _register(app_client, "refresh")
    login_r = await app_client.post(
        "/api/auth/extension/login",
        json={"email": email, "password": REGISTER_PAYLOAD["password"]},
    )
    assert login_r.status_code == 200
    refresh_token = login_r.json()["refresh_token"]

    refresh_r = await app_client.post(
        "/api/auth/extension/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_r.status_code == 200, refresh_r.text
    new_body = refresh_r.json()
    assert "access_token" in new_body
    assert "refresh_token" in new_body
    # Rotated token must differ from the original.
    assert new_body["refresh_token"] != refresh_token


@pytest.mark.asyncio
async def test_extension_refresh_reuse_is_rejected(app_client: AsyncClient) -> None:
    _, email = await _register(app_client, "reuse")
    login_r = await app_client.post(
        "/api/auth/extension/login",
        json={"email": email, "password": REGISTER_PAYLOAD["password"]},
    )
    refresh_token = login_r.json()["refresh_token"]

    # First refresh — OK.
    await app_client.post(
        "/api/auth/extension/refresh",
        json={"refresh_token": refresh_token},
    )

    # Second refresh with the same (now-revoked) token.
    reuse_r = await app_client.post(
        "/api/auth/extension/refresh",
        json={"refresh_token": refresh_token},
    )
    assert reuse_r.status_code == 401
    assert reuse_r.json()["detail"]["code"] in (
        "refresh_token_reuse",
        "refresh_token_invalid",
    )


@pytest.mark.asyncio
async def test_extension_refresh_invalid_token(app_client: AsyncClient) -> None:
    r = await app_client.post(
        "/api/auth/extension/refresh",
        json={"refresh_token": "totally-invalid-token-value"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_extension_login_disabled_flag_returns_403(
    app_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When EXTENSION_AUTH_ENABLED=False, both routes return 403, not 404.

    The point is to fail closed without leaking endpoint existence to a
    scanner: a 404 would imply "no such route ever", a 403 implies "route
    exists but disabled". 403 is the honest answer.
    """
    monkeypatch.setattr(settings, "EXTENSION_AUTH_ENABLED", False)

    r = await app_client.post(
        "/api/auth/extension/login",
        json={"email": "anyone@example.com", "password": "doesnotmatter1"},
    )
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "extension_auth_disabled"

    r2 = await app_client.post(
        "/api/auth/extension/refresh",
        json={"refresh_token": "anything"},
    )
    assert r2.status_code == 403
    assert r2.json()["detail"]["code"] == "extension_auth_disabled"


@pytest.mark.asyncio
async def test_extension_login_rejects_totp_user(
    app_client: AsyncClient,
    db_session: AsyncSession,
) -> None:
    """TOTP-enrolled users must not be issued tokens by the extension flow.

    The web flow returns a 2fa_challenge token which depends on cookies the
    extension cannot use. Phase 2 deliberately rejects TOTP users with a
    distinct error code so the popup can surface actionable guidance.
    """
    _, email = await _register(app_client, "totp")

    user = (
        await db_session.execute(
            User.__table__.select().where(User.email == email)
        )
    ).first()
    assert user is not None
    user_id = user.id

    # Flip has_totp directly. We do not exercise the full enrolment flow
    # because that requires a TOTP code round-trip; the route under test
    # only inspects user.has_totp.
    db_user = await db_session.get(User, user_id)
    assert db_user is not None
    db_user.totp_secret = b"encrypted-placeholder"
    db_user.totp_recovery_codes = ["$2b$12$placeholder.hash.for.test"]
    await db_session.commit()

    r = await app_client.post(
        "/api/auth/extension/login",
        json={"email": email, "password": REGISTER_PAYLOAD["password"]},
    )
    assert r.status_code == 403
    assert r.json()["detail"]["code"] == "totp_not_supported_on_extension"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider", "auth_provider_enum"),
    [
        ("github", AuthProvider.github),
        ("microsoft", AuthProvider.microsoft),
    ],
)
async def test_extension_oauth_callback_creates_new_user(
    app_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    auth_provider_enum: AuthProvider,
) -> None:
    """A mocked github/microsoft OAuth code creates a new user with the
    correct AuthProvider, a registration credit grant, and returns tokens
    -- the same shape the (already-existing) Google path relies on.
    """
    email = f"new-{provider}-user@example.com"
    provider_id = f"{provider}-sub-{uuid.uuid4()}"
    profile = _fake_profile(email=email, provider_id=provider_id)
    _patch_exchange(
        monkeypatch,
        github=profile if provider == "github" else None,
        microsoft=profile if provider == "microsoft" else None,
    )

    redirect_uri = (
        _github_callback_uri() if provider == "github" else _microsoft_callback_uri()
    )
    r = await app_client.post(
        "/api/auth/extension/callback",
        json={
            "provider": provider,
            "code": "fake-oauth-code",
            "redirect_uri": redirect_uri,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["user"]["email"] == email

    user = (
        await db_session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    assert user is not None
    assert user.auth_provider == auth_provider_enum
    assert user.provider_id == provider_id
    assert user.credit_balance > 0

    txn = (
        await db_session.execute(
            select(CreditTransaction).where(CreditTransaction.user_id == user.id)
        )
    ).scalar_one_or_none()
    assert txn is not None
    assert txn.note == f"registration grant via {provider} (extension)"


@pytest.mark.asyncio
async def test_extension_oauth_callback_rejects_cross_provider_redirect_uri(
    app_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A valid github code posted with the microsoft callback URL (and vice
    versa) must be rejected with 400 invalid_redirect_uri BEFORE any token
    exchange is attempted.
    """
    profile = _fake_profile(email="cross-provider@example.com", provider_id="whatever")
    calls = _patch_exchange(monkeypatch, github=profile, microsoft=profile)

    # GitHub code + Microsoft's callback URL.
    r = await app_client.post(
        "/api/auth/extension/callback",
        json={
            "provider": "github",
            "code": "fake-github-code",
            "redirect_uri": _microsoft_callback_uri(),
        },
    )
    assert r.status_code == 400, r.text
    assert r.json()["detail"]["code"] == "invalid_redirect_uri"
    assert calls["github"] == []

    # Microsoft code + Google's chromiumapp.org redirect URI (must also be
    # rejected -- chromiumapp.org is Google-only).
    r2 = await app_client.post(
        "/api/auth/extension/callback",
        json={
            "provider": "microsoft",
            "code": "fake-microsoft-code",
            "redirect_uri": "https://abcdefghijklmnopabcdefghijklmnop.chromiumapp.org/",
        },
    )
    assert r2.status_code == 400, r2.text
    assert r2.json()["detail"]["code"] == "invalid_redirect_uri"
    assert calls["microsoft"] == []


@pytest.mark.asyncio
async def test_extension_oauth_callback_rejects_unknown_provider(
    app_client: AsyncClient,
) -> None:
    """A provider value outside the Literal must fail pydantic validation
    (422), not reach any application logic.
    """
    r = await app_client.post(
        "/api/auth/extension/callback",
        json={
            "provider": "linkedin",
            "code": "whatever",
            "redirect_uri": "https://example.com/auth/extension/linkedin/callback",
        },
    )
    assert r.status_code == 422, r.text


@pytest.mark.asyncio
async def test_extension_oauth_callback_email_collision_reports_existing_provider(
    app_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An existing google-registered user's email colliding with a new
    github signup attempt must return 409 with with_provider: "google" --
    the EXISTING user's provider, not the incoming github attempt.
    """
    collision_email = "collision-google-github@example.com"

    existing = User(
        id=uuid.uuid4(),
        email=collision_email,
        display_name="Existing Google User",
        auth_provider=AuthProvider.google,
        provider_id="google-sub-existing",
        credit_balance=0,
        accepted_tos_version="oauth",
    )
    db_session.add(existing)
    await db_session.commit()

    profile = _fake_profile(email=collision_email, provider_id="github-sub-new")
    calls = _patch_exchange(monkeypatch, github=profile)

    r = await app_client.post(
        "/api/auth/extension/callback",
        json={
            "provider": "github",
            "code": "fake-github-code",
            "redirect_uri": _github_callback_uri(),
        },
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "email_already_registered"
    assert r.json()["detail"]["with_provider"] == "google"
    # The exchange DID run here (validation passed); this test targets the
    # post-exchange collision branch, not pre-exchange validation.
    assert len(calls["github"]) == 1


@pytest.mark.asyncio
async def test_extension_oauth_callback_same_provider_email_match_logs_in(
    app_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Website Microsoft user with a different stored provider_id can sign in
    via the extension (Graph id may differ from id_token oid on first web signup).
    """
    email = "ms-extension-link@example.com"
    existing = User(
        id=uuid.uuid4(),
        email=email,
        display_name="MS Web User",
        auth_provider=AuthProvider.microsoft,
        provider_id="legacy-oid-from-web",
        credit_balance=0,
        accepted_tos_version="oauth",
    )
    db_session.add(existing)
    await db_session.commit()

    profile = _fake_profile(email=email, provider_id="graph-id-from-extension")
    calls = _patch_exchange(monkeypatch, microsoft=profile)

    r = await app_client.post(
        "/api/auth/extension/callback",
        json={
            "provider": "microsoft",
            "code": "fake-ms-code",
            "redirect_uri": _microsoft_callback_uri(),
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user"]["email"] == email
    assert len(calls["microsoft"]) == 1

    await db_session.refresh(existing)
    assert existing.provider_id == "graph-id-from-extension"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "redirect_uri",
    [
        # Web (Firefox) callback -- the FRONTEND_BASE_URL route.
        pytest.param(_google_callback_uri(), id="web_callback"),
        # Chrome chrome.identity.getRedirectURL() shape.
        pytest.param(
            "https://abcdefghijklmnopabcdefghijklmnop.chromiumapp.org/",
            id="chromiumapp_org",
        ),
    ],
)
async def test_extension_oauth_callback_google_accepts_both_redirect_shapes(
    app_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    redirect_uri: str,
) -> None:
    """Regression test for the github/microsoft provider-gate refactor:
    Google must still accept BOTH its web callback (Firefox tab flow) AND a
    ``*.chromiumapp.org`` redirect_uri (Chrome chrome.identity flow) --
    nothing about adding github/microsoft should have narrowed Google's own
    ``_is_valid_extension_redirect_uri`` allowance.
    """
    email = f"google-regress-{uuid.uuid4()}@example.com"
    provider_id = f"google-sub-{uuid.uuid4()}"
    profile = _fake_profile(email=email, provider_id=provider_id)
    calls = _patch_exchange(monkeypatch, google=profile)

    r = await app_client.post(
        "/api/auth/extension/callback",
        json={
            "provider": "google",
            "code": "fake-google-code",
            "redirect_uri": redirect_uri,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "access_token" in body
    assert body["user"]["email"] == email
    assert len(calls["google"]) == 1

    user = (
        await db_session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    assert user is not None
    assert user.auth_provider == AuthProvider.google
    assert user.provider_id == provider_id


@pytest.mark.asyncio
async def test_extension_oauth_callback_same_provider_id_different_providers_do_not_cross_match(
    app_client: AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A github user and a microsoft user that happen to share the same
    literal ``provider_id`` string value must be treated as two distinct
    accounts -- the user-lookup SELECT filters on
    ``(auth_provider, provider_id)`` together, not ``provider_id`` alone.
    """
    shared_provider_id = "12345"
    github_email = f"github-shared-{uuid.uuid4()}@example.com"
    microsoft_email = f"microsoft-shared-{uuid.uuid4()}@example.com"

    github_profile = _fake_profile(
        email=github_email, provider_id=shared_provider_id
    )
    calls = _patch_exchange(monkeypatch, github=github_profile)
    r1 = await app_client.post(
        "/api/auth/extension/callback",
        json={
            "provider": "github",
            "code": "fake-github-code",
            "redirect_uri": _github_callback_uri(),
        },
    )
    assert r1.status_code == 200, r1.text
    github_user_id = r1.json()["user"]["id"]

    microsoft_profile = _fake_profile(
        email=microsoft_email, provider_id=shared_provider_id
    )
    calls2 = _patch_exchange(monkeypatch, microsoft=microsoft_profile)
    r2 = await app_client.post(
        "/api/auth/extension/callback",
        json={
            "provider": "microsoft",
            "code": "fake-microsoft-code",
            "redirect_uri": _microsoft_callback_uri(),
        },
    )
    assert r2.status_code == 200, r2.text
    microsoft_user_id = r2.json()["user"]["id"]

    # Two distinct accounts, not one reused across providers.
    assert github_user_id != microsoft_user_id
    assert len(calls["github"]) == 1
    assert len(calls2["microsoft"]) == 1

    github_user = (
        await db_session.execute(select(User).where(User.email == github_email))
    ).scalar_one_or_none()
    microsoft_user = (
        await db_session.execute(
            select(User).where(User.email == microsoft_email)
        )
    ).scalar_one_or_none()
    assert github_user is not None
    assert microsoft_user is not None
    assert github_user.id != microsoft_user.id
    assert github_user.auth_provider == AuthProvider.github
    assert microsoft_user.auth_provider == AuthProvider.microsoft
    assert github_user.provider_id == shared_provider_id
    assert microsoft_user.provider_id == shared_provider_id
