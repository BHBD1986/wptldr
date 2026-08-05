import argparse
from datetime import date

from backend.config import settings
from backend.db import get_conn
from backend.ingest import run as run_ingest
from backend.classify import run as run_classify
from backend.summarize import run as run_summarize
from backend.update_state import set_stage


def run_update(topic: str | None = None):
    conn = get_conn()
    row = conn.execute("SELECT DATE(MAX(published_at), '-1 day') FROM articles").fetchone()
    conn.close()
    start = row[0] or settings.DEFAULT_START
    today = date.today().isoformat()

    set_stage("ingestion")
    print(f"=== Ingestion ({start} -> {today}) ===")
    run_ingest(start, today)

    set_stage("classification")
    print("\n=== Classification ===")
    run_classify()

    topics = [topic] if topic else settings.TOPICS
    for t in topics:
        set_stage(f"summarization:{t}")
        print(f"\n=== Summarization ({t}) ===")
        run_summarize(limit=settings.SUMMARIZE_LIMIT, topic=t, dry_run=False)

    print("\nDone.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--topic",
        default=None,
        help="Only summarize this topic (default: all topics)",
    )
    args = parser.parse_args()
    run_update(args.topic)
