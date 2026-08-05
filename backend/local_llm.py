"""Local CPU inference via llama-cpp-python with a bundled GGUF model.

Used automatically when no ``LLM_API_KEY`` is configured. The model file is
downloaded once on first use (see ``LOCAL_MODEL_PATH`` / ``LOCAL_MODEL_URL``
in settings) and cached in ``models/`` afterwards, so the app runs fully
offline.
"""

import threading
from pathlib import Path

from backend.config import settings

_llm = None
_llm_lock = threading.Lock()
_download_lock = threading.Lock()


def _model_path() -> Path:
    return Path(settings.LOCAL_MODEL_PATH).resolve()


def model_available() -> bool:
    return _model_path().exists()


def _download_model(progress_cb=None) -> Path:
    import httpx

    dest = _model_path()
    with _download_lock:
        if dest.exists():
            return dest

        url = settings.LOCAL_MODEL_URL
        if not url:
            raise RuntimeError("Local model file missing and LOCAL_MODEL_URL is not set")

        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading local model ({url.rsplit('/', 1)[-1]}) ...")
        if progress_cb:
            progress_cb(0, 0)
        with httpx.stream("GET", url, follow_redirects=True, timeout=600) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            done = 0
            last_reported = 0
            tmp = dest.with_suffix(dest.suffix + ".part")
            with open(tmp, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=256 * 1024):
                    f.write(chunk)
                    done += len(chunk)
                    if total and done - last_reported > total * 0.05:
                        print(f"  {done // (1024 ** 2)}/{total // (1024 ** 2)} MB")
                        last_reported = done
                    if progress_cb and total:
                        progress_cb(done, total)
            tmp.replace(dest)
        print(f"Model saved to {dest}")
        return dest


def download_model(progress_cb=None) -> Path:
    return _download_model(progress_cb)


def _get_llm():
    global _llm
    if _llm is None:
        try:
            from llama_cpp import Llama
        except ImportError:
            raise RuntimeError(
                "llama-cpp-python is not installed. Run: pip install llama-cpp-python"
            )

        _download_model()
        n_threads = settings.LOCAL_MODEL_N_THREADS or None
        _llm = Llama(
            model_path=str(_model_path()),
            n_ctx=8192,
            n_threads=n_threads,
            verbose=False,
        )
    return _llm


def _extract_content(resp) -> str:
    if isinstance(resp, dict):
        return resp["choices"][0]["message"]["content"]
    return resp.choices[0].message.content


def generate(user: str, system: str = "", json_mode: bool = True) -> str:
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user})

    kwargs = {
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 2048,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    with _llm_lock:
        resp = _get_llm().create_chat_completion(**kwargs)

    return _extract_content(resp)


def model_name() -> str:
    return _model_path().stem
