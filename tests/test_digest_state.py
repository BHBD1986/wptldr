import json
import time

import pytest
from fastapi.testclient import TestClient

from backend import digest_state
from backend.main import app


def test_start_digest_runs_to_done(monkeypatch, tmp_path):
    import backend.digest
    from backend.config import settings

    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "test.db"))

    calls = []
    canned = {
        "digest": {"period_summary": "p", "themes": [], "key_stories": [], "context": "", "outlook": ""},
        "item_count": 3,
        "cached": False,
    }

    def fake_generate(topic, from_, to, force=False, progress=None):
        if progress:
            progress("generating", 30, item_count=3)
        time.sleep(0.3)
        if progress:
            progress("done", 100, item_count=3)
        calls.append((topic, from_, to, force))
        return canned

    monkeypatch.setattr(backend.digest, "generate_digest", fake_generate)

    assert digest_state.start_digest("agtech", "2026-01-01", "2026-07-01") is True
    assert digest_state.start_digest("agtech", "2026-01-01", "2026-07-01") is False

    for _ in range(50):
        if not digest_state.get_state()["running"]:
            break
        time.sleep(0.05)

    state = digest_state.get_state()
    assert state["running"] is False
    assert state["pct"] == 100
    assert state["item_count"] == 3
    assert calls == [("agtech", "2026-01-01", "2026-07-01", False)]


def test_start_digest_reports_failure(monkeypatch, tmp_path):
    import backend.digest
    from backend.config import settings

    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "test.db"))

    def boom(topic, from_, to, force=False, progress=None):
        raise ValueError("No articles found for topic and date range")

    monkeypatch.setattr(backend.digest, "generate_digest", boom)

    assert digest_state.start_digest("agtech", "2026-01-01", "2026-07-01") is True
    for _ in range(50):
        if not digest_state.get_state()["running"]:
            break
        time.sleep(0.05)

    state = digest_state.get_state()
    assert state["running"] is False
    assert state["stage"] == "failed"
    assert "No articles" in state["error"]


def test_api_digest_post_and_status(monkeypatch, tmp_path):
    import backend.digest
    from backend.config import settings
    from backend.db import init_db

    monkeypatch.setattr(settings, "DB_PATH", str(tmp_path / "test.db"))
    init_db()

    canned = {
        "digest": {"period_summary": "p", "themes": [], "key_stories": [], "context": "", "outlook": ""},
        "item_count": 2,
        "cached": False,
    }
    def fake_generate(topic, from_, to, force=False, progress=None):
        time.sleep(0.3)
        if progress:
            progress("done", 100, item_count=2)
        return canned

    monkeypatch.setattr(backend.digest, "generate_digest", fake_generate)

    client = TestClient(app)
    resp = client.post("/api/digest?topic=agtech&from=2026-01-01&to=2026-07-01")
    assert resp.status_code == 200
    assert resp.json()["started"] is True

    status = None
    for _ in range(50):
        status = client.get("/api/digest/status").json()
        if not status["running"]:
            break
        time.sleep(0.05)

    assert status["running"] is False
    assert status["stage"] == "done"
