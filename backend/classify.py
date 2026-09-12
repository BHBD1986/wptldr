import json
from collections import Counter

from backend.classifier import classify
from backend.db import get_conn
from backend.config import settings


def run(rebuild: bool = False):
    conn = get_conn()
    if rebuild:
        conn.execute("DELETE FROM article_topics")
        conn.commit()
        query = """SELECT a.id, a.categories, a.title, a.content_text
                   FROM articles a"""
    else:
        query = """SELECT a.id, a.categories, a.title, a.content_text
                   FROM articles a
                   WHERE a.id NOT IN (SELECT article_id FROM article_topics)"""
    rows = conn.execute(query).fetchall()

    classified = []
    for row in rows:
        cats = json.loads(row["categories"])
        text = row["title"] + " " + (row["content_text"] or "")[:2000]
        topics = classify(cats, text)
        if not topics:
            topics = [("unclassified", 0.0)]
        for topic, score in topics:
            classified.append((row["id"], topic, score))

    if classified:
        conn.executemany(
            "INSERT OR REPLACE INTO article_topics VALUES (?,?,?)",
            classified,
        )
        conn.commit()

    counts = Counter(t for _, t, _ in classified)
    print(f"Classified {len(classified)} topic assignments")
    for topic in settings.TOPICS:
        print(f"  {topic}: {counts.get(topic, 0)}")
    conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Clear existing topics and reclassify every article",
    )
    args = parser.parse_args()
    run(rebuild=args.rebuild)
