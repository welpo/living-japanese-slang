from living_japanese_slang.source import referenced_post_identifiers


def test_referenced_post_identifiers_reads_only_first_capsule_links() -> None:
    html = """
    <p class="wp-block-paragraph has-background">
      <a href="https://wesleycrobertson.wordpress.com/?p=123&amp;preview=true#Word">語</a>
      <a href="https://example.test/secondary">secondary</a>
    </p>
    <p class="wp-block-paragraph has-background">
      <a href="https://wesleycrobertson.wordpress.com/2025/10/31/a-post/#Term">語</a>
    </p>
    <p class="wp-block-paragraph has-background"><a href="#A">navigation</a></p>
    """
    assert referenced_post_identifiers(html) == ({123}, {"a-post"})
