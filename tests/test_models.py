# tests/test_models.py
import pytest

from models import CompetitorData, Post, WeeklyReport


def _post(**kw):
    base = dict(
        id="123", platform="instagram", url="https://instagram.com/p/123",
        caption="Test post", published_at="2026-02-10T12:00:00",
        likes=100, comments=10, shares=5, reach=2000, views=None,
    )
    base.update(kw)
    return Post(**base)


def test_post_engagement_rate():
    assert _post().engagement_rate == pytest.approx(5.75, rel=0.01)  # (100+10+5)/2000*100


def test_post_engagement_rate_no_reach():
    assert _post(reach=0).engagement_rate == 0.0


def test_post_total_interactions():
    assert _post(likes=10, comments=2, shares=3).total_interactions == 15


def test_competitor_data_deltas():
    c = CompetitorData(
        name="Pizza Hut Polska",
        ig_followers=100000,
        fb_followers=500000,
        tt_followers=50000,
        ig_followers_prev=99000,
        fb_followers_prev=499000,
        tt_followers_prev=49500,
        posts=[],
        best_post=None,
        content_summary="",
    )
    assert c.ig_follower_delta == 1000
    assert c.fb_follower_delta == 1000
    assert c.tt_follower_delta == 500


def test_weekly_report_minimal():
    report = WeeklyReport(
        report_title="Competitor Brands — Weekly Social Report",
        week_label="8.06 – 14.06.2026",
        week_iso="2026-06-08_2026-06-14",
        competitors=[],
    )
    assert report.generation_log == []
    assert report.report_title.startswith("Competitor Brands")
