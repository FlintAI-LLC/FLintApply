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


def _mirror_vocab_term(suggestion: str) -> str | None:
    """Lowercase JD term when the first line is a Mirror JD vocabulary issue."""
    first = suggestion.strip().split("\n")[0].strip()
    match = MIRROR_JD_VOCABULARY.match(first)
    if not match:
        return None
    return match.group(1).strip().lower()


def refresh_mirror_jd_blocking_issues(
    issues: list,
    jd_text: str | None,
) -> list:
    """Enrich every mirror-JD row and collapse duplicate terms (keep richest copy)."""
    from app.models.qa import BlockingIssue

    enriched: list[BlockingIssue] = []
    for issue in issues:
        first_line = issue.suggestion.strip().split("\n")[0].strip()
        if MIRROR_JD_VOCABULARY.match(first_line) and "Example for your resume" not in issue.suggestion:
            enriched.append(
                issue.model_copy(
                    update={
                        "suggestion": enrich_tone_vocabulary_suggestion(
                            first_line, jd_text
                        )
                    }
                )
            )
        else:
            enriched.append(issue)

    by_term: dict[str, BlockingIssue] = {}
    rest: list[BlockingIssue] = []
    for issue in enriched:
        term_key = _mirror_vocab_term(issue.suggestion)
        if term_key is None:
            rest.append(issue)
            continue
        prev = by_term.get(term_key)
        if prev is None or len(issue.suggestion) > len(prev.suggestion):
            by_term[term_key] = issue
    return rest + list(by_term.values())
