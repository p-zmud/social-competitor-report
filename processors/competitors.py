# processors/competitors.py
from typing import Optional
from models import Post


def get_best_post(posts: list[Post]) -> Optional[Post]:
    """Returns post with highest engagement rate (or views if ER = 0)."""
    if not posts:
        return None
    return max(posts, key=lambda p: p.engagement_rate or (p.views or 0))
