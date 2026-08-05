import os
from pathlib import Path
from dotenv import dotenv_values

env_file = Path(__file__).resolve().parents[1] / ".env"
_file_env = dotenv_values(env_file) if env_file.exists() else {}


class Settings:
    WP_API_BASE: str = "https://www.producer.com/wp-json/wp/v2"
    LLM_BASE_URL: str = "https://api.deepseek.com/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "deepseek-v4-flash"
    DB_PATH: str = "data/wptldr.db"
    TOPICS: list[str] = ["agtech", "livestock", "crops", "markets", "politics", "unclassified"]
    DEFAULT_START: str = "2026-01-01"
    LOCAL_MODEL_PATH: str = "models/qwen2.5-0.5b-instruct-q4_k_m.gguf"
    LOCAL_MODEL_URL: str = "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf"
    LOCAL_MODEL_N_THREADS: int = 0
    SUMMARIZE_LIMIT: int = 500
    DIGEST_MAX_ITEMS: int = 60

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


settings = Settings()
