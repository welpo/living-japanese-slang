from bs4 import BeautifulSoup

from living_japanese_slang.parser import (
    audit_source_links,
    dom_text,
    parse_capsules,
    split_headword_reading,
)


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
    assert [(item["kind"], item["number"]) for item in records[0]["field_sequence"]] == [
        ("type", 1),
        ("meaning", 1),
        ("meaning", 2),
        ("example", 2),
    ]
    assert not [item for item in anomalies if item["severity"] in {"error", "warning"}]


def test_preview_links_publish_but_do_not_block() -> None:
    html = """<p class="wp-block-paragraph has-background"><strong><a href="https://example.test/?p=25079&preview=true#Duo">DUOる</a></strong><br>
    <strong>Type:</strong> Verb<br><strong>Meaning:</strong> to grind Duolingo<br><strong>Example:</strong> 毎日DUOってる (I DUO every day)</p>"""
    records, anomalies, _ = parse_capsules(html, [], {"entries": {}})
    assert records[0]["expression"] == "DUOる"
    assert records[0]["source"]["url"] == "https://example.test/?p=25079#Duo"
    assert records[0]["raw_source_url"] == "https://example.test/?p=25079&preview=true#Duo"
    assert [(item["severity"], item["code"]) for item in anomalies] == [("info", "source-unpublished")]
    assert audit_source_links(records, []) == []


def test_plain_links_share_an_unpublished_posts_preview_status() -> None:
    html = """<p class="wp-block-paragraph has-background"><a href="https://example.test/?p=25480&amp;preview=true#One">一</a><br>
    Type: Noun<br>Meaning: one<br>Example: 一</p>
    <p class="wp-block-paragraph has-background"><a href="https://example.test/?p=25480#Two">二</a><br>
    Type: Noun<br>Meaning: two<br>Example: 二</p>
    <p class="wp-block-paragraph has-background"><a href="https://example.test/?p=999#Three">三</a><br>
    Type: Noun<br>Meaning: three<br>Example: 三</p>"""
    records, parse_anomalies, _ = parse_capsules(html, [], {"entries": {}})
    audit_anomalies = audit_source_links(records, [])

    assert [(item["expression"], item["severity"], item["code"]) for item in parse_anomalies + audit_anomalies] == [
        ("一", "info", "source-unpublished"),
        ("二", "info", "source-unpublished"),
        ("三", "warning", "source-post-unresolved"),
    ]
    assert records[1]["source"]["url"] == "https://example.test/?p=25480#Two"


def test_published_preview_link_has_its_fragment_checked() -> None:
    html = """<p class="wp-block-paragraph has-background"><a href="https://example.test/?p=25480&amp;preview=true#Missing">語</a><br>
    Type: Noun<br>Meaning: word<br>Example: 語</p>"""
    posts = [
        {
            "id": 25480,
            "link": "https://example.test/2026/09/article/",
            "content": {"rendered": '<h2 id="Present">Article</h2>'},
        }
    ]
    records, parse_anomalies, _ = parse_capsules(html, posts, {"entries": {}})

    assert parse_anomalies == []
    assert records[0]["source"]["url"] == "https://example.test/2026/09/article/#Missing"
    assert [(item["severity"], item["code"]) for item in audit_source_links(records, posts)] == [
        ("warning", "source-fragment-not-found")
    ]


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
    assert [item["kind"] for item in records[0]["field_sequence"]] == ["type", "meaning", "example"]
    assert records[0]["source"]["url"] == "https://example.test/november/#Rariru"
    assert [item["severity"] for item in anomalies] == ["editorial", "editorial"]
