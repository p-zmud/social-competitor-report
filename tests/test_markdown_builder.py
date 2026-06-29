# tests/test_markdown_builder.py
from models import CompetitorData, Post, StepResult, WeeklyReport
from writers.markdown_builder import build_report


def make_post(id, platform, likes, comments, shares, caption="Test", views=None,
              published_at="2026-06-10T10:00:00"):
    return Post(id=id, platform=platform, url=f"https://example.com/{id}",
                caption=caption, published_at=published_at,
                likes=likes, comments=comments, shares=shares, reach=0, views=views)


def make_competitor(name="Pizza Hut Polska", posts=None):
    if posts is None:
        posts = [
            make_post("a", "instagram", 500, 30, 10, "New pizza launch",
                      views=None, published_at="2026-06-12T09:00:00"),
            make_post("b", "tiktok", 1200, 60, 20, "Dance challenge",
                      views=50000, published_at="2026-06-10T09:00:00"),
        ]
    best = max(posts, key=lambda p: (p.views or 0)) if posts else None
    return CompetitorData(
        name=name,
        ig_followers=890000, fb_followers=1200000, tt_followers=45000,
        ig_followers_prev=888000, fb_followers_prev=1198000, tt_followers_prev=44500,
        posts=posts, best_post=best,
        content_summary="Brand promoted new menu items.",
    )


def make_report(competitors=None, log=None):
    return WeeklyReport(
        report_title="Competitor Brands — Weekly Social Report",
        week_label="8.06 – 14.06.2026",
        week_iso="2026-06-08_2026-06-14",
        competitors=competitors if competitors is not None else [make_competitor()],
        generation_log=log or [],
    )


def test_header_uses_report_title():
    md = build_report(make_report())
    assert "# Competitor Brands — Weekly Social Report" in md
    assert "## 8.06 – 14.06.2026" in md


def test_no_own_brand_sections():
    md = build_report(make_report())
    for forbidden in ["Campaigns", "Weekly Summary", "Top 3", "Meta Ads", "Highlight"]:
        assert forbidden not in md


def test_competitor_block_has_content_best_and_posts_table():
    md = build_report(make_report())
    assert "## 1. Competitors" in md
    assert "### Pizza Hut Polska" in md
    assert "**Content this period:** Brand promoted new menu items." in md
    assert "**Best post (TikTok):**" in md  # best = highest views
    assert "**All posts this period (2):**" in md
    assert "| Platform | Date | Description | Likes | Comments | Shares | Views | Link |" in md
    # newest-first within the posts table: 06-12 IG row before 06-10 TikTok row
    table = md.split("**All posts this period")[1]
    assert table.index("New pizza launch") < table.index("Dance challenge")


def test_follower_delta_rendered():
    md = build_report(make_report())
    assert "+2 000" in md  # IG: 890000-888000


def test_empty_posts_brand_renders_empty_state():
    md = build_report(make_report(competitors=[make_competitor(posts=[])]))
    assert "**All posts this period (0):**" in md
    assert "_No posts published in this period._" in md


def test_generation_report_present_when_log():
    log = [
        StepResult(name="Apify (batch)", status="ok", duration_s=2.1, items_count=4),
        StepResult(name="Summary: KFC", status="failed", duration_s=0.3, error="llm down"),
    ]
    md = build_report(make_report(log=log))
    assert "## 2. Generation report" in md
    assert "Apify (batch)" in md
    assert "llm down" in md


def test_generation_report_absent_when_no_log():
    assert "Generation report" not in build_report(make_report(log=[]))
