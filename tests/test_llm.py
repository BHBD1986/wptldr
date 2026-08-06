import json

import pytest

import backend.llm
from backend.llm import chat, model_name


def test_license_expired_blocks_chat(monkeypatch):
    monkeypatch.setattr(backend.llm.settings, "LLM_API_KEY", "secret")
    monkeypatch.setattr(backend.llm.settings, "LICENSE_EXPIRY", "2000-01-01")
    with pytest.raises(RuntimeError, match="license has expired"):
        chat("hello")


def test_license_valid_allows_chat(monkeypatch):
    monkeypatch.setattr(backend.llm.settings, "LLM_API_KEY", "secret")
    monkeypatch.setattr(backend.llm.settings, "LICENSE_EXPIRY", "2999-01-01")
    monkeypatch.setattr(backend.llm.settings, "LLM_BASE_URL", "https://example.com/v1")
    monkeypatch.setattr(backend.llm.settings, "LLM_MODEL", "test-model")

    class FakeResp:
        choices = [type("C", (), {"message": type("M", (), {"content": "{}"})})()]

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        @property
        def chat(self):
            return self

        @property
        def completions(self):
            return self

        def create(self, **kwargs):
            return FakeResp()

    monkeypatch.setattr(backend.llm, "OpenAI", FakeClient)
    assert chat("hi") == "{}"



def test_chat_routes_to_cloud(monkeypatch):
    monkeypatch.setattr(backend.llm.settings, "LLM_API_KEY", "secret")
    monkeypatch.setattr(backend.llm.settings, "LLM_BASE_URL", "https://example.com/v1")
    monkeypatch.setattr(backend.llm.settings, "LLM_MODEL", "test-model")

    captured = {}

    class FakeResp:
        class _Choice:
            message = type("M", (), {"content": '{"ok": true}'})()
        choices = [_Choice]

    class FakeClient:
        def __init__(self, **kwargs):
            captured["kwargs"] = kwargs

        @property
        def chat(self):
            return self

        @property
        def completions(self):
            return self

        def create(self, **kwargs):
            captured["create"] = kwargs
            return FakeResp()

    monkeypatch.setattr(backend.llm, "OpenAI", FakeClient)
    assert chat("hi", system="sys") == '{"ok": true}'
    assert captured["kwargs"]["api_key"] == "secret"
    assert captured["kwargs"]["base_url"] == "https://example.com/v1"
    assert captured["create"]["model"] == "test-model"
    assert captured["create"]["messages"][0]["role"] == "system"


def test_chat_cloud_sends_json_mode(monkeypatch):
    monkeypatch.setattr(backend.llm.settings, "LLM_API_KEY", "secret")
    monkeypatch.setattr(backend.llm.settings, "LLM_MODEL", "test-model")

    captured = {}

    class FakeResp:
        choices = [type("C", (), {"message": type("M", (), {"content": "{}"})})()]

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        @property
        def chat(self):
            return self

        @property
        def completions(self):
            return self

        def create(self, **kwargs):
            captured["kwargs"] = kwargs
            return FakeResp()

    monkeypatch.setattr(backend.llm, "OpenAI", FakeClient)
    chat("hi", json_mode=True)
    assert captured["kwargs"]["response_format"] == {"type": "json_object"}


def test_model_name_returns_configured_model(monkeypatch):
    monkeypatch.setattr(backend.llm.settings, "LLM_MODEL", "google/gemma-4-26b-a4b-it")
    assert model_name() == "google/gemma-4-26b-a4b-it"


def test_bundled_api_key_from_meipass(monkeypatch, tmp_path, sysmod=__import__("sys")):
    from backend.config import bundled_api_key

    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setattr("backend.config._file_env", {})
    key_file = tmp_path / "api_key.txt"
    key_file.write_text("sk-or-bundled\n")
    monkeypatch.setattr(sysmod, "_MEIPASS", str(tmp_path), raising=False)
    monkeypatch.setattr(
        "backend.config._key_candidates", lambda: [key_file]
    )
    assert bundled_api_key() == "sk-or-bundled"


def test_bundled_api_key_empty_without_file(monkeypatch, tmp_path, sysmod=__import__("sys")):
    from backend.config import bundled_api_key

    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setattr("backend.config._file_env", {})
    empty = tmp_path / "empty"
    empty.mkdir()
    missing = empty / "api_key.txt"
    monkeypatch.setattr("backend.config._key_candidates", lambda: [missing])
    assert bundled_api_key() == ""
