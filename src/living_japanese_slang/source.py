from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

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


def capture(snapshot_dir: Path, *, offline: bool) -> Capture:
    dictionary_path = snapshot_dir / "dictionary-post-4360.json"
    feed_path = snapshot_dir / "slang-feed-all.json"
    if offline:
        dictionary = read_json(dictionary_path)
        posts = read_json(feed_path)
        transport = "snapshot"
        page_count = None
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
        write_json(dictionary_path, dictionary)
        write_json(feed_path, posts)
        transport = "fetch"

    metadata = {
        "transport": transport,
        "feed_pages": page_count,
        "dictionary_modified": dictionary["modified"],
        "dictionary_hash": sha256(canonical_json(dictionary)),
        "feed_hash": sha256(canonical_json(posts)),
    }
    write_json(snapshot_dir / "capture-metadata.json", metadata)
    return Capture(dictionary=dictionary, posts=posts, metadata=metadata)
