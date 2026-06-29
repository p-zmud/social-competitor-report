# collectors/apify.py
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from apify_client import ApifyClient

from app_logging import get_logger
from models import Post

_log = get_logger("apify")

WARSAW = ZoneInfo("Europe/Warsaw")


class ApifyCollector:
    def __init__(self, api_token: str):
        self.client = ApifyClient(api_token)

    def _get_dataset_items(self, run: dict) -> list[dict]:
        """Extract items from actor run result (apify-client 2.x returns dict)."""
        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            return []
        return list(self.client.dataset(dataset_id).iterate_items())

    def _parse_ig_item(self, item: dict, owner_username: str = "") -> Post:
        return Post(
            id=str(item.get("id", "")),
            platform="instagram",
            url=item.get("url", ""),
            caption=item.get("caption", ""),
            published_at=item.get("timestamp", ""),
            likes=int(item.get("likesCount") or 0),
            comments=int(item.get("commentsCount") or 0),
            shares=0,
            reach=0,
            views=int(item.get("videoViewCount") or 0) if item.get("type") == "Video" else None,
            image_url=item.get("displayUrl", ""),
        )

    def _parse_tt_item(self, item: dict) -> Post:
        # Cover image: try dynamicCover, covers.default, or videoMeta.coverUrl
        cover = item.get("dynamicCover") or ""
        if not cover:
            covers = item.get("covers", {})
            cover = covers.get("default", covers.get("dynamic", "")) if isinstance(covers, dict) else ""
        if not cover:
            cover = (item.get("videoMeta") or {}).get("coverUrl", "")
        return Post(
            id=str(item.get("id", "")),
            platform="tiktok",
            url=item.get("webVideoUrl", ""),
            caption=item.get("text", ""),
            published_at=item.get("createTimeISO", ""),
            likes=int(item.get("diggCount") or 0),
            comments=int(item.get("commentCount") or 0),
            shares=int(item.get("shareCount") or 0),
            reach=0,
            views=int(item.get("playCount") or 0),
            image_url=cover,
        )

    def _parse_fb_item(self, item: dict) -> Post:
        # Shape from apify/facebook-posts-scraper.
        views = item.get("viewsCount")
        return Post(
            id=str(item.get("postId", item.get("id", ""))),
            platform="facebook",
            url=item.get("url", item.get("topLevelUrl", "")),
            caption=item.get("text", item.get("message", "")),
            published_at=item.get("time", ""),
            likes=int(item.get("likes") or 0),
            comments=int(item.get("comments") or 0),
            shares=int(item.get("shares") or 0),
            reach=0,
            views=int(views) if views else None,
            image_url=self._fb_image(item),
        )

    @staticmethod
    def _fb_image(item: dict) -> str:
        """Best-effort cover image from a Facebook post item's media."""
        media = item.get("media")
        if isinstance(media, list):
            for m in media:
                if not isinstance(m, dict):
                    continue
                for key in ("thumbnail", "image", "photo_image", "full_picture", "url"):
                    v = m.get(key)
                    if isinstance(v, str) and v.startswith("http"):
                        return v
                    if isinstance(v, dict):
                        uri = v.get("uri") or v.get("url") or v.get("src")
                        if isinstance(uri, str) and uri.startswith("http"):
                            return uri
        for key in ("image", "fullPicture", "thumbnailUrl"):
            v = item.get(key)
            if isinstance(v, str) and v.startswith("http"):
                return v
        return ""

    def _filter_by_date(self, posts: list[Post], init_date: str, end_date: str) -> list[Post]:
        try:
            start = datetime.combine(date.fromisoformat(init_date), time.min, tzinfo=WARSAW)
            end = datetime.combine(date.fromisoformat(end_date), time.max, tzinfo=WARSAW)
        except ValueError:
            return posts
        result = []
        for p in posts:
            try:
                ts = p.published_at.replace("Z", "+00:00")
                dt = datetime.fromisoformat(ts)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=WARSAW)
                if start <= dt <= end:
                    result.append(p)
            except (ValueError, AttributeError):
                continue
        if posts and not result:
            _log.warning(
                "Filter dropped all %d items — possible date-format issue", len(posts)
            )
        return result

    def get_instagram_followers(self, username: str) -> int:
        """Returns follower count using lightweight followers-count scraper."""
        try:
            run = self.client.actor("apify/instagram-followers-count-scraper").call(run_input={
                "usernames": [username],
            })
            items = self._get_dataset_items(run)
            for item in items:
                if item.get("followersCount"):
                    return int(item["followersCount"])
            return 0
        except Exception as e:
            _log.error("Instagram followers error for %s: %s", username, e)
            return 0

    def get_tiktok_data(self, handle: str, init_date: str, end_date: str) -> tuple[int, list[Post]]:
        try:
            run = self.client.actor("clockworks/tiktok-scraper").call(run_input={
                "profiles": [handle],
                "resultsPerPage": 30,
            })
            items = self._get_dataset_items(run)
            followers = 0
            posts = []
            for item in items:
                if item.get("id"):
                    # Extract followers from authorMeta of first post
                    if not followers:
                        author = item.get("authorMeta", {})
                        followers = int(author.get("fans") or 0)
                    posts.append(self._parse_tt_item(item))
            posts = self._filter_by_date(posts, init_date, end_date)
            return followers, posts
        except Exception as e:
            _log.error("TikTok error for %s: %s", handle, e)
            return 0, []

    # --- Batch + Parallel ---

    def _batch_instagram(self, handles: list[str], init_date: str, end_date: str
                         ) -> dict[str, tuple[int, list[Post]]]:
        """Batch IG profiles + posts for all handles via profile-scraper."""
        result: dict[str, tuple[int, list[Post]]] = {h: (0, []) for h in handles}
        try:
            run = self.client.actor("apify/instagram-profile-scraper").call(
                run_input={"usernames": handles},
                timeout_secs=300,
                memory_mbytes=512,
            )
            for item in self._get_dataset_items(run):
                uname = (item.get("username") or "").lower()
                if uname not in result:
                    continue
                followers = int(item.get("followersCount") or 0)
                posts = []
                for p in item.get("latestPosts", []):
                    posts.append(self._parse_ig_item(p, uname))
                filtered = self._filter_by_date(posts, init_date, end_date)
                result[uname] = (followers, filtered)
        except Exception as e:
            _log.error("Batch IG error: %s", e)
        return result

    def _batch_tiktok(self, handles: list[str], init_date: str, end_date: str
                      ) -> dict[str, tuple[int, list[Post]]]:
        """Batch TikTok data for all handles in one actor run."""
        result = {h: (0, []) for h in handles}
        try:
            run = self.client.actor("clockworks/tiktok-scraper").call(
                run_input={"profiles": handles, "resultsPerPage": 30},
                timeout_secs=300,
                memory_mbytes=512,
            )
            posts_by_handle: dict[str, list[Post]] = {h: [] for h in handles}
            followers_by_handle: dict[str, int] = {h: 0 for h in handles}
            for item in self._get_dataset_items(run):
                if not item.get("id"):
                    continue
                author = item.get("authorMeta", {})
                uid = (author.get("uniqueId") or author.get("name") or author.get("nickName") or "").lower()
                if uid not in posts_by_handle:
                    continue
                fans = int(author.get("fans") or 0)
                if fans > 0 and followers_by_handle.get(uid, 0) == 0:
                    followers_by_handle[uid] = fans
                posts_by_handle[uid].append(self._parse_tt_item(item))
            for h in handles:
                filtered = self._filter_by_date(posts_by_handle[h], init_date, end_date)
                result[h] = (followers_by_handle[h], filtered)
        except Exception as e:
            _log.error("Batch TikTok error: %s", e)
        return result

    def _batch_fb_followers(self, pages: list[str]) -> dict[str, int]:
        """Follower count per page via facebook-pages-scraper (page details only)."""
        result = {p: 0 for p in pages}
        if not pages:
            return result
        try:
            start_urls = [{"url": f"https://www.facebook.com/{p}/"} for p in pages]
            run = self.client.actor("apify/facebook-pages-scraper").call(
                run_input={"startUrls": start_urls},
                timeout_secs=300,
                memory_mbytes=512,
            )
            for item in self._get_dataset_items(run):
                page_key = self._match_fb_page(item, pages)
                if not page_key:
                    continue
                followers = int(item.get("followers") or item.get("fans")
                                or item.get("likes") or 0)
                if followers:
                    result[page_key] = followers
        except Exception as e:
            _log.error("Batch FB followers error: %s", e)
        return result

    def _batch_fb_posts(self, pages: list[str], init_date: str, end_date: str
                        ) -> dict[str, list[Post]]:
        """Posts per page via facebook-posts-scraper (the pages-scraper returns none)."""
        result: dict[str, list[Post]] = {p: [] for p in pages}
        if not pages:
            return result
        try:
            start_urls = [{"url": f"https://www.facebook.com/{p}"} for p in pages]
            run = self.client.actor("apify/facebook-posts-scraper").call(
                run_input={"startUrls": start_urls, "resultsLimit": 30},
                timeout_secs=300,
                memory_mbytes=512,
            )
            posts_by_page: dict[str, list[Post]] = {p: [] for p in pages}
            for item in self._get_dataset_items(run):
                # Real posts always carry a postId. An unscrapeable page returns an
                # error record ({error, errorDescription, url}) with a url but no postId;
                # without this guard it became a phantom empty-timestamp post that the
                # date filter then dropped with a misleading "date-format" warning.
                if not item.get("postId"):
                    continue
                page_key = self._match_fb_page(item, pages)
                if not page_key:
                    continue
                posts_by_page[page_key].append(self._parse_fb_item(item))
            for p in pages:
                result[p] = self._filter_by_date(posts_by_page[p], init_date, end_date)
        except Exception as e:
            _log.error("Batch FB posts error: %s", e)
        return result

    @staticmethod
    def _match_fb_page(item: dict, pages: list[str]) -> str | None:
        """Match an FB dataset item (page details or post) back to a page handle."""
        for field in ("facebookUrl", "pageUrl", "inputUrl", "url", "topLevelUrl"):
            val = (item.get(field) or "").lower()
            if val:
                for p in pages:
                    if p.lower() in val:
                        return p
        pname = (item.get("pageName") or "").lower()
        if pname:
            for p in pages:
                if p.lower() == pname:
                    return p
        return None

    def fetch_all_competitors(self, competitors_cfg: list[dict],
                              init_date: str, end_date: str) -> dict:
        """Fetch all competitor data in 4 parallel batched actor runs
        (Instagram, TikTok, Facebook followers, Facebook posts).

        Returns dict keyed by competitor name:
            {name: {ig_followers, fb_followers, tt_followers, ig_posts, fb_posts, tt_posts}}
        """
        ig_handles = [h for h in (c.get("instagram_handle", "") for c in competitors_cfg) if h]
        tt_handles = [h for h in (c.get("tiktok_handle", "") for c in competitors_cfg) if h]
        fb_pages = [p for p in (c.get("facebook_page", "") for c in competitors_cfg) if p]

        ig_data: dict = {}
        tt_data: dict = {}
        fb_followers_data: dict = {}
        fb_posts_data: dict = {}

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(self._batch_instagram, ig_handles, init_date, end_date): "ig",
                pool.submit(self._batch_tiktok, tt_handles, init_date, end_date): "tt",
                pool.submit(self._batch_fb_followers, fb_pages): "fbf",
                pool.submit(self._batch_fb_posts, fb_pages, init_date, end_date): "fbp",
            }
            for future in as_completed(futures):
                key = futures[future]
                try:
                    data = future.result()
                except Exception as e:
                    _log.error("Parallel %s error: %s", key, e)
                    data = {}
                if key == "ig":
                    ig_data = data
                elif key == "tt":
                    tt_data = data
                elif key == "fbf":
                    fb_followers_data = data
                else:
                    fb_posts_data = data

        result = {}
        for comp in competitors_cfg:
            name = comp.get("name", "")
            ig_handle = comp.get("instagram_handle", "")
            tt_handle = comp.get("tiktok_handle", "")
            fb_page = comp.get("facebook_page", "")

            ig_followers, ig_posts = ig_data.get(ig_handle, (0, [])) if ig_handle else (0, [])
            tt_followers, tt_posts = tt_data.get(tt_handle, (0, [])) if tt_handle else (0, [])
            fb_followers = fb_followers_data.get(fb_page, 0) if fb_page else 0
            fb_posts = fb_posts_data.get(fb_page, []) if fb_page else []

            result[name] = {
                "ig_followers": ig_followers,
                "fb_followers": fb_followers,
                "tt_followers": tt_followers,
                "ig_posts": ig_posts,
                "fb_posts": fb_posts,
                "tt_posts": tt_posts,
            }
        return result
