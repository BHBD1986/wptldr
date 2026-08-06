import socket

from backend import launcher


def test_find_free_port_returns_open_port():
    port = launcher.find_free_port()
    assert isinstance(port, int)
    with socket.socket() as s:
        s.bind(("127.0.0.1", port))


def test_resolve_port_uses_override(monkeypatch):
    monkeypatch.setenv("WPTLDR_PORT", "7777")
    assert launcher.resolve_port() == 7777


def test_resolve_port_finds_free_without_override(monkeypatch):
    monkeypatch.delenv("WPTLDR_PORT", raising=False)
    port = launcher.resolve_port()
    with socket.socket() as s:
        s.bind(("127.0.0.1", port))
