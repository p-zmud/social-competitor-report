# utils/validation.py
"""Startup validation for credentials (Apify + OpenRouter) and config.yaml.

Credentials are resolved through utils.settings, so the dashboard Settings UI
(data/settings.json) satisfies these checks without a .env file.
"""
import os
import yaml

from app_logging import get_logger
from utils.profiles import effective_competitors
from utils.settings import get_apify_token, get_openrouter_key

_log = get_logger("validation")


class ConfigError(Exception):
    """Raised when required configuration is missing or malformed."""


def validate_environment(*, no_llm: bool = False, skip_apify: bool = False,
                         strict: bool = True) -> list[str]:
    """Return a list of problem descriptions. If strict and non-empty, raise ConfigError."""
    problems: list[str] = []

    if not no_llm and not get_openrouter_key():
        problems.append(
            "Missing OpenRouter API key — set it in the dashboard Settings or as OPENROUTER_API_KEY."
        )
    if not skip_apify and not get_apify_token():
        problems.append(
            "Missing Apify token — set it in the dashboard Settings or as APIFY_TOKEN."
        )

    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config.yaml",
    )
    cfg = None
    if not os.path.isfile(config_path):
        problems.append(f"Missing config.yaml at {config_path}")
    else:
        try:
            with open(config_path) as f:
                cfg = yaml.safe_load(f)
        except yaml.YAMLError as e:
            problems.append(f"config.yaml: parse error ({e})")
        if cfg is not None and not isinstance(cfg, dict):
            problems.append("config.yaml: not a mapping")

    # Competitors may come from config.yaml OR a dashboard profiles override.
    config_competitors = cfg.get("competitors") if isinstance(cfg, dict) else []
    if not effective_competitors(config_competitors):
        problems.append(
            "No competitors configured — add profiles in the dashboard Settings or config.yaml."
        )

    if problems:
        for p in problems:
            _log.error("Validation: %s", p)
        if strict:
            raise ConfigError("Validation failed:\n  - " + "\n  - ".join(problems))
    return problems
