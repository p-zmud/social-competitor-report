"""Tests for report generation endpoint and WebSocket."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from main import app, _generate_state


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    """Reset generation state before each test and stub validation env."""
    for var in ["OPENROUTER_API_KEY", "APIFY_TOKEN"]:
        monkeypatch.setenv(var, "test")
    monkeypatch.setattr("utils.validation.validate_environment", lambda **kw: [])
    _generate_state["running"] = False
    _generate_state["reporter"] = None
    _generate_state["thread"] = None
    yield
    _generate_state["running"] = False
    _generate_state["reporter"] = None
    _generate_state["thread"] = None


@pytest.fixture
def client():
    return TestClient(app)


@patch("main.run_pipeline")
def test_generate_starts_pipeline(mock_pipeline, client):
    """POST /api/reports/generate should start pipeline and return status started."""
    mock_pipeline.return_value = {"report_path": "/tmp/test.md"}

    resp = client.post("/api/reports/generate", json={
        "week": "2026-W07",
        "no_llm": True,
        "skip_apify": True,
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "started"

    # Wait for background thread to finish
    thread = _generate_state["thread"]
    if thread:
        thread.join(timeout=5)


@patch("main.run_pipeline")
def test_generate_with_date_range(mock_pipeline, client):
    """POST with start_date and end_date should pass them to pipeline."""
    mock_pipeline.return_value = {"report_path": "/tmp/test.md"}

    resp = client.post("/api/reports/generate", json={
        "start_date": "2026-02-09",
        "end_date": "2026-02-15",
        "no_llm": True,
        "skip_apify": True,
    })

    assert resp.status_code == 200
    assert resp.json()["status"] == "started"

    thread = _generate_state["thread"]
    if thread:
        thread.join(timeout=5)

    # Verify pipeline was called with date range params
    mock_pipeline.assert_called_once()
    call_kwargs = mock_pipeline.call_args
    assert call_kwargs.kwargs["start_date"] == "2026-02-09"
    assert call_kwargs.kwargs["end_date"] == "2026-02-15"


@patch("main.run_pipeline")
def test_generate_default_week(mock_pipeline, client):
    """POST with empty body should work (defaults: all None/False)."""
    mock_pipeline.return_value = {"report_path": "/tmp/test.md"}

    resp = client.post("/api/reports/generate", json={})

    assert resp.status_code == 200
    assert resp.json()["status"] == "started"

    thread = _generate_state["thread"]
    if thread:
        thread.join(timeout=5)


def test_generate_already_running(client):
    """If generation is already running, should return already_running."""
    _generate_state["running"] = True

    resp = client.post("/api/reports/generate", json={})

    assert resp.status_code == 200
    assert resp.json()["status"] == "already_running"
