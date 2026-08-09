import zipfile
from pathlib import Path
from typing import Any

import pytest

from living_japanese_slang.yomitan import (
    _cross_referenced,
    _tags,
    create_dictionary,
    split_translation,
    stylesheet,
    write_archive,
)


def _record(**overrides: Any) -> dict[str, Any]:
    record = {
        "expression": "語",
        "reading": "ご",
        "types": [],
        "meanings": [{"number": None, "value": "A word"}],
        "examples": [],
        "notes": [],
        "source": {"url": "", "post_id": None, "fragment": ""},
    }
    record.update(overrides)
    return record


def _post(post_id: int = 7) -> dict[str, Any]:
    return {"id": post_id, "date": "2021-10-30T09:00:00", "link": "https://example.test/post"}


def _blocks(record: dict[str, Any], posts: list[dict[str, Any]] | None = None) -> list[Any]:
    """The structured-content blocks Yomitan renders for a single entry."""
    _, terms = create_dictionary([record], posts or [], {}, "2026-08-02")
    return terms[0][5][0]["content"]


def _lines(block: dict[str, Any]) -> list[str]:
    return [line["content"] for line in block["content"]]


def _text(node: Any) -> str:
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(_text(item) for item in node)
    if isinstance(node, dict):
        return _text(node.get("content"))
    return ""


def test_tags_use_yomitan_spaces_without_discarding_creative_fragments() -> None:
    record = _record(
        types=[{"value": "Noun, often in the phrase 親指溶鉱炉に沈むシーン"}],
    )
    assert _tags(record) == "noun often_in_the_phrase_親指溶鉱炉に沈むシーン japanese_slang"


def test_source_order_keeps_types_meanings_and_examples_together() -> None:
    record = _record(
        types=[{"number": 1, "value": "Command"}, {"number": 2, "value": "Noun"}],
        meanings=[{"number": 1, "value": "Do it"}, {"number": 1, "value": "A thing"}],
        examples=[{"number": None, "value": "やれ"}, {"number": None, "value": "物"}],
        field_sequence=[
            {"kind": "type", "number": 1, "value": "Command"},
            {"kind": "meaning", "number": 1, "value": "Do it"},
            {"kind": "example", "number": None, "value": "やれ"},
            {"kind": "type", "number": 2, "value": "Noun"},
            {"kind": "meaning", "number": 1, "value": "A thing"},
            {"kind": "example", "number": None, "value": "物"},
        ],
    )
    assert [_text(block) for block in _blocks(record)] == [
        "Type 1Command",
        "Meaning 1Do it",
        "Exampleやれ",
        "Type 2Noun",
        "Meaning 1A thing",
        "Example物",
    ]


def test_headword_forms_share_one_sequence_and_glossary() -> None:
    record = _record(expression="甲 or 乙", reading="both こう", id="capsule")
    overrides = {
        "entries": {
            "甲 or 乙": {
                "headword": {
                    "forms": [
                        {"expression": "甲", "reading": "こう"},
                        {"expression": "乙", "reading": "おつ"},
                    ]
                }
            }
        }
    }
    _, terms = create_dictionary([record], [], overrides, "2026-08-02")
    assert [(term[0], term[1]) for term in terms] == [("甲", "こう"), ("乙", "おつ")]
    assert terms[0][5] == terms[1][5]
    assert terms[0][6] == terms[1][6] == 0


def test_dictionary_advertises_release_updates() -> None:
    index, _ = create_dictionary([_record()], [], {}, "2026-08-09")

    assert index["isUpdatable"] is True
    assert index["indexUrl"] == ("https://github.com/welpo/living-japanese-slang/releases/latest/download/index.json")
    assert index["downloadUrl"] == (
        "https://github.com/welpo/living-japanese-slang/releases/download/2026-08-09/"
        "living-japanese-slang-2026-08-09.zip"
    )


def test_example_label_sits_on_its_own_line() -> None:
    block = _blocks(_record(examples=[{"number": None, "value": "語を使う。"}]))[1]
    assert _lines(block) == ["Example", "語を使う。"]
    assert block["content"][0]["data"] == {"part": "label"}


def test_translation_moves_below_the_sentence() -> None:
    value = "彼女の隣の席をきぼんぬ (I hope I get the seat next to her)."
    block = _blocks(_record(examples=[{"number": None, "value": value}]))[1]
    assert _lines(block) == ["Example", "彼女の隣の席をきぼんぬ", "I hope I get the seat next to her"]


@pytest.mark.parametrize(
    ("value", "japanese", "translation"),
    [
        # A bracketed Japanese aside is skipped; the translation keeps its own nested brackets.
        (
            "昨日は楽しかった（小並感）(Yesterday was fun (sorry for my lack of vocabulary))",
            "昨日は楽しかった（小並感）",
            "Yesterday was fun (sorry for my lack of vocabulary)",
        ),
        # The source never closed this bracket, so the translation runs to the end of the line.
        (
            "彼の爆イケな表情に惚れちゃった (I fell for his super attractive expression",
            "彼の爆イケな表情に惚れちゃった",
            "I fell for his super attractive expression",
        ),
        # Sentence-ending 。before the bracket stays put.
        (
            "明日のおしゃピクのために買っておいた。(I bought lots of nice cupcakes.)",
            "明日のおしゃピクのために買っておいた。",
            "I bought lots of nice cupcakes.",
        ),
        # No length floor: a two-word translation splits like any other.
        ("チョリーッス! (Yo!)", "チョリーッス!", "Yo!"),
        # A translation may cite a Japanese word without ceasing to be a translation.
        (
            "女性のシワシワネームの例は子で終わる名前 (Names that end in the kanji 子)",
            "女性のシワシワネームの例は子で終わる名前",
            "Names that end in the kanji 子",
        ),
        # Curly quotes delimit a translation too, and keep their quote marks.
        (
            "「もんだいになるよ。誰だ今の？」 “But if you do that…” “Great God of Chikuwa”",
            "「もんだいになるよ。誰だ今の？」",
            "“But if you do that…” “Great God of Chikuwa”",
        ),
        # The translation may sit on its own line, with the Japanese entirely above it.
        (
            "「レスが１００超えたら秘密を言う。」「ksk」\n(“When this gets 100 responses I’ll tell you a secret!” “response”)",
            "「レスが１００超えたら秘密を言う。」「ksk」",
            "“When this gets 100 responses I’ll tell you a secret!” “response”",
        ),
        # A newline ends the translation, so a trailing cross-reference is not swallowed.
        (
            "自己投影型ゲーム好き？ (Do you like games where you play as yourself?)\n\nSee also: 自認",
            "自己投影型ゲーム好き？ See also: 自認",
            "Do you like games where you play as yourself?",
        ),
        # Preserve brackets authored inside the translation and discard punctuation stranded after
        # extracting the outer translation. Cross-reference linking happens in a later pass.
        (
            "猫をhshsすると癒される (Nuzzling my nose into my cat and sniffing deeply calms me [see 猫吸い]).",
            "猫をhshsすると癒される",
            "Nuzzling my nose into my cat and sniffing deeply calms me [see 猫吸い]",
        ),
    ],
)
def test_split_translation(value: str, japanese: str, translation: str) -> None:
    assert split_translation(value) == (japanese, translation)


@pytest.mark.parametrize(
    "value",
    [
        "ギョプりたかったが牛肉しかなかった",  # no translation at all
        "きゅんからぎゃきゅん！(ノ ∩ )ノ彡きゅん♡ (Bleh I don’t want your heart (ノ ∩ )ノ彡きゅん♡)",  # kaomoji
        "[link to original video] [link to video meme remix]",  # placeholder, no Japanese at all
        # The only roman bracket sits inside an English translation, so none of it is a clean split.
        'この例文が理解できますよ（自身）\nうにお願いします (注文)\n"Understand this sentence (confidence) urchin please"',
    ],
)
def test_examples_without_a_clean_translation_are_left_whole(value: str) -> None:
    assert split_translation(value) == (value, None)
    assert _lines(_blocks(_record(examples=[{"number": None, "value": value}]))[1]) == ["Example", value]


def test_styled_parts_are_hooked_to_the_stylesheet_not_inline_styles() -> None:
    """imi drops inline structured-content styles, so styling has to travel via styles.css."""
    block = _blocks(_record(examples=[{"number": None, "value": "語を使う。"}]))[1]
    label = block["content"][0]
    assert label["data"] == {"part": "label"}
    assert "style" not in label
    assert '[data-sc-part="label"] { font-weight: bold; font-size: 0.85em; }' in stylesheet()


def test_no_entry_carries_an_inline_style() -> None:
    record = _record(examples=[{"number": None, "value": "語を使う。(Use the word.)"}], notes=[{"value": "A note"}])

    def styles(node: Any) -> list[Any]:
        if isinstance(node, dict):
            found = [node["style"]] if "style" in node else []
            return found + styles(node.get("content"))
        return [item for child in node for item in styles(child)] if isinstance(node, list) else []

    assert styles(_blocks(record)) == []


def test_stylesheet_covers_every_styled_part() -> None:
    css = stylesheet()
    assert [part for part in ("block", "label", "body", "footnote") if f'"{part}"' not in css] == []


@pytest.mark.parametrize(
    ("text", "terms"),
    [
        ("Nuzzling my cat calms me [see 猫吸い]", ["猫吸い"]),
        ("When you spend money (see 爆死) and get nothing", ["爆死"]),
        ("See also: 白湯メイク, 甜妹メイク", ["白湯メイク", "甜妹メイク"]),
    ],
)
def test_cross_references_become_dictionary_lookups(text: str, terms: list[str]) -> None:
    nodes = _cross_referenced(text, frozenset(terms))
    links = [node for node in nodes if isinstance(node, dict)]
    assert [link["content"] for link in links] == terms
    assert [link["href"] for link in links] == [f"?query={term}&wildcards=off" for term in terms]
    assert "".join(node if isinstance(node, str) else node["content"] for node in nodes) == text


def test_http_urls_become_external_links_without_consuming_punctuation() -> None:
    text = "See https://example.test/a, then http://example.test/b)."
    nodes = _cross_referenced(text)
    links = [node for node in nodes if isinstance(node, dict)]

    assert [(link["content"], link["href"]) for link in links] == [
        ("https://example.test/a", "https://example.test/a"),
        ("http://example.test/b", "http://example.test/b"),
    ]
    assert "".join(node if isinstance(node, str) else node["content"] for node in nodes) == text


@pytest.mark.parametrize(
    "text",
    [
        "A word with no cross-reference at all",
        "See the article for details",  # "see" followed by English, not a term
    ],
)
def test_text_without_a_japanese_cross_reference_is_untouched(text: str) -> None:
    assert _cross_referenced(text, frozenset(["猫吸い"])) == text


def test_cross_reference_to_a_term_this_dictionary_lacks_stays_plain_text() -> None:
    """Neither app searches by prefix, so linking 爆死 when the entry is 爆死する would find nothing."""
    text = "When you spend money (see 爆死) and get nothing"
    assert _cross_referenced(text, frozenset(["爆死する"])) == text


def test_footnote_is_a_single_link_carrying_the_article_date() -> None:
    record = _record(source={"url": "https://example.test/post#Go", "post_id": 7, "fragment": "Go"})
    footnote = _blocks(record, [_post()])[-1]
    assert footnote["content"] == {
        "tag": "a",
        "href": "https://example.test/post#Go",
        "content": "Original 2021-10-30 entry",
    }


def test_footnote_drops_the_date_when_the_article_is_unknown() -> None:
    record = _record(source={"url": "https://example.test/post#Go", "post_id": None, "fragment": "Go"})
    assert _blocks(record)[-1]["content"]["content"] == "Original entry"


def test_footnote_is_omitted_without_a_source_article() -> None:
    blocks = _blocks(_record())
    assert len(blocks) == 1
    assert blocks[0]["content"] == "A word"


def test_archive_is_reproducible(tmp_path: Path) -> None:
    index = {"title": "Test", "revision": "1", "format": 3, "author": "A", "url": "https://example.test"}
    terms = [["語", "ご", "noun", "", 0, ["word"], 0, ""]]
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    assert write_archive(first, index, terms, "2026-08-01") == write_archive(second, index, terms, "2026-08-01")
    with zipfile.ZipFile(first) as archive:
        assert archive.namelist() == ["index.json", "term_bank_1.json", "styles.css"]
