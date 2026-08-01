from living_japanese_slang.diff import compare


def _record(entry_type: str) -> dict:
    return {
        "expression": "語",
        "reading": "ご",
        "types": [{"value": entry_type}],
        "meanings": [{"value": "word"}],
        "examples": [],
        "notes": [],
        "source": {"url": "https://example.test/#word"},
    }


def test_type_change_is_an_edition() -> None:
    result = compare([_record("Noun")], [_record("Verb")])
    assert len(result["edited"]) == 1
    assert result["edited"][0]["changes"] == ["type"]
