import argparse
import json
import time

from backend.config import settings
from backend.db import get_conn
from backend.summarizer import summarize_article

_ARTICLE_FIELDS = "a.id, a.title, a.content_text, a.excerpt"


def _summarize_rows(conn, rows, dry_run: bool) -> int:
    for i, row in enumerate(rows, 1):
        print(f"{i}/{len(rows)} {row['title'][:60]}...")
        data = summarize_article(conn, row) if not dry_run else {
            "tldr": "(dry run)",
            "key_points": ["placeholder"],
            "why_it_matters": "(dry run)",
        }
        print(f"  TLDR: {data.get('tldr', '')[:80]}")
        if dry_run:
            print(json.dumps(data, indent=2))
        time.sleep(0.3)
    return len(rows)


def run(limit: int, topic: str, dry_run: bool):
    """Summarize articles in one topic that don't yet have a summary.

    Short articles are included so every article can be covered.
    """
    conn = get_conn()
    rows = conn.execute(
        f"""SELECT {_ARTICLE_FIELDS}
           FROM articles a
           JOIN article_topics t ON a.id = t.article_id
           WHERE t.topic = ?
             AND a.id NOT IN (SELECT article_id FROM summaries)
           ORDER BY a.published_at DESC
           LIMIT ?""",
        (topic, limit),
    ).fetchall()

    _summarize_rows(conn, rows, dry_run)
    conn.close()


def run_coverage(limit: int, dry_run: bool):
    """Summarize every article lacking a summary, across all topics, once each."""
    conn = get_conn()
    rows = conn.execute(
        f"""SELECT {_ARTICLE_FIELDS}
           FROM articles a
           WHERE a.id NOT IN (SELECT article_id FROM summaries)
           ORDER BY a.published_at DESC
           LIMIT ?""",
        (limit,),
    ).fetchall()

    _summarize_rows(conn, rows, dry_run)
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--topic", default="agtech")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Summarize every article missing a summary (all topics)",
    )
    args = parser.parse_args()
    if args.all:
        run_coverage(args.limit, args.dry_run)
    else:
        run(args.limit, args.topic, args.dry_run)
