import os
import sys

import pytest

from backend import runtime_paths as rp


def test_env_override_for_settings(monkeypatch):
    from backend.config import Settings

    monkeypatch.setenv("SUMMARIZE_LIMIT", "7")
    monkeypatch.setenv("LLM_API_KEY", "from-env")
    s = Settings()
    assert s.SUMMARIZE_LIMIT == 7
    assert s.LLM_API_KEY == "from-env"


def test_app_data_dir_uses_localappdata_on_windows(monkeypatch):
    if os.name != "nt":
        return
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\Test\AppData\Local")
    assert str(rp.app_data_dir()) == r"C:\Users\Test\AppData\Local\WPTLDR"


def test_model_path_filename_matches_model_url():
    from backend.config import settings

    assert rp.model_path().name == settings.LOCAL_MODEL_URL.rsplit("/", 1)[-1]


def test_frontend_dir_exists_in_dev():
    assert rp.frontend_dir().is_dir()


def test_seed_db_copies_bundle_when_target_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(rp, "is_frozen", lambda: True)
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    (seed_dir / "wptldr.db").write_bytes(b"seed-bytes")
    monkeypatch.setattr(rp, "db_path", lambda: tmp_path / "target" / "wptldr.db")
    monkeypatch.setattr(rp, "app_data_dir", lambda: tmp_path / "target")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert rp.seed_db() is True
    assert (tmp_path / "target" / "wptldr.db").read_bytes() == b"seed-bytes"


def test_seed_db_does_not_overwrite_populated_db(monkeypatch, tmp_path):
    import sqlite3

    monkeypatch.setattr(rp, "is_frozen", lambda: True)
    target = tmp_path / "wptldr.db"
    conn = sqlite3.connect(str(target))
    conn.execute("CREATE TABLE articles (id INTEGER)")
    conn.execute("INSERT INTO articles VALUES (1)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(rp, "db_path", lambda: target)

    assert rp.seed_db() is False
    assert sqlite3.connect(str(target)).execute("SELECT COUNT(*) FROM articles").fetchone()[0] == 1


def test_seed_db_replaces_empty_schema_db(monkeypatch, tmp_path):
    import sqlite3

    monkeypatch.setattr(rp, "is_frozen", lambda: True)
    target = tmp_path / "wptldr.db"
    conn = sqlite3.connect(str(target))
    conn.execute("CREATE TABLE articles (id INTEGER)")
    conn.commit()
    conn.close()
    monkeypatch.setattr(rp, "db_path", lambda: target)
    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    (seed_dir / "wptldr.db").write_bytes(b"seed-bytes")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert rp.seed_db() is True
    assert target.read_bytes() == b"seed-bytes"


def test_seed_db_noop_in_dev(monkeypatch, tmp_path):
    monkeypatch.setattr(rp, "is_frozen", lambda: False)
    assert rp.seed_db() is False
