from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from bs4 import BeautifulSoup, NavigableString, Tag

from .io import sha256

FIELD_RE = re.compile(r"(?:^|\n)\s*(Type|Meaning|Example|Note)\s*(\d*)\s*:\s*", re.IGNORECASE)
READING_RE = re.compile(r"^(.+?)\s*[（(]([^（）()]+)[）)]\s*$")
KANA_RE = re.compile(r"[ぁ-ゖァ-ヺー]")
KANJI_RE = re.compile(r"[一-龯々]")


def normalize_space(value: str) -> str:
    value = re.sub(r"[\t\f\v ]+", " ", value)
    value = re.sub(r" *\n *", "\n", value)
    return re.sub(r"\n{3,}", "\n\n", value).strip()


def dom_text(node: Tag | NavigableString) -> str:
    if isinstance(node, NavigableString):
        return str(node)
    if node.name == "br":
        return "\n"
    return "".join(dom_text(child) for child in node.children if isinstance(child, (Tag, NavigableString)))


def split_headword_reading(value: str) -> tuple[str, str]:
    match = READING_RE.match(value)
    if not match or not KANA_RE.search(match[2]) or KANJI_RE.search(match[2]):
        return value.strip(), ""
    reading = re.sub(r"\s*[・,，]\s*", "・", normalize_space(match[2]))
    return match[1].strip(), reading


def parse_fields(text: str) -> dict[str, list[dict[str, Any]]]:
    sequence = parse_field_sequence(text)
    fields: dict[str, list[dict[str, Any]]] = {"types": [], "meanings": [], "examples": [], "notes": []}
    for item in sequence:
        fields[f"{item['kind']}s"].append({"number": item["number"], "value": item["value"]})
    return fields


def parse_field_sequence(text: str) -> list[dict[str, Any]]:
    """Parse fields in source order as well as by kind.

    The grouped lists are useful for comparisons, but source order carries sense associations. For
    example, Type 2 belongs to the meanings and examples which follow it, not to the whole capsule.
    """
    matches = list(FIELD_RE.finditer(text))
    sequence = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        value = normalize_space(text[match.end() : end])
        if value:
            sequence.append(
                {
                    "kind": match.group(1).lower(),
                    "number": int(match.group(2)) if match.group(2) else None,
                    "value": value,
                }
            )
    return sequence


def post_for_url(raw_url: str, posts: list[dict[str, Any]]) -> dict[str, Any] | None:
    parsed = urlparse(raw_url)
    query = dict(part.split("=", 1) for part in parsed.query.split("&") if "=" in part)
    if query.get("p", "").isdigit():
        post_id = int(query["p"])
        return next((post for post in posts if post["id"] == post_id), None)
    base = f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")
    return next((post for post in posts if post["link"].rstrip("/") == base), None)


def is_preview_url(raw_url: str | None) -> bool:
    """WordPress ``?preview=true`` links point at unpublished drafts, not live posts."""
    return bool(raw_url) and "true" in parse_qs(urlparse(raw_url).query).get("preview", [])


def canonical_short_url(raw_url: str | None) -> str:
    """The stable ``?p=<id>`` short link, dropping the preview flag and other query parameters."""
    if not raw_url:
        return ""
    parsed = urlparse(raw_url)
    post_id = parse_qs(parsed.query).get("p", [""])[0]
    if not post_id:
        return raw_url
    fragment = f"#{unquote(parsed.fragment)}" if parsed.fragment else ""
    return f"{parsed.scheme}://{parsed.netloc}/?p={post_id}{fragment}"


def source_details(raw_url: str, posts: list[dict[str, Any]]) -> dict[str, Any]:
    if not raw_url:
        return {"url": "", "post_id": None, "fragment": ""}
    parsed = urlparse(raw_url)
    fragment = unquote(parsed.fragment)
    post = post_for_url(raw_url, posts)
    if post:
        return {
            "url": f"{post['link']}{f'#{fragment}' if fragment else ''}",
            "post_id": post["id"],
            "fragment": fragment,
        }
    return {"url": raw_url, "post_id": None, "fragment": fragment}


def parse_capsules(
    html: str,
    posts: list[dict[str, Any]],
    overrides: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    soup = BeautifulSoup(html, "html.parser")
    candidates = soup.select("p.wp-block-paragraph.has-background")
    records: list[dict[str, Any]] = []
    anomalies: list[dict[str, Any]] = []
    entries_overrides = overrides.get("entries", {})
    for candidate_index, node in enumerate(candidates, start=1):
        raw_html = str(node)
        raw_text = normalize_space(dom_text(node))
        first_field = FIELD_RE.search(raw_text)
        if not first_field:
            continue
        prefix = normalize_space(raw_text[: first_field.start()])
        expression, reading = split_headword_reading(prefix)
        fields = parse_fields(raw_text)
        field_sequence = parse_field_sequence(raw_text)
        entry_override = entries_overrides.get(expression, {})
        headword_override = entry_override.get("headword")
        if headword_override:
            anomalies.append(
                {
                    "severity": "editorial",
                    "code": "searchable-headwords-defined",
                    "expression": expression,
                    "detail": headword_override["reason"],
                }
            )
        recovery = entry_override.get("meaning_recovery")
        if recovery and not fields["meanings"] and recovery["from_field"] == "example":
            source_field = fields["examples"]
            index = int(recovery.get("index", 0))
            if index < len(source_field):
                recovered = source_field.pop(index)
                fields["meanings"].append(recovered)
                recovered_count = 0
                for item in field_sequence:
                    if item["kind"] != recovery["from_field"]:
                        continue
                    if recovered_count == index:
                        item["kind"] = "meaning"
                        break
                    recovered_count += 1
                anomalies.append(
                    {
                        "severity": "editorial",
                        "code": "meaning-field-recovered",
                        "expression": expression,
                        "detail": recovery["reason"],
                    }
                )

        anchor = node.find("a", href=True)
        raw_source_url = str(anchor["href"]) if isinstance(anchor, Tag) else ""
        source = source_details(raw_source_url, posts)
        source_override = entry_override.get("source")
        if source_override:
            post = None
            if source_override.get("remove"):
                source = {"url": "", "post_id": None, "fragment": ""}
                anomalies.append(
                    {
                        "severity": "editorial",
                        "code": "source-link-removed",
                        "expression": expression,
                        "detail": source_override["reason"],
                    }
                )
            else:
                post = next((item for item in posts if item["id"] == source_override["post_id"]), None)
                fragment = source_override.get("fragment", "")
            if not source_override.get("remove") and post:
                source = {
                    "url": f"{post['link']}{f'#{fragment}' if fragment else ''}",
                    "post_id": post["id"],
                    "fragment": fragment,
                }
                anomalies.append(
                    {
                        "severity": "editorial",
                        "code": "source-link-corrected",
                        "expression": expression,
                        "detail": source_override["reason"],
                    }
                )
            elif not source_override.get("remove"):
                anomalies.append(
                    {
                        "severity": "warning",
                        "code": "source-override-post-not-found",
                        "expression": expression,
                        "detail": source_override["reason"],
                    }
                )

        if is_preview_url(source["url"]):
            source = {**source, "url": canonical_short_url(source["url"])}
            anomalies.append(
                {
                    "severity": "info",
                    "code": "source-unpublished",
                    "expression": expression,
                    "detail": source["url"],
                }
            )

        key = f"{expression}\0{reading}"
        record = {
            "id": f"capsule-{candidate_index:04d}-{sha256(key)[:10]}",
            "expression": expression,
            "reading": reading,
            **fields,
            "field_sequence": field_sequence,
            "source": source,
            "raw_source_url": raw_source_url,
            "raw_html": raw_html,
            "raw_text": raw_text,
            "raw_hash": sha256(raw_html),
        }
        records.append(record)
        if not expression:
            anomalies.append({"severity": "error", "code": "missing-headword", "id": record["id"]})
        if not fields["types"]:
            anomalies.append({"severity": "warning", "code": "missing-type", "expression": expression})
        if not fields["meanings"]:
            anomalies.append({"severity": "warning", "code": "missing-meaning", "expression": expression})
        if not fields["examples"]:
            anomalies.append({"severity": "info", "code": "missing-example", "expression": expression})
        if not raw_source_url:
            anomalies.append({"severity": "info", "code": "missing-source-link", "expression": expression})
        elif source["url"] and not source["fragment"]:
            anomalies.append({"severity": "info", "code": "missing-source-fragment", "expression": expression})

    seen: dict[tuple[str, str], str] = {}
    for record in records:
        key = (record["expression"], record["reading"])
        if key in seen:
            anomalies.append(
                {
                    "severity": "warning",
                    "code": "duplicate-expression-reading",
                    "expression": record["expression"],
                    "detail": seen[key],
                }
            )
        seen[key] = record["id"]
    return records, anomalies, len(candidates)


def audit_source_links(records: list[dict[str, Any]], posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Check every linked article and fragment captured for the dictionary."""
    posts_by_id = {post["id"]: post for post in posts}
    soups: dict[int, BeautifulSoup] = {}
    anomalies = []
    for record in records:
        if not record["raw_source_url"] or not record["source"]["url"]:
            continue
        if is_preview_url(record["raw_source_url"]):
            continue
        post_id = record["source"]["post_id"]
        if post_id is None or post_id not in posts_by_id:
            anomalies.append(
                {
                    "severity": "warning",
                    "code": "source-post-unresolved",
                    "expression": record["expression"],
                    "detail": record["source"]["url"],
                }
            )
            continue
        fragment = record["source"]["fragment"]
        if not fragment:
            continue
        if post_id not in soups:
            soups[post_id] = BeautifulSoup(posts_by_id[post_id]["content"]["rendered"], "html.parser")
        soup = soups[post_id]
        if soup.find(id=fragment) is None:
            anomalies.append(
                {
                    "severity": "warning",
                    "code": "source-fragment-not-found",
                    "expression": record["expression"],
                    "detail": record["source"]["url"],
                }
            )
    return anomalies


def resolve_sections(
    records: list[dict[str, Any]], posts: list[dict[str, Any]], expressions: list[str]
) -> list[dict[str, Any]]:
    posts_by_id = {post["id"]: post for post in posts}
    result = []
    for requested in expressions:
        record = next((item for item in records if item["expression"] == requested), None)
        record = record or next((item for item in records if requested in item["expression"]), None)
        if not record:
            result.append({"expression": requested, "status": "capsule-not-found"})
            continue
        post = posts_by_id.get(record["source"]["post_id"])
        if not post:
            result.append({"expression": requested, "status": "missing-link"})
            continue
        soup = BeautifulSoup(post["content"]["rendered"], "html.parser")
        target = soup.find(id=record["source"]["fragment"])
        if not isinstance(target, Tag):
            result.append(
                {"expression": requested, "status": "fragment-not-found", "source_url": record["source"]["url"]}
            )
            continue
        nodes: list[Tag] = [target]
        for sibling in target.next_siblings:
            classes = sibling.get("class") if isinstance(sibling, Tag) else None
            has_large_font = isinstance(classes, list) and "has-large-font-size" in classes
            if isinstance(sibling, Tag) and (
                sibling.name in {"h1", "h2", "h3", "h4", "h5", "h6"} or (sibling.name == "p" and has_large_font)
            ):
                break
            if isinstance(sibling, Tag):
                nodes.append(sibling)
        text = normalize_space("\n".join(dom_text(node) for node in nodes))
        result.append(
            {
                "expression": requested,
                "status": "resolved",
                "post_id": post["id"],
                "fragment": record["source"]["fragment"],
                "source_url": record["source"]["url"],
                "text": text,
                "text_hash": sha256(text),
            }
        )
    return result
