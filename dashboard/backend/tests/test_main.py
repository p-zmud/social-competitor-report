"""Path-traversal hardening tests for report_id-bearing endpoints."""

import json

import pytest
from fastapi.testclient import TestClient

import main
from main import app

client = TestClient(app)


@pytest.mark.parametrize(
    "bad_id",
    [
        "../../../etc/passwd",
        "..%2F..%2Fetc%2Fpasswd",
        "2026-W07/../../etc",
        "valid-looking-but-../traversal",
        "",
        "a" * 200,
        "../",
        "..",
        "report_id_with_slash/",
        "totally-bogus-format-but-no-slashes",
    ],
)
def test_get_report_rejects_invalid_report_id(bad_id):
    resp = client.get(f"/api/reports/{bad_id}")
    # Empty bad_id resolves to GET /api/reports/ which is the list endpoint
    # (200 OK with empty/array body) — not exploitable, so allow it.
    if bad_id == "":
        assert resp.status_code in (200, 307, 404), f"got {resp.status_code} for empty id"
    else:
        assert resp.status_code in (400, 404), f"got {resp.status_code} for {bad_id!r}"


def test_get_report_validator_returns_400_for_bogus_but_safe_id():
    """A non-traversal but malformed id must hit the validator (400, not 404)."""
    resp = client.get("/api/reports/totally-bogus-format-but-no-slashes")
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Invalid report_id"


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/reports/{rid}",
        "/api/reports/{rid}/data",
        "/api/reports/{rid}/followers",
        "/api/reports/{rid}/log",
        "/api/reports/{rid}/export/markdown",
        "/api/reports/{rid}/export/html",
    ],
)
def test_all_report_id_endpoints_validate(endpoint):
    """Every endpoint that accepts report_id rejects malformed ids with 400."""
    resp = client.get(endpoint.format(rid="not-a-valid-id"))
    assert resp.status_code == 400, (
        f"endpoint {endpoint} returned {resp.status_code}, expected 400"
    )


@pytest.mark.parametrize(
    "good_id",
    [
        "2026-02-13_2026-02-19",
        "2026-W07",
        "2026-W07-legacy-weekly",
    ],
)
def test_validator_accepts_known_report_id_formats(good_id):
    """Known formats must pass validation (may return 200 or 404 depending on
    whether the report exists, but never 400)."""
    resp = client.get(f"/api/reports/{good_id}")
    assert resp.status_code != 400, f"{good_id!r} should be accepted by validator"


def test_get_report_data_skips_corrupted_json(tmp_path, monkeypatch):
    """A corrupt brand JSON must not produce a 500; endpoint returns the
    valid payloads only."""
    report_id = "2026-02-13_2026-02-19"
    data_dir = tmp_path / report_id / "data"
    data_dir.mkdir(parents=True)

    valid = {"name": "Pizza Hut Polska", "fb_followers": 100, "ig_followers": 200, "tt_followers": 300}
    (data_dir / "pizza-hut-polska.json").write_text(json.dumps(valid), encoding="utf-8")
    (data_dir / "broken.json").write_text("{{{not json", encoding="utf-8")

    monkeypatch.setattr(main, "REPORTS_DIR", str(tmp_path))

    resp = client.get(f"/api/reports/{report_id}/data")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "Pizza Hut Polska"


def test_get_followers_summary_skips_corrupted_json(tmp_path, monkeypatch):
    """followers endpoint must skip corrupt JSON without 500."""
    report_id = "2026-02-13_2026-02-19"
    data_dir = tmp_path / report_id / "data"
    data_dir.mkdir(parents=True)

    valid = {"name": "Pizza Hut Polska", "fb_followers": 100, "ig_followers": 200, "tt_followers": 300}
    (data_dir / "pizza-hut-polska.json").write_text(json.dumps(valid), encoding="utf-8")
    (data_dir / "broken.json").write_text("not-json-at-all", encoding="utf-8")

    monkeypatch.setattr(main, "REPORTS_DIR", str(tmp_path))

    resp = client.get(f"/api/reports/{report_id}/followers")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name"] == "Pizza Hut Polska"
    assert body[0]["facebook"] == 100
