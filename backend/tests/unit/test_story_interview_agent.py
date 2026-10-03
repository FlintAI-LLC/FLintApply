"""Unit tests for coached interview question streaming."""

from __future__ import annotations

from typing import AsyncIterator

import pytest

from app.agent.story_interview import next_interview_question, resolve_interview_question_cap
from app.llm.base import LLMClient, LLMMessage, LLMResponse


class _FlakyStreamClient(LLMClient):
    def __init__(self, streams: list[list[str]]) -> None:
        self._streams = streams
        self._call = 0

    @property
    def context_window(self) -> int:
        return 128_000

    @property
    def supports_structured_output(self) -> bool:
        return False

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock"

    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        response_schema: dict | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMResponse:
        raise NotImplementedError

    async def stream(
        self,
        messages: list[LLMMessage],
        *,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> AsyncIterator[str]:
        idx = self._call
        self._call += 1
        chunks = self._streams[idx] if idx < len(self._streams) else []
        for piece in chunks:
            yield piece


@pytest.mark.asyncio
async def test_next_interview_question_retries_empty_stream() -> None:
    client = _FlakyStreamClient([[], ["What metric improved next?"]])
    parts: list[str] = []
    async for delta in next_interview_question([], client):
        parts.append(delta)
    assert "".join(parts) == "What metric improved next?"
    assert client._call == 2


def test_resolve_interview_question_cap() -> None:
    assert resolve_interview_question_cap(0) == 15
    assert resolve_interview_question_cap(1) == 20
    assert resolve_interview_question_cap(99) == 20
