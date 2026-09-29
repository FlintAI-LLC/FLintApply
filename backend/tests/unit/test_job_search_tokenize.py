"""Unit tests for corpus job-search tokenization."""

from app.services.jobs.job_service import (
    _search_variants_for_term,
    tokenize_job_search_terms,
)


def test_tokenize_keeps_two_letter_role_acronyms() -> None:
    assert tokenize_job_search_terms("Software QA Engineer") == [
        "software",
        "qa",
        "engineer",
    ]


def test_qa_expands_to_quality_and_sdet_aliases() -> None:
    variants = _search_variants_for_term("qa")
    assert "quality engineer" in variants
    assert "sdet" in variants


def test_tokenize_keeps_pm_and_drops_single_char() -> None:
    assert tokenize_job_search_terms("PM role") == ["pm", "role"]
    assert tokenize_job_search_terms("a b c engineer") == ["engineer"]


def test_tokenize_strips_punctuation() -> None:
    assert tokenize_job_search_terms("QA, automation.") == ["qa", "automation"]


def test_tokenize_drops_common_stopwords() -> None:
    assert tokenize_job_search_terms("engineer in remote") == ["engineer", "remote"]


import pytest

from app.services.jobs.job_service import _JOB_SEARCH_TERM_ALIASES

_EXPECTED_EXPANSIONS = {
    "swe": "software engineer",
    "sre": "site reliability engineer",
    "mle": "machine learning engineer",
    "ml": "machine learning",
    "ds": "data scientist",
    "fe": "frontend",
    "be": "backend",
    "fs": "full stack",
    "fullstack": "full stack",
    "full-stack": "full stack",
    "devops": "devops engineer",
    "k8s": "kubernetes",
    "ts": "typescript",
    "js": "javascript",
    "llm": "large language model",
    "etl": "data engineer",
    "sdet": "quality engineer",
    "ai": "artificial intelligence",
    "frontend": "front end",
    "front-end": "frontend",
    "backend": "back end",
    "back-end": "backend",
    "qa": "quality assurance",
    "sde": "software engineer",
    "pm": "product manager",
}


@pytest.mark.parametrize(("alias", "expected"), sorted(_EXPECTED_EXPANSIONS.items()))
def test_every_role_alias_expands(alias: str, expected: str) -> None:
    variants = _search_variants_for_term(alias)
    assert expected in variants, f"{alias} -> {variants}"


@pytest.mark.parametrize("alias", ["be", "fe", "fs", "ds", "ts", "js", "ml", "ai"])
def test_ambiguous_short_aliases_never_search_the_raw_token(alias: str) -> None:
    # ilike '%be%' / '%ai%' matches almost every description ("because", "maintain").
    assert alias not in _search_variants_for_term(alias)


def test_unknown_term_is_returned_unchanged() -> None:
    assert _search_variants_for_term("rustacean") == ("rustacean",)


def test_alias_table_keys_are_lowercase_and_not_stopwords() -> None:
    from app.services.jobs.job_service import _SEARCH_STOPWORDS

    for key in _JOB_SEARCH_TERM_ALIASES:
        assert key == key.lower()
        assert key not in _SEARCH_STOPWORDS


@pytest.mark.parametrize("alias", sorted(_EXPECTED_EXPANSIONS))
def test_aliases_survive_tokenization(alias: str) -> None:
    assert tokenize_job_search_terms(f"{alias} engineer") == [alias, "engineer"]


def test_original_aliases_are_unchanged() -> None:
    assert "sdet" in _search_variants_for_term("qa")
    assert _search_variants_for_term("sde") == ("software engineer", "sde")
    assert _search_variants_for_term("pm") == ("product manager", "pm")
