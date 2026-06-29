# utils/profiles.py
"""Tracked competitor profiles: an editable override of config.yaml's `competitors`.

Resolution precedence: data/profiles.json (if present & non-empty) -> config.yaml.
This lets the dashboard edit the monitored brand set without touching the committed
config.yaml, mirroring how utils.settings overrides credentials.
"""
import json
import os

import yaml

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Module-level so tests can monkeypatch to tmp paths.
PROFILES_PATH = os.path.join(_ROOT, "data", "profiles.json")
CONFIG_PATH = os.path.join(_ROOT, "config.yaml")

PROFILE_FIELDS = ("name", "facebook_page", "instagram_handle", "tiktok_handle")
_HANDLE_FIELDS = ("facebook_page", "instagram_handle", "tiktok_handle")


class ProfilesError(ValueError):
    """Raised when a profiles payload fails validation."""


def _config_competitors() -> list[dict]:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except (FileNotFoundError, OSError, yaml.YAMLError):
        return []
    comps = cfg.get("competitors") if isinstance(cfg, dict) else None
    return comps if isinstance(comps, list) else []


def load_override() -> list[dict] | None:
    """Return the stored profile list, or None if no valid override exists."""
    try:
        with open(PROFILES_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, list) and data else None


def effective_competitors(config_competitors=None) -> list[dict]:
    """The competitor list to use: override -> passed config seed -> config.yaml."""
    override = load_override()
    if override is not None:
        return override
    if config_competitors is not None:
        return config_competitors if isinstance(config_competitors, list) else []
    return _config_competitors()


def _normalize(profiles) -> list[dict]:
    if not isinstance(profiles, list) or not profiles:
        raise ProfilesError("At least one profile is required.")
    cleaned: list[dict] = []
    for i, p in enumerate(profiles):
        if not isinstance(p, dict):
            raise ProfilesError(f"Profile #{i + 1} is not an object.")
        row = {k: str(p.get(k, "") or "").strip() for k in PROFILE_FIELDS}
        if not row["name"]:
            raise ProfilesError(f"Profile #{i + 1} is missing a name.")
        if not any(row[h] for h in _HANDLE_FIELDS):
            raise ProfilesError(f"Profile '{row['name']}' needs at least one handle.")
        cleaned.append(row)
    return cleaned


def save_profiles(profiles) -> list[dict]:
    """Validate, normalize, and persist the profile list; return the saved list."""
    cleaned = _normalize(profiles)
    os.makedirs(os.path.dirname(PROFILES_PATH), exist_ok=True)
    with open(PROFILES_PATH, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)
    return cleaned


def reset_profiles() -> list[dict]:
    """Delete the override (revert to config.yaml); return the now-effective list."""
    try:
        os.remove(PROFILES_PATH)
    except FileNotFoundError:
        pass
    return effective_competitors()


def is_override_active() -> bool:
    return load_override() is not None
