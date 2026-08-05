from fastapi.testclient import TestClient

import backend.main
import backend.update_state


def test_update_started(monkeypatch):
    captured = {}
    def fake_start(topic=None):
        captured["topic"] = topic
        return True
    monkeypatch.setattr(backend.main, "_start_update", fake_start)
    resp = TestClient(backend.main.app).post("/api/update?topic=agtech")
    assert resp.status_code == 200
    assert resp.json() == {"started": True}
    assert captured["topic"] == "agtech"


def test_update_status_shape(monkeypatch):
    monkeypatch.setattr(
        backend.main, "_get_state",
        lambda: {"running": False, "stage": None, "topic": None, "result": None,
                 "error": None, "started_at": None, "finished_at": None},
    )
    resp = TestClient(backend.main.app).get("/api/update/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "running" in data
    assert "stage" in data
    assert "topic" in data
    assert "result" in data


def test_update_status_when_running(monkeypatch):
    monkeypatch.setattr(
        backend.main, "_get_state",
        lambda: {"running": True, "stage": "summarization:agtech", "topic": "agtech",
                 "result": None, "error": None, "started_at": "2026-07-25T00:00:00",
                 "finished_at": None},
    )
    resp = TestClient(backend.main.app).get("/api/update/status")
    data = resp.json()
    assert data["running"] is True
    assert data["stage"] == "summarization:agtech"
    assert data["topic"] == "agtech"


def test_update_conflict_when_running(monkeypatch):
    monkeypatch.setattr(
        backend.main, "_get_state",
        lambda: {"running": True, "stage": None, "topic": None, "result": None,
                 "error": None, "started_at": None, "finished_at": None},
    )
    resp = TestClient(backend.main.app).post("/api/update?topic=agtech")
    assert resp.status_code == 409


def test_update_without_topic(monkeypatch):
    captured = {}

    def fake_start(topic=None):
        captured["topic"] = topic
        return True

    monkeypatch.setattr(backend.main, "_start_update", fake_start)
    resp = TestClient(backend.main.app).post("/api/update")
    assert resp.status_code == 200
    assert captured["topic"] is None
