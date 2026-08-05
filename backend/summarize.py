import argparse
import time

from backend.config import settings
from backend.db import get_conn
from backend.summarizer import summarize_article


def run(limit: int, topic: str, dry_run: bool):
    conn = get_conn()
    rows = conn.execute(
        """SELECT a.id, a.title, a.content_text
           FROM articles a
           JOIN article_topics t ON a.id = t.article_id
           WHERE t.topic = ?
             AND a.id NOT IN (SELECT article_id FROM summaries)
             AND a.word_count > 80
           ORDER BY a.published_at DESC
           LIMIT ?""",
        (topic, limit),
    ).fetchall()

    for i, row in enumerate(rows, 1):
        print(f"{i}/{len(rows)} {row['title'][:60]}...")
        data = summarize_article(conn, row) if not dry_run else {
            "tldr": "(dry run)",
            "key_points": ["placeholder"],
            "why_it_matters": "(dry run)",
        }
        print(f"  TLDR: {data.get('tldr', '')[:80]}")
        if dry_run:
            import json
            print(json.dumps(data, indent=2))
        time.sleep(0.3)

    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--topic", default="agtech")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(args.limit, args.topic, args.dry_run)
