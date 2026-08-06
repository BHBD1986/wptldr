import json

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.config import settings


@pytest.fixture
def seeded_db(monkeypatch, tmp_path):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(settings, "DB_PATH", db_path)

    from backend.db import init_db, get_conn
    init_db()
    conn = get_conn()

    conn.execute(
        """INSERT INTO articles (id, wp_id, title, url, section, published_at,
            categories, content_text, excerpt, word_count, ingested_at)
           VALUES (1, 100, 'AgTech robot', 'https://ex.com/1', 'machinery',
                   '2026-07-23T12:00:00', '["machinery"]',
                   'autonomous drone uses AI for precision farming',
                   'excerpt1', 10, '2026-07-24')"""
    )
    conn.execute(
        """INSERT INTO articles (id, wp_id, title, url, section, published_at,
            categories, content_text, excerpt, word_count, ingested_at)
           VALUES (2, 101, 'Cattle prices', 'https://ex.com/2', 'markets',
                   '2026-07-22T12:00:00', '["markets"]',
                   'feeder cattle market prices up bushel per tonne',
                   'excerpt2', 10, '2026-07-24')"""
    )
    conn.execute(
        "INSERT INTO article_topics VALUES (1, 'agtech', 4.0)"
    )
    conn.execute(
        "INSERT INTO article_topics VALUES (2, 'markets', 6.0)"
    )
    conn.execute(
        """INSERT INTO summaries (article_id, tldr, key_points, why_it_matters, model, created_at)
           VALUES (1, 'Robot summary', '["key1","key2"]', 'matters', 'test', '2026-07-24')"""
    )
    conn.commit()
    conn.close()
    return db_path


def test_topics_counts(seeded_db):
    resp = TestClient(app).get("/api/topics")
    assert resp.status_code == 200
    topics = {t["topic"]: t["count"] for t in resp.json()}
    assert topics["agtech"] == 1
    assert topics["markets"] == 1


def test_articles_filter_by_topic(seeded_db):
    resp = TestClient(app).get("/api/articles?topic=agtech")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["tldr"] == "Robot summary"


def test_article_404(seeded_db):
    resp = TestClient(app).get("/api/articles/999")
    assert resp.status_code == 404


def test_import_replaces_database(seeded_db, tmp_path):
    import sqlite3

    from backend.db import init_db

    new_db = tmp_path / "new.db"
    settings.DB_PATH = str(new_db)
    init_db()
    conn = sqlite3.connect(str(new_db))
    conn.execute(
        "INSERT INTO articles (id, wp_id, title, url, section, published_at, categories, content_text, excerpt, word_count, ingested_at) "
        "VALUES (1, 1, 'Imported article', 'http://x.com', 'news', '2026-07-01', '[]', 'text', 'exc', 10, 'now')"
    )
    conn.commit()
    conn.close()
    settings.DB_PATH = seeded_db

    client = TestClient(app)
    with open(new_db, "rb") as f:
        resp = client.post("/api/import", files={"file": ("new.db", f, "application/octet-stream")})

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["articles"] == 1

    stats = client.get("/api/stats").json()
    assert stats["articles"] == 1


def test_import_rejects_non_db_file(seeded_db, tmp_path):
    junk = tmp_path / "junk.db"
    junk.write_text("not a database")
    client = TestClient(app)
    with open(junk, "rb") as f:
        resp = client.post("/api/import", files={"file": ("junk.db", f, "application/octet-stream")})
    assert resp.status_code == 400
