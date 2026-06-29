"""Tests for the single-format competitor report parser.

These round-trip against the real markdown builder so the parser and builder can
never silently drift out of sync.
"""
import pytest

from report_parser import parse_report_content

# build_report + models live at the project root (importable under `python -m pytest`).
from models import CompetitorData, Post, StepResult, WeeklyReport
from writers.markdown_builder import build_report


def _post(id, platform, caption, likes=10, comments=2, shares=1, views=None,
          published_at="2026-06-10T10:00:00", url=None, image_url=None):
    return Post(id=id, platform=platform, url=url or f"https://example.com/{id}",
                caption=caption, published_at=published_at, likes=likes,
                comments=comments, shares=shares, reach=0, views=views, image_url=image_url)


def _competitor(name, posts, best=None, summary="Brand summary."):
    return CompetitorData(
        name=name,
        ig_followers=100000, fb_followers=200000, tt_followers=30000,
        ig_followers_prev=99000, fb_followers_prev=201000, tt_followers_prev=29500,
        posts=posts, best_post=best, content_summary=summary,
    )


def _build(competitors, log=None):
    report = WeeklyReport(
        report_title="Competitor Brands — Weekly Social Report",
        week_label="8.06 – 14.06.2026",
        week_iso="2026-06-08_2026-06-14",
        competitors=competitors, generation_log=log or [],
    )
    return build_report(report)


@pytest.fixture
def parsed():
    best = _post("best", "tiktok", "Best clip ever", views=500000,
                 url="https://tiktok.com/@x/video/1", image_url="images/foo.jpg")
    posts = [
        _post("a", "instagram", "New menu drop", published_at="2026-06-12T09:00:00"),
        best,
    ]
    comp1 = _competitor("Pizza Hut Polska", posts, best=best,
                        summary="Pizza Hut promoted the new menu.")
    comp2 = _competitor("KFC Polska", [], best=None, summary="No post data for this period.")
    md = _build([comp1, comp2], log=[StepResult("Apify (batch)", "ok", 1.0, 8)])
    return parse_report_content(md, report_id="2026-06-08_2026-06-14")


def test_header(parsed):
    assert parsed["report_title"] == "Competitor Brands — Weekly Social Report"
    assert parsed["week_label"] == "8.06 – 14.06.2026"
    assert parsed["report_id"] == "2026-06-08_2026-06-14"


def test_competitor_names_and_order(parsed):
    assert [c["name"] for c in parsed["competitors"]] == ["Pizza Hut Polska", "KFC Polska"]


def test_content_summary(parsed):
    assert parsed["competitors"][0]["content_summary"] == "Pizza Hut promoted the new menu."


def test_best_post(parsed):
    bp = parsed["competitors"][0]["best_post"]
    assert bp["platform"] == "TikTok"
    assert bp["views"] == 500000
    assert bp["url"] == "https://tiktok.com/@x/video/1"
    assert bp["image_url"] == "images/foo.jpg"


def test_followers(parsed):
    f = parsed["competitors"][0]["followers"]
    assert f["facebook"]["current"] == 200000
    assert f["facebook"]["previous"] == 201000
    assert f["facebook"]["delta"] == -1000
    assert f["instagram"]["delta"] == 1000
    assert f["tiktok"]["current"] == 30000


def test_brand_with_no_posts(parsed):
    kfc = parsed["competitors"][1]
    assert kfc["best_post"] is None
    assert kfc["content_summary"] == "No post data for this period."
    assert kfc["followers"]["facebook"]["current"] == 200000


def test_posts_table_does_not_pollute_followers(parsed):
    # Only the three follower platforms — the all-posts table rows must be ignored.
    assert set(parsed["competitors"][0]["followers"].keys()) == {"facebook", "instagram", "tiktok"}


def test_keys(parsed):
    assert set(parsed.keys()) == {"report_title", "week_label", "week_iso", "report_id", "competitors"}


def test_empty_competitor_section():
    result = parse_report_content(_build([]))
    assert result["competitors"] == []
    assert result["week_label"] == "8.06 – 14.06.2026"


def test_best_post_with_er_instead_of_views():
    # A post with reach>0 renders "ER: x%" instead of "Views:"; parser still finds it.
    p = Post(id="z", platform="instagram", url="https://example.com/z", caption="reachy",
             published_at="2026-06-10T10:00:00", likes=50, comments=5, shares=0,
             reach=1000, views=None)
    comp = _competitor("Burger King Polska", [p], best=p, summary="BK posted.")
    parsed = parse_report_content(_build([comp]))
    bp = parsed["competitors"][0]["best_post"]
    assert bp["platform"] == "Instagram"
    assert bp["caption"] == "reachy"
    assert bp["views"] == 0  # ER path -> no Views captured
