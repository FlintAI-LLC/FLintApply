"""AI interview coach for Story Mode segments and whole-story review."""
from __future__ import annotations

import structlog
from pathlib import Path
from typing import AsyncGenerator

from app.llm.base import LLMClient, LLMMessage

log = structlog.get_logger("agent.story_coach")

_PROMPT_PATH = Path(__file__).parent / "prompts" / "story_coach.txt"
_WHOLE_PROMPT_PATH = Path(__file__).parent / "prompts" / "story_coach_whole.txt"
_COMPLETE_SENTINEL = "COMPLETE:"

MAX_EXCHANGES = 3
_WHOLE_STORY_CHAR_CAP = 20_000


def _load_prompt() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _load_whole_prompt() -> str:
    return _WHOLE_PROMPT_PATH.read_text(encoding="utf-8")


def _build_history_text(history: list[dict[str, str]]) -> str:
    if not history:
        return "(no prior exchanges)"
    lines = []
    for msg in history:
        role = msg.get("role", "unknown").capitalize()
        text = msg.get("text", "")
        lines.append(f"{role}: {text}")
    return "\n".join(lines)


def join_whole_story_segments(segments: list[str]) -> str:
    cleaned = [s.strip() for s in segments if (s or "").strip()]
    joined = "\n\n---\n\n".join(cleaned)
    if len(joined) > _WHOLE_STORY_CHAR_CAP:
        return joined[:_WHOLE_STORY_CHAR_CAP]
    return joined


async def _stream_with_empty_retry(
    llm_client: LLMClient,
    messages: list[LLMMessage],
    *,
    max_tokens: int,
    log_event: str,
    attempt_meta: dict[str, object],
) -> AsyncGenerator[str, None]:
    """Stream LLM output; retry once on empty text before optional complete() fallback."""
    for attempt in range(2):
        parts: list[str] = []
        async for delta in llm_client.stream(messages, max_tokens=max_tokens):
            parts.append(delta)
        attempt_text = "".join(parts)
        if attempt_text.strip():
            for delta in parts:
                yield delta
            return
        log.warning(
            f"{log_event}.empty_response",
            attempt=attempt + 1,
            **attempt_meta,
        )

    try:
        response = await llm_client.complete(messages, max_tokens=max_tokens)
        if response.content.strip():
            yield response.content
    except Exception as exc:  # noqa: BLE001
        log.warning(f"{log_event}.complete_fallback_failed", error=str(exc), **attempt_meta)


async def coach_segment(
    segment_text: str,
    history: list[dict[str, str]],
    llm_client: LLMClient,
) -> AsyncGenerator[str, None]:
    """Stream one coaching question for the given segment and conversation history."""
    prompt_template = _load_prompt()
    history_text = _build_history_text(history)
    prompt = (
        prompt_template
        .replace("{segment_text}", segment_text.strip())
        .replace("{history}", history_text)
    )

    log.info(
        "story_coach.start",
        segment_chars=len(segment_text),
        exchange_n=len([m for m in history if m.get("role") == "coach"]) + 1,
    )

    messages = [
        LLMMessage(
            role="system",
            content="You are a concise career interview coach. Ask one short follow-up question.",
        ),
        LLMMessage(role="user", content=prompt),
    ]

    accumulated = ""
    async for delta in _stream_with_empty_retry(
        llm_client,
        messages,
        max_tokens=80,
        log_event="story_coach",
        attempt_meta={"mode": "segment"},
    ):
        accumulated += delta
        yield delta

    is_complete = accumulated.strip().startswith(_COMPLETE_SENTINEL)
    log.info(
        "story_coach.done",
        chars=len(accumulated),
        is_complete_segment=is_complete,
    )


async def coach_whole_story(
    segments: list[str],
    llm_client: LLMClient,
) -> AsyncGenerator[str, None]:
    """Stream whole-story feedback bullets (single pass, no Q&A loop)."""
    segments_text = join_whole_story_segments(segments)
    prompt = _load_whole_prompt().replace("{segments_text}", segments_text)

    log.info(
        "story_coach.whole_start",
        segment_count=len(segments),
        chars=len(segments_text),
    )

    messages = [
        LLMMessage(
            role="system",
            content="You are a concise career coach. Give numbered feedback bullets only.",
        ),
        LLMMessage(role="user", content=prompt),
    ]

    accumulated = ""
    async for delta in _stream_with_empty_retry(
        llm_client,
        messages,
        max_tokens=512,
        log_event="story_coach",
        attempt_meta={"mode": "whole_story"},
    ):
        accumulated += delta
        yield delta

    is_complete = accumulated.strip().startswith(_COMPLETE_SENTINEL)
    log.info(
        "story_coach.whole_done",
        chars=len(accumulated),
        is_complete_story=is_complete,
    )


def is_complete_response(text: str) -> bool:
    """Return True if the coach determined the segment needs no follow-up."""
    return text.strip().startswith(_COMPLETE_SENTINEL)
