from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import is_production_grade
from app.services.auth.client_ip import resolve_client_ip


def rate_limit_key(request: Request) -> str:
    """Bucket requests by the real client, not by the reverse proxy.

    slowapi's ``get_remote_address`` reads the socket peer. Behind Caddy
    that is the proxy for every visitor, which collapses every limit in
    the app into one shared counter — so a handful of logins would 429
    the whole site while doing nothing to bound a single abuser.
    ``resolve_client_ip`` reads ``X-Forwarded-For`` only when the peer is
    a configured trusted proxy, so the key cannot be spoofed by a client
    connecting directly.
    """
    return resolve_client_ip(request) or get_remote_address(request)


def authenticated_user_rate_limit_key(request: Request) -> str:
    """Bucket authenticated routes per user JWT, not only client IP.

    When the reverse proxy is not in ``TRUSTED_PROXY_IPS``, every visitor
    can appear as the same peer address and exhaust shared IP buckets on
    high-traffic routes like ``GET /api/auth/me``.
    """
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth[7:].strip()
        if token:
            try:
                from app.services.auth.tokens import decode_access_token

                claims = decode_access_token(token, expected_type="access")
                subject = str(claims.get("sub") or "").strip()
                if subject:
                    return f"user:{subject}"
            except Exception:  # noqa: BLE001
                return f"token:{token[:64]}"
    return rate_limit_key(request)


# Rate limits apply in ci/staging/production only — local dev should not 429 loops.
limiter = Limiter(key_func=rate_limit_key, enabled=is_production_grade())
