import json
from datetime import datetime

from backend.db import get_conn
from backend.llm import chat, model_name
from backend.text_utils import truncate

_SUMMARY_SYSTEM = (
    "You are an agriculture news summarizer for Canadian farmers. Output ONLY valid JSON."
)
_SUMMARY_PROMPT = (
    'Title: {title}\n\nText:\n{text}\n\n'
    'Return JSON: {{"tldr": "<=60 words summary", '
    '"key_points": ["3-5 short bullet points"], '
    '"why_it_matters": "<=25 words"}}'
)


def _article_text(article_row) -> str:
    """Body text for summarization, padding very short articles with the excerpt."""
    content = article_row["content_text"] or ""
    text = truncate(content, 6000)
    if len(content.strip()) < 200:
        try:
            excerpt = (article_row["excerpt"] or "").strip()
        except (IndexError, KeyError):
            excerpt = ""
        if excerpt and excerpt not in text:
            text = f"{text}\n\n{excerpt}".strip()
    return text


def summarize_article(conn, article_row) -> dict:
    title = article_row["title"]
    text = _article_text(article_row)
    user = _SUMMARY_PROMPT.format(title=title, text=text)

    raw = chat(user, system=_SUMMARY_SYSTEM)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raw = chat(user, system=_SUMMARY_SYSTEM)
        data = json.loads(raw)

    conn.execute(
        """INSERT OR REPLACE INTO summaries
           (article_id, tldr, key_points, why_it_matters, model, created_at)
           VALUES (?,?,?,?,?,?)""",
        (
            article_row["id"],
            data.get("tldr", ""),
            json.dumps(data.get("key_points", [])),
            data.get("why_it_matters", ""),
            model_name(),
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    return data
