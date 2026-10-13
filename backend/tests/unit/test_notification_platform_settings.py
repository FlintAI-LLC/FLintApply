"""Platform notification settings."""

from app.services.career_watch.job_alert_digest import scheduled_digest_send_utc
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def test_scheduled_digest_respects_configured_hour_in_user_tz() -> None:
    utc = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    send_utc = scheduled_digest_send_utc(utc, "America/New_York", hour_local=9)
    local = send_utc.astimezone(ZoneInfo("America/New_York"))
    assert local.hour == 9
    assert local.minute == 0
