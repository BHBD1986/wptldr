import sqlite3
from pathlib import Path

from backend.config import settings

_initialized_paths: set[str] = set()


def get_conn() -> sqlite3.Connection:
    db_path = Path(settings.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    if str(db_path.resolve()) not in _initialized_paths:
        init_db(conn)
        _initialized_paths.add(str(db_path.resolve()))
    return conn


def init_db(conn: sqlite3.Connection | None = None) -> None:
    _owns_conn = conn is None
    if conn is None:
        conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY,
            wp_id INTEGER UNIQUE,
            title TEXT,
            url TEXT,
            section TEXT,
            published_at TEXT,
            categories TEXT,
            content_text TEXT,
            excerpt TEXT,
            word_count INTEGER,
            ingested_at TEXT
        );

        CREATE TABLE IF NOT EXISTS article_topics (
            article_id INTEGER,
            topic TEXT,
            score REAL,
            PRIMARY KEY (article_id, topic)
        );

        CREATE TABLE IF NOT EXISTS summaries (
            article_id INTEGER PRIMARY KEY,
            tldr TEXT,
            key_points TEXT,
            why_it_matters TEXT,
            model TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS expansions (
            article_id INTEGER PRIMARY KEY,
            content TEXT,
            model TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS digests (
            id INTEGER PRIMARY KEY,
            topic TEXT,
            from_date TEXT,
            to_date TEXT,
            content TEXT,
            item_count INTEGER,
            model TEXT,
            created_at TEXT,
            UNIQUE(topic, from_date, to_date)
        );
    """)
    conn.commit()
    if _owns_conn:
        conn.close()
