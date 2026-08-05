"""Path resolution for both dev and packaged (PyInstaller) environments.

In dev, the app stores data/models next to the project. When frozen into a
desktop app, the bundle is read-only, so data + model live in a writable,
per-user application data directory instead.
"""

import os
import sys
from pathlib import Path

_MODEL_FILE = "qwen2.5-0.5b-instruct-q4_k_m.gguf"


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


def model_path() -> Path:
    return app_data_dir() / "models" / _MODEL_FILE


def frontend_dir() -> Path:
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", ".")) / "frontend"
    return Path(__file__).resolve().parents[1] / "frontend"


def configure_settings() -> None:
    """Point DB and model paths at the user app-data dir when packaged."""
    from backend.config import settings

    if not is_frozen():
        return
    base = app_data_dir()
    base.mkdir(parents=True, exist_ok=True)
    (base / "models").mkdir(parents=True, exist_ok=True)
    settings.DB_PATH = str(db_path())
    settings.LOCAL_MODEL_PATH = str(model_path())
