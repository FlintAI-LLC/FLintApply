"""Extension-friendly auth routes (Strategy B Phase 2).

The browser extension cannot use HttpOnly cookies (service workers do not
have access to cookies), so these endpoints return the refresh token in the
JSON response body. Everything else — lockout, audit, rotation — is identical
to the web auth flow.

The cookie-vs-body design choice is documented in
``flint-extension/docs/adr/002-extension-desktop-ipc.md`` (ADR-002):
Phase 2 ships a one-way `flint://` deep link that carries only an opaque
token, so the refresh token must travel in the response body to reach
``chrome.storage.local``.

TOTP is intentionally NOT supported here. The web 2FA challenge flow is
cookie-based, and adding a parallel cookieless flow would expand auth
surface area beyond Phase 2 scope. TOTP-enrolled users get a clear
``totp_not_supported_on_extension`` error and are told to remove TOTP or
wait for Phase 3 (Supabase SSO).

Guarded by ``EXTENSION_AUTH_ENABLED`` feature flag so it can be disabled
in production before the extension is publicly released.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.engine import get_db
from app.limiter import limiter
from app.models.user import (
    AuthAuditEvent,
    AuthProvider,
    CreditTransaction,
    CreditTransactionAction,
    User,
    UserTier,
)
# Cross-router import: ``_me`` builds the canonical MeResponse from a User.
# This is a deliberate coupling — keep both routers in sync if the
# response shape changes. Renaming or moving ``_me`` will break this
# import silently at runtime.
from app.routers.auth import (
    MeResponse,
    _auth_session_id_for_refresh_token,
    _me,
)
from app.services.billing.tier_limits_lookup import registration_grant_credits
from app.services.auth import session as redis_session
from app.services.auth.audit import is_account_locked, record_auth_event
from app.services.auth.client_ip import resolve_client_ip
from app.services.auth.exceptions import (
    OAuthError,
    RefreshTokenReuseError,
    SessionReplacedError,
    TokenExpiredError,
    TokenInvalidError,
)
from app.services.auth.oauth import (
    NormalisedOAuthProfile,
    exchange_github_code,
    exchange_google_code,
    exchange_microsoft_code,
)
from app.services.auth.password import verify_password
from app.services.auth.tokens import (
    create_access_token,
    create_refresh_token,
    make_device_fingerprint,
    new_auth_session_id,
    revoke_all_user_tokens,
    rotate_refresh_token,
)

log = structlog.get_logger("auth.extension")

router = APIRouter(prefix="/api/auth/extension", tags=["auth-extension"])


def _extension_web_callback(provider: str) -> str:
    return f"{settings.FRONTEND_BASE_URL.rstrip('/')}/auth/extension/{provider}/callback"


def _is_valid_extension_redirect_uri(redirect_uri: str, provider: str) -> bool:
    """Accept only the legitimate redirect URI(s) for ``provider``.

    Chrome uses chrome.identity.getRedirectURL() which returns a URI of the
    form ``https://<ext-id>.chromiumapp.org/``.  Google already validates that
    this matches the registered OAuth client, so a suffix-check here is safe
    -- but ONLY for Google. GitHub OAuth Apps allow exactly one registered
    callback URL (no wildcards), so a github/microsoft code paired with a
    chromiumapp.org redirect_uri must be rejected outright: there is no
    provider-side registration that URI could ever match, and accepting it
    here would let a caller skip the tab-callback code path entirely.

    Firefox (and, for github/microsoft, every browser) uses the dedicated
    web-app callback registered with that provider's OAuth app.
    """
    normalised = redirect_uri.rstrip("/")
    web_callback = _extension_web_callback(provider)
    if normalised == web_callback:
        return True
    if provider == "google" and (
        normalised.endswith(".chromiumapp.org") or ".chromiumapp.org/" in redirect_uri
    ):
        return True
    return False


def _validate_extension_oauth_redirect(redirect_uri: str, provider: str) -> None:
    if not _is_valid_extension_redirect_uri(redirect_uri, provider):
        web_callback = _extension_web_callback(provider)
        message = f"redirect_uri must be {web_callback}"
        if provider == "google":
            message += " (Firefox) or a *.chromiumapp.org URL (Chrome)"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_redirect_uri",
                "message": message,
            },
        )



class ExtensionLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=200)


class ExtensionRefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1, max_length=512)


class ExtensionOAuthCallbackRequest(BaseModel):
    provider: Literal["google", "github", "microsoft"]
    code: str = Field(..., min_length=1, max_length=4096)
    redirect_uri: str = Field(..., min_length=1, max_length=1024)


class ExtensionAuthResponse(BaseModel):
    """Access + refresh tokens returned in the JSON body (no cookie)."""

    access_token: str
    refresh_token: str
    expires_in: int
    user: MeResponse


def _client_ip(request: Request) -> str:
    """Client IP for extension device fingerprints and login records.

    Reading the socket peer directly would record the reverse proxy for
    every extension user, collapsing distinct devices onto one
    fingerprint.
    """
    return resolve_client_ip(request)


def _user_agent(request: Request) -> str:
    return request.headers.get("user-agent", "")


def _fingerprint(request: Request) -> str:
    return make_device_fingerprint(_user_agent(request), _client_ip(request))


def _require_enabled() -> None:
    if not settings.EXTENSION_AUTH_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "extension_auth_disabled"},
        )


async def _issue_extension_session(
    db: AsyncSession,
    request: Request,
    user: User,
) -> ExtensionAuthResponse:
    auth_session_id = new_auth_session_id()
    await revoke_all_user_tokens(db, user_id=user.id)
    await redis_session.revoke_all_user_tokens(user.id)
    await redis_session.set_active_auth_session(
        user.id,
        auth_session_id,
        ttl=settings.REFRESH_TOKEN_TTL_SECONDS,
    )
    access = create_access_token(
        user.id,
        ttl=settings.ACCESS_TOKEN_TTL_SECONDS,
        session_id=auth_session_id,
    )
    device_fp = _fingerprint(request)
    issued = await create_refresh_token(
        db,
        user_id=user.id,
        device_fingerprint=device_fp,
        ttl_seconds=settings.REFRESH_TOKEN_TTL_SECONDS,
    )
    await redis_session.bind_refresh_token_to_redis(
        issued.token_id,
        user.id,
        device_fp,
        ttl=settings.REFRESH_TOKEN_TTL_SECONDS,
        auth_session_id=auth_session_id,
    )
    user.last_login_at = datetime.now(timezone.utc)
    # flush() pushes the last_login_at update + refresh token row to the
    # connection. The transaction commit is owned by the get_db dependency
    # (see app/db/engine.py): it commits on successful response, rolls
    # back on any exception. If a downstream raise happens after this
    # flush, the rollback restores the prior last_login_at value.
    await db.flush()
    return ExtensionAuthResponse(
        access_token=access,
        refresh_token=issued.token,
        expires_in=settings.ACCESS_TOKEN_TTL_SECONDS,
        user=_me(user),
    )


@router.post("/login", response_model=ExtensionAuthResponse)
@limiter.limit("10/minute")
async def extension_login(
    request: Request,
    payload: ExtensionLoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExtensionAuthResponse:
    """Authenticate and return tokens in the response body.

    Identical lockout and audit semantics to ``POST /api/auth/login``.
    Refresh token is in the JSON body so service workers can store it
    in ``chrome.storage.local``.
    """
    _require_enabled()

    email = payload.email.lower().strip()
    user = (
        await db.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()

    if user is None or user.auth_provider != AuthProvider.email:
        verify_password(payload.password, None)
        await record_auth_event(
            db,
            user_id=None,
            event=AuthAuditEvent.login_failure,
            ip=_client_ip(request),
            user_agent=_user_agent(request),
            metadata={"reason": "unknown_email", "source": "extension"},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials"},
        )

    if user.is_suspended:
        await record_auth_event(
            db,
            user_id=user.id,
            event=AuthAuditEvent.login_failure,
            ip=_client_ip(request),
            user_agent=_user_agent(request),
            metadata={"reason": "suspended", "source": "extension"},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "account_suspended"},
        )

    if await is_account_locked(db, user_id=user.id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "account_locked"},
        )

    if not verify_password(payload.password, user.password_hash):
        await record_auth_event(
            db,
            user_id=user.id,
            event=AuthAuditEvent.login_failure,
            ip=_client_ip(request),
            user_agent=_user_agent(request),
            metadata={"reason": "bad_password", "source": "extension"},
        )
        await db.commit()
        # Re-evaluate lockout AFTER recording the failure so a threshold-
        # crossing failure surfaces 429 on the same call instead of 401
        # now and 429 on the next attempt. Mirrors the web flow's
        # _process_failed_login behavior without the cross-router import.
        if await is_account_locked(db, user_id=user.id):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"code": "account_locked"},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials"},
        )

    if user.has_totp:
        # See module docstring: TOTP enrolment uses the cookie-based 2fa
        # challenge flow which the extension cannot participate in. Reject
        # cleanly so the popup can show actionable guidance instead of
        # silently falling through to a half-authenticated session.
        await record_auth_event(
            db,
            user_id=user.id,
            event=AuthAuditEvent.login_failure,
            ip=_client_ip(request),
            user_agent=_user_agent(request),
            metadata={"reason": "totp_required", "source": "extension"},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "totp_not_supported_on_extension"},
        )

    await record_auth_event(
        db,
        user_id=user.id,
        event=AuthAuditEvent.login_success,
        ip=_client_ip(request),
        user_agent=_user_agent(request),
        metadata={"reason": "password", "source": "extension"},
    )
    return await _issue_extension_session(db, request, user)


@router.post("/refresh", response_model=ExtensionAuthResponse)
@limiter.limit("30/minute")
async def extension_refresh(
    request: Request,
    payload: ExtensionRefreshRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExtensionAuthResponse:
    """Rotate a refresh token. Body-based, no cookies.

    Rotation semantics are identical to ``POST /api/auth/refresh``:
    the old token is revoked, a new access + refresh pair is issued.
    """
    _require_enabled()

    device_fp = _fingerprint(request)
    auth_session_id = await _auth_session_id_for_refresh_token(
        db, payload.refresh_token
    )
    try:
        issued = await rotate_refresh_token(
            db,
            token=payload.refresh_token,
            device_fingerprint=device_fp,
            ttl_seconds=settings.REFRESH_TOKEN_TTL_SECONDS,
        )
    except SessionReplacedError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "session_replaced"},
        ) from None
    except RefreshTokenReuseError as exc:
        if exc.user_id:
            try:
                await record_auth_event(
                    db,
                    user_id=uuid.UUID(exc.user_id),
                    event=AuthAuditEvent.suspicious_login,
                    ip=_client_ip(request),
                    user_agent=_user_agent(request),
                    metadata={"reason": "refresh_token_reuse", "source": "extension"},
                )
            except Exception:  # pragma: no cover
                pass
            await db.commit()
            await redis_session.revoke_all_user_tokens(exc.user_id)
        else:
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "refresh_token_reuse"},
        ) from exc
    except TokenExpiredError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "refresh_token_expired"},
        ) from None
    except TokenInvalidError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "refresh_token_invalid"},
        ) from None

    user = (
        await db.execute(select(User).where(User.id == issued.row.user_id))
    ).scalar_one_or_none()
    if user is None or user.is_suspended:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "account_suspended"},
        )

    await redis_session.bind_refresh_token_to_redis(
        issued.token_id,
        user.id,
        device_fp,
        ttl=settings.REFRESH_TOKEN_TTL_SECONDS,
        auth_session_id=auth_session_id,
    )
    access = create_access_token(
        user.id,
        ttl=settings.ACCESS_TOKEN_TTL_SECONDS,
        session_id=auth_session_id,
    )
    return ExtensionAuthResponse(
        access_token=access,
        refresh_token=issued.token,
        expires_in=settings.ACCESS_TOKEN_TTL_SECONDS,
        user=_me(user),
    )


async def _exchange_oauth_code(
    provider: str, code: str, redirect_uri: str
) -> NormalisedOAuthProfile:
    """Dispatch to the provider's code-exchange helper.

    Deliberately NOT a ``{provider: function}`` dict built at import time:
    that would capture the original function objects as closures, and
    ``monkeypatch.setattr("app.routers.extension_auth.exchange_github_code",
    ...)`` (used by tests) only rebinds the module's global name -- it would
    never be seen by a dict that already holds the pre-patch reference. A
    plain call by name re-resolves the module global on every invocation, so
    it stays patchable.
    """
    if provider == "google":
        return await exchange_google_code(code, redirect_uri)
    if provider == "github":
        return await exchange_github_code(code, redirect_uri)
    if provider == "microsoft":
        return await exchange_microsoft_code(code, redirect_uri)
    raise AssertionError(f"unhandled provider: {provider}")  # pragma: no cover


@router.post("/callback", response_model=ExtensionAuthResponse)
@limiter.limit("10/minute")
async def extension_oauth_callback(
    request: Request,
    payload: ExtensionOAuthCallbackRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ExtensionAuthResponse:
    """Exchange a provider OAuth code for extension tokens (body-based, no cookie).

    Google, GitHub, and Microsoft each land the browser at
    ``{FRONTEND_BASE_URL}/auth/extension/{provider}/callback`` after the user
    authorizes. Google additionally accepts a ``*.chromiumapp.org`` redirect
    on Chrome (``chrome.identity``); GitHub and Microsoft never do — see
    ``_is_valid_extension_redirect_uri`` for why that is a hard architectural
    line, not an oversight.
    """
    _require_enabled()
    provider = payload.provider
    _validate_extension_oauth_redirect(payload.redirect_uri, provider)

    try:
        profile = await _exchange_oauth_code(provider, payload.code, payload.redirect_uri)
    except OAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "oauth_failed", "message": str(exc)},
        ) from exc

    # AuthProvider(provider) directly, like app/routers/auth.py's web OAuth
    # callback (see `provider_enum = AuthProvider(payload.provider)`) —
    # avoids a second provider->enum mapping in this module that could
    # silently drift out of sync with the AuthProvider enum itself.
    auth_provider = AuthProvider(provider)

    user = (
        await db.execute(
            select(User).where(
                User.auth_provider == auth_provider,
                User.provider_id == profile["provider_id"],
            )
        )
    ).scalar_one_or_none()

    if user is None:
        existing = (
            await db.execute(select(User).where(User.email == profile["email"]))
        ).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "email_already_registered",
                    "with_provider": existing.auth_provider.value,
                },
            )
        grant_amount = await registration_grant_credits(db)
        user = User(
            id=uuid.uuid4(),
            email=profile["email"],
            display_name=profile["display_name"] or profile["email"].split("@", 1)[0],
            auth_provider=auth_provider,
            provider_id=profile["provider_id"],
            email_verified_at=datetime.now(timezone.utc),
            tier=UserTier.free,
            credit_balance=grant_amount,
            accepted_tos_version="oauth",
            last_login_ip=_client_ip(request) or None,
        )
        db.add(user)
        await db.flush()
        db.add(
            CreditTransaction(
                id=uuid.uuid4(),
                user_id=user.id,
                delta=grant_amount,
                action=CreditTransactionAction.registration_grant,
                reason="registration_grant",
                note=f"registration grant via {provider} (extension)",
            )
        )
        await db.flush()

    if user.is_suspended:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "account_suspended"},
        )

    await record_auth_event(
        db,
        user_id=user.id,
        event=AuthAuditEvent.login_success,
        ip=_client_ip(request),
        user_agent=_user_agent(request),
        metadata={"provider": provider, "source": "extension"},
    )
    return await _issue_extension_session(db, request, user)
