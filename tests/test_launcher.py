import socket

from backend import launcher
from backend import local_llm


def test_find_free_port_returns_open_port():
    port = launcher.find_free_port()
    assert isinstance(port, int)
    with socket.socket() as s:
        s.bind(("127.0.0.1", port))


def test_start_model_download_skips_when_present(monkeypatch):
    calls = []
    monkeypatch.setattr(local_llm, "model_available", lambda: True)
    monkeypatch.setattr(local_llm, "download_model", lambda **kw: calls.append(kw))
    launcher._start_model_download(on_progress=lambda *a: None)
    assert calls == []


def test_start_model_download_reports_progress(monkeypatch):
    seen = []

    def fake_download(progress_cb=None):
        progress_cb(50, 100)
        return "path"

    monkeypatch.setattr(local_llm, "model_available", lambda: False)
    monkeypatch.setattr(local_llm, "download_model", fake_download)
    launcher._start_model_download(on_progress=seen.append)
    assert 50 in seen
    assert 100 in seen


def test_start_model_download_reports_error(monkeypatch):
    results = []

    def fake_download(progress_cb=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(local_llm, "model_available", lambda: False)
    monkeypatch.setattr(local_llm, "download_model", fake_download)
    launcher._start_model_download(lambda *a: results.append(a))
    assert results == [(-1, "boom")]
