from bs4 import BeautifulSoup

from living_japanese_slang.parser import dom_text, parse_capsules, split_headword_reading


def test_dom_text_only_breaks_on_br() -> None:
    node = BeautifulSoup("<p>大<strong>団</strong><em>円</em><br>次</p>", "html.parser").p
    assert node is not None
    assert dom_text(node) == "大団円\n次"


def test_split_headword_reading_preserves_semantic_parentheses() -> None:
    assert split_headword_reading("あ、（察し) (あ、さっし)") == ("あ、（察し)", "あ、さっし")


def test_numbered_fields_are_preserved() -> None:
    html = """<p class="wp-block-paragraph has-background"><strong><a href="https://example.test/?p=1#Word">語 (ご)</a></strong><br>
    <strong>Type 1:</strong> Noun<br><strong>Meaning 1:</strong> word<br><strong>Meaning 2:</strong> language<br>
    <strong>Example 2:</strong> 語です (It is a word)</p>"""
    posts = [{"id": 1, "link": "https://example.test/post/"}]
    records, anomalies, _ = parse_capsules(html, posts, {"entries": {}})
    assert records[0]["expression"] == "語"
    assert records[0]["reading"] == "ご"
    assert [item["value"] for item in records[0]["meanings"]] == ["word", "language"]
    assert not [item for item in anomalies if item["severity"] in {"error", "warning"}]


def test_kimeru_overrides_are_data_driven() -> None:
    html = """<p class="wp-block-paragraph has-background"><strong><a href="https://example.test/?p=99#Wrong">キメる</a></strong><br>
    <strong>Type:</strong> Verb<br><strong>Example:</strong> To get high<br><strong>Example:</strong> 薬をキメた (They got high)</p>"""
    posts = [{"id": 21323, "link": "https://example.test/november/"}]
    overrides = {
        "entries": {
            "キメる": {
                "meaning_recovery": {"from_field": "example", "index": 0, "reason": "mislabeled"},
                "source": {"post_id": 21323, "fragment": "Rariru", "reason": "wrong link"},
            }
        }
    }
    records, anomalies, _ = parse_capsules(html, posts, overrides)
    assert records[0]["meanings"][0]["value"] == "To get high"
    assert records[0]["examples"][0]["value"].startswith("薬をキメた")
    assert records[0]["source"]["url"] == "https://example.test/november/#Rariru"
    assert [item["severity"] for item in anomalies] == ["editorial", "editorial"]
