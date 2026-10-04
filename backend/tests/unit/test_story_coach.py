"""Unit tests for agent/story_coach.py."""
from __future__ import annotations

import pytest

from app.agent.story_coach import (
    MAX_EXCHANGES,
    _build_history_text,
    is_complete_response,
    whole_story_feedback_looks_incomplete,
)


class TestBuildHistoryText:
    def test_empty_history(self):
        result = _build_history_text([])
        assert result == "(no prior exchanges)"

    def test_single_coach_message(self):
        result = _build_history_text([{"role": "coach", "text": "How many engineers?"}])
        assert "Coach: How many engineers?" in result

    def test_multi_turn(self):
        history = [
            {"role": "coach", "text": "How many?"},
            {"role": "user", "text": "Six."},
            {"role": "coach", "text": "What was the timeline?"},
        ]
        result = _build_history_text(history)
        assert "Coach: How many?" in result
        assert "User: Six." in result
        assert "Coach: What was the timeline?" in result


class TestIsCompleteResponse:
    def test_complete_prefix_detected(self):
        assert is_complete_response("COMPLETE: This segment is already strong.") is True

    def test_complete_with_leading_whitespace(self):
        assert is_complete_response("  COMPLETE: fine") is True

    def test_regular_question_not_complete(self):
        assert is_complete_response("How many engineers were on the team?") is False

    def test_empty_string(self):
        assert is_complete_response("") is False


class TestMaxExchanges:
    def test_max_exchanges_is_three(self):
        assert MAX_EXCHANGES == 3


class TestCoachSegmentStreaming:
    @pytest.mark.asyncio
    async def test_streams_non_empty_response(self):
        """coach_segment should yield at least one non-empty delta."""

        class FakeLLMClient:
            async def stream(self, messages, max_tokens=80):
                yield "How"
                yield " many engineers were on your team?"

        from app.agent.story_coach import coach_segment

        history: list = []
        deltas = []
        async for delta in coach_segment(
            segment_text="I led the migration to Kubernetes.",
            history=history,
            llm_client=FakeLLMClient(),
        ):
            deltas.append(delta)

        assert len(deltas) > 0
        full = "".join(deltas)
        assert len(full) > 5

    @pytest.mark.asyncio
    async def test_streams_complete_sentinel(self):
        """coach_segment passes through COMPLETE: responses without error."""

        class FakeLLMClient:
            async def stream(self, messages, max_tokens=80):
                yield "COMPLETE: This segment is already strong."

        from app.agent.story_coach import coach_segment, is_complete_response

        history = [
            {"role": "coach", "text": "How many?"},
            {"role": "user", "text": "Six engineers, 3-month timeline, 40% latency reduction."},
        ]
        result = ""
        async for delta in coach_segment(
            segment_text="Led 6-engineer team, 3-month K8s migration, cut latency 40%.",
            history=history,
            llm_client=FakeLLMClient(),
        ):
            result += delta

        assert is_complete_response(result)

    @pytest.mark.asyncio
    async def test_retries_empty_stream_then_succeeds(self):
        """Empty first stream attempt is retried without yielding to the caller."""

        class FlakyLLMClient:
            def __init__(self) -> None:
                self.calls = 0

            async def stream(self, messages, max_tokens=80):
                self.calls += 1
                if self.calls == 1:
                    return
                    yield  # pragma: no cover
                yield "How many people were on the team?"

            async def complete(self, messages, max_tokens=80):
                from app.llm.base import LLMResponse

                return LLMResponse(
                    content="",
                    input_tokens=0,
                    output_tokens=0,
                    model="test",
                    provider="test",
                )

        from app.agent.story_coach import coach_segment

        client = FlakyLLMClient()
        deltas: list[str] = []
        async for delta in coach_segment(
            segment_text="I led a platform migration for our payments stack.",
            history=[],
            llm_client=client,
        ):
            deltas.append(delta)

        assert client.calls == 2
        assert "".join(deltas).strip() == "How many people were on the team?"

    @pytest.mark.asyncio
    async def test_whole_story_uses_complete_not_stream(self):
        class WholeStoryLLM:
            def __init__(self) -> None:
                self.stream_calls = 0
                self.complete_calls = 0

            async def stream(self, messages, max_tokens=2048):
                self.stream_calls += 1
                yield "should not be used"

            async def complete(self, messages, max_tokens=2048):
                self.complete_calls += 1
                from app.llm.base import LLMResponse

                return LLMResponse(
                    content="1. Add dates.\n2. Add team size.",
                    input_tokens=10,
                    output_tokens=20,
                    model="test",
                    provider="test",
                )

        from app.agent.story_coach import coach_whole_story

        client = WholeStoryLLM()
        parts: list[str] = []
        async for delta in coach_whole_story(
            ["I volunteer at the library and tutor math."],
            client,
        ):
            parts.append(delta)

        assert client.stream_calls == 0
        assert client.complete_calls == 1
        assert "".join(parts) == "1. Add dates.\n2. Add team size."


class TestWholeStoryIncompleteHeuristic:
    def test_single_bullet_mid_quote_is_incomplete(self):
        text = (
            "1. Add scope metrics for the tutoring and library volunteering: "
            "number of weeks each ran, hours per session, how many kids at reading hour, "
            "and whether either is still active as of now — the \""
        )
        assert whole_story_feedback_looks_incomplete(text)

    def test_complete_sentinel_not_incomplete(self):
        assert not whole_story_feedback_looks_incomplete("COMPLETE: Your story is detailed.")

    def test_multiple_bullets_not_incomplete(self):
        assert not whole_story_feedback_looks_incomplete(
            "1. Add dates.\n2. Add team size.\n3. Quantify impact."
        )
