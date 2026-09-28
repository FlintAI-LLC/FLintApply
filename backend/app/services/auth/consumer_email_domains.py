"""Common free webmail domains (B2C) for stricter signup rate limits."""

from __future__ import annotations

from app.config import settings

# Major free providers — not disposable, but capped separately from work domains.
_CONSUMER_EMAIL_DOMAINS: frozenset[str] = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "yahoo.co.uk",
        "ymail.com",
        "rocketmail.com",
        "hotmail.com",
        "hotmail.co.uk",
        "outlook.com",
        "live.com",
        "msn.com",
        "icloud.com",
        "me.com",
        "mac.com",
        "aol.com",
        "proton.me",
        "protonmail.com",
        "pm.me",
        "mail.com",
        "gmx.com",
        "gmx.net",
        "gmx.de",
    }
)


def email_domain(email: str) -> str:
    normalized = email.lower().strip()
    if "@" not in normalized:
        return ""
    return normalized.rsplit("@", 1)[-1]


def is_consumer_email(email: str) -> bool:
    domain = email_domain(email)
    return bool(domain) and domain in _CONSUMER_EMAIL_DOMAINS


def is_signup_rate_limit_whitelisted(email: str) -> bool:
    domain = email_domain(email)
    if not domain:
        return False
    allowed = {d.lower().strip() for d in settings.SIGNUP_RATE_LIMIT_WHITELIST_DOMAINS if d.strip()}
    return domain in allowed


__all__ = [
    "email_domain",
    "is_consumer_email",
    "is_signup_rate_limit_whitelisted",
]
