import json

import backend.digest


def test_build_prompt_numbering():
    from backend.digest import build_prompt

    items = [
        {"id": 1, "title": "Article A", "published_at": "2026-07-01T00:00:00", "tldr": "summary a"},
        {"id": 2, "title": "Article B", "published_at": "2026-07-02T00:00:00", "tldr": "summary b"},
    ]
    prompt = build_prompt(items)
    assert "[1]" in prompt
    assert "[2]" in prompt
    assert "key_stories" in prompt
    assert "Article A" in prompt


def test_generate_digest_stores_and_maps_refs(monkeypatch, tmp_path):
    import sqlite3
    from backend.config import settings
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "test.db"))
    from backend.db import init_db, get_conn
    init_db()

    conn = get_conn()
    conn.execute(
        "INSERT INTO articles (id, wp_id, title, url, section, published_at, categories, content_text, excerpt, word_count, ingested_at) "
        "VALUES (1, 1, 'AI', 'http://x.com/1', 'tech', '2026-07-01T00:00:00', '[]', 'text', 'exc', 10, 'now'), "
        "(2, 2, 'Crop', 'http://x.com/2', 'crops', '2026-07-02T00:00:00', '[]', 'text', 'exc', 10, 'now')"
    )
    conn.execute(
        "INSERT INTO article_topics VALUES (1, 'agtech', 3), (2, 'agtech', 3)"
    )
    conn.execute(
        "INSERT INTO summaries VALUES (1, 'tldr1', '[]', 'w', 'm', 'now'), (2, 'tldr2', '[]', 'w', 'm', 'now')"
    )
    conn.commit()
    conn.close()

    canned = json.dumps({
        "period_summary": "test",
        "themes": [{"theme": "T1", "description": "D1"}],
        "key_stories": [{"ref": 1, "title": "title", "why": "why"}],
        "context": "ctx",
        "outlook": "out",
    })

    original_chat = backend.digest.chat
    monkeypatch.setattr(backend.digest, "chat", lambda *a, **kw: canned)

    result = backend.digest.generate_digest("agtech", "2026-07-01", "2026-07-31")

    assert result["cached"] is False
    assert result["item_count"] == 2
    assert result["digest"]["period_summary"] == "test"
    stories = result["digest"]["key_stories"]
    assert stories[0]["article_id"] == 2
    assert stories[0]["title"] == "Crop"

    cached = backend.digest.generate_digest("agtech", "2026-07-01", "2026-07-31")
    assert cached["cached"] is True
