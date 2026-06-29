"""Parse a social-competitor weekly report (markdown) into a structured dict.

Single current format produced by writers/markdown_builder.py:

    # {report_title}
    ## {week_label}

    ## 1. Competitors
    ### {brand}
    - **Content this period:** {summary}
    - **Best post ({Platform}):** {caption} — Views: {n}    (or "ER: {x}%")
      🔗 {url}
      ![post]({image})

    **All posts this period (N):**           <- NOT parsed here; the dashboard
    | … table … |                                attaches full posts from data/*.json

    **Follower changes:**
    | Platform | Current | Previous | Change |

    ## 2. Generation report

The per-post "All posts" table is intentionally NOT parsed out of markdown — the
dashboard reads structured posts from data/{brand}.json instead, so this parser only
needs the brand name, content summary, best post and follower table.
"""
import re


def _parse_number(text: str) -> int:
    """Parse an int with space thousands separators, e.g. '163 097 371' -> 163097371."""
    cleaned = text.strip().replace(" ", "").replace(" ", "")
    if not cleaned or cleaned == "—":
        return 0
    cleaned = cleaned.lstrip("+")
    try:
        return int(cleaned)
    except ValueError:
        return 0


def _extract_section(md: str, section_num: int) -> str:
    """Return the body of '## N. …' up to the next '## M. …' (or end of doc)."""
    m = re.search(rf"^## {section_num}\.\s[^\n]*\n", md, re.MULTILINE)
    if not m:
        return ""
    start = m.end()
    nxt = re.search(r"^## \d+\.\s", md[start:], re.MULTILINE)
    return md[start:start + nxt.start()].strip() if nxt else md[start:].strip()


def parse_report_content(md_text: str, report_id: str | None = None) -> dict:
    """Parse markdown report into a dict: report_title, week_label, week_iso,
    report_id, competitors[{name, content_summary, best_post, followers}]."""
    result = {
        "report_title": "",
        "week_label": "",
        "week_iso": "",
        "report_id": report_id or "",
        "competitors": [],
    }

    # Title = first H1 ("# …", single hash).
    title_m = re.search(r"^#\s+(.+)$", md_text, re.MULTILINE)
    if title_m:
        result["report_title"] = title_m.group(1).strip()

    # Week label = the "## d.mm – d.mm.yyyy" date header.
    label_m = re.search(
        r"^##\s+(\d{1,2}\.\d{1,2}\s*[–-]\s*\d{1,2}\.\d{1,2}\.\d{4})\s*$",
        md_text, re.MULTILINE,
    )
    if label_m:
        result["week_label"] = label_m.group(1).strip()

    # Competitors = section 1.
    sec = _extract_section(md_text, 1)
    if sec:
        for block in re.split(r"(?=^### )", sec, flags=re.MULTILINE):
            block = block.strip()
            if not block.startswith("###"):
                continue
            name_m = re.match(r"###\s+(.+)", block)
            if not name_m:
                continue
            name = name_m.group(1).strip()

            content_m = re.search(
                r"\*\*Content this period:\*\*\s*(.+?)(?=\n- \*\*|\n\*\*All posts|\n\*\*Follower|\Z)",
                block, re.DOTALL,
            )
            content_summary = " ".join(content_m.group(1).split()).strip() if content_m else ""

            best_post = None
            best_m = re.search(
                r"\*\*Best post \((\w+)\):\*\*\s*(.+?)\s*—\s*(?:Views:\s*([\d\s]+)|ER:\s*[\d.,]+%)",
                block, re.DOTALL,
            )
            if best_m:
                bp_url_m = re.search(r"Best post.*?🔗\s*(https?://\S+)", block, re.DOTALL)
                bp_img_m = re.search(r"Best post.*?!\[[^\]]*\]\(([^)\s]+)\)", block, re.DOTALL)
                best_post = {
                    "platform": best_m.group(1).strip(),
                    "caption": " ".join(best_m.group(2).split()).strip(),
                    "views": _parse_number(best_m.group(3)) if best_m.group(3) else 0,
                    "url": bp_url_m.group(1).strip() if bp_url_m else "",
                    "image_url": bp_img_m.group(1).strip() if bp_img_m else "",
                }

            # Followers: scope to the region after "**Follower changes:**" so the
            # 8-column all-posts table (which also has Platform rows) can't match.
            fc_idx = block.find("**Follower changes:**")
            region = block[fc_idx:] if fc_idx != -1 else ""
            followers = {}
            for fm in re.finditer(
                r"\|\s*(Facebook|Instagram|TikTok)\s*\|\s*([\d\s]+)\s*\|\s*([\d\s]+)\s*\|\s*([+\-]?[\d\s]+)\s*\|",
                region,
            ):
                followers[fm.group(1).strip().lower()] = {
                    "current": _parse_number(fm.group(2)),
                    "previous": _parse_number(fm.group(3)),
                    "delta": _parse_number(fm.group(4)),
                }

            result["competitors"].append({
                "name": name,
                "content_summary": content_summary,
                "best_post": best_post,
                "followers": followers,
            })

    return result
