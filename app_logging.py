# app_logging.py
"""Project-wide logging setup. JSON-lines per-run files in logs/runs/.

Usage:
    from app_logging import setup_logging, get_logger
    setup_logging("2026-05-10_2026-05-16")
    log = get_logger(__name__)
    log.info("Pipeline started")
"""
import json
import logging
import os
from datetime import datetime, timezone
from logging import Logger

LOGS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs", "runs")
KEEP_LATEST_N = 50


class _JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(run_id: str) -> Logger:
    """Configure root 'app' logger with per-run file + stderr handlers. Idempotent."""
    os.makedirs(LOGS_DIR, exist_ok=True)
    _cleanup_old_logs()

    root = logging.getLogger("app")
    root.setLevel(logging.DEBUG)
    root.propagate = False
    for h in list(root.handlers):
        root.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass

    file_path = os.path.join(LOGS_DIR, f"{run_id}.jsonl")
    fh = logging.FileHandler(file_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(_JsonLineFormatter())
    root.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setLevel(logging.INFO)
    sh.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    root.addHandler(sh)
    return root


def _cleanup_old_logs() -> None:
    if not os.path.isdir(LOGS_DIR):
        return
    files = [f for f in os.listdir(LOGS_DIR) if f.endswith(".jsonl")]
    files.sort(key=lambda f: os.path.getmtime(os.path.join(LOGS_DIR, f)), reverse=True)
    for stale in files[KEEP_LATEST_N:]:
        try:
            os.remove(os.path.join(LOGS_DIR, stale))
        except OSError:
            pass


def get_logger(name: str) -> Logger:
    """Module-level logger; auto-prefixes with 'app.'"""
    if name.startswith("app."):
        return logging.getLogger(name)
    return logging.getLogger(f"app.{name}")
