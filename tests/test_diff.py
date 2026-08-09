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


def test_field_order_change_is_an_edition_once_both_snapshots_record_it() -> None:
    before = _record("Noun")
    after = _record("Noun")
    before["field_sequence"] = [
        {"kind": "type", "value": "Noun"},
        {"kind": "meaning", "value": "word"},
        {"kind": "example", "value": "語"},
    ]
    after["field_sequence"] = [
        {"kind": "type", "value": "Noun"},
        {"kind": "example", "value": "語"},
        {"kind": "meaning", "value": "word"},
    ]

    result = compare([before], [after])

    assert len(result["edited"]) == 1
    assert result["edited"][0]["changes"] == ["field order"]


def test_field_number_change_is_an_edition() -> None:
    before = _record("Noun")
    after = _record("Noun")
    before["field_sequence"] = [
        {"kind": "type", "number": None, "value": "Noun"},
        {"kind": "meaning", "number": 1, "value": "word"},
    ]
    after["field_sequence"] = [
        {"kind": "type", "number": None, "value": "Noun"},
        {"kind": "meaning", "number": 2, "value": "word"},
    ]

    result = compare([before], [after])

    assert len(result["edited"]) == 1
    assert result["edited"][0]["changes"] == ["field number"]


def test_adding_field_order_to_a_legacy_snapshot_is_not_an_edition() -> None:
    before = _record("Noun")
    after = _record("Noun")
    after["field_sequence"] = [
        {"kind": "type", "value": "Noun"},
        {"kind": "meaning", "value": "word"},
    ]

    result = compare([before], [after])

    assert not result["edited"]
    assert len(result["unchanged"]) == 1
