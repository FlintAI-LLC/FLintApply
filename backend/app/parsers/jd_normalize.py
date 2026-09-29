"""Normalize job descriptions: HTML fragments and plain text to readable plain text."""
from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser

# Known HTML element names only. A generic "<[a-z]" test would treat "List<String>"
# as markup and strip it from plain-text descriptions.
_HTML_TAG_NAMES = frozenset(
    {
        "div", "p", "ul", "ol", "li", "br", "hr", "span", "h1", "h2", "h3", "h4", "h5",
        "h6", "table", "thead", "tbody", "tfoot", "caption", "tr", "td", "th", "a",
        "strong", "em", "b", "i", "u", "small", "sub", "sup", "code", "pre",
        "blockquote", "dl", "dt", "dd", "section", "article", "header", "footer",
        "nav", "main", "aside", "figure", "figcaption", "font", "center", "label",
        "img", "iframe", "object", "embed", "video", "audio", "source", "form",
        "input", "button", "select", "textarea", "script", "style", "noscript",
        "template", "svg", "html", "head", "body", "meta", "link",
    }
)
_TAG_LIKE = re.compile(
    r"<(?:" + "|".join(sorted(_HTML_TAG_NAMES, key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)
_ENTITY_UNRESOLVED = re.compile(r"&(?:[a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);")

_BLOCK_TAGS = frozenset(
    {"p", "div", "section", "article", "h1", "h2", "h3", "h4", "h5", "h6", "tr"}
)
_SKIP_TAGS = frozenset(
    {
        "script", "style", "noscript", "template", "svg", "head", "meta", "link",
        "iframe", "object", "embed",
    }
)
_LIST_TAGS = frozenset({"ul", "ol"})
_CELL_TAGS = frozenset({"td", "th"})

_MAX_UNESCAPE_ITER = 3
_MAX_RAW_INPUT_CHARS = 500_000
_MAX_JSON_WALK_DEPTH = 40
_MAX_JSON_STRING_PARTS = 200
_MAX_LIST_DEPTH = 24


@dataclass(frozen=True)
class NormalizedJd:
    text: str
    was_html: bool
    truncated: bool
    warnings: tuple[str, ...]


def _looks_like_full_document(text: str) -> bool:
    t = text.lstrip()[:200].lower()
    return t.startswith("<!doctype") or t.startswith("<html") or "<head" in t


def _looks_like_html_content(text: str) -> bool:
    if _looks_like_full_document(text):
        return True
    return bool(_TAG_LIKE.search(text))


def _unescape_until_stable(raw: str) -> str:
    current = raw
    for _ in range(_MAX_UNESCAPE_ITER):
        nxt = html.unescape(current)
        if nxt == current:
            break
        current = nxt
    return current


def _extract_next_data(html_doc: str) -> str | None:
    m = re.search(
        r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        html_doc,
        re.DOTALL,
    )
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except (ValueError, KeyError, RecursionError):
        return None

    parts: list[str] = []

    def _walk(obj: object, depth: int = 0) -> None:
        if depth > _MAX_JSON_WALK_DEPTH or len(parts) >= _MAX_JSON_STRING_PARTS:
            return
        if isinstance(obj, str) and len(obj) >= 60:
            parts.append(obj.strip())
        elif isinstance(obj, dict):
            for v in obj.values():
                _walk(v, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item, depth + 1)

    _walk(data)
    return "\n".join(parts) if parts else None


class _JdHtmlExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._list_depth = 0
        self._in_li = False
        self._cell_open = False
        self._in_anchor = False
        self._anchor_href = ""
        self._anchor_text: list[str] = []
        self._parts: list[str] = []

    def _append(self, s: str) -> None:
        if s:
            self._parts.append(s)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if t in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth > 0:
            return
        if t in _LIST_TAGS:
            self._list_depth = min(self._list_depth + 1, _MAX_LIST_DEPTH)
        elif t == "li":
            indent = "  " * max(0, min(self._list_depth, _MAX_LIST_DEPTH) - 1)
            self._append(f"\n{indent}- ")
            self._in_li = True
        elif t == "br":
            self._append("\n")
        elif t in _BLOCK_TAGS:
            self._append("\n\n")
        elif t in _CELL_TAGS:
            self._cell_open = True
        elif t == "a":
            href = ""
            for k, v in attrs:
                if k.lower() == "href" and v:
                    href = v.strip()
                    break
            self._in_anchor = True
            self._anchor_href = href
            self._anchor_text = []

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t in _SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth > 0:
            return
        if t in _LIST_TAGS:
            self._list_depth = max(0, self._list_depth - 1)
            self._append("\n")
        elif t == "li":
            self._in_li = False
        elif t in _BLOCK_TAGS:
            self._append("\n\n")
        elif t in _CELL_TAGS:
            if self._cell_open:
                self._append(" | ")
            self._cell_open = False
        elif t == "a":
            link_text = "".join(self._anchor_text).strip()
            self._append(link_text)
            href = self._anchor_href
            if (
                href
                and href.startswith(("http://", "https://"))
                and href != link_text
                and len(href) <= 120
            ):
                self._append(f" ({href})")
            self._in_anchor = False
            self._anchor_href = ""
            self._anchor_text = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        if not data:
            return
        if self._in_anchor:
            self._anchor_text.append(data)
        else:
            self._append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


def _html_to_text(html_content: str) -> str:
    if _looks_like_full_document(html_content):
        next_text = _extract_next_data(html_content)
        if next_text and len(next_text) >= 200:
            return _normalize_plain_text(next_text)
    extractor = _JdHtmlExtractor()
    try:
        extractor.feed(html_content)
        extractor.close()
    except Exception:
        extractor = _JdHtmlExtractor()
        extractor.feed(html_content)
    return _normalize_plain_text(extractor.get_text())


def _normalize_plain_text(text: str) -> str:
    text = text.replace("\xa0", " ").replace("\u200b", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    for line in text.split("\n"):
        stripped = line.rstrip()
        if re.match(r"^(\s*)-\s", stripped):
            lead, rest = re.match(r"^(\s*)(.*)$", stripped).groups()  # type: ignore[union-attr]
            body = re.sub(r"[ \t]+", " ", rest).strip()
            lines.append(f"{lead}{body}")
        else:
            lines.append(re.sub(r"[ \t]+", " ", stripped).strip())
    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _truncate(text: str, max_chars: int) -> tuple[str, bool]:
    if max_chars < 0:
        max_chars = 0
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def normalize_job_description(raw: str | None, *, max_chars: int) -> NormalizedJd:
    warnings: list[str] = []
    if raw is None or raw == "":
        return NormalizedJd(text="", was_html=False, truncated=False, warnings=tuple())

    if len(raw) > _MAX_RAW_INPUT_CHARS:
        raw = raw[:_MAX_RAW_INPUT_CHARS]
        warnings.append("input_truncated")

    if "<" not in raw and not _ENTITY_UNRESOLVED.search(raw):
        text, truncated = _truncate(raw, max_chars)
        return NormalizedJd(
            text=text, was_html=False, truncated=truncated, warnings=tuple()
        )

    unescaped = _unescape_until_stable(raw)
    was_html = _looks_like_html_content(unescaped)

    if was_html:
        text = _html_to_text(unescaped)
    else:
        text = _normalize_plain_text(unescaped)

    text, truncated = _truncate(text, max_chars)
    return NormalizedJd(
        text=text,
        was_html=was_html,
        truncated=truncated,
        warnings=tuple(warnings),
    )
