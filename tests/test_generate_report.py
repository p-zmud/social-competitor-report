# tests/test_generate_report.py
"""Pipeline behavior for the Apify-only flow: per-brand summary failure must not
abort; total data loss early-returns and finalizes the reporter; --skip-apify is a
valid dry run.
"""
import json
import os
import shutil

import pytest

from models import Post


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


def _post(id="c1"):
    return Post(id=id, platform="instagram", url=f"https://example/{id}",
                caption="comp post", published_at="2026-05-02",
                likes=5, comments=0, shares=0, reach=0, views=50, image_url=None)


def test_competitor_summary_failure_does_not_abort(isolated_run, mocker):
    import yaml
    from generate_report import run_pipeline
    from writers.llm_writer import LLMWriter

    competitors = yaml.safe_load(
        (isolated_run / "config.yaml").read_text(encoding="utf-8"))["competitors"]
    fail_name, ok_name = competitors[0]["name"], competitors[1]["name"]

    def fake_fetch(cfgs, init_date, end_date):
        return {c["name"]: {"ig_followers": 100, "fb_followers": 200, "tt_followers": 300,
                            "ig_posts": [_post()], "fb_posts": [], "tt_posts": []}
                for c in cfgs}
    mocker.patch("collectors.apify.ApifyCollector.fetch_all_competitors", side_effect=fake_fetch)
    mocker.patch("processors.followers_history.FollowersHistory.save")
    mocker.patch("processors.followers_history.FollowersHistory.update")
    mocker.patch("processors.followers_history.FollowersHistory.get_previous", return_value=0)
    mocker.patch("utils.image_downloader.download_post_images", return_value={})

    def fake_summary(self, name, posts):
        if name == fail_name:
            raise RuntimeError("simulated failure")
        return "ok summary"
    mocker.patch.object(LLMWriter, "write_competitor_summary", autospec=True,
                        side_effect=fake_summary)

    result = run_pipeline(start_date="2026-05-01", end_date="2026-05-07",
                          no_llm=False, skip_apify=False)

    md_path = result["filepath"]
    assert os.path.isfile(md_path)
    log_path = os.path.join(os.path.dirname(md_path), "data", "generation_log.json")
    with open(log_path) as f:
        names = {s["name"]: s for s in json.load(f)}
    assert names[f"Summary: {fail_name}"]["status"] == "failed"
    assert "simulated failure" in (names[f"Summary: {fail_name}"]["error"] or "")
    assert names[f"Summary: {ok_name}"]["status"] == "ok"

    md = open(md_path, encoding="utf-8").read()
    assert "Summary unavailable." in md
    assert "ok summary" in md
    assert result["competitor_count"] == len(competitors)


def test_no_apify_data_early_returns_and_finalizes_reporter(isolated_run, mocker):
    from generate_report import run_pipeline
    from utils.progress import ProgressReporter

    def empty_fetch(cfgs, init_date, end_date):
        return {c["name"]: {"ig_followers": 0, "fb_followers": 0, "tt_followers": 0,
                            "ig_posts": [], "fb_posts": [], "tt_posts": []} for c in cfgs}
    mocker.patch("collectors.apify.ApifyCollector.fetch_all_competitors", side_effect=empty_fetch)
    mocker.patch("processors.followers_history.FollowersHistory.save")

    reporter = ProgressReporter()
    result = run_pipeline(start_date="2026-05-01", end_date="2026-05-07",
                          no_llm=True, skip_apify=False, reporter=reporter)

    snap = reporter.snapshot()
    assert snap["finished"] is True
    assert snap["result"] == result
    assert result["post_count"] == 0
    assert result["competitor_count"] == 0


def test_skip_apify_dry_run_produces_empty_report(isolated_run, mocker):
    from generate_report import run_pipeline
    mocker.patch("processors.followers_history.FollowersHistory.save")
    mocker.patch("utils.image_downloader.download_post_images", return_value={})

    result = run_pipeline(start_date="2026-05-01", end_date="2026-05-07",
                          no_llm=True, skip_apify=True)

    assert os.path.isfile(result["filepath"])
    assert result["post_count"] == 0
    assert result["competitor_count"] == 4  # brands present, no data
    md = open(result["filepath"], encoding="utf-8").read()
    assert "## 1. Competitors" in md
