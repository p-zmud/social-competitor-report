# utils/image_downloader.py
"""Download remote post images (covers, post pictures) to a per-report folder
so the report markdown can reference local files at full resolution.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Iterable
from urllib.parse import urlparse

import requests

from app_logging import get_logger

_log = get_logger("image_downloader")

# Extensions we recognise; default to .jpg when unknown.
_EXT_BY_CONTENT_TYPE = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _guess_ext(url: str, content_type: str | None) -> str:
    if content_type:
        base = content_type.split(";", 1)[0].strip().lower()
        if base in _EXT_BY_CONTENT_TYPE:
            return _EXT_BY_CONTENT_TYPE[base]
    path = urlparse(url).path.lower()
    for ext in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return ".jpg"


def _safe_filename(platform: str, url: str, ext: str) -> str:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    plat = (platform or "img").lower().replace(" ", "")[:10]
    return f"{plat}_{digest}{ext}"


def _is_remote(url: str) -> bool:
    return bool(url) and url.startswith(("http://", "https://"))


def _is_safe_rel(rel: str, base: str) -> bool:
    """True if `rel` is a relative path that stays inside `base` (no traversal).

    `image_index.json` is written by this module, but harden the read path so a
    corrupted/tampered index can never point image_url at a file outside the report.
    """
    if not rel or os.path.isabs(rel) or ".." in rel.replace("\\", "/").split("/"):
        return False
    base_norm = os.path.normpath(base)
    full = os.path.normpath(os.path.join(base_norm, rel))
    return full == base_norm or full.startswith(base_norm + os.sep)


def download_post_images(posts: Iterable, images_dir: str,
                          *, timeout: float = 20.0) -> dict[str, str]:
    """Download remote image_url for each post into images_dir.

    Mutates each post: replaces remote `image_url` with a relative path
    (e.g. "images/instagram_abc123.jpg") that resolves from the report.md.

    Returns a {remote_url: relative_path} index so callers can persist it.
    Posts without a remote image_url are skipped silently.
    """
    os.makedirs(images_dir, exist_ok=True)
    index_path = os.path.join(images_dir, "..", "data", "image_index.json")
    # Load existing index if present so we can append across re-runs.
    existing: dict[str, str] = {}
    if os.path.isfile(index_path):
        try:
            with open(index_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (OSError, json.JSONDecodeError):
            existing = {}

    index: dict[str, str] = dict(existing)

    for post in posts:
        url = getattr(post, "image_url", None) or ""
        if not _is_remote(url):
            continue
        # Already downloaded in a previous run?
        if url in index:
            rel = index[url]
            base = os.path.dirname(images_dir)
            if _is_safe_rel(rel, base):
                local_path = os.path.join(base, rel)
                if os.path.isfile(local_path):
                    post.image_url = rel
                    continue
            # Unsafe path or missing file — fall through and re-download.

        try:
            resp = requests.get(url, timeout=timeout, stream=True)
            resp.raise_for_status()
        except requests.RequestException as e:
            _log.warning("Image download failed (%s): %s", url[:80], e)
            continue

        ext = _guess_ext(url, resp.headers.get("Content-Type"))
        filename = _safe_filename(getattr(post, "platform", "img"), url, ext)
        out_path = os.path.join(images_dir, filename)
        try:
            with open(out_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        f.write(chunk)
        except OSError as e:
            _log.warning("Image write failed (%s): %s", out_path, e)
            continue

        rel = f"images/{filename}"
        index[url] = rel
        post.image_url = rel
        _log.info("Image saved: %s (%s)", rel, getattr(post, "platform", "?"))

    # Persist index next to the rest of the per-report data.
    try:
        os.makedirs(os.path.dirname(index_path), exist_ok=True)
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False, indent=2)
    except OSError as e:
        _log.warning("Failed to write image_index.json: %s", e)

    return index
