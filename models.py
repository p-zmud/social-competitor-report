# models.py
from dataclasses import dataclass, field
from typing import Literal, Optional

StepStatus = Literal["ok", "failed", "skipped", "partial"]


@dataclass
class StepResult:
    name: str
    status: StepStatus
    duration_s: float
    items_count: int = 0
    error: Optional[str] = None


@dataclass
class Post:
    id: str
    platform: str          # "facebook" | "instagram" | "tiktok"
    url: str
    caption: str
    published_at: str      # ISO datetime string
    likes: int
    comments: int
    shares: int
    reach: int
    views: Optional[int]
    image_url: Optional[str] = None

    @property
    def engagement_rate(self) -> float:
        # Competitor posts have no reach data from Apify, so this is 0 for them.
        if not self.reach:
            return 0.0
        return round((self.likes + self.comments + self.shares) / self.reach * 100, 2)

    @property
    def total_interactions(self) -> int:
        return self.likes + self.comments + self.shares


@dataclass
class CompetitorData:
    name: str
    ig_followers: int
    fb_followers: int
    tt_followers: int
    ig_followers_prev: int
    fb_followers_prev: int
    tt_followers_prev: int
    posts: list["Post"]
    best_post: Optional["Post"]
    content_summary: str

    @property
    def ig_follower_delta(self) -> int:
        return self.ig_followers - self.ig_followers_prev

    @property
    def fb_follower_delta(self) -> int:
        return self.fb_followers - self.fb_followers_prev

    @property
    def tt_follower_delta(self) -> int:
        return self.tt_followers - self.tt_followers_prev


@dataclass
class WeeklyReport:
    report_title: str
    week_label: str
    week_iso: str                       # = report_id, e.g. "2026-06-08_2026-06-14"
    competitors: list["CompetitorData"]
    generation_log: list["StepResult"] = field(default_factory=list)
