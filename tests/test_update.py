from backend import update
from backend.config import settings


class FakeConn:
    def __init__(self):
        self.rows = [("2026-08-01",)]

    def execute(self, sql, params=()):
        return self

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def close(self):
        pass


def _patch_pipeline(monkeypatch):
    summarize_calls = []
    monkeypatch.setattr(update, "get_conn", lambda: FakeConn())
    monkeypatch.setattr(update, "run_ingest", lambda *a, **kw: None)
    monkeypatch.setattr(update, "run_classify", lambda: None)
    monkeypatch.setattr(
        update, "run_summarize",
        lambda **kw: summarize_calls.append(kw),
    )
    return summarize_calls


def test_run_update_summarizes_only_requested_topic(monkeypatch):
    calls = _patch_pipeline(monkeypatch)
    update.run_update(topic="markets")
    assert [c["topic"] for c in calls] == ["markets"]
    assert calls[0]["limit"] == settings.SUMMARIZE_LIMIT


def test_run_update_summarizes_all_topics_when_none_given(monkeypatch):
    calls = _patch_pipeline(monkeypatch)
    update.run_update()
    assert [c["topic"] for c in calls] == settings.TOPICS


def test_run_update_always_ingests_and_classifies(monkeypatch):
    calls = _patch_pipeline(monkeypatch)
    update.run_update(topic="crops")
    assert len(calls) == 1
