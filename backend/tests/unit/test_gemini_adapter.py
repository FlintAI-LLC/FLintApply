"""Unit tests for Gemini 3.x adapter helpers."""
from types import SimpleNamespace

import pytest

from app.llm.base import LLMMessage
from app.llm.providers.gemini_adapter import GeminiAdapter


def test_gemini_3_expands_output_token_cap():
    adapter = GeminiAdapter(model="gemini-3.6-flash", api_key="test-key")
    assert adapter._output_token_cap(1500) == 4096


def test_gemini_25_keeps_requested_cap():
    adapter = GeminiAdapter(model="gemini-2.5-flash", api_key="test-key")
    assert adapter._output_token_cap(1500) == 1500


def test_visible_text_skips_thought_parts():
    adapter = GeminiAdapter(model="gemini-3.6-flash", api_key="test-key")
    resp = SimpleNamespace(
        text="",
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[
                        SimpleNamespace(thought=True, text="hidden reasoning"),
                        SimpleNamespace(thought=False, text="PROFESSIONAL SUMMARY\nEngineer"),
                    ]
                )
            )
        ],
    )
    assert adapter._visible_text(resp) == "PROFESSIONAL SUMMARY\nEngineer"


@pytest.mark.asyncio
async def test_stream_yields_visible_text_after_thought_only_chunks():
    adapter = GeminiAdapter(model="gemini-3.5-flash", api_key="test-key")

    thought_chunk = SimpleNamespace(
        usage_metadata=None,
        text="",
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[SimpleNamespace(thought=True, text="internal reasoning")]
                )
            )
        ],
    )
    visible_chunk = SimpleNamespace(
        usage_metadata=None,
        text="",
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[SimpleNamespace(thought=False, text="1. Add dates for volunteer work.")]
                )
            )
        ],
    )

    class _FakeStream:
        def __aiter__(self):
            self._items = [thought_chunk, visible_chunk]
            return self

        async def __anext__(self):
            if not self._items:
                raise StopAsyncIteration
            return self._items.pop(0)

    async def _fake_generate(*_args, **_kwargs):
        return _FakeStream()

    import app.llm.providers.gemini_adapter as gemini_mod

    original = gemini_mod.genai.GenerativeModel

    class _FakeModel:
        def __init__(self, *args, **kwargs):
            pass

        async def generate_content_async(self, *args, **kwargs):
            return await _fake_generate()

    gemini_mod.genai.GenerativeModel = _FakeModel
    try:
        parts: list[str] = []
        async for delta in adapter.stream(
            [LLMMessage(role="user", content="review my story")],
            max_tokens=256,
        ):
            parts.append(delta)
    finally:
        gemini_mod.genai.GenerativeModel = original

    assert "".join(parts) == "1. Add dates for volunteer work."


@pytest.mark.asyncio
async def test_stream_emits_incremental_suffix_when_chunks_are_cumulative():
    adapter = GeminiAdapter(model="gemini-3.5-flash", api_key="test-key")

    chunk_a = SimpleNamespace(
        usage_metadata=None,
        text="",
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[SimpleNamespace(thought=False, text="1. First")]
                )
            )
        ],
    )
    chunk_b = SimpleNamespace(
        usage_metadata=None,
        text="",
        candidates=[
            SimpleNamespace(
                content=SimpleNamespace(
                    parts=[SimpleNamespace(thought=False, text="1. First bullet.")]
                )
            )
        ],
    )

    class _FakeStream:
        def __aiter__(self):
            self._items = [chunk_a, chunk_b]
            return self

        async def __anext__(self):
            if not self._items:
                raise StopAsyncIteration
            return self._items.pop(0)

    async def _fake_generate(*_args, **_kwargs):
        return _FakeStream()

    import app.llm.providers.gemini_adapter as gemini_mod

    original = gemini_mod.genai.GenerativeModel

    class _FakeModel:
        def __init__(self, *args, **kwargs):
            pass

        async def generate_content_async(self, *args, **kwargs):
            return await _fake_generate()

    gemini_mod.genai.GenerativeModel = _FakeModel
    try:
        parts: list[str] = []
        async for delta in adapter.stream(
            [LLMMessage(role="user", content="hi")],
            max_tokens=256,
        ):
            parts.append(delta)
    finally:
        gemini_mod.genai.GenerativeModel = original

    assert "".join(parts) == "1. First bullet."
