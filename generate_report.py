#!/usr/bin/env python3
# generate_report.py
"""Social Competitor Report — weekly generator.

Usage:
  python3 generate_report.py                                  # last 7 days
  python3 generate_report.py --start-date 2026-06-08 --end-date 2026-06-14
  python3 generate_report.py --no-llm --skip-apify            # dry run ($0)
"""
import argparse
import json
import os
import time
from dataclasses import asdict
from datetime import datetime, timedelta

import yaml
from dotenv import load_dotenv

from app_logging import get_logger, setup_logging
from collectors.apify import ApifyCollector
from models import CompetitorData, StepResult, WeeklyReport
from processors.competitors import get_best_post
from processors.followers_history import FollowersHistory
from utils.profiles import effective_competitors
from utils.settings import get_apify_token, get_model, get_openrouter_key
from writers.llm_writer import LLMWriter
from writers.markdown_builder import build_report

_pipeline_log = get_logger("pipeline")

DEFAULT_TITLE = "Weekly Social Report"


def _items_count(value) -> int:
    """Best-effort count for a step's return value."""
    if value is None:
        return 0
    if isinstance(value, (list, dict, tuple)):
        return len(value)
    return 0


def run_step(name: str, fn, *args, **kwargs):
    """Wrap a pipeline step. Returns (StepResult, fn return value or None on failure)."""
    t0 = time.monotonic()
    try:
        value = fn(*args, **kwargs)
    except Exception as e:
        dt = time.monotonic() - t0
        _pipeline_log.exception("Step '%s' failed: %s", name, e)
        return StepResult(name=name, status="failed", duration_s=dt, error=str(e)[:200]), None
    dt = time.monotonic() - t0
    items = _items_count(value)
    _pipeline_log.info("Step '%s' ok (%.2fs, %d items)", name, dt, items)
    return StepResult(name=name, status="ok", duration_s=dt, items_count=items), value


def skipped_step(name: str):
    """Returns a StepResult marking a step as skipped (e.g. due to --no-llm)."""
    return StepResult(name=name, status="skipped", duration_s=0.0), None


def get_date_range(start_date: str | None = None, end_date: str | None = None,
                   week_iso: str | None = None) -> tuple[str, str, str, str]:
    """Returns (start_date, end_date, label, report_id).

    Priority: explicit dates > week_iso > default (last 7 days).
    report_id format: "2026-06-08_2026-06-14"; label: "8.06 – 14.06.2026".
    """
    if start_date and end_date:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    elif week_iso:
        year, week = week_iso.split("-W")
        start = datetime.fromisocalendar(int(year), int(week), 1)
        end = start + timedelta(days=6)
    else:
        today = datetime.now()
        end = today - timedelta(days=today.weekday() + 1)  # last Sunday
        start = end - timedelta(days=6)  # Monday before

    init_date = start.strftime("%Y-%m-%d")
    end_date_str = end.strftime("%Y-%m-%d")
    label = f"{start.day}.{start.month:02d} – {end.day}.{end.month:02d}.{end.year}"
    report_id = f"{init_date}_{end_date_str}"
    return init_date, end_date_str, label, report_id


def _load_config(base_dir: str) -> dict:
    with open(os.path.join(base_dir, "config.yaml")) as f:
        return yaml.safe_load(f) or {}


def _early_return_report(report_id: str, report_title: str, week_label: str,
                         steps: list, base_dir: str, *, reports_dir: str = "reports",
                         reporter=None) -> dict:
    """Build a minimal report when validation fails or no Apify data is available."""
    out_dir = os.path.join(base_dir, reports_dir, report_id)
    os.makedirs(os.path.join(out_dir, "data"), exist_ok=True)
    report = WeeklyReport(
        report_title=report_title,
        week_label=week_label,
        week_iso=report_id,
        competitors=[],
        generation_log=steps,
    )
    md_path = os.path.join(out_dir, "report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(build_report(report))
    log_path = os.path.join(out_dir, "data", "generation_log.json")
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump([asdict(s) for s in steps], f, ensure_ascii=False, indent=2)
    _pipeline_log.error("Early return: %s", md_path)
    result = {
        "filepath": md_path,
        "post_count": 0,
        "competitor_count": 0,
        "report_id": report_id,
        "week_label": week_label,
    }
    if reporter is not None:
        reporter.finish(result)
    return result


def run_pipeline(week_iso: str | None = None, no_llm: bool = False,
                 skip_apify: bool = False, reporter=None,
                 start_date: str | None = None, end_date: str | None = None) -> dict:
    """Run the full report pipeline (Apify collect -> per-brand process -> markdown).

    Returns dict: filepath, post_count, competitor_count, report_id, week_label.
    """
    load_dotenv()
    init_date, end_date, week_label, report_id = get_date_range(start_date, end_date, week_iso)
    setup_logging(report_id)
    base_dir = os.path.dirname(os.path.abspath(__file__))

    from utils.validation import ConfigError, validate_environment

    try:
        config = _load_config(base_dir)
    except Exception as e:
        config = {}
        _pipeline_log.error("config.yaml load failed: %s", e)
    report_title = config.get("report_title", DEFAULT_TITLE)
    reports_dir = config.get("output_dir", "reports")
    data_dir = config.get("data_dir", "data")
    competitors_cfg = effective_competitors(config.get("competitors", []) or [])

    try:
        validate_environment(no_llm=no_llm, skip_apify=skip_apify, strict=True)
    except ConfigError as e:
        _pipeline_log.error("Validation failed: %s", e)
        if reporter is not None:
            reporter.set_error(str(e))
        steps = [StepResult(name="Validation", status="failed", duration_s=0.0, error=str(e)[:200])]
        return _early_return_report(report_id, report_title, week_label, steps, base_dir,
                                    reports_dir=reports_dir, reporter=reporter)

    def _step_start(name, detail=""):
        if reporter:
            reporter.start_step(name, detail)

    def _step_update(detail):
        if reporter:
            reporter.update_step(detail)

    def _step_done(name=None):
        if reporter:
            reporter.done_step(name)

    _pipeline_log.info("Generating report for: %s (%s)", week_label, report_id)
    _pipeline_log.info("Date range: %s → %s", init_date, end_date)
    _step_start("Preparation", f"{week_label} ({report_id})")
    _step_done("Preparation")

    steps: list[StepResult] = []

    apify = None if skip_apify else ApifyCollector(api_token=get_apify_token())
    llm = None if no_llm else LLMWriter(api_key=get_openrouter_key(), model=get_model())
    history = FollowersHistory(os.path.join(base_dir, data_dir, "followers_history.json"))

    # --- Apify batch (critical data source) ---
    if apify:
        _step_start("Apify (batch)", "3 platforms in parallel...")
        step, prefetched = run_step("Apify (batch)", apify.fetch_all_competitors,
                                    competitors_cfg, init_date, end_date)
        prefetched = prefetched or {}
        steps.append(step)
        _step_done("Apify (batch)")
    else:
        s, _ = skipped_step("Apify (batch)")
        steps.append(s)
        prefetched = {}

    # Critical abort: Apify enabled but every brand came back empty.
    if apify:
        any_data = any(
            (d.get("ig_followers") or d.get("fb_followers") or d.get("tt_followers")
             or d.get("ig_posts") or d.get("fb_posts") or d.get("tt_posts"))
            for d in prefetched.values()
        )
        if not any_data:
            _pipeline_log.error("No Apify data for any brand — aborting.")
            return _early_return_report(report_id, report_title, week_label, steps, base_dir,
                                        reports_dir=reports_dir, reporter=reporter)

    previous_followers_by_name: dict[str, dict[str, int]] = {}
    competitors_data: list[CompetitorData] = []
    total_posts = 0

    for comp in competitors_cfg:
        name = comp["name"]
        _step_start(f"Brand: {name}", "")
        _pipeline_log.info("Processing: %s...", name)

        data = prefetched.get(name, {}) if apify else {}
        ig_followers = data.get("ig_followers", 0)
        fb_followers = data.get("fb_followers", 0)
        tt_followers = data.get("tt_followers", 0)
        all_comp_posts = (data.get("ig_posts", []) + data.get("fb_posts", [])
                          + data.get("tt_posts", []))
        total_posts += len(all_comp_posts)

        ig_prev = history.get_previous(name, "instagram")
        fb_prev = history.get_previous(name, "facebook")
        tt_prev = history.get_previous(name, "tiktok")
        previous_followers_by_name[name] = {
            "instagram": ig_prev, "facebook": fb_prev, "tiktok": tt_prev,
        }
        if apify:
            history.update(name, instagram=ig_followers, facebook=fb_followers, tiktok=tt_followers)

        best = get_best_post(all_comp_posts)

        if llm and all_comp_posts:
            _step_update("LLM summary...")
            sr, content_summary = run_step(f"Summary: {name}", llm.write_competitor_summary,
                                           name, all_comp_posts)
            steps.append(sr)
            if content_summary is None:
                content_summary = "Summary unavailable."
        else:
            content_summary = "No post data for this period."

        competitors_data.append(CompetitorData(
            name=name,
            ig_followers=ig_followers, fb_followers=fb_followers, tt_followers=tt_followers,
            ig_followers_prev=ig_prev, fb_followers_prev=fb_prev, tt_followers_prev=tt_prev,
            posts=all_comp_posts, best_post=best, content_summary=content_summary,
        ))
        _step_done(f"Brand: {name}")

    # --- Download best-post images (the posts table is text/stats, no thumbnails) ---
    reports_base = os.path.join(base_dir, reports_dir)
    report_dir = os.path.join(reports_base, report_id)
    images_dir = os.path.join(report_dir, "images")
    os.makedirs(images_dir, exist_ok=True)

    from utils.image_downloader import download_post_images
    posts_to_download = [c.best_post for c in competitors_data if c.best_post]
    _step_start("Downloading images", f"{len(posts_to_download)} posts...")
    step, _ = run_step("Downloading images", download_post_images, posts_to_download, images_dir)
    steps.append(step)
    _step_done("Downloading images")

    # --- Build + persist ---
    _step_start("Building report", "Markdown...")
    report = WeeklyReport(
        report_title=report_title, week_label=week_label, week_iso=report_id,
        competitors=competitors_data, generation_log=steps,
    )
    markdown = build_report(report)
    os.makedirs(report_dir, exist_ok=True)
    filepath = os.path.join(report_dir, "report.md")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(markdown)

    if prefetched:
        data_dir_path = os.path.join(report_dir, "data")
        os.makedirs(data_dir_path, exist_ok=True)
        _save_apify_data(prefetched, data_dir_path, previous_followers=previous_followers_by_name)

    history.save()

    log_path = os.path.join(report_dir, "data", "generation_log.json")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump([asdict(s) for s in steps], f, ensure_ascii=False, indent=2)
    _pipeline_log.info("generation_log.json saved: %s", log_path)

    _step_done("Building report")
    _pipeline_log.info("Report saved: %s", filepath)
    print(f"\n✅ Report saved: {filepath}")

    result = {
        "filepath": filepath,
        "post_count": total_posts,
        "competitor_count": len(competitors_data),
        "report_id": report_id,
        "week_label": week_label,
    }
    if reporter:
        reporter.finish(result)
    return result


def _post_to_dict(post) -> dict:
    """Convert a Post to a serializable dict."""
    return {
        "id": post.id,
        "platform": post.platform,
        "url": post.url,
        "caption": post.caption,
        "published_at": post.published_at,
        "likes": post.likes,
        "comments": post.comments,
        "shares": post.shares,
        "reach": post.reach,
        "views": post.views,
        "image_url": getattr(post, "image_url", None) or "",
    }


def _save_apify_data(prefetched: dict, data_dir: str, *, previous_followers: dict | None = None):
    """Save raw Apify-scraped data as one JSON file per brand."""
    scraped_at = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    previous_followers = previous_followers or {}
    for name, data in prefetched.items():
        safe_name = name.lower().replace(" ", "-").replace("'", "")
        prev = previous_followers.get(name, {})
        comp_data = {
            "name": name,
            "scraped_at": scraped_at,
            "ig_followers": data.get("ig_followers", 0),
            "fb_followers": data.get("fb_followers", 0),
            "tt_followers": data.get("tt_followers", 0),
            "ig_followers_prev": prev.get("instagram", 0),
            "fb_followers_prev": prev.get("facebook", 0),
            "tt_followers_prev": prev.get("tiktok", 0),
            "ig_posts": [_post_to_dict(p) for p in data.get("ig_posts", [])],
            "fb_posts": [_post_to_dict(p) for p in data.get("fb_posts", [])],
            "tt_posts": [_post_to_dict(p) for p in data.get("tt_posts", [])],
        }
        with open(os.path.join(data_dir, f"{safe_name}.json"), "w", encoding="utf-8") as f:
            json.dump(comp_data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Social Competitor Report generator")
    parser.add_argument("--week", help="ISO week e.g. 2026-W24 (backward compat)")
    parser.add_argument("--start-date", dest="start_date", help="Start date YYYY-MM-DD")
    parser.add_argument("--end-date", dest="end_date", help="End date YYYY-MM-DD")
    parser.add_argument("--no-llm", action="store_true", dest="no_llm", help="Skip LLM calls")
    parser.add_argument("--skip-apify", action="store_true", dest="skip_apify",
                        help="Skip Apify (produces an empty report — dry run)")
    args = parser.parse_args()

    if bool(args.start_date) != bool(args.end_date):
        parser.error("--start-date and --end-date must be provided together")

    run_pipeline(week_iso=args.week, no_llm=args.no_llm, skip_apify=args.skip_apify,
                 start_date=args.start_date, end_date=args.end_date)


if __name__ == "__main__":
    main()
