"""Observability for complete_structured — latency and PII-safe logs."""

from __future__ import annotations

import io
import json
import logging

import pytest
import structlog

from app.llm.base import LLMClient, LLMMessage, LLMResponse
from app.llm.structured import LLMParseError, complete_structured
from pydantic import BaseModel

pytestmark = pytest.mark.unit


class _Schema(BaseModel):
    verdict: str


class _OneShotLLM(LLMClient):
    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        response_schema: dict | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMResponse:
        return LLMResponse(
            content='{"verdict": "ok"}',
            input_tokens=12,
            output_tokens=4,
            model="test-model",
            provider="test-provider",
        )

    async def stream(self, messages, *, max_tokens=4096, temperature=0.2):
        yield ""

    @property
    def context_window(self) -> int:
        return 4096

    @property
    def supports_structured_output(self) -> bool:
        return True

    @property
    def provider_name(self) -> str:
        return "test-provider"

    @property
    def model_name(self) -> str:
        return "test-model"


@pytest.mark.asyncio
async def test_complete_structured_emits_llm_step_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    buffer = io.StringIO()
    import app.llm.structured as structured_mod

    test_logger = structlog.wrap_logger(
        structlog.PrintLogger(file=buffer),
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )
    monkeypatch.setattr(structured_mod, "log", test_logger)

    client = _OneShotLLM()
    resume_snippet = "SECRET-RESUME-BODY-PII"
    jd_snippet = "SECRET-JD-BODY-PII"
    messages = [
        LLMMessage(role="system", content="system"),
        LLMMessage(role="user", content=f"{resume_snippet}\n{jd_snippet}"),
    ]

    result = await complete_structured(
        client,
        messages,
        _Schema,
        step="phase3_test",
        session_id="sess-1",
    )

    assert result.verdict == "ok"
    line = buffer.getvalue().strip()
    assert line
    payload = json.loads(line)
    assert payload["event"] == "llm_step_complete"
    assert payload["latency_ms"] > 0
    assert payload["retries"] == 0
    assert payload["tokens_in"] == 12
    assert payload["tokens_out"] == 4
    assert payload["accepted"] is True
    serialized = json.dumps(payload)
    assert resume_snippet not in serialized
    assert jd_snippet not in serialized


@pytest.mark.asyncio
async def test_complete_structured_warning_when_retries_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    buffer = io.StringIO()
    import app.llm.structured as structured_mod

    test_logger = structlog.wrap_logger(
        structlog.PrintLogger(file=buffer),
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING),
    )
    monkeypatch.setattr(structured_mod, "log", test_logger)

    class _BadLLM(_OneShotLLM):
        async def complete(self, messages, **kwargs) -> LLMResponse:
            return LLMResponse(
                content="not-json",
                input_tokens=1,
                output_tokens=1,
                model="test-model",
                provider="test-provider",
            )

    with pytest.raises(LLMParseError):
        await complete_structured(_BadLLM(), [LLMMessage(role="user", content="x")], _Schema, max_retries=2)

    lines = [json.loads(raw) for raw in buffer.getvalue().strip().split("\n") if raw]
    events = [row.get("event") for row in lines]
    assert "llm_step_complete" in events
    assert "llm_step_exhausted_retries" in events
