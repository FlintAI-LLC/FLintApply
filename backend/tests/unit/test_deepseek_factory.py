"""Unit tests for DeepSeek factory wiring."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.llm.base import LLMMessage
from app.llm.factory import get_llm_client
from app.llm.providers.deepseek_adapter import DeepSeekAdapter
from app.llm.tracking_client import TrackingLLMClient


_FAKE_KEY = "unit-test-placeholder-not-a-secret"


def test_get_llm_client_returns_deepseek_adapter_wrapped_in_tracking() -> None:
    with patch("app.llm.factory.settings") as mock_settings:
        mock_settings.DEEPSEEK_API_KEY = "x" * 32
        client = get_llm_client(provider="deepseek", model="deepseek-v4-flash")

    assert isinstance(client, TrackingLLMClient)
    assert isinstance(client._inner, DeepSeekAdapter)
    assert client.provider_name == "deepseek"
    assert client.model_name == "deepseek-v4-flash"


def test_deepseek_adapter_provider_metadata() -> None:
    adapter = DeepSeekAdapter(model="deepseek-v4-flash", api_key=_FAKE_KEY)
    assert adapter.provider_name == "deepseek"
    assert adapter.model_name == "deepseek-v4-flash"
    # DeepSeek's API rejects OpenAI's strict json_schema response_format;
    # it only supports {"type": "json_object"}. Schema is prompt-injected.
    assert adapter.supports_structured_output is False


@pytest.mark.asyncio
async def test_deepseek_adapter_uses_json_object_response_format(monkeypatch) -> None:
    """Regression test: DeepSeek must never send OpenAI's json_schema mode.

    DeepSeek's chat API returns a 400 for response_format.type == "json_schema",
    which previously surfaced to users as a 500 "Something went wrong" on any
    step routed to DeepSeek (see production incident on resume/text).
    """
    captured_kwargs: dict = {}

    class _FakeMessage:
        content = '{"ok": true}'

    class _FakeChoice:
        message = _FakeMessage()

    class _FakeResponse:
        choices = [_FakeChoice()]
        usage = None

    class _FakeCompletions:
        async def create(self, **kwargs):
            captured_kwargs.update(kwargs)
            return _FakeResponse()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        chat = _FakeChat()

    adapter = DeepSeekAdapter(model="deepseek-v4-flash", api_key=_FAKE_KEY)
    monkeypatch.setattr(adapter, "_client", _FakeClient())

    await adapter.complete(
        [LLMMessage(role="user", content="hello")],
        response_schema={"type": "object"},
    )

    assert captured_kwargs["response_format"] == {"type": "json_object"}
