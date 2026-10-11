"""Regression: long multi-state locations must not break ingest."""

from app.services.career_watch.corpus_sync import _truncate_field


def test_truncate_field_logs_long_location_safety() -> None:
    long_location = ", ".join([f"State-{index}" for index in range(1200)])
    truncated = _truncate_field(long_location, max_len=8000, field="location")
    assert len(truncated) <= 8000
    assert truncated.endswith("...")


def test_truncate_field_keeps_short_values() -> None:
    value = "Remote, US"
    assert _truncate_field(value, max_len=8000, field="location") == value
