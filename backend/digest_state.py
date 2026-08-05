import threading
from copy import deepcopy
from datetime import datetime

_state = {
    "running": False,
    "stage": None,
    "pct": 0,
    "topic": None,
    "from": None,
    "to": None,
    "item_count": None,
    "error": None,
    "started_at": None,
    "finished_at": None,
}
_lock = threading.Lock()


def get_state() -> dict:
    with _lock:
        return deepcopy(_state)


def start_digest(topic: str, from_: str, to: str, force: bool = False) -> bool:
    with _lock:
        if _state["running"]:
            return False
        _state.update(
            running=True, stage="queued", pct=0, topic=topic, from_=from_, to=to,
            item_count=None, error=None,
            started_at=datetime.utcnow().isoformat(), finished_at=None,
        )

    def _progress(stage, pct, item_count=None, error=None):
        with _lock:
            _state["stage"] = stage
            _state["pct"] = pct
            if item_count is not None:
                _state["item_count"] = item_count
            if error is not None:
                _state["error"] = error

    def _worker():
        from backend.digest import generate_digest
        try:
            generate_digest(topic, from_, to, force=force, progress=_progress)
            with _lock:
                _state["running"] = False
                _state["finished_at"] = datetime.utcnow().isoformat()
        except ValueError as e:
            with _lock:
                _state.update(running=False, stage="failed", pct=100,
                              error=str(e), finished_at=datetime.utcnow().isoformat())
        except Exception as e:
            with _lock:
                _state.update(running=False, stage="failed", pct=100,
                              error=f"Brief generation failed: {e}",
                              finished_at=datetime.utcnow().isoformat())

    threading.Thread(target=_worker, daemon=True).start()
    return True
