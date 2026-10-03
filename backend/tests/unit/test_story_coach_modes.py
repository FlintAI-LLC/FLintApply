"""Coach mode request validation and tier authorization helpers."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.story import CoachRequest


def test_whole_story_request_accepts_segments() -> None:
    req = CoachRequest(
        coach_mode="whole_story",
        segments=["I led a team of six engineers on a migration project."],
        session_id="build-1",
    )
    assert req.coach_mode == "whole_story"


def test_whole_story_rejects_history() -> None:
    with pytest.raises(ValidationError):
        CoachRequest(
            coach_mode="whole_story",
            segments=["I led a team of six engineers on a migration project."],
            history=[{"role": "coach", "text": "How many?"}],
        )


def test_segment_mode_requires_segment_text() -> None:
    with pytest.raises(ValidationError):
        CoachRequest(coach_mode="segment", segment_text="short")
