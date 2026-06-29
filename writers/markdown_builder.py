# writers/markdown_builder.py
from datetime import datetime

from models import CompetitorData, Post, WeeklyReport

PLATFORM_LABEL = {
    "facebook": "Facebook",
    "instagram": "Instagram",
    "tiktok": "TikTok",
}


def _fmt(n) -> str:
    """Format a number with a space thousands separator."""
    return f"{int(n):,}".replace(",", " ")


def _delta_str(d: int) -> str:
    return f"+{_fmt(d)}" if d >= 0 else f"-{_fmt(abs(d))}"


def _date_short(iso: str) -> str:
    """ISO datetime -> 'd.mm'; '—' on parse failure / empty."""
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return f"{dt.day}.{dt.month:02d}"
    except ValueError:
        return "—"


def _cell(text: str, width: int = 60) -> str:
    """Sanitize free text for a markdown table cell: no pipes/newlines, truncated."""
    text = (text or "").replace("|", "/").replace("\n", " ").replace("\r", " ").strip()
    if len(text) > width:
        text = text[:width].rstrip() + "…"
    return text or "—"


def _posts_table(posts: list[Post]) -> list[str]:
    """Render every post in the period as a stats table (sorted newest-first)."""
    lines = [f"**All posts this period ({len(posts)}):**", ""]
    if not posts:
        lines.append("_No posts published in this period._")
        return lines
    lines.append("| Platform | Date | Description | Likes | Comments | Shares | Views | Link |")
    lines.append("|----------|------|-------------|-------|----------|--------|-------|------|")
    for p in sorted(posts, key=lambda x: x.published_at or "", reverse=True):
        platform = PLATFORM_LABEL.get(p.platform, p.platform.title())
        views = _fmt(p.views) if p.views else "—"
        link = p.url or "—"
        lines.append(
            f"| {platform} | {_date_short(p.published_at)} | {_cell(p.caption)} "
            f"| {_fmt(p.likes)} | {_fmt(p.comments)} | {_fmt(p.shares)} | {views} | {link} |"
        )
    return lines


def _competitor_block(c: CompetitorData) -> str:
    lines = [f"### {c.name}"]
    lines.append(f"- **Content this period:** {c.content_summary}")
    if c.best_post:
        p = c.best_post
        platform = PLATFORM_LABEL.get(p.platform, p.platform.title())
        er_info = f"ER: {p.engagement_rate}%" if p.engagement_rate else f"Views: {_fmt(p.views or 0)}"
        lines.append(f"- **Best post ({platform}):** {_cell(p.caption, 100)} — {er_info}")
        if p.url:
            lines.append(f"  🔗 {p.url}")
        if p.image_url:
            lines.append(f"  ![post]({p.image_url})")
    lines.append("")
    lines.extend(_posts_table(c.posts))
    lines.append("")
    lines.append("**Follower changes:**")
    lines.append("")
    lines.append("| Platform | Current | Previous | Change |")
    lines.append("|----------|---------|----------|--------|")
    lines.append(f"| Facebook  | {_fmt(c.fb_followers)} | {_fmt(c.fb_followers_prev)} | {_delta_str(c.fb_follower_delta)} |")
    lines.append(f"| Instagram | {_fmt(c.ig_followers)} | {_fmt(c.ig_followers_prev)} | {_delta_str(c.ig_follower_delta)} |")
    lines.append(f"| TikTok    | {_fmt(c.tt_followers)} | {_fmt(c.tt_followers_prev)} | {_delta_str(c.tt_follower_delta)} |")
    return "\n".join(lines)


def build_report(report: WeeklyReport) -> str:
    sections = []
    title = report.report_title or "Weekly Social Report"
    sections.append(f"# {title}")
    sections.append(f"## {report.week_label}")
    sections.append("")

    sections.append("## 1. Competitors")
    sections.append("")
    if report.competitors:
        for comp in report.competitors:
            sections.append(_competitor_block(comp))
            sections.append("")
    else:
        sections.append("_No competitor data._")
        sections.append("")

    if report.generation_log:
        sections.append("## 2. Generation report")
        sections.append("")
        sections.append("| Step | Status | Duration | Items |")
        sections.append("|------|--------|----------|-------|")
        status_icon = {"ok": "✓", "failed": "✗", "skipped": "—", "partial": "⚠"}
        for s in report.generation_log:
            icon = status_icon.get(s.status, "?")
            items = s.items_count if s.status == "ok" else "—"
            sections.append(f"| {s.name} | {icon} {s.status} | {s.duration_s:.1f}s | {items} |")
        sections.append("")
        errors = [s for s in report.generation_log if s.status == "failed"]
        if errors:
            sections.append("**Errors:**")
            sections.append("")
            for s in errors:
                sections.append(f"- {s.name}: {s.error}")
            sections.append("")

    return "\n".join(sections)
