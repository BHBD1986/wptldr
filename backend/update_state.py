import threading
from copy import deepcopy
from datetime import datetime

_state = {
    "running": False,
    "stage": None,
    "topic": None,
    "result": None,
    "error": None,
    "started_at": None,
    "finished_at": None,
}
_lock = threading.Lock()


def get_state() -> dict:
    with _lock:
        return deepcopy(_state)


def set_stage(stage: str | None):
    with _lock:
        _state["stage"] = stage


def start_update(topic: str | None = None):
    with _lock:
        if _state["running"]:
            return False
        _state.update(
            running=True, stage=None, topic=topic, result=None,
            error=None, started_at=datetime.utcnow().isoformat(),
            finished_at=None,
        )

    def _worker():
        from backend.update import run_update
        try:
            run_update(topic)
            with _lock:
                _state["result"] = "completed"
        except Exception as e:
            with _lock:
                _state["error"] = str(e)
                _state["result"] = "failed"
        finally:
            with _lock:
                _state["running"] = False
                _state["stage"] = None
                _state["finished_at"] = datetime.utcnow().isoformat()

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return True
