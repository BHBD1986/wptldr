import argparse
import html
import json
from datetime import datetime, date
from urllib.parse import urlparse

from backend.config import settings
from backend.db import get_conn
from backend.text_utils import html_to_text, truncate
from backend.wp_client import fetch_category_map, fetch_posts


def run(start: str, end: str):
    cat_map = fetch_category_map()
    conn = get_conn()
    ingested = 0
    updated = 0

    for post in fetch_posts(start, end):
        wp_id = post["id"]
        title = html.unescape(post["title"]["rendered"])
        url = post["link"]
        section = urlparse(url).path.strip("/").split("/")[0] or "uncategorized"
        published_at = post["date"]
        category_ids = post.get("categories", [])
        categories = json.dumps([cat_map.get(cid, "unknown") for cid in category_ids])
        content_text = html_to_text(post.get("content", {}).get("rendered", ""))
        excerpt = html_to_text(post.get("excerpt", {}).get("rendered", ""))
        word_count = len(content_text.split())

        existing = conn.execute(
            "SELECT 1 FROM articles WHERE wp_id=?", (wp_id,)
        ).fetchone()

        conn.execute(
            """INSERT INTO articles
               (wp_id, title, url, section, published_at, categories,
                content_text, excerpt, word_count, ingested_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(wp_id) DO UPDATE SET
               title=excluded.title, content_text=excluded.content_text,
               excerpt=excluded.excerpt, word_count=excluded.word_count,
               ingested_at=excluded.ingested_at""",
            (
                wp_id,
                title,
                url,
                section,
                published_at,
                categories,
                truncate(content_text),
                truncate(excerpt, 2000),
                word_count,
                datetime.utcnow().isoformat(),
            ),
        )

        if existing:
            updated += 1
        else:
            ingested += 1

    conn.commit()
    conn.close()
    print(f"ingested {ingested}, updated {updated}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default=settings.DEFAULT_START)
    parser.add_argument("--end", default=date.today().isoformat())
    args = parser.parse_args()
    run(args.start, args.end)
