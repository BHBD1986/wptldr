import json
from collections import Counter

from backend.classifier import classify
from backend.db import get_conn
from backend.config import settings


def run():
    conn = get_conn()
    rows = conn.execute(
        """SELECT a.id, a.categories, a.title, a.content_text
           FROM articles a
           WHERE a.id NOT IN (SELECT article_id FROM article_topics)"""
    ).fetchall()

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
    run()
