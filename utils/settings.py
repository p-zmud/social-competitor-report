# utils/settings.py
"""User settings: API keys + LLM model id, persisted to data/settings.json.

Resolution precedence for every value: settings.json (if non-empty) -> env var -> default.
This lets dashboard users configure everything in the UI without touching .env, while
CLI/.env usage still works. Secrets are never returned raw by the dashboard API — the
API layer uses mask()/settings_status() instead.
"""
import json
import os
from typing import Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Module-level so tests can monkeypatch it to a tmp path.
SETTINGS_PATH = os.path.join(_ROOT, "data", "settings.json")

DEFAULT_MODEL = "deepseek/deepseek-v4-flash"
DEFAULT_SUMMARY_PROMPT = (
    "Write 1-2 sentences in simple English about what this brand posted on social "
    "media recently. What topics did they cover? What was their communication style? "
    "Do not add any headers, titles, or markdown formatting — just plain text sentences. "
    "Do not say you lack access to data — the posts are provided below."
)

# Vetted OpenRouter model ids (verified against the live /models API). The UI also
# accepts any custom id via a free-text field, so this is just a convenience shortlist.
CURATED_MODELS = [
    "deepseek/deepseek-v4-flash",
    "anthropic/claude-sonnet-4.6",
    "anthropic/claude-haiku-4.5",
    "openai/gpt-4o",
    "openai/gpt-4o-mini",
    "meta-llama/llama-3.3-70b-instruct",
    "deepseek/deepseek-chat",
]

_ALLOWED_KEYS = ("openrouter_api_key", "apify_token", "model", "summary_prompt")


def load_settings() -> dict:
    """Return persisted settings, or {} if the file is missing/corrupt."""
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def save_settings(partial: dict) -> dict:
    """Merge non-empty allowed fields from `partial` into stored settings; write; return full.

    Empty strings and unknown keys are ignored, so the UI can submit only the fields the
    user actually changed without clobbering the others.
    """
    current = load_settings()
    for key in _ALLOWED_KEYS:
        if key not in partial:
            continue
        value = partial[key]
        if value is None:
            continue
        value = str(value).strip()
        if value:
            current[key] = value
        elif key == "summary_prompt":
            current.pop(key, None)  # explicit empty reverts to default
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)
    return current


def _resolve(json_key: str, env_var: str, default: Optional[str] = None) -> str:
    stored = load_settings().get(json_key)
    if stored and str(stored).strip():
        return str(stored).strip()
    env = os.getenv(env_var)
    if env and env.strip():
        return env.strip()
    return default or ""


def get_openrouter_key() -> str:
    return _resolve("openrouter_api_key", "OPENROUTER_API_KEY")


def get_apify_token() -> str:
    return _resolve("apify_token", "APIFY_TOKEN")


def get_model(default: str = DEFAULT_MODEL) -> str:
    return _resolve("model", "OPENROUTER_MODEL", default)


def get_summary_prompt(default: str = DEFAULT_SUMMARY_PROMPT) -> str:
    return _resolve("summary_prompt", "SUMMARY_PROMPT", default)


def stored_summary_prompt() -> str:
    """The user's stored custom prompt, or '' when the default is in use."""
    val = load_settings().get("summary_prompt")
    return str(val).strip() if val and str(val).strip() else ""


def mask(secret: str) -> str:
    """Mask a secret for safe display: keep only the last 4 chars (e.g. '…ab12'). Empty -> ''."""
    if not secret:
        return ""
    secret = str(secret)
    if len(secret) <= 4:
        return "…" + secret[-1:]
    return "…" + secret[-4:]


def settings_status() -> dict:
    """Non-secret view of settings for the dashboard API (never includes raw key values)."""
    or_key = get_openrouter_key()
    apify = get_apify_token()
    return {
        "model": get_model(),
        "models": list(CURATED_MODELS),
        "summary_prompt": stored_summary_prompt(),
        "summary_prompt_default": DEFAULT_SUMMARY_PROMPT,
        "openrouter_api_key_set": bool(or_key),
        "openrouter_api_key_masked": mask(or_key),
        "apify_token_set": bool(apify),
        "apify_token_masked": mask(apify),
    }
