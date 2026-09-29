"""Tests for normalize_job_description."""
from __future__ import annotations

from pathlib import Path

import pytest

from app.parsers.jd_normalize import normalize_job_description

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
COINBASE = (FIXTURES / "jd_coinbase_lever.html").read_text(encoding="utf-8")


def test_empty_and_none() -> None:
    assert normalize_job_description(None, max_chars=10_000).text == ""
    assert normalize_job_description("", max_chars=10_000).text == ""


def test_coinbase_lever_fragment_no_raw_tags() -> None:
    out = normalize_job_description(COINBASE, max_chars=20_000)
    assert out.was_html
    assert "<div" not in out.text.lower()
    assert "<p" not in out.text.lower()
    assert "- Design and build scalable backend systems" in out.text
    assert "  - Partner with product on roadmap" in out.text


def test_nested_list_indentation() -> None:
    html = "<ul><li>outer<ul><li>inner</li></ul></li></ul>"
    out = normalize_job_description(html, max_chars=5000)
    assert out.text.index("- outer") < out.text.index("  - inner")
    assert "<ul" not in out.text.lower()


def test_table_cells() -> None:
    html = "<table><tr><td>A</td><td>B</td></tr></table>"
    out = normalize_job_description(html, max_chars=5000)
    assert out.was_html
    assert "A | B" in out.text
    assert "<td" not in out.text.lower()


def test_entities_and_double_encoded() -> None:
    out = normalize_job_description("&amp;nbsp;hello&amp;nbsp;", max_chars=5000)
    assert out.text == "hello"
    assert not out.was_html
    out2 = normalize_job_description("&lt;p&gt;plain tag text&lt;/p&gt;", max_chars=5000)
    assert out2.was_html
    assert out2.text == "plain tag text"


def test_html_fragment_with_inline_markup_becomes_plain_text() -> None:
    desc = "<p>We are hiring a <strong>Software Engineer</strong>.</p>"
    out = normalize_job_description(desc, max_chars=5000)
    assert out.text == "We are hiring a Software Engineer."


def test_next_data_full_document() -> None:
    long_desc = "A" * 220
    html = (
        "<!DOCTYPE html><html><head></head><body>"
        f'<script id="__NEXT_DATA__" type="application/json">'
        f'{{"props":{{"pageProps":{{"description":"{long_desc}"}}}}}}'
        f"</script></body></html>"
    )
    out = normalize_job_description(html, max_chars=20_000)
    assert long_desc in out.text


def test_plain_passthrough_unchanged() -> None:
    plain = "Line one\n\nLine two\n  spaced"
    out = normalize_job_description(plain, max_chars=5000)
    assert not out.was_html
    assert out.text == "Line one\n\nLine two\n  spaced"


def test_plain_less_than_not_html() -> None:
    out = normalize_job_description("if 5 < 10 then ok", max_chars=5000)
    assert not out.was_html
    assert out.text == "if 5 < 10 then ok"


def test_truncation_flag() -> None:
    out = normalize_job_description("x" * 100, max_chars=50)
    assert out.truncated
    assert out.text == "x" * 50
    ok = normalize_job_description("x" * 50, max_chars=50)
    assert not ok.truncated


def test_idempotence() -> None:
    samples = [
        COINBASE,
        "&amp;nbsp;hello&amp;nbsp;",
        '<a href="https://example.com/x">Apply</a>',
        "<table><tr><td>A</td><td>B</td></tr></table>",
        "x" * 100,
    ]
    for sample in samples:
        first = normalize_job_description(sample, max_chars=20_000)
        second = normalize_job_description(first.text, max_chars=20_000)
        assert second.text == first.text
        if first.was_html:
            assert not second.was_html


def test_pay_range_preserved() -> None:
    out = normalize_job_description(COINBASE, max_chars=20_000)
    assert "IC3 | $180,000 - $220,000 USD" in out.text
    assert "<" not in out.text


def test_eeo_preserved() -> None:
    out = normalize_job_description(COINBASE, max_chars=20_000)
    assert "Coinbase is an equal opportunity employer" in out.text
    assert "<" not in out.text


def test_script_style_dropped_isolated() -> None:
    html = (
        "<p>We monitor alerts in production</p>"
        "<script>alert('ignore')</script>"
        "<style>.hidden{display:none}</style>"
    )
    out = normalize_job_description(html, max_chars=5000)
    assert "We monitor alerts in production" in out.text
    assert "ignore" not in out.text
    assert "display:none" not in out.text
    assert "<script" not in out.text.lower()


def test_oversized_input_truncated_without_hang() -> None:
    huge = "<p>" + ("word " * 80_000) + "</p>"
    out = normalize_job_description(huge, max_chars=10_000)
    assert out.truncated
    assert len(out.text) == 10_000
    assert out.text.startswith("word")
    assert "<p" not in out.text.lower()


def test_link_href_when_differs() -> None:
    html = '<a href="https://example.com/job/1">Apply here</a>'
    out = normalize_job_description(html, max_chars=5000)
    assert "Apply here (https://example.com/job/1)" in out.text


def test_link_href_omitted_when_same_as_text() -> None:
    url = "https://jobs.lever.co/coinbase/abc123"
    html = f'<a href="{url}">{url}</a>'
    out = normalize_job_description(html, max_chars=5000)
    assert out.text.strip() == url
    assert f"({url})" not in out.text


def test_next_data_nested_json_does_not_raise() -> None:
    depth = 5000
    nested = "[" * depth + "]" * depth
    html = (
        "<!DOCTYPE html><html><head></head><body>"
        f'<script id="__NEXT_DATA__" type="application/json">{nested}</script>'
        "<p>fallback visible text for jd normalize path</p>"
        "</body></html>"
    )
    out = normalize_job_description(html, max_chars=20_000)
    assert "fallback visible text" in out.text


def test_link_javascript_href_omitted() -> None:
    html = '<a href="javascript:alert(1)">click</a>'
    out = normalize_job_description(html, max_chars=5000)
    assert out.text.strip() == "click"
    assert "javascript" not in out.text


@pytest.mark.parametrize(
    "raw",
    [
        "<img src=x onerror=alert(1)>Great team",
        "<script>alert(1)</script>Great team",
        "<iframe src=javascript:alert(1)></iframe>Great team",
        "<svg onload=alert(1)><circle r=1></circle></svg>Great team",
        "<style>body{display:none}</style>Great team",
        "<b>Great</b> team",
    ],
)
def test_tag_fragments_outside_the_common_list_are_stripped(raw: str) -> None:
    out = normalize_job_description(raw, max_chars=5000)
    assert "<" not in out.text
    assert "alert(1)" not in out.text
    assert "display:none" not in out.text
    assert " ".join(out.text.split()).endswith("Great team")


@pytest.mark.parametrize(
    "raw",
    [
        "Experience with List<String> and Map<K, V> in Java.",
        "Comfortable with a < b comparisons and x <= y checks.",
        "Templates such as vector<int> are a plus.",
    ],
)
def test_angle_brackets_in_plain_text_are_preserved(raw: str) -> None:
    out = normalize_job_description(raw, max_chars=5000)
    assert out.was_html is False
    assert out.text == raw
