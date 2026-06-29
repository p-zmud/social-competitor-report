# tests/test_validation.py
import pytest

from utils import settings as settings_module
from utils import validation as validation_module
from utils.validation import ConfigError, validate_environment


@pytest.fixture(autouse=True)
def isolate_settings(tmp_path, monkeypatch):
    """No settings.json / no profiles override + clean env -> deterministic resolvers."""
    from utils import profiles as profiles_module
    monkeypatch.setattr(settings_module, "SETTINGS_PATH", str(tmp_path / "no-settings.json"))
    monkeypatch.setattr(profiles_module, "PROFILES_PATH", str(tmp_path / "no-profiles.json"))
    for var in ("OPENROUTER_API_KEY", "APIFY_TOKEN", "OPENROUTER_MODEL"):
        monkeypatch.delenv(var, raising=False)


def _redirect_config(monkeypatch, tmp_path):
    """Point validation at tmp_path/fakeproj/config.yaml via a fake __file__."""
    fake_root = tmp_path / "fakeproj"
    (fake_root / "utils").mkdir(parents=True)
    monkeypatch.setattr(validation_module, "__file__", str(fake_root / "utils" / "validation.py"))
    return fake_root


def _write_config(root, body="competitors:\n  - {name: Foo}\n"):
    (root / "config.yaml").write_text(body)


def test_missing_keys_raise_strict(monkeypatch, tmp_path):
    root = _redirect_config(monkeypatch, tmp_path)
    _write_config(root)
    with pytest.raises(ConfigError) as exc:
        validate_environment(strict=True)
    msg = str(exc.value)
    assert "OpenRouter" in msg
    assert "Apify" in msg


def test_missing_keys_returns_list(monkeypatch, tmp_path):
    root = _redirect_config(monkeypatch, tmp_path)
    _write_config(root)
    problems = validate_environment(strict=False)
    assert any("OpenRouter" in p for p in problems)
    assert any("Apify" in p for p in problems)


def test_no_llm_skips_openrouter(monkeypatch, tmp_path):
    monkeypatch.setenv("APIFY_TOKEN", "x")
    root = _redirect_config(monkeypatch, tmp_path)
    _write_config(root)
    problems = validate_environment(no_llm=True, strict=False)
    assert not any("OpenRouter" in p for p in problems)
    assert problems == []


def test_skip_apify_skips_apify(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    root = _redirect_config(monkeypatch, tmp_path)
    _write_config(root)
    problems = validate_environment(skip_apify=True, strict=False)
    assert not any("Apify" in p for p in problems)
    assert problems == []


def test_keys_from_settings_file_pass(monkeypatch, tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text('{"openrouter_api_key": "sk-x", "apify_token": "ap-x"}')
    monkeypatch.setattr(settings_module, "SETTINGS_PATH", str(settings_path))
    root = _redirect_config(monkeypatch, tmp_path)
    _write_config(root)
    assert validate_environment(strict=False) == []


def test_missing_config_flagged(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    monkeypatch.setenv("APIFY_TOKEN", "x")
    _redirect_config(monkeypatch, tmp_path)  # no config.yaml created
    problems = validate_environment(strict=False)
    assert any("config.yaml" in p for p in problems)


def test_empty_competitors_flagged(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    monkeypatch.setenv("APIFY_TOKEN", "x")
    root = _redirect_config(monkeypatch, tmp_path)
    _write_config(root, body="competitors: []\n")
    problems = validate_environment(strict=False)
    assert any("competitors" in p for p in problems)


def test_valid_setup_returns_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    monkeypatch.setenv("APIFY_TOKEN", "x")
    root = _redirect_config(monkeypatch, tmp_path)
    _write_config(root)
    assert validate_environment(strict=False) == []


def test_validation_passes_with_override_competitors(monkeypatch, tmp_path):
    from utils import profiles as pf
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    monkeypatch.setenv("APIFY_TOKEN", "x")
    root = _redirect_config(monkeypatch, tmp_path)
    _write_config(root, body="competitors: []\n")  # config has none...
    monkeypatch.setattr(pf, "PROFILES_PATH", str(tmp_path / "profiles.json"))
    monkeypatch.setattr(pf, "CONFIG_PATH", str(root / "config.yaml"))
    pf.save_profiles([{"name": "Subway", "instagram_handle": "subwaypl"}])  # ...but override does
    problems = validate_environment(strict=False)
    assert not any("competitors" in p.lower() for p in problems)


def test_validation_flags_when_no_competitors_anywhere(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    monkeypatch.setenv("APIFY_TOKEN", "x")
    root = _redirect_config(monkeypatch, tmp_path)
    _write_config(root, body="competitors: []\n")
    problems = validate_environment(strict=False)
    assert any("competitors" in p.lower() for p in problems)
