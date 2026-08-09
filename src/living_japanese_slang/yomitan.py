from __future__ import annotations

import json
import re
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

from .io import sha256

_REPOSITORY_URL = "https://github.com/welpo/living-japanese-slang"
_LATEST_INDEX_URL = f"{_REPOSITORY_URL}/releases/latest/download/index.json"


def _tags(record: dict[str, Any]) -> str:
    values = []
    for item in record["types"]:
        for value in re.split(r"[,;/]|\band\b", item["value"].lower()):
            value = re.sub(r"[^\w+_-]+", "", re.sub(r"\s+", "_", value.strip()))
            if value and value not in values:
                values.append(value)
    values.append("japanese_slang")
    # Yomitan's term-bank format uses spaces between tags. Commas make the whole value one tag.
    return " ".join(values)


def source_label(article_date: str | None) -> str:
    """Wording for the source-article link; the date is part of the link text, not a separate note."""
    return f"Original {article_date} entry" if article_date else "Original entry"


# Every styled part of an entry, declared once and rendered as the dictionary's styles.css. Nodes
# carry a data-sc-part hook rather than an inline style, which imi ignores entirely.
_PART_STYLES: dict[str, dict[str, str]] = {
    "block": {"marginTop": "0.5em"},
    "label": {"fontWeight": "bold", "fontSize": "0.85em"},
    "body": {"marginLeft": "0.5em"},
    "footnote": {"fontSize": "0.75em", "marginTop": "0.75em"},
}


def _styled(part: str, content: Any, tag: str = "div", **attributes: Any) -> dict[str, Any]:
    """A structured-content node hooked to its rule in the stylesheet."""
    return {"tag": tag, "data": {"part": part}, "content": content, **attributes}


def stylesheet() -> str:
    """The dictionary's styles.css, generated from the part declarations above."""
    rules = []
    for part, style in _PART_STYLES.items():
        properties = " ".join(
            f"{re.sub(r'(?<!^)(?=[A-Z])', '-', name).lower()}: {value};" for name, value in style.items()
        )
        rules.append(f'[data-sc-part="{part}"] {{ {properties} }}')
    return "\n".join(rules) + "\n"


_CROSS_REFERENCE = re.compile(r"((?:[Ss]ee also:|[Ss]ee)\s+)([^\s,\]\)）］]+(?:,\s*[^\s,\]\)）］]+)*)")
_WEB_URL = re.compile(r"https?://[^\s<>\"']+")
_URL_TRAILING_PUNCTUATION = ".,;:!?)]}。、，；：！？）］｝"


def _linked_urls(text: str) -> str | list[Any]:
    nodes: list[Any] = []
    position = 0
    for match in _WEB_URL.finditer(text):
        candidate = match.group()
        url = candidate.rstrip(_URL_TRAILING_PUNCTUATION)
        if not url:
            continue
        nodes.append(text[position : match.start()])
        nodes.append({"tag": "a", "href": url, "content": url})
        nodes.append(candidate[len(url) :])
        position = match.end()
    if not nodes:
        return text
    nodes.append(text[position:])
    return [node for node in nodes if node != ""]


def _link_urls_in_nodes(nodes: list[Any]) -> list[Any]:
    result = []
    for node in nodes:
        linked = _linked_urls(node) if isinstance(node, str) else node
        result.extend(linked if isinstance(linked, list) else [linked])
    return [node for node in result if node != ""]


def _cross_referenced(text: str, headwords: frozenset[str] = frozenset()) -> Any:
    """Turn dictionary references into in-app lookups and web URLs into external links.

    An href beginning with "?" is a search rather than a web address, which is how both Yomitan and
    imi render cross-references. Only terms that are headwords here are linked — neither app
    searches by prefix, so a link to a term this dictionary spells differently would find nothing.
    Text with nothing to link is returned unchanged. Only explicit HTTP and HTTPS URLs become web
    links; surrounding prose and trailing punctuation remain text.
    """
    nodes: list[Any] = []
    position = 0
    for match in _CROSS_REFERENCE.finditer(text):
        terms = [term.strip() for term in match.group(2).split(",")]
        if not all(term in headwords for term in terms):
            continue
        nodes.append(text[position : match.start()] + match.group(1))
        for index, term in enumerate(terms):
            if index:
                nodes.append(", ")
            nodes.append({"tag": "a", "href": f"?query={term}&wildcards=off", "content": term})
        position = match.end()
    if not nodes:
        return _linked_urls(text)
    nodes.append(text[position:])
    return _link_urls_in_nodes(nodes)


_BRACKETS_OPEN = "(（[［"
_BRACKETS_CLOSE = ")）]］"
_QUOTE_OPEN = "“"
_QUOTE_CLOSE = "”"
_OPENERS = _BRACKETS_OPEN + _QUOTE_OPEN
_SENTENCE_PUNCTUATION = " \t.。!！?？…、,"
_CJK = re.compile(r"[぀-ヿ㐀-鿿ｦ-ﾟ]")
_LATIN = re.compile(r"[A-Za-z]")
_MIN_ROMAN_RATIO = 0.9


def _roman_ratio(text: str) -> float:
    """Share of the text's letters that are roman rather than Japanese."""
    roman, japanese = len(_LATIN.findall(text)), len(_CJK.findall(text))
    return roman / (roman + japanese) if roman or japanese else 0.0


def _delimiter_end(value: str, start: int) -> tuple[int, bool]:
    """Index closing the delimiter at value[start], or of the line end when it is never closed."""
    line_end = value.find("\n", start)
    line_end = len(value) if line_end < 0 else line_end
    if value[start] == _QUOTE_OPEN:
        # Quotes do not nest, and a translation may be several quoted fragments in a row.
        last = value.rfind(_QUOTE_CLOSE, start + 1, line_end)
        return (last, True) if last > start else (line_end, False)
    depth = 0
    for position in range(start, line_end):
        character = value[position]
        if character in _BRACKETS_OPEN:
            depth += 1
        elif character in _BRACKETS_CLOSE:
            depth -= 1
            if not depth:
                return position, True
    return line_end, False


def split_translation(value: str) -> tuple[str, str | None]:
    """Split "日本語。(English.)" into the sentence and its translation.

    The source writes the translation as a bracketed or quoted aside, so the first delimiter whose
    contents are overwhelmingly roman is it. Japanese asides like （草）or（小並感）are skipped over,
    and a delimiter the source never closed runs to the end of the line. An example that fits none
    of this is left whole rather than guessed at.
    """
    if not _CJK.search(value):  # An example with no Japanese in it has nothing to translate.
        return value, None
    for start, character in enumerate(value):
        if character not in _OPENERS:
            continue
        # A delimiter inside English prose is part of the translation, not the start of one.
        preceding = value[value.rfind("\n", 0, start) + 1 : start]
        if preceding.strip() and not _CJK.search(preceding):
            continue
        end, closed = _delimiter_end(value, start)
        # Quotation marks read as part of the sentence, so they stay; brackets do not.
        inner = value[start : end + 1] if character == _QUOTE_OPEN else value[start + 1 : end]
        translation = inner.strip()
        if not translation or not _LATIN.search(translation) or _roman_ratio(translation) < _MIN_ROMAN_RATIO:
            continue
        japanese = value[:start].rstrip()
        # Whatever follows the translation rejoins the sentence, unless it is stray punctuation.
        remainder = value[end + 1 :].strip().strip(_SENTENCE_PUNCTUATION).strip() if closed else ""
        return (f"{japanese} {remainder}".strip() if remainder else japanese), translation
    return value, None


def _labelled_block(label: str, value: str, headwords: frozenset[str], *, translate: bool = False) -> dict[str, Any]:
    """Label on its own line, value beneath it and slightly indented."""
    japanese, translation = split_translation(value) if translate else (value, None)
    lines: list[Any] = [
        _styled("label", label),
        _styled("body", _cross_referenced(japanese, headwords)),
    ]
    if translation:
        lines.append(_styled("body", _cross_referenced(translation, headwords)))
    return _styled("block", lines)


def _field_sequence(record: dict[str, Any]) -> list[dict[str, Any]]:
    sequence = record.get("field_sequence")
    if isinstance(sequence, list):
        return sequence
    return [
        {"kind": kind, "number": item.get("number"), "value": item["value"]}
        for kind, plural in (("type", "types"), ("meaning", "meanings"), ("example", "examples"), ("note", "notes"))
        for item in record[plural]
    ]


def _glossary(record: dict[str, Any], posts: dict[int, dict[str, Any]], headwords: frozenset[str]) -> list[Any]:
    content: list[Any] = []
    multiple_types = len(record["types"]) > 1
    multiple_meanings = len(record["meanings"]) > 1
    for item in _field_sequence(record):
        kind = item["kind"]
        number = item.get("number")
        value = item["value"]
        if kind == "type":
            # A single Type already appears as tags. Multiple Type blocks delimit separate senses,
            # so retaining them in place is necessary to preserve the source's associations.
            if multiple_types:
                suffix = f" {number}" if number is not None else ""
                content.append(_labelled_block(f"Type{suffix}", value, headwords))
        elif kind == "meaning":
            if multiple_meanings:
                suffix = f" {number}" if number is not None else ""
                content.append(_labelled_block(f"Meaning{suffix}", value, headwords))
            else:
                content.append({"tag": "div", "content": _cross_referenced(value, headwords)})
        elif kind == "example":
            suffix = f" {number}" if number is not None else ""
            content.append(_labelled_block(f"Example{suffix}", value, headwords, translate=True))
        elif kind == "note":
            suffix = f" {number}" if number is not None else ""
            content.append(_labelled_block(f"Note{suffix}", value, headwords))

    source = record["source"]
    if source["url"]:
        post = posts.get(source["post_id"])
        link = {"tag": "a", "href": source["url"], "content": source_label(post["date"][:10] if post else None)}
        content.append(_styled("footnote", link))
    return [{"type": "structured-content", "content": content}]


def _headword_forms(record: dict[str, Any], entries_overrides: dict[str, Any]) -> list[dict[str, str]]:
    headword = entries_overrides.get(record["expression"], {}).get("headword", {})
    forms = headword.get("forms")
    if not forms:
        return [{"expression": record["expression"], "reading": record["reading"]}]
    result = [{"expression": str(form["expression"]), "reading": str(form.get("reading", ""))} for form in forms]
    keys = [(form["expression"], form["reading"]) for form in result]
    if any(not expression for expression, _ in keys) or len(keys) != len(set(keys)):
        raise ValueError(f"Invalid headword forms for {record['expression']}")
    return result


def expected_term_count(records: list[dict[str, Any]], overrides: dict[str, Any]) -> int:
    entries_overrides = overrides.get("entries", {})
    return sum(
        len(_headword_forms(record, entries_overrides))
        for record in records
        if record["expression"] and record["meanings"]
    )


def create_dictionary(
    records: list[dict[str, Any]],
    posts: list[dict[str, Any]],
    overrides: dict[str, Any],
    build_date: str,
) -> tuple[dict[str, Any], list[list[Any]]]:
    entries_overrides = overrides.get("entries", {})
    posts_by_id = {post["id"]: post for post in posts}
    published = [record for record in records if record["expression"] and record["meanings"]]
    forms_by_record = [_headword_forms(record, entries_overrides) for record in published]
    headwords = frozenset(form["expression"] for forms in forms_by_record for form in forms)
    revision = build_date
    download_url = f"{_REPOSITORY_URL}/releases/download/{revision}/living-japanese-slang-{revision}.zip"
    index = {
        "title": "Living Japanese Slang Dictionary (Scripting Japan)",
        "revision": revision,
        "format": 3,
        "sequenced": True,
        "isUpdatable": True,
        "indexUrl": _LATEST_INDEX_URL,
        "downloadUrl": download_url,
        "author": "Wes Robertson (Scripting Japan)",
        "url": "https://wesleycrobertson.wordpress.com/2022/06/19/living-japanese-slang-dictionary/",
        "description": f"Live concise entries rebuilt on {build_date}; source data under CC BY-NC-SA 4.0.",
        "attribution": (
            "Data: Wes Robertson / Scripting Japan, CC BY-NC-SA 4.0. Dictionary: github.com/welpo/living-japanese-slang"
        ),
        "sourceLanguage": "ja",
        "targetLanguage": "en",
    }
    terms = []
    for sequence, (record, forms) in enumerate(zip(published, forms_by_record, strict=True)):
        rules = entries_overrides.get(record["expression"], {}).get("inflection", {}).get("rules", [])
        glossary = _glossary(record, posts_by_id, headwords)
        for form in forms:
            terms.append(
                [
                    form["expression"],
                    form["reading"],
                    _tags(record),
                    " ".join(rules),
                    0,
                    glossary,
                    sequence,
                    "",
                ]
            )
    return index, terms


def validate(index: dict[str, Any], terms: list[list[Any]], expected_entries: int) -> None:
    if index.get("format") != 3 or not all(index.get(key) for key in ("title", "revision", "author", "url")):
        raise ValueError("Invalid Yomitan index metadata")
    if len(terms) != expected_entries:
        raise ValueError(f"Expected {expected_entries} terms, generated {len(terms)}")
    for position, term in enumerate(terms):
        if len(term) != 8 or not isinstance(term[0], str) or not term[0] or not isinstance(term[5], list):
            raise ValueError(f"Malformed term at position {position}")


def write_archive(path: Path, index: dict[str, Any], terms: list[list[Any]], build_date: str) -> str:
    stamp = date.fromisoformat(build_date)
    zip_time = (max(stamp.year, 1980), stamp.month, stamp.day, 0, 0, 0)
    path.parent.mkdir(parents=True, exist_ok=True)
    payloads = {
        "index.json": (json.dumps(index, ensure_ascii=False, separators=(",", ":")) + "\n").encode(),
        "term_bank_1.json": (json.dumps(terms, ensure_ascii=False, separators=(",", ":")) + "\n").encode(),
        "styles.css": stylesheet().encode(),
    }
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, payload in payloads.items():
            info = zipfile.ZipInfo(name, zip_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, payload, compresslevel=9)
    return sha256(path.read_bytes())
