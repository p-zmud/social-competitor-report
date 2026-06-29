# tests/test_pipeline_resilience.py
"""Integration test: Apify is the only data source, so a hard Apify failure must
early-return a minimal report (not crash) with the failure captured in the log.
"""
import json
import os
import shutil

import pytest


@pytest.fixture
def isolated_run(tmp_path, monkeypatch):
    monkeypatch.setenv("APIFY_TOKEN", "x")
    monkeypatch.setenv("OPENROUTER_API_KEY", "x")
    from utils import settings as st
    monkeypatch.setattr(st, "SETTINGS_PATH", str(tmp_path / "no-settings.json"))
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    shutil.copy(os.path.join(project_root, "config.yaml"), tmp_path / "config.yaml")
    monkeypatch.chdir(tmp_path)
    import generate_report
    monkeypatch.setattr(generate_report, "__file__", str(tmp_path / "generate_report.py"))
    import app_logging
    monkeypatch.setattr(app_logging, "LOGS_DIR", str(tmp_path / "logs" / "runs"))
    yield tmp_path


def test_pipeline_early_returns_on_apify_failure(isolated_run, mocker):
    from generate_report import run_pipeline

    mocker.patch("collectors.apify.ApifyCollector.fetch_all_competitors",
                 side_effect=RuntimeError("apify down"))
    mocker.patch("processors.followers_history.FollowersHistory.save")

    result = run_pipeline(start_date="2026-05-01", end_date="2026-05-07",
                          no_llm=True, skip_apify=False)

    md_path = result["filepath"]
    assert os.path.isfile(md_path)
    log_path = os.path.join(os.path.dirname(md_path), "data", "generation_log.json")
    with open(log_path) as f:
        names = {s["name"]: s for s in json.load(f)}
    assert names["Apify (batch)"]["status"] == "failed"
    assert "apify down" in (names["Apify (batch)"]["error"] or "")
    # Apify is the sole source -> total data loss -> minimal report, no brands rendered.
    assert result["competitor_count"] == 0
