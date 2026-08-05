import json

import backend.llm
import backend.local_llm
from backend.llm import chat, model_name


def test_chat_routes_to_local_when_no_key(monkeypatch):
    monkeypatch.setattr(backend.llm.settings, "LLM_API_KEY", "")
    canned = '{"tldr": "hi"}'
    monkeypatch.setattr(backend.local_llm, "generate", lambda *a, **kw: canned)
    assert chat("hello") == canned


def test_chat_routes_to_cloud_when_key(monkeypatch):
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


def test_local_generate_returns_valid_json(monkeypatch):
    canned = {"choices": [{"message": {"content": '{"tldr": "x"}'}}]}

    class FakeLLM:
        def create_chat_completion(self, **kwargs):
            return canned

    monkeypatch.setattr(backend.local_llm, "_get_llm", lambda: FakeLLM())
    out = backend.local_llm.generate("prompt", system="sys", json_mode=True)
    assert json.loads(out) == {"tldr": "x"}


def test_model_name_local_when_no_key(monkeypatch):
    monkeypatch.setattr(backend.llm.settings, "LLM_API_KEY", "")
    assert model_name() == "qwen2.5-0.5b-instruct-q4_k_m"


def test_model_name_cloud_when_key(monkeypatch):
    monkeypatch.setattr(backend.llm.settings, "LLM_API_KEY", "k")
    monkeypatch.setattr(backend.llm.settings, "LLM_MODEL", "deepseek-x")
    assert model_name() == "deepseek-x"
