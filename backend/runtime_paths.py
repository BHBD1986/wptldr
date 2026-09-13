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


def _db_fingerprint(path: Path) -> tuple[str | None, int]:
    """Return (newest published_at, article count) for a DB.

    Falls back to (None, 0) when the file is missing, empty, or unreadable.
    """
    if not path.exists() or path.stat().st_size == 0:
        return None, 0
    try:
        import sqlite3

        conn = sqlite3.connect(str(path))
        try:
            try:
                row = conn.execute(
                    "SELECT MAX(published_at), COUNT(*) FROM articles"
                ).fetchone()
                return (row[0], row[1] or 0)
            except sqlite3.Error:
                count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
                return (None, count or 0)
        finally:
            conn.close()
    except Exception:
        return None, 0


def seed_max_date(path: Path) -> str | None:
    """Newest article date in a DB, or None when it is missing/empty/unreadable."""
    return _db_fingerprint(path)[0]


def seed_is_newer(seed: Path, target: Path) -> bool:
    """True when the bundled seed holds more recent articles than target.

    Compares newest article dates; falls back to article count when either
    side has no usable dates.
    """
    if not seed.exists():
        return False
    seed_date, seed_count = _db_fingerprint(seed)
    if seed_count == 0:
        return False
    target_date, target_count = _db_fingerprint(target)
    if target_count == 0:
        return True
    if seed_date and target_date:
        return seed_date > target_date
    return seed_count > target_count


def _bundled_seed_path() -> Path:
    return Path(getattr(sys, "_MEIPASS", ".")) / "seed" / "wptldr.db"


def _backup_db(target: Path) -> None:
    if target.exists():
        shutil.copy2(target, target.with_suffix(".db.bak"))


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
    """Merge a newer bundled dataset into an existing user DB.

    Only runs when the bundled seed's newest article is newer than the user's.
    Articles/topics/new rows are added, bundled summaries replace older ones,
    and user-generated tables (``expansions``) are left untouched. Returns
    ``(articles_added, summaries_added)`` or ``None`` when nothing was done.
    """
    if not is_frozen():
        return None
    target = db_path()
    seed = _bundled_seed_path()
    if not seed.exists() or not target.exists():
        return None
    if not seed_is_newer(seed, target):
        return None

    _backup_db(target)
    import sqlite3

    conn = sqlite3.connect(str(target))
    try:
        conn.execute("ATTACH DATABASE ? AS seed", (str(seed),))
        before_articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        before_summaries = conn.execute("SELECT COUNT(*) FROM summaries").fetchone()[0]
        conn.executescript(
            """
            INSERT OR IGNORE INTO articles
                (id, wp_id, title, url, section, published_at, categories,
                 content_text, excerpt, word_count, ingested_at)
                SELECT id, wp_id, title, url, section, published_at, categories,
                       content_text, excerpt, word_count, ingested_at
                FROM seed.articles;

            INSERT OR IGNORE INTO article_topics (article_id, topic, score)
                SELECT article_id, topic, score FROM seed.article_topics;

            INSERT OR REPLACE INTO summaries
                (article_id, tldr, key_points, why_it_matters, model, created_at)
                SELECT article_id, tldr, key_points, why_it_matters, model, created_at
                FROM seed.summaries;

            INSERT OR IGNORE INTO digests
                (topic, from_date, to_date, content, item_count, model, created_at)
                SELECT topic, from_date, to_date, content, item_count, model,
                       created_at
                FROM seed.digests;
            """
        )
        conn.commit()
        after_articles = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        after_summaries = conn.execute("SELECT COUNT(*) FROM summaries").fetchone()[0]
        return after_articles - before_articles, after_summaries - before_summaries
    finally:
        conn.close()


def ensure_seed() -> str:
    """Seed on first run, or merge a newer bundled dataset on upgrade.

    Returns a short status string suitable for logging.
    """
    if not is_frozen():
        return "dev"
    if _db_is_empty(db_path()):
        return "seeded" if seed_db() else "no-seed"
    result = sync_seed()
    if result is None:
        return "current"
    added_articles, added_summaries = result
    return f"synced (+{added_articles} articles, +{added_summaries} summaries)"
