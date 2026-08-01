from __future__ import annotations

import html
from typing import Any


def _escape(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _values(items: list[Any]) -> str:
    return " / ".join(item if isinstance(item, str) else item["value"] for item in items)


def _release_item(record: dict[str, Any], suffix: str = "") -> str:
    expression = str(record["expression"]).replace("[", "\\[").replace("]", "\\]")
    source = record.get("source", {}).get("url", "")
    label = f"[{expression}]({source})" if source else f"**{expression}**"
    meaning = _values(record.get("meanings", []))
    if len(meaning) > 180:
        meaning = f"{meaning[:177]}…"
    detail = f" — {meaning}" if meaning else ""
    return f"- {label}{suffix}{detail}"


def release_notes(summary: dict[str, Any], diff: dict[str, Any]) -> str:
    counts = summary["changes"]
    lines = [
        f"# Living Japanese Slang {summary['version']}",
        "",
        (
            f"{summary['published']} Yomitan entries; "
            f"{counts['added']} additions, {counts['edited']} edits, and {counts['removed']} removals "
            "since the previous release."
        ),
        "",
    ]
    if not any(counts[key] for key in ("added", "edited", "removed")):
        message = (
            "Editorial override metadata changed; dictionary content remains otherwise stable."
            if summary.get("overrides_changed") and summary.get("previous_release")
            else "Initial snapshot of the live dictionary."
        )
        lines.extend([message, ""])
    if diff["added"]:
        lines.extend(["## New words", ""])
        lines.extend(_release_item(record) for record in diff["added"][:30])
        if len(diff["added"]) > 30:
            lines.append(f"- …and {len(diff['added']) - 30} more additions; see `report.html`.")
        lines.append("")
    if diff["edited"]:
        lines.extend(["## Edited entries", ""])
        for item in diff["edited"][:30]:
            suffix = f" ({', '.join(item['changes'])})" if item["changes"] else ""
            lines.append(_release_item(item["after"], suffix))
        if len(diff["edited"]) > 30:
            lines.append(f"- …and {len(diff['edited']) - 30} more edits; see `report.html`.")
        lines.append("")
    if diff["removed"]:
        lines.extend(["## Old-only entries", ""])
        lines.extend(_release_item(record) for record in diff["removed"][:20])
        lines.append("")
    lines.extend(
        [
            "## Downloads",
            "",
            f"Import `{summary['archive']}` directly into Yomitan. `report.html` contains the full diff and audit.",
            "",
            "Data: Wes Robertson / Scripting Japan, CC BY-NC-SA 4.0.",
            "",
        ]
    )
    return "\n".join(lines)


def render(
    summary: dict[str, Any], diff: dict[str, Any], anomalies: list[dict[str, Any]], sections: list[dict[str, Any]]
) -> str:
    additions = "".join(
        f"<tr><td><b>{_escape(record['expression'])}</b><small>{_escape(record['reading'])}</small></td>"
        f"<td>{_escape(_values(record['meanings']))}</td><td>{_escape(_values(record['types']))}</td>"
        f"<td>{f'<a href="{_escape(record["source"]["url"])}">source</a>' if record['source']['url'] else '—'}</td></tr>"
        for record in diff["added"]
    )
    editions = "".join(
        f"<tr><td><b>{_escape(item['after']['expression'])}</b><small>{_escape(item['after']['reading'])}</small></td>"
        f"<td>{' '.join(f'<span>{_escape(change)}</span>' for change in item['changes'])}</td>"
        f'<td><details><summary>Compare meanings</summary><div class="compare"><p><b>Before</b><br>{_escape(_values(item["before"].get("meanings", [])))}</p>'
        f"<p><b>After</b><br>{_escape(_values(item['after']['meanings']))}</p></div></details></td></tr>"
        for item in diff["edited"]
    )
    anomaly_rows = "".join(
        f'<tr><td><i class="{_escape(item["severity"])}">{_escape(item["severity"])}</i></td><td><code>{_escape(item["code"])}</code></td>'
        f"<td>{_escape(item.get('expression') or item.get('id'))}</td><td>{_escape(item.get('detail'))}</td></tr>"
        for item in anomalies
    )
    section_rows = "".join(
        f"<tr><td><b>{_escape(item['expression'])}</b></td><td>{_escape(item['status'])}</td>"
        f"<td>{f'<a href="{_escape(item["source_url"])}">evidence</a>' if item.get('source_url') else '—'}</td></tr>"
        for item in sections
    )
    counts = summary["changes"]
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Living Japanese Slang · {summary["build_date"]}</title>
<style>:root{{--ink:#18221c;--paper:#f3efe5;--card:#fffdf8;--green:#176047;--acid:#d7ef65;--line:#d8d0c1;--muted:#69736d;font-family:Inter,system-ui,sans-serif;color:var(--ink);background:var(--paper);line-height:1.5}}*{{box-sizing:border-box}}body{{margin:0}}header{{padding:5rem max(5vw,1.5rem);background:var(--ink);color:white}}header em{{color:var(--acid);font-style:normal;text-transform:uppercase;letter-spacing:.16em;font-weight:800}}h1{{font-size:clamp(3.2rem,8vw,7rem);line-height:.9;letter-spacing:-.06em;margin:.8rem 0;max-width:900px}}header p{{color:#d6dfd9;max-width:700px;font-size:1.15rem}}main{{width:min(1180px,calc(100% - 3rem));margin:auto;padding:4rem 0 7rem}}.metrics{{display:grid;grid-template-columns:repeat(5,1fr);gap:1px;background:var(--line);border:1px solid var(--line);margin-top:-6rem;margin-bottom:5rem;position:relative}}.metric{{background:var(--card);padding:1.3rem}}.metric b{{display:block;font-size:2rem}}.metric small,td small{{display:block;color:var(--muted)}}section{{margin-bottom:5rem}}h2{{font-size:clamp(2rem,4vw,3.5rem);letter-spacing:-.05em;margin-bottom:.3rem}}.lede{{color:var(--muted);max-width:760px}}table{{width:100%;border-collapse:collapse;background:var(--card);font-size:.9rem}}th,td{{padding:.8rem;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}}th{{font-size:.7rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted)}}td span,i{{display:inline-block;border-radius:1rem;padding:.12rem .45rem;background:#e4eadf;font-size:.72rem;font-style:normal}}i.warning{{background:#ffe2bb}}i.editorial{{background:#dce4ff}}i.info{{background:#e5eaed}}a{{color:var(--green);font-weight:700}}.compare{{display:grid;grid-template-columns:1fr 1fr;gap:1rem}}code{{background:#ece6da;padding:.1rem .25rem}}@media(max-width:800px){{.metrics{{grid-template-columns:repeat(2,1fr)}}.compare{{grid-template-columns:1fr}}}}</style></head>
<body><header><em>Build report · {summary["build_date"]}</em><h1>Living Japanese Slang</h1></header><main>
<div class="metrics"><div class="metric"><b>{summary["published"]}</b><small>entries</small></div><div class="metric"><b>+{counts["added"]}</b><small>additions</small></div><div class="metric"><b>{counts["edited"]}</b><small>editions</small></div><div class="metric"><b>{counts["removed"]}</b><small>old-only</small></div><div class="metric"><b>{summary["examples"]}</b><small>with examples</small></div></div>
<section><h2>Additions</h2><p class="lede">New expression-reading records since the last release.</p><table><thead><tr><th scope="col">Entry</th><th scope="col">Meaning</th><th scope="col">Type</th><th scope="col">Evidence</th></tr></thead><tbody>{additions or '<tr><td colspan="4">No additions.</td></tr>'}</tbody></table></section>
<section><h2>Editions</h2><p class="lede">Changes to readings, meanings, examples, notes, or source links.</p><table><thead><tr><th scope="col">Entry</th><th scope="col">Fields</th><th scope="col">Comparison</th></tr></thead><tbody>{editions or '<tr><td colspan="3">No editions.</td></tr>'}</tbody></table></section>
<section><h2>Parsing and editorial audit</h2><table><thead><tr><th scope="col">Severity</th><th scope="col">Code</th><th scope="col">Entry</th><th scope="col">Detail</th></tr></thead><tbody>{anomaly_rows}</tbody></table></section>
<section><h2>Evidence drill</h2><table><thead><tr><th scope="col">Entry</th><th scope="col">Status</th><th scope="col">Evidence</th></tr></thead><tbody>{section_rows}</tbody></table></section>
<p class="lede">Data by <a href="https://wesleycrobertson.wordpress.com/2022/06/19/living-japanese-slang-dictionary/">Wes Robertson / Scripting Japan's Living Japanese Slang Dictionary</a>, CC BY-NC-SA 4.0. Software GPL-3.0-or-later. No generated definitions or examples.</p></main></body></html>"""
