# tests/test_competitors.py
from models import Post
from processors.competitors import get_best_post


def make_post(id, er_likes, er_reach):
    return Post(id=id, platform="instagram", url="", caption="test",
                published_at="", likes=er_likes, comments=0, shares=0,
                reach=er_reach, views=None)


def test_get_best_post_returns_highest_er():
    posts = [
        make_post("1", 100, 2000),   # ER 5%
        make_post("2", 500, 5000),   # ER 10%
        make_post("3", 50, 1000),    # ER 5%
    ]
    best = get_best_post(posts)
    assert best.id == "2"


def test_get_best_post_empty():
    assert get_best_post([]) is None


def test_get_best_post_single():
    posts = [make_post("1", 100, 1000)]
    assert get_best_post(posts).id == "1"
