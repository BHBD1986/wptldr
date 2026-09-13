import sqlite3

from backend import summarize
from backend.summarizer import _article_text

_SCHEMA = """
CREATE TABLE articles (
    id INTEGER PRIMARY KEY, wp_id INTEGER, title TEXT, url TEXT, section TEXT,
    published_at TEXT, categories TEXT, content_text TEXT, excerpt TEXT,
    word_count INTEGER, ingested_at TEXT
);
CREATE TABLE article_topics (
    article_id INTEGER, topic TEXT, score REAL, PRIMARY KEY (article_id, topic)
);
CREATE TABLE summaries (
    article_id INTEGER PRIMARY KEY, tldr TEXT, key_points TEXT,
    why_it_matters TEXT, model TEXT, created_at TEXT
);
"""


def _connect(path):
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def _seed_db(path, articles, topics=()):
    conn = _connect(path)
    conn.executescript(_SCHEMA)
    conn.executemany(
        "INSERT INTO articles VALUES (?,?,?,?,?,?,?,?,?,?,?)", articles
    )
    if topics:
        conn.executemany("INSERT INTO article_topics VALUES (?,?,?)", topics)
    conn.commit()
    conn.close()


def _fake_summarizer(calls):
    def fake(conn, row):
        calls.append(row["id"])
        conn.execute(
            "INSERT OR REPLACE INTO summaries (article_id, tldr) VALUES (?,?)",
            (row["id"], "summary"),
        )
        conn.commit()
        return {"tldr": "summary", "key_points": [], "why_it_matters": ""}

    return fake


def test_article_text_pads_short_content_with_excerpt():
    row = {"content_text": "Short.", "excerpt": "Extra detail from the excerpt."}
    text = _article_text(row)
    assert "Short." in text
    assert "Extra detail from the excerpt." in text


def test_run_coverage_includes_short_articles(monkeypatch, tmp_path):
    db = tmp_path / "coverage.db"
    _seed_db(
        db,
        [
            (1, 101, "short", "u", "s", "2026-09-12T10:00:00", "[]", "tiny", "", 30, "t"),
            (2, 102, "long", "u", "s", "2026-09-11T10:00:00", "[]", "body " * 300, "", 600, "t"),
        ],
    )

    calls = []
    monkeypatch.setattr(summarize, "get_conn", lambda: _connect(db))
    monkeypatch.setattr(summarize, "summarize_article", _fake_summarizer(calls))

    summarize.run_coverage(limit=10, dry_run=False)

    assert set(calls) == {1, 2}
    conn = _connect(db)
    assert conn.execute("SELECT COUNT(*) FROM summaries").fetchone()[0] == 2
    conn.close()


def test_run_topic_includes_short_articles(monkeypatch, tmp_path):
    db = tmp_path / "topic.db"
    _seed_db(
        db,
        [
            (1, 101, "short crops", "u", "s", "2026-09-12T10:00:00", "[]", "tiny", "", 20, "t"),
            (2, 102, "other", "u", "s", "2026-09-11T10:00:00", "[]", "body " * 300, "", 600, "t"),
        ],
        topics=[(1, "crops", 1.0), (2, "livestock", 1.0)],
    )

    calls = []
    monkeypatch.setattr(summarize, "get_conn", lambda: _connect(db))
    monkeypatch.setattr(summarize, "summarize_article", _fake_summarizer(calls))

    summarize.run(limit=10, topic="crops", dry_run=False)

    assert calls == [1]


def test_run_coverage_skips_already_summarized(monkeypatch, tmp_path):
    db = tmp_path / "skip.db"
    _seed_db(
        db,
        [
            (1, 101, "done", "u", "s", "2026-09-12T10:00:00", "[]", "body " * 300, "", 600, "t"),
            (2, 102, "todo", "u", "s", "2026-09-11T10:00:00", "[]", "body " * 300, "", 600, "t"),
        ],
    )
    conn = _connect(db)
    conn.execute("INSERT INTO summaries (article_id, tldr) VALUES (1, 'x')")
    conn.commit()
    conn.close()

    calls = []
    monkeypatch.setattr(summarize, "get_conn", lambda: _connect(db))
    monkeypatch.setattr(summarize, "summarize_article", _fake_summarizer(calls))

    summarize.run_coverage(limit=10, dry_run=False)

    assert calls == [2]
