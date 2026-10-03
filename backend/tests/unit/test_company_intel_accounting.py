"""Regression: company intel extraction must bind LLM accounting context."""

from __future__ import annotations

import json

import pytest

from app.llm.base import LLMClient, LLMMessage, LLMResponse
from app.services.company_intel.extractor import extract_from_jd

pytestmark = pytest.mark.unit


class _FakeExtractionLLM(LLMClient):
    async def complete(
        self,
        messages: list[LLMMessage],
        *,
        response_schema: dict | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> LLMResponse:
        payload = {
            "mission": "Build great products",
            "values": ["Speed"],
            "culture_notes": "Collaborative",
        }
        return LLMResponse(
            content=json.dumps(payload),
            input_tokens=10,
            output_tokens=20,
            model="gpt-4o-mini",
            provider="openai",
        )

    async def stream(self, messages, *, max_tokens=4096, temperature=0.2):
        yield ""

    @property
    def context_window(self) -> int:
        return 8192

    @property
    def supports_structured_output(self) -> bool:
        return False

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return "gpt-4o-mini"


@pytest.mark.asyncio
async def test_extract_from_jd_runs_without_name_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.llm.factory.has_platform_extraction_key",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.services.company_intel.extractor._get_extraction_client",
        lambda: _FakeExtractionLLM(),
    )

    intel = await extract_from_jd(
        "Acme Corp",
        "About Us: We ship fast.\nMission: Build great products.",
        user_id="user-123",
    )

    assert intel is not None
    assert intel.mission == "Build great products"
