"""Path resolution for both dev and packaged (PyInstaller) environments.

In dev, the app stores data next to the project. When frozen into a
desktop app, the bundle is read-only, so data lives in a writable,
per-user application data directory instead.
"""

import os
import shutil
import sys
from pathlib import Path


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def app_data_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        return Path(base) / "WPTLDR"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "WPTLDR"
    return Path.home() / ".wptldr"


def db_path() -> Path:
    return app_data_dir() / "wptldr.db"


def frontend_dir() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", ".")) / "frontend"
    return Path(__file__).resolve().parents[1] / "frontend"


def configure_settings() -> None:
    """Point the DB path at the user app-data dir when packaged."""
    from backend.config import settings

    if not is_frozen():
        return
    base = app_data_dir()
    base.mkdir(parents=True, exist_ok=True)
    settings.DB_PATH = str(db_path())


def _db_is_empty(path: Path) -> bool:
    """True when the target DB is missing, has no tables, or holds no articles."""
    return _db_fingerprint(path)[1] == 0


def _db_fingerprint(path: Path) -> tuple[str | None, int, int]:
    """Return (newest published_at, article count, summary count) for a DB.

    Falls back to (None, 0, 0) when the file is missing, empty, or unreadable.
    """
    if not path.exists() or path.stat().st_size == 0:
        return None, 0, 0
    try:
        import sqlite3

        conn = sqlite3.connect(str(path))
        try:
            try:
                articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
            except sqlite3.Error:
                articles = 0
            try:
                max_date = conn.execute(
                    "SELECT MAX(published_at) FROM articles"
                ).fetchone()[0]
            except sqlite3.Error:
                max_date = None
            try:
                summaries = conn.execute("SELECT COUNT(*) FROM summaries").fetchone()[0]
            except sqlite3.Error:
                summaries = 0
            return (max_date, articles or 0, summaries or 0)
        finally:
            conn.close()
    except Exception:
        return None, 0, 0


def seed_max_date(path: Path) -> str | None:
    """Newest article date in a DB, or None when it is missing/empty/unreadable."""
    return _db_fingerprint(path)[0]


def seed_is_newer(seed: Path, target: Path) -> bool:
    """True when the bundled seed holds newer data than the target DB.

    Triggers on a newer newest-article date, more articles, or more summaries,
    so upgrades also deliver summaries added to the bundle since last install.
    """
    if not seed.exists():
        return False
    seed_date, seed_articles, seed_summaries = _db_fingerprint(seed)
    if seed_articles == 0:
        return False
    target_date, target_articles, target_summaries = _db_fingerprint(target)
    if target_articles == 0:
        return True
    if seed_date and target_date:
        if seed_date != target_date:
            return seed_date > target_date
    elif seed_date and not target_date:
        return True
    if seed_articles > target_articles:
        return True
    return seed_summaries > target_summaries


def _bundled_seed_path() -> Path:
    return Path(getattr(sys, "_MEIPASS", ".")) / "seed" / "wptldr.db"


def _backup_db(target: Path) -> None:
    if target.exists():
        shutil.copy2(target, target.with_suffix(".db.bak"))


def _seed_fingerprint(seed: Path) -> str:
    """Content hash of the bundled seed, used to detect a new dataset."""
    import hashlib

    digest = hashlib.sha256()
    with open(seed, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_meta(conn) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
    )


def _read_fingerprint(target: Path) -> str | None:
    """Return the seed fingerprint last applied to this DB, if any."""
    if not target.exists() or target.stat().st_size == 0:
        return None
    try:
        import sqlite3

        conn = sqlite3.connect(str(target))
        try:
            _ensure_meta(conn)
            row = conn.execute(
                "SELECT value FROM meta WHERE key='seed_fingerprint'"
            ).fetchone()
            return row[0] if row else None
        finally:
            conn.close()
    except Exception:
        return None


def _write_fingerprint(target: Path, value: str) -> None:
    import sqlite3

    conn = sqlite3.connect(str(target))
    try:
        _ensure_meta(conn)
        conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) "
            "VALUES ('seed_fingerprint', ?)",
            (value,),
        )
        conn.commit()
    finally:
        conn.close()


def seed_db() -> bool:
    """Copy the bundled seed database to the user's app-data dir on first run.

    Replaces a missing, empty, or article-free DB so first launch already has
    the 2026 articles/summaries. Never overwrites an existing populated DB.
    """
    if not is_frozen():
        return False
    target = db_path()
    if not _db_is_empty(target):
        return False
    seed = _bundled_seed_path()
    if not seed.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(seed, target)
    return True


def sync_seed() -> tuple[int, int] | None:
    """Merge the bundled dataset into an existing user DB, keyed on ``wp_id``.

    The local autoincrement ``id`` is never used as the join key: on installs
    whose id numbering differs from the bundle's (e.g. after the app's Update
    fetched articles in another order), joining on ``id`` attaches summaries
    and topics to the wrong articles. Here every bundled row is matched to the
    target by its stable WordPress id.

    Articles present in the bundle are reconciled to the bundled summaries and
    topics; user-only articles and ``expansions`` are left untouched. Returns
    ``(articles_added, summaries_added)`` or ``None`` when nothing was done.
    """
    if not is_frozen():
        return None
    target = db_path()
    seed = _bundled_seed_path()
    if not seed.exists() or not target.exists():
        return None

    _backup_db(target)
    import sqlite3

    conn = sqlite3.connect(str(target))
    try:
        conn.execute("ATTACH DATABASE ? AS seed", (str(seed),))
        before_articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        before_summaries = conn.execute("SELECT COUNT(*) FROM summaries").fetchone()[0]

        # 1. Add articles missing from the target, matched on wp_id. Omitting
        #    the local id lets SQLite assign a fresh one, so a numerically
        #    colliding row can never shadow a different article.
        conn.execute(
            """INSERT OR IGNORE INTO articles
               (wp_id, title, url, section, published_at, categories,
                content_text, excerpt, word_count, ingested_at)
               SELECT wp_id, title, url, section, published_at, categories,
                      content_text, excerpt, word_count, ingested_at
               FROM seed.articles"""
        )
        # 2. Rebuild topics for every bundled article, mapped wp_id -> target
        #    id. Deleting first removes any previously mis-assigned rows.
        conn.execute(
            """DELETE FROM article_topics
               WHERE article_id IN (
                   SELECT ta.id FROM articles ta
                   JOIN seed.articles sa ON sa.wp_id = ta.wp_id)"""
        )
        conn.execute(
            """INSERT OR REPLACE INTO article_topics (article_id, topic, score)
               SELECT ta.id, st.topic, st.score
               FROM seed.article_topics st
               JOIN seed.articles sa ON sa.id = st.article_id
               JOIN articles ta ON ta.wp_id = sa.wp_id"""
        )
        # 3. Bundled summaries for bundled articles, mapped by wp_id.
        conn.execute(
            """INSERT OR REPLACE INTO summaries
               (article_id, tldr, key_points, why_it_matters, model, created_at)
               SELECT ta.id, s.tldr, s.key_points, s.why_it_matters,
                      s.model, s.created_at
               FROM seed.summaries s
               JOIN seed.articles sa ON sa.id = s.article_id
               JOIN articles ta ON ta.wp_id = sa.wp_id"""
        )
        # 4. Bundled briefs win over any stale local copy.
        conn.execute(
            """INSERT OR REPLACE INTO digests
               (topic, from_date, to_date, content, item_count, model, created_at)
               SELECT topic, from_date, to_date, content, item_count, model,
                      created_at
               FROM seed.digests"""
        )
        conn.commit()
        after_articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        after_summaries = conn.execute("SELECT COUNT(*) FROM summaries").fetchone()[0]
        return after_articles - before_articles, after_summaries - before_summaries
    finally:
        conn.close()


def ensure_seed() -> str:
    """Seed on first run, or reconcile the DB with the bundled dataset.

    Runs the merge when the bundled seed fingerprint differs from the one last
    applied (which repairs installs whose summaries/topics were mis-assigned by
    older id-keyed merges), or when the bundle is simply newer. The applied
    fingerprint is recorded so the merge runs at most once per dataset.

    Returns a short status string suitable for logging.
    """
    if not is_frozen():
        return "dev"
    seed = _bundled_seed_path()
    target = db_path()
    if _db_is_empty(target):
        if not seed_db():
            return "no-seed"
        _write_fingerprint(target, _seed_fingerprint(seed))
        return "seeded"
    if not seed.exists():
        return "no-seed"

    fingerprint = _seed_fingerprint(seed)
    already_applied = _read_fingerprint(target)
    if already_applied == fingerprint and not seed_is_newer(seed, target):
        return "current"

    result = sync_seed()
    if result is None:
        return "no-seed"
    _write_fingerprint(target, fingerprint)
    added_articles, added_summaries = result
    return f"synced (+{added_articles} articles, +{added_summaries} summaries)"
