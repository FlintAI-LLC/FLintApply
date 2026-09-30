"""Deterministic copy for JD tone-alignment blocking issues (no LLM)."""

from __future__ import annotations

import re

MIRROR_JD_VOCABULARY = re.compile(
    r"^Mirror JD vocabulary: ['\"]([^'\"]{2,40})['\"]\.?$",
    re.IGNORECASE,
)

_IRREGULAR_PAST: dict[str, str] = {
    "lead": "led",
    "drive": "drove",
    "build": "built",
    "run": "ran",
    "write": "wrote",
    "spearhead": "spearheaded",
    "champion": "championed",
    "architect": "architected",
    "establish": "established",
    "operate": "operated",
    "deliver": "delivered",
    "design": "designed",
    "implement": "implemented",
    "scale": "scaled",
    "own": "owned",
    "manage": "managed",
}

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _past_tense(verb: str) -> str:
    key = verb.strip().lower()
    if key in _IRREGULAR_PAST:
        return _IRREGULAR_PAST[key]
    if key.endswith("e"):
        return key + "d"
    if key.endswith("y") and len(key) > 2 and key[-2] not in "aeiou":
        return key[:-1] + "ied"
    if key.endswith("ed") or key.endswith("ing"):
        return key
    return key + "ed"


def jd_snippet_for_term(jd_text: str, term: str, *, max_len: int = 200) -> str | None:
    """First JD sentence that uses ``term`` (word stem), truncated for UI."""
    if not jd_text.strip() or not term.strip():
        return None
    stem = re.escape(term.strip())
    pattern = re.compile(rf"\b{stem}\w*\b", re.IGNORECASE)
    for raw in _SENTENCE_SPLIT.split(jd_text.replace("\n", " ")):
        sent = " ".join(raw.split())
        if not sent or not pattern.search(sent):
            continue
        if len(sent) <= max_len:
            return sent
        return sent[: max_len - 1].rstrip() + "…"
    return None


def resume_example_line(term: str) -> str:
    """Generic bullet-style example; user must adapt to real work."""
    past = _past_tense(term)
    return (
        f"Example for your resume (only if accurate): "
        f"Led and {past} secure architectural solutions across core products "
        f"to drive platform scalability."
    )


def enrich_tone_vocabulary_suggestion(issue_text: str, jd_text: str | None) -> str:
    """Append JD context + resume example to Mirror JD vocabulary issues."""
    match = MIRROR_JD_VOCABULARY.match(issue_text.strip())
    if not match:
        return issue_text
    term = match.group(1).strip()
    parts = [issue_text.strip()]
    if jd_text:
        snippet = jd_snippet_for_term(jd_text, term)
        if snippet:
            parts.append(f'In the JD they use it like: "{snippet}"')
    parts.append(resume_example_line(term))
    return "\n\n".join(parts)
