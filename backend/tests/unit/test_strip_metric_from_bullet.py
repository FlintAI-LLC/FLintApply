"""Regression: metric strip must not leave dangling en-dash ranges."""

from __future__ import annotations

from app.agent.phase3_truthfulness import _strip_metric_from_bullet


def test_strip_metric_from_bullet_range_leaves_no_trailing_dash() -> None:
    bullet = "improving performance 10–15% across services"
    cleaned = _strip_metric_from_bullet(bullet, "10–15%")
    assert cleaned.endswith("–") is False
    assert cleaned.endswith("—") is False
    assert "10" not in cleaned or "across" in cleaned
    assert cleaned.strip().endswith("services")
