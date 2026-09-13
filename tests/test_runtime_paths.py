import os
import sys

import pytest

from backend import runtime_paths as rp


def test_env_override_for_settings(monkeypatch):
    from backend.config import Settings

    monkeypatch.setenv("SUMMARIZE_LIMIT", "7")
    monkeypatch.setenv("LLM_API_KEY", "from-env")
    s = Settings()
    assert s.SUMMARIZE_LIMIT == 7
    assert s.LLM_API_KEY == "from-env"


def test_app_data_dir_uses_localappdata_on_windows(monkeypatch):
    if os.name != "nt":
        return
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\Test\AppData\Local")
    assert str(rp.app_data_dir()) == r"C:\Users\Test\AppData\Local\WPTLDR"


def test_frontend_dir_exists_in_dev():
    assert rp.frontend_dir().is_dir()


def test_seed_db_copies_bundle_when_target_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(rp, "is_frozen", lambda: True)
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    (seed_dir / "wptldr.db").write_bytes(b"seed-bytes")
    monkeypatch.setattr(rp, "db_path", lambda: tmp_path / "target" / "wptldr.db")
    monkeypatch.setattr(rp, "app_data_dir", lambda: tmp_path / "target")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert rp.seed_db() is True
    assert (tmp_path / "target" / "wptldr.db").read_bytes() == b"seed-bytes"


def test_seed_db_does_not_overwrite_populated_db(monkeypatch, tmp_path):
    import sqlite3

    monkeypatch.setattr(rp, "is_frozen", lambda: True)
    target = tmp_path / "wptldr.db"
    conn = sqlite3.connect(str(target))
    conn.execute("CREATE TABLE articles (id INTEGER)")
    conn.execute("INSERT INTO articles VALUES (1)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(rp, "db_path", lambda: target)

    assert rp.seed_db() is False
    assert sqlite3.connect(str(target)).execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 1


def test_seed_db_replaces_empty_schema_db(monkeypatch, tmp_path):
    import sqlite3

    monkeypatch.setattr(rp, "is_frozen", lambda: True)
    target = tmp_path / "wptldr.db"
    conn = sqlite3.connect(str(target))
    conn.execute("CREATE TABLE articles (id INTEGER)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(rp, "db_path", lambda: target)
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    (seed_dir / "wptldr.db").write_bytes(b"seed-bytes")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert rp.seed_db() is True
    assert target.read_bytes() == b"seed-bytes"


def test_seed_db_noop_in_dev(monkeypatch, tmp_path):
    monkeypatch.setattr(rp, "is_frozen", lambda: False)
    assert rp.seed_db() is False


_SCHEMA = """
CREATE TABLE articles (
    id INTEGER PRIMARY KEY, wp_id INTEGER UNIQUE, title TEXT, url TEXT,
    section TEXT, published_at TEXT, categories TEXT, content_text TEXT,
    excerpt TEXT, word_count INTEGER, ingested_at TEXT
);
CREATE TABLE article_topics (
    article_id INTEGER, topic TEXT, score REAL, PRIMARY KEY (article_id, topic)
);
CREATE TABLE summaries (
    article_id INTEGER PRIMARY KEY, tldr TEXT, key_points TEXT,
    why_it_matters TEXT, model TEXT, created_at TEXT
);
CREATE TABLE expansions (
    article_id INTEGER PRIMARY KEY, content TEXT, model TEXT, created_at TEXT
);
CREATE TABLE digests (
    id INTEGER PRIMARY KEY, topic TEXT, from_date TEXT, to_date TEXT,
    content TEXT, item_count INTEGER, model TEXT, created_at TEXT,
    UNIQUE(topic, from_date, to_date)
);
"""


def _article(article_id, published_at):
    return (
        article_id, article_id, f"title-{article_id}", "http://x", "section",
        published_at, "agtech", "body", "excerpt", 10, "2026-01-01",
    )


def _make_db(path, articles, summaries=(), topics=(), digests=()):
    import sqlite3

    conn = sqlite3.connect(str(path))
    conn.executescript(_SCHEMA)
    conn.executemany("INSERT INTO articles VALUES (?,?,?,?,?,?,?,?,?,?,?)", articles)
    if summaries:
        conn.executemany("INSERT INTO summaries VALUES (?,?,?,?,?,?)", summaries)
    if topics:
        conn.executemany("INSERT INTO article_topics VALUES (?,?,?)", topics)
    if digests:
        conn.executemany(
            "INSERT INTO digests "
            "(topic, from_date, to_date, content, item_count, model, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            digests,
        )
    conn.commit()
    conn.close()


def _frozen(tmp_path, monkeypatch, seed):
    monkeypatch.setattr(rp, "is_frozen", lambda: True)
    monkeypatch.setattr(rp, "db_path", lambda: tmp_path / "wptldr.db")
    monkeypatch.setattr(rp, "_bundled_seed_path", lambda: seed)


def test_seed_is_newer_compares_dates(monkeypatch, tmp_path):
    old = tmp_path / "old.db"
    new = tmp_path / "new.db"
    _make_db(old, [_article(1, "2026-08-06T10:00:00")])
    _make_db(
        new,
        [_article(1, "2026-08-06T10:00:00"), _article(2, "2026-09-11T10:00:00")],
    )

    assert rp.seed_max_date(new) == "2026-09-11T10:00:00"
    assert rp.seed_is_newer(new, old) is True
    assert rp.seed_is_newer(old, new) is False
    assert rp.seed_is_newer(old, old) is False
    assert rp.seed_is_newer(tmp_path / "missing.db", old) is False


def test_seed_is_newer_detects_added_summaries(monkeypatch, tmp_path):
    seed = tmp_path / "seed.db"
    target = tmp_path / "wptldr.db"
    _make_db(target, [_article(1, "2026-09-11T10:00:00")])
    _make_db(
        seed,
        [_article(1, "2026-09-11T10:00:00")],
        summaries=[(1, "seed summary", "kp", "why", "m", "t")],
    )

    assert rp.seed_is_newer(seed, target) is True
    assert rp.seed_is_newer(target, seed) is False


def test_sync_seed_adds_missing_summaries(monkeypatch, tmp_path):
    import sqlite3

    seed = tmp_path / "seed.db"
    target = tmp_path / "wptldr.db"
    _make_db(target, [_article(1, "2026-09-11T10:00:00")])
    _make_db(
        seed,
        [_article(1, "2026-09-11T10:00:00")],
        summaries=[(1, "seed summary", "kp", "why", "m", "t")],
    )

    _frozen(tmp_path, monkeypatch, seed)
    assert rp.ensure_seed().startswith("synced")

    conn = sqlite3.connect(str(target))
    assert conn.execute("SELECT COUNT(*) FROM summaries").fetchone()[0] == 1
    conn.close()


def test_sync_seed_merges_newer_bundle(monkeypatch, tmp_path):
    import sqlite3

    seed = tmp_path / "seed.db"
    target = tmp_path / "wptldr.db"
    _make_db(
        target,
        [_article(1, "2026-08-06T10:00:00")],
        summaries=[(1, "user summary", "kp", "why", "m", "t")],
    )
    _make_db(
        seed,
        [_article(1, "2026-08-06T10:00:00"), _article(2, "2026-09-11T10:00:00")],
        summaries=[
            (1, "seed summary", "kp", "why", "m", "t"),
            (2, "seed summary 2", "kp", "why", "m", "t"),
        ],
        topics=[(1, "agtech", 1.0), (2, "crops", 1.0)],
        digests=[("agtech", "2026-01-01", "2026-09-11", "{}", 300, "m", "t")],
    )
    conn = sqlite3.connect(str(target))
    conn.execute("INSERT INTO expansions VALUES (1, 'user expansion', 'm', 't')")
    conn.commit()
    conn.close()

    _frozen(tmp_path, monkeypatch, seed)
    assert rp.sync_seed() == (1, 1)

    conn = sqlite3.connect(str(target))
    assert conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM summaries").fetchone()[0] == 2
    assert (
        conn.execute("SELECT tldr FROM summaries WHERE article_id=1").fetchone()[0]
        == "seed summary"
    )
    assert conn.execute("SELECT COUNT(*) FROM article_topics").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM digests").fetchone()[0] == 1
    assert (
        conn.execute(
            "SELECT content FROM expansions WHERE article_id=1"
        ).fetchone()[0]
        == "user expansion"
    )
    conn.close()

    assert (tmp_path / "wptldr.db.bak").exists()
    assert rp.ensure_seed() == "current"
    assert rp.sync_seed() == (0, 0)


def test_sync_seed_noop_when_current(monkeypatch, tmp_path):
    seed = tmp_path / "seed.db"
    target = tmp_path / "wptldr.db"
    _make_db(target, [_article(1, "2026-09-11T10:00:00")])
    _make_db(seed, [_article(1, "2026-09-11T10:00:00")])

    _frozen(tmp_path, monkeypatch, seed)
    assert rp.ensure_seed() == "current"
    assert not (tmp_path / "wptldr.db.bak").exists()


def test_sync_seed_noop_in_dev(monkeypatch):
    monkeypatch.setattr(rp, "is_frozen", lambda: False)
    assert rp.sync_seed() is None


def test_ensure_seed_first_run_copies(monkeypatch, tmp_path):
    seed = tmp_path / "seed.db"
    _make_db(seed, [_article(1, "2026-09-11T10:00:00")])

    _frozen(tmp_path, monkeypatch, seed)
    assert rp.ensure_seed() == "seeded"
    assert (tmp_path / "wptldr.db").exists()


def test_ensure_seed_syncs_newer_bundle(monkeypatch, tmp_path):
    seed = tmp_path / "seed.db"
    target = tmp_path / "wptldr.db"
    _make_db(target, [_article(1, "2026-08-06T10:00:00")])
    _make_db(
        seed,
        [_article(1, "2026-08-06T10:00:00"), _article(2, "2026-09-11T10:00:00")],
    )

    _frozen(tmp_path, monkeypatch, seed)
    assert rp.ensure_seed().startswith("synced")


def test_ensure_seed_current(monkeypatch, tmp_path):
    seed = tmp_path / "seed.db"
    target = tmp_path / "wptldr.db"
    _make_db(target, [_article(1, "2026-09-11T10:00:00")])
    _make_db(seed, [_article(1, "2026-09-11T10:00:00")])

    _frozen(tmp_path, monkeypatch, seed)
    assert rp.ensure_seed() == "current"


def test_ensure_seed_noop_in_dev(monkeypatch):
    monkeypatch.setattr(rp, "is_frozen", lambda: False)
    assert rp.ensure_seed() == "dev"
