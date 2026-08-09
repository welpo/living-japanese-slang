from living_japanese_slang.report import release_notes


def test_release_notes_are_clear_linked_and_do_not_expose_change_field_names() -> None:
    summary = {
        "version": "2026-08-09",
        "archive": "living-japanese-slang-2026-08-09.zip",
        "published": 832,
        "terms": 869,
        "previous_release": "2026-08-01",
        "overrides_changed": False,
        "changes": {"added": 0, "edited": 1, "removed": 0},
    }
    diff = {
        "added": [],
        "edited": [
            {
                "changes": ["source link"],
                "after": {
                    "expression": "語",
                    "meanings": [
                        {
                            "value": (
                                "A deliberately long definition made from complete words that should be shortened "
                                "cleanly instead of being cut through the middle of its final visible word when the "
                                "release Markdown is generated for GitHub readers"
                            )
                        }
                    ],
                    "source": {"url": "https://example.test/word"},
                },
            }
        ],
        "removed": [],
    }

    notes = release_notes(summary, diff)

    assert not notes.startswith("# ")
    assert "Compared with the previous snapshot (2026-08-01)" in notes
    assert "## Updated entries" in notes
    assert "source link" not in notes
    assert "releas…" not in notes
    assert "release…" in notes
    assert (
        "[**Download living-japanese-slang-2026-08-09.zip**]"
        "(https://github.com/welpo/living-japanese-slang/releases/download/2026-08-09/"
        "living-japanese-slang-2026-08-09.zip)"
    ) in notes
    assert (
        "[View the full build report]"
        "(https://github.com/welpo/living-japanese-slang/releases/download/2026-08-09/report.html)"
    ) in notes
