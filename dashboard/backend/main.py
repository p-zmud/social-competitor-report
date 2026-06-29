"""FastAPI backend for the Social Competitor Report dashboard."""

import asyncio
import json
import logging
import os
import re
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

_log = logging.getLogger("app.dashboard")

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from pydantic import BaseModel

from report_parser import parse_report_content

# Add project root to sys.path for generate_report / utils imports.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from generate_report import run_pipeline
from utils.progress import ProgressReporter
from utils.settings import CURATED_MODELS, save_settings, settings_status
from utils.profiles import (
    ProfilesError, effective_competitors, is_override_active,
    reset_profiles, save_profiles,
)

# Load .env from project root so credential resolution works under any launcher.
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# Patchable in tests.
REPORTS_DIR = os.path.join(PROJECT_ROOT, "reports")

app = FastAPI(title="Social Competitor Report Dashboard")

# Local-only CORS: the dashboard frontend runs on localhost:5003 in dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5003",
        "http://127.0.0.1:5003",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Legacy week-ISO id (kept only so old filenames don't break the validator).
WEEK_ISO_RE = re.compile(r"(\d{4}-W\d{2})")
# Folder-per-report id: 2026-06-08_2026-06-14
DATE_RANGE_RE = re.compile(r"(\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2})")

_REPORT_ID_RE = re.compile(
    r"^(?:\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2}|\d{4}-W\d{2}(?:-[a-z0-9-]+)?)$"
)



def _validate_report_id(report_id: str) -> str:
    if not _REPORT_ID_RE.match(report_id):
        raise HTTPException(status_code=400, detail="Invalid report_id")
    return report_id


def _extract_report_id(filename: str) -> str | None:
    m = DATE_RANGE_RE.search(filename)
    if m:
        return m.group(1)
    m = WEEK_ISO_RE.search(filename)
    if m:
        return m.group(1)
    return None


def _find_report_file(report_id: str) -> Path | None:
    reports_path = Path(REPORTS_DIR)
    if not reports_path.is_dir():
        return None
    folder = reports_path / report_id / "report.md"
    if folder.is_file():
        return folder
    for f in reports_path.iterdir():
        if f.suffix == ".md" and report_id in f.name:
            return f
    return None


def _has_failures(report_id: str) -> bool:
    log_path = os.path.join(REPORTS_DIR, report_id, "data", "generation_log.json")
    if not os.path.isfile(log_path):
        return False
    try:
        with open(log_path) as f:
            log = json.load(f)
        return any(s.get("status") == "failed" for s in log)
    except (OSError, ValueError):
        return False


def _brand_order_tokens() -> list[str]:
    """Lowercased brand names in configured order — the single ordering source."""
    return [str(c.get("name", "")).lower() for c in effective_competitors()]


def _brand_rank(name: str, tokens: list[str]) -> int:
    lower = name.lower()
    for i, token in enumerate(tokens):
        if token and (token == lower or token in lower or lower in token):
            return i
    return len(tokens)


@app.get("/api/reports")
def list_reports():
    """List available reports (folder-per-report and legacy flat files)."""
    reports_path = Path(REPORTS_DIR)
    if not reports_path.is_dir():
        return []

    results = []
    seen_ids = set()

    for d in reports_path.iterdir():
        if not d.is_dir():
            continue
        report_md = d / "report.md"
        if not report_md.is_file():
            continue
        report_id = d.name
        seen_ids.add(report_id)
        parsed = parse_report_content(report_md.read_text(encoding="utf-8"), report_id=report_id)
        st = report_md.stat()
        results.append({
            "report_id": report_id,
            "week_iso": parsed.get("week_iso", ""),
            "week_label": parsed.get("week_label", ""),
            "has_data": len(parsed.get("competitors", [])) > 0,
            "size_kb": round(st.st_size / 1024, 1),
            "has_failures": _has_failures(report_id),
            "_mtime": st.st_mtime,
        })

    for f in reports_path.iterdir():
        if f.suffix != ".md":
            continue
        report_id = _extract_report_id(f.name)
        if not report_id or report_id in seen_ids:
            continue
        parsed = parse_report_content(f.read_text(encoding="utf-8"), report_id=report_id)
        st = f.stat()
        results.append({
            "report_id": report_id,
            "week_iso": parsed.get("week_iso", ""),
            "week_label": parsed.get("week_label", ""),
            "has_data": len(parsed.get("competitors", [])) > 0,
            "size_kb": round(st.st_size / 1024, 1),
            "has_failures": False,
            "_mtime": st.st_mtime,
        })

    results.sort(key=lambda r: r["_mtime"], reverse=True)
    for r in results:
        del r["_mtime"]
    return results


@app.get("/api/reports/{report_id}/log")
def get_generation_log(report_id: str):
    _validate_report_id(report_id)
    log_path = os.path.join(REPORTS_DIR, report_id, "data", "generation_log.json")
    if not os.path.isfile(log_path):
        raise HTTPException(404, f"No generation log for {report_id}")
    with open(log_path, encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/reports/{report_id}")
def get_report(report_id: str):
    _validate_report_id(report_id)
    f = _find_report_file(report_id)
    if not f:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    parsed = parse_report_content(f.read_text(encoding="utf-8"), report_id=report_id)
    _enrich_with_images(parsed, report_id)
    _attach_posts(parsed, report_id)
    _tokens = _brand_order_tokens()
    parsed["competitors"].sort(
        key=lambda c: (_brand_rank(c.get("name", ""), _tokens), c.get("name", "").lower())
    )
    return parsed


def _attach_posts(parsed: dict, report_id: str) -> None:
    """Attach each competitor's full post list (newest-first) from data/{brand}.json."""
    data_dir = Path(REPORTS_DIR) / report_id / "data"
    if not data_dir.is_dir():
        for comp in parsed.get("competitors", []):
            comp["posts"] = []
        return
    posts_by_name: dict[str, list] = {}
    for f in data_dir.iterdir():
        if f.suffix != ".json" or f.name in ("image_index.json", "generation_log.json"):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict) or not data.get("name"):
            continue
        posts = data.get("ig_posts", []) + data.get("fb_posts", []) + data.get("tt_posts", [])
        posts.sort(key=lambda p: p.get("published_at") or "", reverse=True)
        posts_by_name[data["name"]] = posts
    for comp in parsed.get("competitors", []):
        comp["posts"] = posts_by_name.get(comp.get("name", ""), [])


def _enrich_with_images(parsed: dict, report_id: str):
    """Resolve competitor best-post image_url to something the frontend can render."""
    report_dir = Path(REPORTS_DIR) / report_id
    data_dir = report_dir / "data"
    api_prefix = f"/api/reports/{report_id}/images/"

    def _local_to_api(path: str) -> str:
        if not path:
            return path
        if path.startswith(("http://", "https://", "/api/")):
            return path
        if path.startswith("images/"):
            return api_prefix + path.split("/", 1)[1]
        return path

    url_to_local: dict[str, str] = {}
    index_path = data_dir / "image_index.json"
    if index_path.is_file():
        try:
            url_to_local = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            _log.warning("Corrupt image_index.json: %s", index_path)

    url_to_cdn_image: dict[str, str] = {}
    if data_dir.is_dir():
        for f in data_dir.iterdir():
            if f.suffix != ".json" or f.name == "image_index.json":
                continue
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if not isinstance(data, dict):
                continue
            for key in ("ig_posts", "fb_posts", "tt_posts"):
                for post in data.get(key, []):
                    url = post.get("url", "")
                    img = post.get("image_url", "")
                    if url and img:
                        url_to_cdn_image[url] = img

    def _resolve(post: dict):
        img = post.get("image_url", "")
        if img:
            post["image_url"] = _local_to_api(img)
            if post["image_url"]:
                return
        url = post.get("url", "")
        if url and url in url_to_local:
            post["image_url"] = _local_to_api(url_to_local[url])
            return
        if url and url in url_to_cdn_image:
            post["image_url"] = _local_to_api(url_to_cdn_image[url])

    for comp in parsed.get("competitors", []):
        bp = comp.get("best_post")
        if bp:
            _resolve(bp)


@app.get("/api/reports/{report_id}/images/{filename}")
def get_report_image(report_id: str, filename: str):
    _validate_report_id(report_id)
    safe = Path(filename).name
    if not safe or safe.startswith("."):
        raise HTTPException(400, "Invalid filename")
    fp = Path(REPORTS_DIR) / report_id / "images" / safe
    if not fp.is_file():
        raise HTTPException(404, "Image not found")
    return FileResponse(fp)


@app.get("/api/reports/{report_id}/data")
def get_report_data(report_id: str):
    _validate_report_id(report_id)
    data_dir = Path(REPORTS_DIR) / report_id / "data"
    if not data_dir.is_dir():
        return []
    result = []
    for f in sorted(data_dir.iterdir()):
        if f.suffix != ".json":
            continue
        try:
            result.append(json.loads(f.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            _log.warning("Skipping corrupted JSON: %s", f)
            continue
    return result


def _previous_report_followers(report_id: str) -> dict[str, dict[str, int]]:
    reports_path = Path(REPORTS_DIR)
    if not reports_path.is_dir():
        return {}
    candidates = sorted(
        d.name for d in reports_path.iterdir()
        if d.is_dir() and d.name < report_id and (d / "data").is_dir()
    )
    if not candidates:
        return {}
    prev_id = candidates[-1]
    out: dict[str, dict[str, int]] = {}
    for f in (reports_path / prev_id / "data").iterdir():
        if f.suffix != ".json" or f.name in ("image_index.json", "generation_log.json"):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict) or not data.get("name"):
            continue
        out[data["name"]] = {
            "fb": data.get("fb_followers", 0),
            "ig": data.get("ig_followers", 0),
            "tt": data.get("tt_followers", 0),
        }
    return out


@app.get("/api/reports/{report_id}/followers")
def get_followers_summary(report_id: str):
    _validate_report_id(report_id)
    data_dir = Path(REPORTS_DIR) / report_id / "data"
    if not data_dir.is_dir():
        return []
    fallback_prev = _previous_report_followers(report_id)
    result = []
    for f in sorted(data_dir.iterdir()):
        if f.suffix != ".json" or f.name in ("image_index.json", "generation_log.json"):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            _log.warning("Skipping corrupted JSON: %s", f)
            continue
        if not isinstance(data, dict) or not data.get("name"):
            continue
        name = data["name"]
        fb = data.get("fb_followers", 0)
        ig = data.get("ig_followers", 0)
        tt = data.get("tt_followers", 0)
        fb_prev = data.get("fb_followers_prev", 0)
        ig_prev = data.get("ig_followers_prev", 0)
        tt_prev = data.get("tt_followers_prev", 0)
        fb_fb = fallback_prev.get(name, {})
        if not fb_prev:
            fb_prev = fb_fb.get("fb", 0)
        if not ig_prev:
            ig_prev = fb_fb.get("ig", 0)
        if not tt_prev:
            tt_prev = fb_fb.get("tt", 0)
        result.append({
            "name": name,
            "facebook": fb,
            "instagram": ig,
            "tiktok": tt,
            "facebook_delta": (fb - fb_prev) if fb_prev else None,
            "instagram_delta": (ig - ig_prev) if ig_prev else None,
            "tiktok_delta": (tt - tt_prev) if tt_prev else None,
        })
    _tokens = _brand_order_tokens()
    result.sort(key=lambda r: (_brand_rank(r["name"], _tokens), r["name"].lower()))
    return result


@app.get("/api/reports/{report_id}/export/markdown")
def export_markdown(report_id: str):
    _validate_report_id(report_id)
    f = _find_report_file(report_id)
    if not f:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    return PlainTextResponse(content=f.read_text(encoding="utf-8"), media_type="text/markdown")


@app.get("/api/reports/{report_id}/export/html")
def export_html(report_id: str):
    _validate_report_id(report_id)
    f = _find_report_file(report_id)
    if not f:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    parsed = parse_report_content(f.read_text(encoding="utf-8"), report_id=report_id)
    _resolve_export_images(parsed, report_id)
    _attach_posts(parsed, report_id)
    return HTMLResponse(content=_render_html(parsed), media_type="text/html")


def _resolve_export_images(parsed: dict, report_id: str) -> None:
    """Rewrite best-post image_url to original platform CDN URLs (local paths are
    useless outside this machine). Unresolvable local paths are blanked."""
    index_path = Path(REPORTS_DIR) / report_id / "data" / "image_index.json"
    local_to_remote: dict[str, str] = {}
    if index_path.exists():
        try:
            index = json.loads(index_path.read_text(encoding="utf-8"))
            if isinstance(index, dict):
                local_to_remote = {local: remote for remote, local in index.items()
                                   if isinstance(local, str)}
        except (json.JSONDecodeError, OSError):
            pass

    def _resolve(post: dict) -> None:
        img = post.get("image_url", "")
        if not img or img.startswith(("http://", "https://")):
            return
        post["image_url"] = local_to_remote.get(img, "")

    for comp in parsed.get("competitors", []):
        if comp.get("best_post"):
            _resolve(comp["best_post"])


def _esc(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _fmt_int(n) -> str:
    try:
        return f"{int(n):,}".replace(",", " ")
    except (TypeError, ValueError):
        return "0"


def _fmt_post_date(iso: str) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return f"{dt.day}.{dt.month:02d}"
    except ValueError:
        return "—"


def _render_html(data: dict) -> str:
    parts = []
    has_images = False

    def _img_tag(src: str, max_width: int = 200) -> str:
        nonlocal has_images
        if not src or not src.startswith(("http://", "https://")):
            return ""
        has_images = True
        return (f'<img src="{_esc(src)}" alt="post" '
                f'style="max-width: {max_width}px; border-radius: 4px;">')

    parts.append('<div style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; '
                 'max-width: 860px; margin: 0 auto; padding: 20px; color: #222;">')
    title = data.get("report_title") or "Weekly Social Report"
    parts.append(f'<h1 style="color:#111; border-bottom:2px solid #e11d48; '
                 f'padding-bottom:8px;">{_esc(title)}</h1>')
    parts.append(f'<p style="font-size:16px;color:#666;">Week: '
                 f'<strong>{_esc(data.get("week_label", ""))}</strong></p>')

    th = ('style="border:1px solid #ddd; padding:6px 10px; background:#e11d48; '
          'color:white; text-align:left; font-size:13px;"')
    td = 'style="border:1px solid #ddd; padding:6px 10px; font-size:13px;"'

    for comp in data.get("competitors", []):
        parts.append(f'<h2 style="color:#111;margin-top:28px;">{_esc(comp["name"])}</h2>')
        if comp.get("content_summary"):
            parts.append(f'<p style="line-height:1.6;">{_esc(comp["content_summary"])}</p>')

        best = comp.get("best_post")
        if best:
            caption = best.get("caption", "")
            cap = caption[:120] + "…" if len(caption) > 120 else caption
            views_part = f" — Views: {_fmt_int(best['views'])}" if best.get("views") else ""
            parts.append(f'<p style="margin-bottom:4px;"><strong>Best post '
                         f'({_esc(best.get("platform", ""))}):</strong> '
                         f'{_esc(cap)}{views_part}</p>')
            tag = _img_tag(best.get("image_url", ""))
            if tag:
                parts.append(f'<p style="margin:4px 0;">{tag}</p>')
            if best.get("url"):
                parts.append(f'<p style="margin-top:4px;"><a href="{_esc(best["url"])}">'
                             f'{_esc(best["url"])}</a></p>')

        posts = comp.get("posts", [])
        if posts:
            parts.append(f'<p style="margin-top:14px;font-weight:bold;">'
                         f'All posts this period ({len(posts)})</p>')
            parts.append('<table style="border-collapse:collapse;width:100%;margin-top:6px;">')
            parts.append("<thead><tr>")
            for h in ["Platform", "Date", "Description", "Likes", "Comments", "Shares", "Views", "Link"]:
                parts.append(f"<th {th}>{h}</th>")
            parts.append("</tr></thead><tbody>")
            for p in posts:
                cap = (p.get("caption") or "")[:80]
                url = p.get("url") or ""
                link = f'<a href="{_esc(url)}">link</a>' if url else "—"
                views = _fmt_int(p["views"]) if p.get("views") else "—"
                parts.append("<tr>")
                parts.append(f'<td {td}>{_esc((p.get("platform") or "").title())}</td>')
                parts.append(f'<td {td}>{_fmt_post_date(p.get("published_at", ""))}</td>')
                parts.append(f'<td {td}>{_esc(cap)}</td>')
                parts.append(f'<td {td}>{_fmt_int(p.get("likes", 0))}</td>')
                parts.append(f'<td {td}>{_fmt_int(p.get("comments", 0))}</td>')
                parts.append(f'<td {td}>{_fmt_int(p.get("shares", 0))}</td>')
                parts.append(f'<td {td}>{views}</td>')
                parts.append(f'<td {td}>{link}</td>')
                parts.append("</tr>")
            parts.append("</tbody></table>")

        followers = comp.get("followers", {})
        if followers:
            parts.append('<table style="border-collapse:collapse;width:100%;margin-top:8px;">')
            parts.append("<thead><tr>")
            for h in ["Platform", "Current", "Previous", "Change"]:
                parts.append(f"<th {th}>{h}</th>")
            parts.append("</tr></thead><tbody>")
            for platform, fdata in followers.items():
                delta = fdata.get("delta", 0)
                sign = "+" if delta > 0 else ""
                parts.append("<tr>")
                parts.append(f'<td {td}>{_esc(platform.title())}</td>')
                parts.append(f'<td {td}>{_fmt_int(fdata.get("current", 0))}</td>')
                parts.append(f'<td {td}>{_fmt_int(fdata.get("previous", 0))}</td>')
                parts.append(f'<td {td}>{sign}{_fmt_int(delta)}</td>')
                parts.append("</tr>")
            parts.append("</tbody></table>")

    if has_images:
        parts.append('<p style="margin-top:24px;font-size:12px;color:#999;">'
                     "Note: post images use platform CDN links that expire after a few "
                     "weeks — paste this report soon after generation.</p>")

    parts.append("</div>")
    return "\n".join(parts)


# --- Settings ---

class SettingsRequest(BaseModel):
    openrouter_api_key: Optional[str] = None
    apify_token: Optional[str] = None
    model: Optional[str] = None
    summary_prompt: Optional[str] = None


@app.get("/api/settings")
def get_settings():
    """Non-secret view of current settings + curated model list."""
    return settings_status()


@app.post("/api/settings")
def update_settings(req: SettingsRequest):
    """Persist provided (non-empty) settings fields. Never echoes raw secrets back."""
    save_settings(req.model_dump(exclude_none=True))
    return settings_status()


# --- Profiles ---

class ProfilesRequest(BaseModel):
    profiles: list[dict]


@app.get("/api/profiles")
def get_profiles():
    """Effective tracked profiles (override or config.yaml defaults)."""
    return {"profiles": effective_competitors(), "is_override": is_override_active()}


@app.put("/api/profiles")
def put_profiles(req: ProfilesRequest):
    """Persist a profiles override. 400 on validation failure."""
    try:
        saved = save_profiles(req.profiles)
    except ProfilesError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"profiles": saved, "is_override": True}


@app.delete("/api/profiles")
def delete_profiles():
    """Remove the override; revert to config.yaml defaults."""
    return {"profiles": reset_profiles(), "is_override": False}


# --- Report generation ---

_generate_state = {"running": False, "reporter": None, "thread": None}
_generate_lock = threading.Lock()


class GenerateRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    week: Optional[str] = None
    no_llm: bool = False
    skip_apify: bool = False


def _run_in_thread(week, no_llm, skip_apify, reporter, start_date=None, end_date=None):
    try:
        run_pipeline(week_iso=week, no_llm=no_llm, skip_apify=skip_apify,
                     reporter=reporter, start_date=start_date, end_date=end_date)
    except Exception as exc:
        reporter.set_error(str(exc))
    finally:
        with _generate_lock:
            _generate_state["running"] = False


@app.post("/api/reports/generate")
def generate_report(req: GenerateRequest):
    from utils.validation import ConfigError, validate_environment
    try:
        validate_environment(no_llm=req.no_llm, skip_apify=req.skip_apify, strict=True)
    except ConfigError as e:
        raise HTTPException(400, str(e))

    reporter = ProgressReporter()
    with _generate_lock:
        if _generate_state["running"]:
            return {"status": "already_running"}
        _generate_state["running"] = True
        _generate_state["reporter"] = reporter

    thread = threading.Thread(
        target=_run_in_thread,
        args=(req.week, req.no_llm, req.skip_apify, reporter),
        kwargs={"start_date": req.start_date, "end_date": req.end_date},
        daemon=True,
    )
    _generate_state["thread"] = thread
    thread.start()
    return {"status": "started"}


@app.websocket("/ws/generate")
async def ws_generate(ws: WebSocket):
    await ws.accept()
    idle_ticks = 0
    try:
        while True:
            reporter = _generate_state.get("reporter")
            if reporter is None:
                idle_ticks += 1
                if idle_ticks >= 10:
                    await ws.send_json({"finished": True, "error": "no_active_generation"})
                    break
                await asyncio.sleep(0.5)
                continue
            idle_ticks = 0
            snap = reporter.snapshot()
            await ws.send_json(snap)
            if snap["finished"] or snap["error"]:
                break
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
    finally:
        try:
            await ws.close()
        except RuntimeError:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
