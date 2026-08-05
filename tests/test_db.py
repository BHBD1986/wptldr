import sqlite3
from pathlib import Path

import pytest
from backend import db
from backend.config import settings


def test_init_db_creates_all_tables(monkeypatch, tmp_path):
    test_db = str(tmp_path / "test.db")
    monkeypatch.setattr(settings, "DB_PATH", test_db)
    db.init_db()
    conn = sqlite3.connect(test_db)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    assert tables == ["article_topics", "articles", "digests", "expansions", "summaries"]
