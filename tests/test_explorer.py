import json
import zipfile
from pathlib import Path

import pytest

from living_japanese_slang.explorer import main, read_dictionary, render


def test_archive_renders_grouped_forms_as_safe_static_html(tmp_path: Path) -> None:
    archive_path = tmp_path / "dictionary.zip"
    index = {
        "title": "Tiny <Dictionary>",
        "revision": "1",
        "author": "Author",
        "url": "https://example.test",
        "description": "A tiny dictionary.",
    }
    glossary = [
        "Meaning 1: first\nMeaning 2: second",
        {"type": "structured-content", "content": {"tag": "div", "content": "A meaning"}},
        {"type": "structured-content", "content": {"tag": "script", "content": "not executable"}},
    ]
    terms = [
        ["甲", "こう", "noun japanese_slang", "", 0, glossary, 0, ""],
        ["乙", "おつ", "noun japanese_slang", "", 0, glossary, 0, ""],
    ]
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("index.json", json.dumps(index))
        archive.writestr("term_bank_1.json", json.dumps(terms))

    loaded_index, loaded_terms = read_dictionary(archive_path)
    html = render(loaded_index, loaded_terms)

    assert "Tiny &lt;Dictionary&gt;" in html
    assert "甲" in html and "乙" in html
    assert "1 entries" in html and "2 searchable forms" in html
    assert "Meaning 1: first<br>Meaning 2: second" in html
    assert ".definition>br" not in html
    assert "<script" not in html
    assert "not executable" in html


def test_output_cannot_overwrite_input_archive(tmp_path: Path) -> None:
    archive_path = tmp_path / "dictionary.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "index.json",
            json.dumps({"title": "Tiny", "revision": "1", "author": "Author", "url": "https://example.test"}),
        )
        archive.writestr("term_bank_1.json", "[]")
    original = archive_path.read_bytes()

    with pytest.raises(SystemExit, match="2"):
        main([str(archive_path), "--output", str(archive_path)])

    assert archive_path.read_bytes() == original
