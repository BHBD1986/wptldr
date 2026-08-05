import argparse
import json
from datetime import datetime

from backend.config import settings
from backend.db import get_conn
from backend.llm import chat, model_name
from backend.text_utils import truncate

_SYSTEM = "You are a senior agriculture analyst writing a one-page brief for Canadian farmers. Output ONLY valid JSON."


def fetch_items(topic: str, from_: str, to: str, cap: int | None = None):
    cap = cap or settings.DIGEST_MAX_ITEMS
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


def _chunk(items, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


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


def build_chunk_prompt(chunk, chunk_index: int, total_chunks: int) -> str:
    """Pass-1 prompt: produce a condensed digest for one article batch."""
    lines = []
    for i, row in enumerate(chunk, 1):
        tldr = truncate(row["tldr"] or "", 140)
        lines.append(f"[{i}] {row['published_at'][:10]} -- {row['title']} -- {tldr}")

    items_text = "\n".join(lines)
    return (
        f"Below are {len(chunk)} summarized articles (batch {chunk_index} of {total_chunks}). "
        "Produce a CONCISE digest of this batch. Return ONLY valid JSON with this structure:\n"
        '{\n'
        '  "period_summary": "1-2 sentence overview",\n'
        '  "themes": [{"theme": "short name", "description": "explanation"}],\n'
        '  "key_stories": [{"ref": <item number within this batch>, "title": "title", "why": "why it matters"}],\n'
        '  "context": "one sentence",\n'
        '  "outlook": "one sentence"\n'
        '}\n\n'
        "Articles (format [N] date -- title -- summary):\n\n"
        f"{items_text}"
    )


def build_combine_prompt(chunk_digests: list[dict]) -> str:
    """Pass-2 prompt: merge condensed batch digests into one final brief."""
    blocks = []
    for i, d in enumerate(chunk_digests, 1):
        themes = "; ".join(
            f"{t.get('theme', '')}: {t.get('description', '')}"
            for t in d.get("themes", []) if isinstance(t, dict)
        )
        stories = "; ".join(
            f"[{s.get('ref')}] {s.get('title')}: {s.get('why', '')}"
            for s in d.get("key_stories", []) if isinstance(s, dict)
        )
        blocks.append(
            f"Batch {i} overview: {d.get('period_summary', '')}\n"
            f"Themes: {themes}\n"
            f"Key stories: {stories}\n"
            f"Context: {d.get('context', '')}\n"
            f"Outlook: {d.get('outlook', '')}"
        )

    batches_text = "\n\n".join(blocks)
    return (
        f"Below are condensed digests of {len(chunk_digests)} article batches covering one period. "
        "Combine them into ONE final one-page brief. "
        "The key_stories ref numbers are GLOBAL article numbers (from the full list). "
        "Return ONLY valid JSON with this exact structure:\n"
        '{\n'
        '  "period_summary": "3-4 sentence overview of the whole period",\n'
        '  "themes": [{"theme": "short name", "description": "explanation"}],\n'
        '  "key_stories": [{"ref": <global article number>, "title": "title", "why": "why this matters"}],\n'
        '  "context": "background on what led up to this period",\n'
        '  "outlook": "what to watch for next"\n'
        '}\n\n'
        "Batches:\n\n"
        f"{batches_text}"
    )


def _parse_digest_json(raw: str, items) -> dict:
    """Parse the model's JSON response into a dict.

    Handles the local model occasionally wrapping the object in prose or
    emitting a bare string; retries the LLM once before giving up.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict):
        return data
    if isinstance(data, str):
        embedded = _extract_json_object(data)
        if embedded is not None:
            data = embedded
            if isinstance(data, dict):
                return data
    embedded = _extract_json_object(raw)
    if isinstance(embedded, dict):
        return embedded
    return data


def _extract_json_object(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    return None
    return None


def generate_digest(topic: str, from_: str, to: str, force: bool = False, dry_run: bool = False, progress=None) -> dict:
    conn = get_conn()

    if not force:
        row = conn.execute(
            "SELECT content, item_count FROM digests WHERE topic=? AND from_date=? AND to_date=?",
            (topic, from_, to),
        ).fetchone()
        if row:
            conn.close()
            if progress:
                progress("cached", 100, item_count=row["item_count"])
            return {"digest": json.loads(row["content"]), "item_count": row["item_count"], "cached": True}

    if progress:
        progress("fetching", 10)
    items = fetch_items(topic, from_, to)
    if not items:
        conn.close()
        if progress:
            progress("failed", 100, error="No articles found for this topic and date range")
        raise ValueError("No articles found for topic and date range")

    if len(items) <= settings.DIGEST_CHUNK_SIZE:
        if progress:
            progress("generating", 30, item_count=len(items))
        prompt = build_prompt(items)
        data = _handle_raw(prompt, items, progress)
    else:
        data = _two_pass(items, progress)

    if dry_run:
        conn.close()
        return {"digest": data, "item_count": len(items), "cached": False, "_dry": True}

    for story in data.get("key_stories", []):
        if not isinstance(story, dict):
            continue
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

    if progress:
        progress("done", 100, item_count=len(items))
    return {"digest": data, "item_count": len(items), "cached": False}


def _handle_raw(prompt: str, items, progress) -> dict:
    """Parse the model's output into a dict, retrying the LLM once if needed."""
    raw = chat(prompt, system=_SYSTEM)
    try:
        data = _parse_digest_json(raw, items)
    except (json.JSONDecodeError, TypeError):
        raw = chat(prompt, system=_SYSTEM)
        data = _parse_digest_json(raw, items)

    if not isinstance(data, dict):
        if progress:
            progress("failed", 100, error="The model did not return a structured brief")
        raise RuntimeError(
            "The model did not return a structured brief (it returned too much content to fit). "
            "Narrow the date range or use the search box, then try again."
        )
    return data


def _two_pass(items, progress) -> dict:
    """Hierarchical brief: summarize each article batch, then merge the
    condensed digests into one final brief so long ranges fit the model."""
    size = settings.DIGEST_CHUNK_SIZE
    chunks = list(_chunk(items, size))
    total = len(chunks)

    if progress:
        progress("generating", 20, item_count=len(items))

    chunk_digests = []
    base = 0
    for ci, chunk in enumerate(chunks, 1):
        if progress:
            progress("chunk", 20 + int(ci / total * 60), item_count=len(items))
        prompt = build_chunk_prompt(chunk, ci, total)
        raw = chat(prompt, system=_SYSTEM)
        try:
            data = _parse_digest_json(raw, chunk)
        except (json.JSONDecodeError, TypeError):
            raw = chat(prompt, system=_SYSTEM)
            data = _parse_digest_json(raw, chunk)
        if not isinstance(data, dict):
            data = {"period_summary": "", "themes": [], "key_stories": [], "context": "", "outlook": ""}
        for story in data.get("key_stories", []):
            if isinstance(story, dict) and isinstance(story.get("ref"), int):
                story["ref"] = base + story["ref"]
        chunk_digests.append(data)
        base += len(chunk)

    if progress:
        progress("combining", 85, item_count=len(items))
    prompt = build_combine_prompt(chunk_digests)
    raw = chat(prompt, system=_SYSTEM)
    try:
        data = _parse_digest_json(raw, items)
    except (json.JSONDecodeError, TypeError):
        raw = chat(prompt, system=_SYSTEM)
        data = _parse_digest_json(raw, items)

    if not isinstance(data, dict):
        if progress:
            progress("failed", 100, error="The model did not return a structured brief")
        raise RuntimeError(
            "The model did not return a structured brief after merging batches. "
            "Try again, or narrow the date range."
        )
    return data


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
