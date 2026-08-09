from __future__ import annotations

import argparse
import json
import re
import zipfile
from collections.abc import Sequence
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

_BANK_RE = re.compile(r"term_bank_(\d+)\.json$")
_SAFE_TAGS = {"a", "br", "div", "li", "ol", "p", "rp", "rt", "ruby", "span", "ul"}


def _term_banks(names: list[str]) -> list[str]:
    banks = []
    for name in names:
        match = _BANK_RE.fullmatch(name)
        if match:
            banks.append((int(match.group(1)), name))
    return [name for _, name in sorted(banks)]


def read_dictionary(path: Path) -> tuple[dict[str, Any], list[list[Any]]]:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if "index.json" not in names:
            raise ValueError(f"{path} has no index.json")
        banks = _term_banks(names)
        if not banks:
            raise ValueError(f"{path} has no term banks")
        index = json.loads(archive.read("index.json"))
        terms = [term for bank in banks for term in json.loads(archive.read(bank))]
    return index, terms


def _safe_href(value: str, targets: dict[str, str]) -> str:
    if value.startswith("?"):
        query = parse_qs(value[1:]).get("query", [""])[0]
        return f"#{targets[query]}" if query in targets else ""
    parsed = urlparse(value)
    return value if parsed.scheme in {"http", "https"} else ""


def _render_node(node: Any, targets: dict[str, str]) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return escape(node).replace("\n", "<br>")
    if isinstance(node, list):
        return "".join(_render_node(item, targets) for item in node)
    if not isinstance(node, dict):
        return escape(str(node))
    if node.get("type") == "structured-content" and "tag" not in node:
        return f'<div class="structured">{_render_node(node.get("content"), targets)}</div>'

    tag = str(node.get("tag", "span")).lower()
    tag = tag if tag in _SAFE_TAGS else "span"
    content = _render_node(node.get("content"), targets)
    if tag == "br":
        return "<br>"

    attributes = []
    data = node.get("data")
    if isinstance(data, dict) and data.get("part"):
        attributes.append(f'data-sc-part="{escape(str(data["part"]), quote=True)}"')
    style = node.get("style")
    if isinstance(style, dict) and style.get("fontSize") in {"x-small", "small"}:
        attributes.append('class="source-meta"')
    if tag == "a":
        href = _safe_href(str(node.get("href", "")), targets)
        if href:
            attributes.append(f'href="{escape(href, quote=True)}"')
            if href.startswith(("http://", "https://")):
                attributes.append('target="_blank" rel="noopener noreferrer"')
    suffix = f" {' '.join(attributes)}" if attributes else ""
    return f"<{tag}{suffix}>{content}</{tag}>"


def _tags(value: Any) -> list[str]:
    return [item for item in re.split(r"[\s,]+", str(value).strip()) if item]


def _group_terms(terms: list[list[Any]]) -> list[list[list[Any]]]:
    groups: dict[Any, list[list[Any]]] = {}
    order: list[Any] = []
    for position, term in enumerate(terms):
        if len(term) != 8:
            raise ValueError(f"Malformed term at position {position}")
        key = term[6]
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(term)
    return [groups[key] for key in order]


def render(index: dict[str, Any], terms: list[list[Any]]) -> str:
    groups = _group_terms(terms)
    ids = [f"entry-{position:04d}" for position in range(1, len(groups) + 1)]
    targets: dict[str, str] = {}
    for anchor, group in zip(ids, groups, strict=True):
        for term in group:
            targets.setdefault(str(term[0]), anchor)

    cards = []
    for anchor, group in zip(ids, groups, strict=True):
        forms = []
        seen_forms: set[tuple[str, str]] = set()
        tags = []
        for term in group:
            expression, reading = str(term[0]), str(term[1])
            if (expression, reading) not in seen_forms:
                seen_forms.add((expression, reading))
                reading_html = f'<small lang="ja">{escape(reading)}</small>' if reading else ""
                forms.append(f'<span class="form"><b lang="ja">{escape(expression)}</b>{reading_html}</span>')
            for tag in _tags(term[2]):
                if tag not in tags:
                    tags.append(tag)
        tag_html = "".join(f"<li>{escape(tag.replace('_', ' '))}</li>" for tag in tags)
        glossary = group[0][5]
        definition = _render_node(glossary, targets)
        cards.append(
            f'<article class="entry" id="{anchor}"><h2>{"".join(forms)}</h2>'
            f'<ul class="tags">{tag_html}</ul><div class="definition">{definition}</div>'
            '<a class="back" href="#top" aria-label="Back to top">↑</a></article>'
        )

    title = escape(str(index.get("title", "Dictionary")))
    revision = escape(str(index.get("revision", "unknown")))
    description = escape(str(index.get("description", "")))
    author = escape(str(index.get("author", "")))
    source_url = _safe_href(str(index.get("url", "")), {})
    source = (
        f'<a href="{escape(source_url, quote=True)}" target="_blank" rel="noopener noreferrer">{author}</a>'
        if source_url
        else author
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} · {revision}</title>
<style>
:root {{
  --paper:#f7f2e8; --card:#fffdf8; --ink:#252521; --muted:#716f66; --line:#ddd5c6;
  --accent:#e66b51; --soft:#f6d8c9; color-scheme:light;
  font-family:ui-rounded,"SF Pro Rounded","Hiragino Maru Gothic ProN",system-ui,sans-serif;
  background:var(--paper); color:var(--ink);
}}
* {{ box-sizing:border-box }}
html {{ scroll-behavior:smooth }}
body {{ margin:0; line-height:1.65 }}
a {{ color:#a63e2c; text-underline-offset:.18em }}
header {{
  padding:clamp(3rem,8vw,7rem) max(1.25rem,calc((100vw - 72rem)/2));
  background:var(--soft); border-bottom:1px solid var(--line);
}}
header p {{ max-width:48rem; color:#554f48 }}
.eyebrow {{ font-size:.78rem; font-weight:800; letter-spacing:.12em; text-transform:uppercase; color:#873626 }}
h1 {{ max-width:54rem; margin:.35rem 0 1rem; font-size:clamp(2.7rem,7vw,6rem); line-height:.95 }}
.stats {{ display:flex; gap:.65rem; flex-wrap:wrap; margin-top:1.5rem }}
.stats span,.tags li {{
  border:1px solid rgba(92,65,52,.18); border-radius:99rem; background:rgba(255,255,255,.55);
  padding:.22rem .68rem; font-size:.78rem;
}}
main {{
  width:min(72rem,calc(100% - 2rem)); margin:2rem auto 6rem; display:grid;
  grid-template-columns:repeat(2,minmax(0,1fr)); gap:1rem; align-items:start;
}}
.entry {{
  position:relative; scroll-margin-top:1rem; background:var(--card); border:1px solid var(--line);
  border-radius:1rem; padding:1.35rem; box-shadow:0 4px 18px rgba(62,49,36,.045);
}}
.entry:target {{ outline:3px solid var(--accent); outline-offset:2px }}
h2 {{ display:flex; align-items:baseline; gap:.7rem; flex-wrap:wrap; margin:0 2rem .55rem 0; line-height:1.2 }}
.form {{ display:inline-flex; align-items:baseline; gap:.45rem }}
.form:not(:last-child)::after {{ content:"·"; color:var(--accent); margin-left:.25rem }}
.form b {{ font-size:1.45rem }}
.form small {{ font-size:.78rem; font-weight:500; color:var(--muted) }}
.tags {{ display:flex; flex-wrap:wrap; gap:.3rem; list-style:none; margin:0 0 1rem; padding:0 }}
.tags li {{ background:#f3eee3; color:#5e5b54; padding:.12rem .5rem }}
.definition [data-sc-part="block"] {{ margin-top:.7rem }}
.definition [data-sc-part="label"] {{
  font-size:.76rem; font-weight:800; text-transform:uppercase; letter-spacing:.06em; color:#873626;
}}
.definition [data-sc-part="body"] {{ margin-left:.7rem }}
.definition [data-sc-part="footnote"],.source-meta {{
  display:inline-block; margin-top:.8rem; font-size:.75rem; color:var(--muted);
}}
.structured {{ margin-top:.65rem }}
.back {{ position:absolute; right:1rem; top:1rem; text-decoration:none; color:#aaa }}
footer {{ padding:2rem; text-align:center; color:var(--muted); font-size:.82rem; border-top:1px solid var(--line) }}
@media(max-width:720px) {{ main {{ grid-template-columns:1fr }} header {{ padding-top:3.5rem }} }}
@media print {{
  header {{ padding:1rem }} main {{ display:block; width:auto; margin:0 }}
  .entry {{ break-inside:avoid; box-shadow:none; margin:.5rem 0 }} .back {{ display:none }}
}}
</style>
</head>
<body id="top">
<header>
<div class="eyebrow">Pocket-sized web edition · {revision}</div>
<h1>{title}</h1><p>{description}</p>
<div class="stats">
<span>{len(groups)} entries</span><span>{len(terms)} searchable forms</span><span>No JavaScript</span>
</div>
</header>
<main>{"".join(cards)}</main>
<footer>Dictionary data by {source}. Generated directly from the Yomitan archive.</footer>
</body>
</html>
"""


def latest_archive(root: Path) -> Path:
    candidates = list((root / "dist").glob("living-japanese-slang-*.zip"))
    if not candidates:
        raise FileNotFoundError(f"No dictionary ZIP found in {root / 'dist'}")
    return max(candidates, key=lambda path: path.stat().st_mtime)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Render a Yomitan dictionary ZIP as a static HTML page")
    result.add_argument("archive", nargs="?", type=Path, help="Dictionary ZIP; defaults to the newest local build")
    result.add_argument("--output", "-o", type=Path, help="Output HTML path; defaults beside the archive")
    return result


def main(argv: Sequence[str] | None = None) -> None:
    argument_parser = parser()
    arguments = argument_parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    archive = arguments.archive.resolve() if arguments.archive else latest_archive(root)
    output = arguments.output.resolve() if arguments.output else archive.with_suffix(".html")
    if output == archive:
        argument_parser.error("output path must differ from the input dictionary ZIP")
    index, terms = read_dictionary(archive)
    output.write_text(render(index, terms))
    print(output)


if __name__ == "__main__":
    main()
