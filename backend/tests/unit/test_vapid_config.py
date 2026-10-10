"""VAPID env normalization."""

from app.config import Settings


def test_vapid_private_key_unescapes_literal_newlines() -> None:
    one_line = "-----BEGIN PRIVATE KEY-----\\nABC\\n-----END PRIVATE KEY-----"
    s = Settings(
        WEB_PUSH_VAPID_PRIVATE_KEY=one_line,
        WEB_PUSH_VAPID_PUBLIC_KEY="pub",
        WEB_PUSH_VAPID_SUBJECT="mailto:a@b.com",
    )
    assert "\nABC\n" in s.WEB_PUSH_VAPID_PRIVATE_KEY
    assert "\\n" not in s.WEB_PUSH_VAPID_PRIVATE_KEY
