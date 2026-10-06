"""Regression: tutor keyword must not match tutorial via substring."""

import re


def _word_match(term: str, text: str) -> bool:
    text_cf = text.casefold()
    return bool(re.search(rf"(^|[^a-z0-9]){re.escape(term)}([^a-z0-9]|$)", text_cf))


def test_tutorial_does_not_match_tutor_token() -> None:
    assert not _word_match("tutor", "Tutorial Writer at Acme")


def test_tutor_matches_standalone() -> None:
    assert _word_match("tutor", "Math Tutor — part time")
