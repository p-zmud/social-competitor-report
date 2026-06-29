import json

import pytest

from utils import settings as st


@pytest.fixture
def tmp_settings(tmp_path, monkeypatch):
    p = tmp_path / "settings.json"
    monkeypatch.setattr(st, "SETTINGS_PATH", str(p))
    # Clean env so resolver tests are deterministic.
    for var in ("OPENROUTER_API_KEY", "APIFY_TOKEN", "OPENROUTER_MODEL", "SUMMARY_PROMPT"):
        monkeypatch.delenv(var, raising=False)
    return p


def test_default_model_when_nothing_set(tmp_settings):
    assert st.get_model() == st.DEFAULT_MODEL


def test_env_fallback(tmp_settings, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-env-123456")
    monkeypatch.setenv("APIFY_TOKEN", "apify_api_env")
    assert st.get_openrouter_key() == "sk-env-123456"
    assert st.get_apify_token() == "apify_api_env"


def test_settings_file_overrides_env(tmp_settings, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-env-123456")
    st.save_settings({"openrouter_api_key": "sk-file-999"})
    assert st.get_openrouter_key() == "sk-file-999"


def test_save_ignores_empty_fields(tmp_settings):
    st.save_settings({"model": "openai/gpt-4o"})
    st.save_settings({"model": "   ", "apify_token": ""})  # empty -> ignored
    data = json.loads(tmp_settings.read_text())
    assert data["model"] == "openai/gpt-4o"
    assert "apify_token" not in data


def test_save_ignores_unknown_keys(tmp_settings):
    st.save_settings({"evil": "x", "model": "openai/gpt-4o-mini"})
    data = json.loads(tmp_settings.read_text())
    assert "evil" not in data
    assert data["model"] == "openai/gpt-4o-mini"


def test_mask_keeps_only_last_four():
    assert st.mask("") == ""
    masked = st.mask("apify_api_abcd1234")
    assert masked.startswith("…")
    assert masked.endswith("1234")
    assert "abcd" not in masked
    assert "apify_api" not in masked


def test_status_never_leaks_raw_secret(tmp_settings):
    st.save_settings({
        "openrouter_api_key": "sk-or-supersecretvalue",
        "apify_token": "apify_api_topsecretvalue",
        "model": "openai/gpt-4o",
    })
    status = st.settings_status()
    blob = json.dumps(status)
    assert "supersecretvalue" not in blob
    assert "topsecretvalue" not in blob
    assert status["openrouter_api_key_set"] is True
    assert status["apify_token_set"] is True
    assert status["model"] == "openai/gpt-4o"
    assert "anthropic/claude-sonnet-4.6" in status["models"]


def test_corrupt_file_returns_empty(tmp_settings):
    tmp_settings.write_text("{ not valid json")
    assert st.load_settings() == {}


def test_summary_prompt_default_when_nothing_set(tmp_settings):
    assert st.get_summary_prompt() == st.DEFAULT_SUMMARY_PROMPT
    assert st.stored_summary_prompt() == ""


def test_summary_prompt_saved_and_resolved(tmp_settings):
    st.save_settings({"summary_prompt": "Custom instructions here"})
    assert st.get_summary_prompt() == "Custom instructions here"
    assert st.stored_summary_prompt() == "Custom instructions here"


def test_summary_prompt_empty_reverts_to_default(tmp_settings):
    st.save_settings({"summary_prompt": "Custom instructions here"})
    st.save_settings({"summary_prompt": ""})  # explicit empty -> delete key
    data = json.loads(tmp_settings.read_text())
    assert "summary_prompt" not in data
    assert st.get_summary_prompt() == st.DEFAULT_SUMMARY_PROMPT


def test_settings_status_includes_prompt(tmp_settings):
    status = st.settings_status()
    assert status["summary_prompt"] == ""
    assert status["summary_prompt_default"] == st.DEFAULT_SUMMARY_PROMPT
