import os

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
