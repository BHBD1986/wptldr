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
    if not path.exists() or path.stat().st_size == 0:
        return True
    try:
        import sqlite3

        conn = sqlite3.connect(str(path))
        try:
            count = conn.execute("SELECT COUNT(*) FROM articles").fetchone()[0]
        finally:
            conn.close()
        return count == 0
    except Exception:
        return True


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
    seed = Path(getattr(sys, "_MEIPASS", ".")) / "seed" / "wptldr.db"
    if not seed.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(seed, target)
    return True
