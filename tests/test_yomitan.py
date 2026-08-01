import zipfile
from pathlib import Path

from living_japanese_slang.yomitan import write_archive


def test_archive_is_reproducible(tmp_path: Path) -> None:
    index = {"title": "Test", "revision": "1", "format": 3, "author": "A", "url": "https://example.test"}
    terms = [["語", "ご", "noun", "", 0, ["word"], 0, ""]]
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    assert write_archive(first, index, terms, "2026-08-01") == write_archive(second, index, terms, "2026-08-01")
    with zipfile.ZipFile(first) as archive:
        assert archive.namelist() == ["index.json", "term_bank_1.json"]
