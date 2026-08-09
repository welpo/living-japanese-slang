from living_japanese_slang.build import _semantic_index
from living_japanese_slang.yomitan import create_dictionary


def test_release_urls_do_not_turn_a_new_build_date_into_a_semantic_change() -> None:
    first, _ = create_dictionary([], [], {}, "2026-08-09")
    second, _ = create_dictionary([], [], {}, "2026-08-16")

    assert first["downloadUrl"] != second["downloadUrl"]
    assert _semantic_index(first) == _semantic_index(second)
