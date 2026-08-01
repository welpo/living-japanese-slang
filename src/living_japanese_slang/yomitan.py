from __future__ import annotations

import json
import re
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

from .io import sha256


def _tags(record: dict[str, Any]) -> str:
    values = []
    for item in record["types"]:
        for value in re.split(r"[,;/]|\band\b", item["value"].lower()):
            value = re.sub(r"[^\w+_-]+", "", re.sub(r"\s+", "_", value.strip()))
            if value and value not in values:
                values.append(value)
    values.append("japanese_slang")
    return ",".join(values)


def _glossary(record: dict[str, Any], posts: dict[int, dict[str, Any]], build_date: str) -> list[Any]:
    lines = []
    for index, item in enumerate(record["meanings"], start=1):
        prefix = f"Meaning {item.get('number') or index}: " if len(record["meanings"]) > 1 else ""
        lines.append(f"{prefix}{item['value']}")
    for index, item in enumerate(record["examples"], start=1):
        suffix = f" {item.get('number') or index}" if len(record["examples"]) > 1 else ""
        lines.append(f"Example{suffix}: {item['value']}")
    for index, item in enumerate(record["notes"], start=1):
        suffix = f" {item.get('number') or index}" if len(record["notes"]) > 1 else ""
        lines.append(f"Note{suffix}: {item['value']}")
    source = record["source"]
    source_content: list[Any] = []
    if source["url"]:
        source_content.append({"tag": "a", "href": source["url"], "content": "Further explanation"})
    else:
        source_content.append("No linked source article in the capsule page")
    post = posts.get(source["post_id"])
    article_date = f" · article {post['date'][:10]}" if post else ""
    source_content.append(
        {
            "tag": "span",
            "style": {"fontSize": "x-small", "color": "#777777"},
            "content": f" · capsule checked {build_date}{article_date}",
        }
    )
    return ["\n".join(lines), {"type": "structured-content", "content": source_content}]


def create_dictionary(
    records: list[dict[str, Any]],
    posts: list[dict[str, Any]],
    overrides: dict[str, Any],
    build_date: str,
) -> tuple[dict[str, Any], list[list[Any]]]:
    entries_overrides = overrides.get("entries", {})
    posts_by_id = {post["id"]: post for post in posts}
    published = [record for record in records if record["expression"] and record["meanings"]]
    revision = build_date
    index = {
        "title": "Living Japanese Slang Dictionary (Scripting Japan)",
        "revision": revision,
        "format": 3,
        "sequenced": True,
        "author": "Wes Robertson (Scripting Japan)",
        "url": "https://wesleycrobertson.wordpress.com/2022/06/19/living-japanese-slang-dictionary/",
        "description": f"Live concise entries rebuilt on {build_date}; source data under CC BY-NC-SA 4.0.",
        "attribution": (
            "Data by Wes Robertson / Scripting Japan, CC BY-NC-SA 4.0; transformed and modified by this updater."
        ),
        "sourceLanguage": "ja",
        "targetLanguage": "en",
    }
    terms = []
    for sequence, record in enumerate(published):
        rules = entries_overrides.get(record["expression"], {}).get("inflection", {}).get("rules", [])
        terms.append(
            [
                record["expression"],
                record["reading"],
                _tags(record),
                " ".join(rules),
                0,
                _glossary(record, posts_by_id, build_date),
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
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, value in (("index.json", index), ("term_bank_1.json", terms)):
            info = zipfile.ZipInfo(name, zip_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            payload = (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode()
            archive.writestr(info, payload, compresslevel=9)
    return sha256(path.read_bytes())
