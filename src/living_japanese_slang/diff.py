from __future__ import annotations

import json
import re
from typing import Any

from .parser import normalize_space


def _values(items: list[Any]) -> list[str]:
    return [normalize_space(item if isinstance(item, str) else item["value"]) for item in items]


def _comparable(record: dict[str, Any]) -> str:
    return json.dumps(
        {
            "types": _values(record.get("types", [])),
            "meanings": _values(record.get("meanings", [])),
            "examples": _values(record.get("examples", [])),
            "notes": _values(record.get("notes", [])),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _link(value: str) -> str:
    value = value.replace("&amp;", "&")
    value = re.sub(r"[?&](?:preview=true|_thumbnail_id=\d+)", "", value)
    return value.rstrip("?&")


def _changes(before: dict[str, Any], after: dict[str, Any]) -> list[str]:
    changes = []
    if before.get("reading", "") != after.get("reading", ""):
        changes.append("reading")
    for label in ("type", "meaning", "example", "note"):
        plural = f"{label}s"
        if _values(before.get(plural, [])) != _values(after.get(plural, [])):
            changes.append(label)
    before_url = before.get("source", {}).get("url", before.get("source_url", ""))
    after_url = after.get("source", {}).get("url", "")
    if _link(before_url) != _link(after_url):
        changes.append("source link")
    return changes


def compare(previous: list[dict[str, Any]], current: list[dict[str, Any]]) -> dict[str, Any]:
    unmatched_previous = {id(record): record for record in previous}
    unmatched_current = {id(record): record for record in current}
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    previous_by_key = {(record["expression"], record.get("reading", "")): record for record in previous}
    for record in current:
        old = previous_by_key.get((record["expression"], record.get("reading", "")))
        if old is not None and id(old) in unmatched_previous:
            pairs.append((old, record))
            unmatched_previous.pop(id(old))
            unmatched_current.pop(id(record))

    previous_by_expression: dict[str, list[dict[str, Any]]] = {}
    current_by_expression: dict[str, list[dict[str, Any]]] = {}
    for record in unmatched_previous.values():
        previous_by_expression.setdefault(record["expression"], []).append(record)
    for record in unmatched_current.values():
        current_by_expression.setdefault(record["expression"], []).append(record)
    for expression, records in current_by_expression.items():
        old = previous_by_expression.get(expression, [])
        if len(records) == len(old) == 1:
            pairs.append((old[0], records[0]))
            unmatched_previous.pop(id(old[0]))
            unmatched_current.pop(id(records[0]))

    edited = []
    unchanged = []
    for before, after in pairs:
        changes = _changes(before, after)
        if _comparable(before) != _comparable(after) or changes:
            edited.append({"before": before, "after": after, "changes": changes})
        else:
            unchanged.append(after)
    return {
        "added": list(unmatched_current.values()),
        "edited": edited,
        "removed": list(unmatched_previous.values()),
        "unchanged": unchanged,
    }
