"""Tests for FastAPI backend endpoints (single new format)."""
import json
import os
import tempfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from models import CompetitorData, Post, WeeklyReport
from writers.markdown_builder import build_report


def _post(id, platform, caption, likes=10, comments=2, shares=1, views=None,
          published_at="2026-06-10T10:00:00", url=None, image_url=None):
    return Post(id=id, platform=platform, url=url or f"https://example.com/{id}",
                caption=caption, published_at=published_at, likes=likes,
                comments=comments, shares=shares, reach=0, views=views, image_url=image_url)


def _competitor(name, posts, best=None, summary="Brand summary."):
    return CompetitorData(
        name=name, ig_followers=100000, fb_followers=200000, tt_followers=30000,
        ig_followers_prev=99000, fb_followers_prev=201000, tt_followers_prev=29500,
        posts=posts, best_post=best, content_summary=summary)


PH_DATA = {
    "name": "Pizza Hut Polska",
    "ig_followers": 100000, "fb_followers": 200000, "tt_followers": 30000,
    "ig_followers_prev": 99000, "fb_followers_prev": 201000, "tt_followers_prev": 29500,
    "ig_posts": [
        {"id": "p1", "platform": "instagram", "url": "https://ig.com/p1", "caption": "Newest",
         "published_at": "2026-06-13T10:00:00", "likes": 100, "comments": 5, "shares": 1,
         "reach": 0, "views": None, "image_url": ""},
        {"id": "p2", "platform": "instagram", "url": "https://ig.com/p2", "caption": "Older",
         "published_at": "2026-06-09T10:00:00", "likes": 50, "comments": 2, "shares": 0,
         "reach": 0, "views": None, "image_url": ""},
    ],
    "fb_posts": [], "tt_posts": [],
}


@pytest.fixture
def reports_root(tmp_path):
    best = _post("best", "tiktok", "Top clip", views=500000,
                 url="https://tiktok.com/@x/1", image_url="images/tt_best.jpg")
    posts = [_post("p1", "instagram", "Newest", published_at="2026-06-13T10:00:00"), best]
    comp = _competitor("Pizza Hut Polska", posts, best=best,
                       summary="Pizza Hut promoted new menu.")
    rep = WeeklyReport(report_title="Competitor Brands — Weekly Social Report",
                       week_label="8.06 – 14.06.2026", week_iso="2026-06-08_2026-06-14",
                       competitors=[comp])
    rdir = tmp_path / "2026-06-08_2026-06-14"
    (rdir / "data").mkdir(parents=True)
    (rdir / "report.md").write_text(build_report(rep), encoding="utf-8")
    (rdir / "data" / "pizza-hut-polska.json").write_text(json.dumps(PH_DATA), encoding="utf-8")
    (rdir / "data" / "image_index.json").write_text(
        json.dumps({"https://cdn.example/tt.jpg": "images/tt_best.jpg"}), encoding="utf-8")
    return tmp_path


@pytest.fixture
def client(reports_root):
    with patch("main.REPORTS_DIR", str(reports_root)):
        from main import app
        yield TestClient(app)


def test_list_reports(client):
    data = client.get("/api/reports").json()
    assert len(data) == 1
    assert data[0]["report_id"] == "2026-06-08_2026-06-14"
    assert data[0]["week_label"] == "8.06 – 14.06.2026"
    assert data[0]["has_data"] is True


def test_get_report_competitors(client):
    data = client.get("/api/reports/2026-06-08_2026-06-14").json()
    assert data["report_title"] == "Competitor Brands — Weekly Social Report"
    assert "top_posts" not in data
    assert "campaigns" not in data
    comp = data["competitors"][0]
    assert comp["name"] == "Pizza Hut Polska"
    assert comp["content_summary"] == "Pizza Hut promoted new menu."
    assert comp["best_post"]["platform"] == "TikTok"


def test_get_report_attaches_posts_newest_first(client):
    data = client.get("/api/reports/2026-06-08_2026-06-14").json()
    posts = data["competitors"][0]["posts"]
    assert len(posts) == 2
    assert posts[0]["caption"] == "Newest"
    assert posts[1]["caption"] == "Older"


def test_get_report_not_found(client):
    assert client.get("/api/reports/2099-01-01_2099-01-07").status_code == 404


def test_followers_summary(client):
    data = client.get("/api/reports/2026-06-08_2026-06-14/followers").json()
    assert len(data) == 1
    assert data[0]["name"] == "Pizza Hut Polska"
    assert data[0]["facebook"] == 200000
    assert data[0]["facebook_delta"] == -1000


def test_export_markdown(client):
    r = client.get("/api/reports/2026-06-08_2026-06-14/export/markdown")
    assert r.status_code == 200
    assert "text/markdown" in r.headers["content-type"]
    assert "## 1. Competitors" in r.text


def test_export_html_has_posts_table_and_no_legacy(client):
    html = client.get("/api/reports/2026-06-08_2026-06-14/export/html").text
    assert "Pizza Hut Polska" in html
    assert "All posts this period" in html
    for forbidden in ["Campaigns", "Meta Ads", "Weekly Summary"]:
        assert forbidden not in html


def test_export_html_best_post_image_resolved_to_cdn(client):
    html = client.get("/api/reports/2026-06-08_2026-06-14/export/html").text
    assert 'src="https://cdn.example/tt.jpg"' in html
    assert 'src="images/' not in html
    assert "expire" in html


def test_settings_get_no_raw_secret(client, monkeypatch):
    from utils import settings as st
    monkeypatch.setattr(st, "SETTINGS_PATH", os.path.join(tempfile.mkdtemp(), "settings.json"))
    body = client.get("/api/settings").json()
    assert "anthropic/claude-sonnet-4.6" in body["models"]
    assert "openrouter_api_key_set" in body
    assert "openrouter_api_key" not in body  # only *_set / *_masked keys exist


def test_settings_post_saves_and_masks(client, monkeypatch, tmp_path):
    from utils import settings as st
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(st, "SETTINGS_PATH", str(settings_file))
    body = client.post("/api/settings", json={
        "openrouter_api_key": "sk-or-supersecret-9999",
        "model": "openai/gpt-4o",
    }).json()
    assert body["model"] == "openai/gpt-4o"
    assert body["openrouter_api_key_set"] is True
    assert "supersecret" not in json.dumps(body)
    saved = json.loads(settings_file.read_text())
    assert saved["openrouter_api_key"] == "sk-or-supersecret-9999"


def test_settings_summary_prompt_round_trip(client, monkeypatch, tmp_path):
    from utils import settings as st
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(st, "SETTINGS_PATH", str(settings_file))
    monkeypatch.delenv("SUMMARY_PROMPT", raising=False)

    client.post("/api/settings", json={"summary_prompt": "My custom prompt"})
    body = client.get("/api/settings").json()
    assert body["summary_prompt"] == "My custom prompt"
    assert "summary_prompt_default" in body

    client.post("/api/settings", json={"summary_prompt": ""})  # revert
    body2 = client.get("/api/settings").json()
    assert body2["summary_prompt"] == ""


def test_profiles_get_put_reset(client, monkeypatch, tmp_path):
    from utils import profiles as pf
    cfg = tmp_path / "config.yaml"
    cfg.write_text("competitors:\n  - name: Config Brand\n    instagram_handle: cfgig\n")
    monkeypatch.setattr(pf, "CONFIG_PATH", str(cfg))
    monkeypatch.setattr(pf, "PROFILES_PATH", str(tmp_path / "data" / "profiles.json"))

    body = client.get("/api/profiles").json()
    assert body["is_override"] is False
    assert body["profiles"][0]["name"] == "Config Brand"

    put = client.put("/api/profiles", json={"profiles": [
        {"name": "Subway", "instagram_handle": "subwaypl"}]})
    assert put.status_code == 200
    assert put.json()["is_override"] is True
    assert [p["name"] for p in client.get("/api/profiles").json()["profiles"]] == ["Subway"]

    client.delete("/api/profiles")
    assert client.get("/api/profiles").json()["is_override"] is False


def test_profiles_put_rejects_invalid(client, monkeypatch, tmp_path):
    from utils import profiles as pf
    monkeypatch.setattr(pf, "PROFILES_PATH", str(tmp_path / "data" / "profiles.json"))
    r = client.put("/api/profiles", json={"profiles": [{"name": "", "instagram_handle": "x"}]})
    assert r.status_code == 400


def test_brand_rank_follows_profile_order(monkeypatch, tmp_path):
    import main
    from utils import profiles as pf
    cfg = tmp_path / "config.yaml"
    cfg.write_text(
        "competitors:\n"
        "  - name: KFC Polska\n    instagram_handle: k\n"
        "  - name: Subway\n    instagram_handle: s\n")
    monkeypatch.setattr(pf, "CONFIG_PATH", str(cfg))
    monkeypatch.setattr(pf, "PROFILES_PATH", str(tmp_path / "nope.json"))

    tokens = main._brand_order_tokens()
    assert main._brand_rank("KFC Polska", tokens) == 0
    assert main._brand_rank("Subway", tokens) == 1
    assert main._brand_rank("Unknown Brand", tokens) == 2
