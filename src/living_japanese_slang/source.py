from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from .io import canonical_json, read_json, sha256, write_json

SITE = "wesleycrobertson.wordpress.com"
API_ROOT = f"https://public-api.wordpress.com/wp/v2/sites/{SITE}"
DICTIONARY_URL = f"{API_ROOT}/posts/4360"
FEED_URL = f"{API_ROOT}/posts"
FIELDS = "id,date,modified,link,slug,title,content"


@dataclass(frozen=True)
class Capture:
    dictionary: dict[str, Any]
    posts: list[dict[str, Any]]
    metadata: dict[str, Any]


def referenced_post_identifiers(html: str) -> tuple[set[int], set[str]]:
    """Return WordPress post IDs and slugs linked as the first anchor of each capsule."""
    post_ids: set[int] = set()
    slugs: set[str] = set()
    soup = BeautifulSoup(html, "html.parser")
    for capsule in soup.select("p.wp-block-paragraph.has-background"):
        anchor = capsule.find("a", href=True)
        if not isinstance(anchor, Tag):
            continue
        parsed = urlparse(str(anchor["href"]))
        if parsed.netloc != SITE:
            continue
        query = parse_qs(parsed.query)
        if query.get("p", [""])[0].isdigit():
            post_ids.add(int(query["p"][0]))
            continue
        parts = [unquote(part) for part in parsed.path.strip("/").split("/")]
        if len(parts) == 4 and all(part.isdigit() for part in parts[:3]):
            slugs.add(parts[3])
    return post_ids, slugs


def _fetch_referenced_posts(
    client: httpx.Client, dictionary: dict[str, Any], posts: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    post_ids, slugs = referenced_post_identifiers(dictionary["content"]["rendered"])
    known_ids = {post["id"] for post in posts}
    known_slugs = {post["slug"] for post in posts}
    fetched = []
    missing_ids = sorted(post_ids - known_ids)
    if missing_ids:
        response = client.get(
            FEED_URL,
            params={"include": ",".join(map(str, missing_ids)), "per_page": 100, "_fields": FIELDS},
        )
        response.raise_for_status()
        fetched.extend(response.json())
    for slug in sorted(slugs - known_slugs):
        response = client.get(FEED_URL, params={"slug": slug, "per_page": 1, "_fields": FIELDS})
        response.raise_for_status()
        fetched.extend(response.json())
    result = []
    for post in fetched:
        if post["id"] in known_ids:
            continue
        known_ids.add(post["id"])
        result.append(post)
    return result


def capture(snapshot_dir: Path, *, offline: bool) -> Capture:
    dictionary_path = snapshot_dir / "dictionary-post-4360.json"
    feed_path = snapshot_dir / "slang-feed-all.json"
    if offline:
        dictionary = read_json(dictionary_path)
        posts = read_json(feed_path)
        transport = "snapshot"
        page_count = None
        referenced_count = None
    else:
        headers = {"User-Agent": "living-japanese-slang/0.1 (+noncommercial dictionary build)"}
        with httpx.Client(headers=headers, timeout=45, follow_redirects=True) as client:
            response = client.get(DICTIONARY_URL, params={"_fields": FIELDS})
            response.raise_for_status()
            dictionary = response.json()
            posts = []
            page = 1
            page_count = 1
            while page <= page_count:
                response = client.get(
                    FEED_URL,
                    params={"tags": 8138, "per_page": 100, "page": page, "_fields": FIELDS},
                )
                response.raise_for_status()
                page_posts = response.json()
                posts.extend(page_posts)
                page_count = int(response.headers.get("x-wp-totalpages", page_count))
                write_json(snapshot_dir / f"slang-feed-page-{page}.json", page_posts)
                page += 1
            referenced_posts = _fetch_referenced_posts(client, dictionary, posts)
            posts.extend(referenced_posts)
            referenced_count = len(referenced_posts)
            write_json(snapshot_dir / "referenced-posts.json", referenced_posts)
        write_json(dictionary_path, dictionary)
        write_json(feed_path, posts)
        transport = "fetch"

    metadata = {
        "transport": transport,
        "feed_pages": page_count,
        "referenced_posts": referenced_count,
        "dictionary_modified": dictionary["modified"],
        "dictionary_hash": sha256(canonical_json(dictionary)),
        "feed_hash": sha256(canonical_json(posts)),
    }
    write_json(snapshot_dir / "capture-metadata.json", metadata)
    return Capture(dictionary=dictionary, posts=posts, metadata=metadata)
