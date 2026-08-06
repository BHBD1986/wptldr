import os
import sys
from pathlib import Path
from dotenv import dotenv_values

env_file = Path(__file__).resolve().parents[1] / ".env"
_file_env = dotenv_values(env_file) if env_file.exists() else {}


def _key_candidates() -> list[Path]:
    meipass = getattr(sys, "_MEIPASS", None)
    candidates = []
    if meipass:
        candidates.append(Path(meipass) / "api_key.txt")
    candidates.append(Path(__file__).resolve().parents[1] / "api_key.txt")
    return candidates


def bundled_api_key() -> str:
    """A gitignored key baked into the installer so users never configure one.

    Resolution order (first non-empty wins):
      1. env var LLM_API_KEY / .env  (user/developer override)
      2. api_key.txt in the PyInstaller bundle (_MEIPASS)
      3. api_key.txt next to the repo (dev)
    """
    if os.environ.get("LLM_API_KEY") or _file_env.get("LLM_API_KEY"):
        return ""
    for p in _key_candidates():
        if p.exists():
            val = p.read_text(encoding="utf-8").strip()
            if val:
                return val
    return ""


class Settings:
    WP_API_BASE: str = "https://www.producer.com/wp-json/wp/v2"
    LLM_BASE_URL: str = "https://openrouter.ai/api/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "google/gemma-4-26b-a4b-it"
    DB_PATH: str = "data/wptldr.db"
    TOPICS: list[str] = ["agtech", "livestock", "crops", "markets", "politics", "unclassified"]
    DEFAULT_START: str = "2026-01-01"
    SUMMARIZE_LIMIT: int = 500
    DIGEST_MAX_ITEMS: int = 300
    DIGEST_CHUNK_SIZE: int = 40

    def __init__(self):
        hints = self.__class__.__annotations__
        for key in dir(self):
            if key.startswith("_") or callable(getattr(self, key)):
                continue
            env_val = os.environ.get(key)
            if env_val is None:
                env_val = _file_env.get(key)
            if env_val is None:
                continue
            annotation = hints.get(key)
            if annotation is int:
                env_val = int(env_val)
            elif annotation is bool:
                env_val = env_val.lower() in ("1", "true", "yes", "on")
            object.__setattr__(self, key, env_val)
        if not self.LLM_API_KEY:
            object.__setattr__(self, "LLM_API_KEY", bundled_api_key())


settings = Settings()
