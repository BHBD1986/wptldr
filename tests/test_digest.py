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


def test_parse_digest_json_extracts_embedded_object():
    from backend.digest import _parse_digest_json, _extract_json_object

    raw = 'Sure! Here is the brief: {"period_summary": "ok", "themes": [], "key_stories": [], "context": "", "outlook": ""}'
    out = _parse_digest_json(raw, [])
    assert out["period_summary"] == "ok"

    assert _extract_json_object('{"a": 1}') == {"a": 1}
    assert _extract_json_object('prefix {"a": 1} suffix') == {"a": 1}
    assert _extract_json_object("no json here") is None


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


def test_two_pass_digest_for_large_ranges(monkeypatch, tmp_path):
    """Ranges with more than DIGEST_CHUNK_SIZE items use hierarchical two-pass."""
    import sqlite3
    from backend.config import settings
    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(settings, "DIGEST_CHUNK_SIZE", 3)
    from backend.db import init_db, get_conn
    init_db()

    conn = get_conn()
    for i in range(1, 8):
        conn.execute(
            "INSERT INTO articles (id, wp_id, title, url, section, published_at, categories, content_text, excerpt, word_count, ingested_at) "
            "VALUES (?, ?, ?, 'http://x.com', 'tech', ?, '[]', 'text', 'exc', 10, 'now')",
            (i, i, f"Article {i}", f"2026-07-0{i}T00:00:00"),
        )
        conn.execute("INSERT INTO article_topics VALUES (?, 'agtech', 3)", (i,))
        conn.execute("INSERT INTO summaries VALUES (?, 'tldr', '[]', 'w', 'm', 'now')", (i,))
    conn.commit()
    conn.close()

    chunk_calls = []
    combine_calls = []

    def fake_chat(prompt, system="", json_mode=True):
        if "Combine them" in prompt:
            combine_calls.append(prompt)
            return json.dumps({
                "period_summary": "final",
                "themes": [],
                "key_stories": [{"ref": 7, "title": "Story", "why": "why"}],
                "context": "ctx",
                "outlook": "out",
            })
        chunk_calls.append(prompt)
        return json.dumps({
            "period_summary": "batch",
            "themes": [],
            "key_stories": [{"ref": 1, "title": "ChunkStory", "why": "why"}],
            "context": "c",
            "outlook": "o",
        })

    monkeypatch.setattr(backend.digest, "chat", fake_chat)

    result = backend.digest.generate_digest("agtech", "2026-07-01", "2026-07-31")

    assert len(chunk_calls) == 3
    assert len(combine_calls) == 1
    assert result["item_count"] == 7
    assert result["digest"]["period_summary"] == "final"
    # ref 7 is a 1-based index into the date-desc list (oldest article, id 1)
    assert result["digest"]["key_stories"][0]["article_id"] == 1
