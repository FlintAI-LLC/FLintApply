"""Unit tests for extension web-handoff codes."""

from __future__ import annotations

import uuid

import pytest

from app.services.auth.extension_web_handoff import (
    _reset_for_tests,
    consume_web_handoff_code,
    mint_web_handoff_code,
)


@pytest.mark.asyncio
async def test_web_handoff_code_round_trip() -> None:
    _reset_for_tests()
    user_id = uuid.uuid4()
    sid = uuid.uuid4()
    code, expires_in = await mint_web_handoff_code(user_id, sid)
    assert expires_in == 60
    redeemed = await consume_web_handoff_code(code)
    assert redeemed == {"user_id": str(user_id), "web_sid": str(sid)}


@pytest.mark.asyncio
async def test_web_handoff_code_single_use() -> None:
    _reset_for_tests()
    user_id = uuid.uuid4()
    sid = uuid.uuid4()
    code, _ = await mint_web_handoff_code(user_id, sid)
    first = await consume_web_handoff_code(code)
    assert first == {"user_id": str(user_id), "web_sid": str(sid)}
    assert await consume_web_handoff_code(code) is None


@pytest.mark.asyncio
async def test_web_handoff_code_unknown_or_empty() -> None:
    _reset_for_tests()
    assert await consume_web_handoff_code("not-a-real-code") is None
    assert await consume_web_handoff_code("") is None
