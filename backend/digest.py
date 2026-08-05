import argparse
import json
from datetime import datetime

from backend.config import settings
from backend.db import get_conn
from backend.llm import chat, model_name
from backend.text_utils import truncate

_SYSTEM = "You are a senior agriculture analyst writing a one-page brief for Canadian farmers. Output ONLY valid JSON."


def fetch_items(topic: str, from_: str, to: str, cap: int = 150):
    conn = get_conn()
    rows = conn.execute(
        """SELECT a.id, a.title, a.published_at, s.tldr
           FROM articles a
           JOIN article_topics t ON a.id = t.article_id
           JOIN summaries s ON a.id = s.article_id
           WHERE t.topic = ? AND a.published_at BETWEEN ? AND ?
           ORDER BY a.published_at DESC
           LIMIT ?""",
        (topic, from_, to, cap),
    ).fetchall()
    conn.close()
    return rows


def build_prompt(items) -> str:
    lines = []
    for i, row in enumerate(items, 1):
        tldr = truncate(row["tldr"] or "", 200)
        lines.append(f"[{i}] {row['published_at'][:10]} -- {row['title']} -- {tldr}")

    items_text = "\n".join(lines)
    return (
        f"Below are {len(items)} summarized articles on a topic. "
        "Return ONLY valid JSON with this exact structure:\n"
        '{\n'
        '  "period_summary": "3-4 sentence overview of this period",\n'
        '  "themes": [{"theme": "short name", "description": "explanation"}],\n'
        '  "key_stories": [{"ref": <item number>, "title": "title", "why": "why this matters"}],\n'
        '  "context": "background on what led up to this period",\n'
        '  "outlook": "what to watch for next"\n'
        '}\n\n'
        "Articles (format [N] date -- title -- summary):\n\n"
        f"{items_text}"
    )


def generate_digest(topic: str, from_: str, to: str, force: bool = False, dry_run: bool = False) -> dict:
    conn = get_conn()

    if not force:
        row = conn.execute(
            "SELECT content, item_count FROM digests WHERE topic=? AND from_date=? AND to_date=?",
            (topic, from_, to),
        ).fetchone()
        if row:
            conn.close()
            return {"digest": json.loads(row["content"]), "item_count": row["item_count"], "cached": True}

    items = fetch_items(topic, from_, to)
    if not items:
        conn.close()
        raise ValueError("No articles found for topic and date range")

    prompt = build_prompt(items)
    raw = chat(prompt, system=_SYSTEM)

    if dry_run:
        data = json.loads(raw)
        conn.close()
        return {"digest": data, "item_count": len(items), "cached": False, "_dry": True}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raw = chat(prompt, system=_SYSTEM)
        data = json.loads(raw)

    for story in data.get("key_stories", []):
        ref = story.get("ref")
        if ref and 1 <= ref <= len(items):
            item = items[ref - 1]
            story["article_id"] = item["id"]
            story["url"] = ""  # URLs aren't fetched; article_id is sufficient for frontend
            story["title"] = item["title"]

    conn.execute(
        "INSERT OR REPLACE INTO digests (topic, from_date, to_date, content, item_count, model, created_at) "
        "VALUES (?,?,?,?,?,?,?)",
        (topic, from_, to, json.dumps(data), len(items), model_name(), datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()

    return {"digest": data, "item_count": len(items), "cached": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default="agtech")
    parser.add_argument("--from", dest="from_", default=settings.DEFAULT_START)
    parser.add_argument("--to", default=datetime.utcnow().strftime("%Y-%m-%d"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = generate_digest(args.topic, args.from_, args.to, force=args.force, dry_run=args.dry_run)
    print(json.dumps(result, indent=2, ensure_ascii=False))
