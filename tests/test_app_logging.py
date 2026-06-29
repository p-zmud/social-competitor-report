# tests/test_app_logging.py
import json
import logging
import os

import pytest

from app_logging import setup_logging, get_logger


@pytest.fixture
def isolated_logs_dir(tmp_path, monkeypatch):
    log_dir = tmp_path / "runs"
    monkeypatch.setattr("app_logging.LOGS_DIR", str(log_dir))
    yield str(log_dir)


def test_setup_logging_creates_file(isolated_logs_dir):
    setup_logging("test-run-1")
    assert os.path.isfile(os.path.join(isolated_logs_dir, "test-run-1.jsonl"))


def test_log_message_is_jsonline(isolated_logs_dir):
    setup_logging("test-run-2")
    log = get_logger("collectors.demo")
    log.info("hello %s", "world")
    for h in logging.getLogger("app").handlers:
        h.flush()
    log_file = os.path.join(isolated_logs_dir, "test-run-2.jsonl")
    with open(log_file) as f:
        line = f.readline().strip()
    obj = json.loads(line)
    assert obj["level"] == "INFO"
    assert obj["logger"] == "app.collectors.demo"
    assert obj["msg"] == "hello world"
    assert "ts" in obj


def test_setup_logging_is_idempotent(isolated_logs_dir):
    setup_logging("test-run-3")
    setup_logging("test-run-3")
    handlers = logging.getLogger("app").handlers
    assert len(handlers) == 2


def test_cleanup_old_logs_keeps_latest_n(isolated_logs_dir, monkeypatch):
    monkeypatch.setattr("app_logging.KEEP_LATEST_N", 3)
    os.makedirs(isolated_logs_dir, exist_ok=True)
    import time
    for i in range(5):
        path = os.path.join(isolated_logs_dir, f"old-{i}.jsonl")
        with open(path, "w") as f:
            f.write("{}\n")
        os.utime(path, (time.time() - (5 - i) * 60, time.time() - (5 - i) * 60))
    setup_logging("new-run")
    remaining = sorted(f for f in os.listdir(isolated_logs_dir) if f.endswith(".jsonl"))
    assert len(remaining) == 4
    assert "new-run.jsonl" in remaining
    assert "old-0.jsonl" not in remaining
