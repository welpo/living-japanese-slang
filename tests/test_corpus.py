import json
import tomllib
from pathlib import Path

from living_japanese_slang.yomitan import create_dictionary, validate

ROOT = Path(__file__).resolve().parents[1]


def test_every_accepted_capsule_builds_searchable_yomitan_terms() -> None:
    records = json.loads((ROOT / "data/current-entries.json").read_text())
    overrides = tomllib.loads((ROOT / "overrides.toml").read_text())
    _, terms = create_dictionary(records, [], overrides, "2026-08-01")

    expected = sum(
        len(overrides.get("entries", {}).get(record["expression"], {}).get("headword", {}).get("forms", [])) or 1
        for record in records
    )
    assert set(overrides["entries"]) <= {record["expression"] for record in records}
    assert len(terms) == expected
    validate(
        {"title": "Corpus", "revision": "1", "format": 3, "author": "A", "url": "https://example.test"},
        terms,
        expected,
    )

    assert len({(term[0], term[1], term[6]) for term in terms}) == len(terms)
    assert not [term[2] for term in terms if "," in term[2]]
    assert not [term[1] for term in terms if any(prose in term[1] for prose in (" or ", "both ", "often "))]

    expressions = {term[0] for term in terms}
    assert {
        "(ry",
        "現場から以上です",
        "私、魔女のキキ！こっちは＿＿＿＿＿",
        "ナレ死",
        "フラスタ",
        "わかんのみほ",
        "だてマスク",
    } <= expressions
    assert (
        not {
            "ry)",
            "現状から以上です",
            "私、魔法のキキ！こっちは＿＿＿＿＿",
            "ナレシ",
            "フラスト",
            "わかのみほ",
            "だってマスク",
        }
        & expressions
    )
    assert {
        "らりる",
        "ラリる",
        "チョリーッス",
        "チョリッス",
        "ほかてら",
        "ほかいま",
        "ほかえり",
        "ほかあり",
    } <= expressions

    thumb = next(record for record in records if record["expression"] == "親指溶鉱炉")
    thumb_terms = [term for term in terms if term[6] == records.index(thumb)]
    assert "often_in_the_phrase_親指溶鉱炉に沈むシーン" in thumb_terms[0][2].split()

    headword_overrides = [entry["headword"] for entry in overrides["entries"].values() if "headword" in entry]
    assert all(item.get("reason") and item.get("forms") for item in headword_overrides)
