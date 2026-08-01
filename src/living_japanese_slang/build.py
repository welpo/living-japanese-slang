from __future__ import annotations

import tomllib
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

from .diff import compare
from .io import canonical_json, read_json, sha256, write_json
from .parser import parse_capsules, resolve_sections
from .report import release_notes, render
from .source import capture
from .yomitan import create_dictionary, validate, write_archive

SAMPLE_EXPRESSIONS = [
    "おじアタック",
    "アニオリ",
    "モテ期",
    "シュバる",
    "ｱｰｳ",
    "タゴサク構文",
    "びっくりした、〇〇かと思った",
    "おまいつ",
    "めじるしチャーム",
    "ゴチミヤ",
    "蛙化現象",
]


def _release_snapshot(snapshot_dir: Path, output: Path, build_date: str) -> Path:
    target = output / f"source-snapshots-{build_date}.zip"
    stamp = date.fromisoformat(build_date)
    zip_time = (max(stamp.year, 1980), stamp.month, stamp.day, 0, 0, 0)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for source in sorted(snapshot_dir.glob("*.json")):
            info = zipfile.ZipInfo(source.name, zip_time)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, source.read_bytes(), compresslevel=9)
    return target


def _canonical_entry(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in {"raw_html", "raw_text"}}


def run(
    *,
    root: Path,
    output: Path,
    build_date: str,
    offline: bool,
    baseline_path: Path,
    state_path: Path,
    overrides_path: Path,
) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    snapshot_dir = output / "source-snapshots" / build_date
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    overrides = tomllib.loads(overrides_path.read_text())
    source = capture(snapshot_dir, offline=offline)
    records, anomalies, candidate_count = parse_capsules(
        source.dictionary["content"]["rendered"], source.posts, overrides
    )
    blocking = [item for item in anomalies if item["severity"] in {"error", "warning"}]
    if blocking:
        write_json(output / "anomalies.json", anomalies)
        raise RuntimeError(
            f"Refusing to publish with {len(blocking)} parser errors/warnings; inspect {output / 'anomalies.json'}"
        )

    baseline = read_json(baseline_path) if baseline_path.exists() else []
    state = read_json(state_path) if state_path.exists() else {}
    changes = compare(baseline, records)
    index, terms = create_dictionary(records, source.posts, overrides, build_date)
    validate(index, terms, len(records))
    version = index["revision"]
    archive_path = output / f"living-japanese-slang-{version}.zip"
    archive_hash = write_archive(archive_path, index, terms, build_date)
    validate(index, terms, len(records))
    sections = resolve_sections(records, source.posts, SAMPLE_EXPRESSIONS)
    inventory = [
        {
            "id": post["id"],
            "date": post["date"],
            "modified": post["modified"],
            "link": post["link"],
            "slug": post["slug"],
            "content_hash": sha256(post["content"]["rendered"]),
        }
        for post in source.posts
    ]
    counts = {key: len(changes[key]) for key in ("added", "edited", "removed", "unchanged")}
    overrides_hash = sha256(canonical_json(overrides))
    overrides_changed = overrides_hash != state.get("overrides_hash")
    changed = (
        not state.get("last_release") or any(counts[key] for key in ("added", "edited", "removed")) or overrides_changed
    )
    summary = {
        "build_date": build_date,
        "changed": changed,
        "previous_release": state.get("last_release"),
        "offline": offline,
        "revision": index["revision"],
        "version": version,
        "overrides_hash": overrides_hash,
        "overrides_changed": overrides_changed,
        "archive": archive_path.name,
        "archive_sha256": archive_hash,
        "published": len(terms),
        "examples": sum(bool(record["examples"]) for record in records),
        "candidates": candidate_count,
        "parsed": len(records),
        "changes": counts,
        "anomalies": {
            severity: sum(item["severity"] == severity for item in anomalies)
            for severity in ("error", "warning", "info", "editorial")
        },
        "source": source.metadata,
        "validation": "passed",
    }
    next_state = {
        "dictionary_hash": source.metadata["dictionary_hash"],
        "feed_hash": source.metadata["feed_hash"],
        "overrides_hash": overrides_hash,
        "last_release": build_date,
        "entries": len(records),
        "revision": index["revision"],
    }
    canonical_records = [_canonical_entry(record) for record in records]
    write_json(output / "normalized-entries.json", records)
    write_json(output / "next-current-entries.json", canonical_records)
    write_json(output / "next-state.json", next_state)
    write_json(output / "anomalies.json", anomalies)
    write_json(output / "evidence-sections.json", sections)
    write_json(output / "source-inventory.json", inventory)
    write_json(output / "change-report.json", {"counts": counts, **changes})
    write_json(output / "build-summary.json", summary)
    (output / "report.html").write_text(render(summary, changes, anomalies, sections))
    (output / "release-notes.md").write_text(release_notes(summary, changes))
    snapshot_archive = _release_snapshot(snapshot_dir, output, build_date)
    checksum_files = [
        archive_path,
        snapshot_archive,
        output / "report.html",
        output / "release-notes.md",
        output / "normalized-entries.json",
    ]
    (output / "SHA256SUMS").write_text(
        "".join(f"{sha256(item.read_bytes())}  {item.name}\n" for item in checksum_files)
    )
    return summary
