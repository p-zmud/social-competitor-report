# tests/test_apify.py
from unittest.mock import MagicMock, call
from collectors.apify import ApifyCollector
from models import Post


def _make_post(published_at: str, post_id: str = "p1") -> Post:
    return Post(
        id=post_id,
        platform="instagram",
        url="https://example.com/p",
        caption="x",
        published_at=published_at,
        likes=0,
        comments=0,
        shares=0,
        reach=0,
        views=None,
    )


def test_filter_by_date_handles_tz_aware_post_at_day_boundary(mocker):
    """Post at 23:30 CEST belongs to that local date (TZ-aware comparison)."""
    mocker.patch("collectors.apify.ApifyClient")
    collector = ApifyCollector(api_token="fake")
    posts = [_make_post("2026-05-10T23:30:00+02:00")]
    result = collector._filter_by_date(posts, "2026-05-10", "2026-05-10")
    assert len(result) == 1


def test_filter_by_date_excludes_post_outside_local_day(mocker):
    """Post at 00:30 CEST on next day does NOT belong to previous local date."""
    mocker.patch("collectors.apify.ApifyClient")
    collector = ApifyCollector(api_token="fake")
    posts = [_make_post("2026-05-11T00:30:00+02:00")]
    result = collector._filter_by_date(posts, "2026-05-10", "2026-05-10")
    assert result == []


def test_filter_by_date_handles_z_suffix_utc(mocker):
    """UTC 'Z' suffix is converted; 21:30 UTC == 23:30 CEST belongs to local day."""
    mocker.patch("collectors.apify.ApifyClient")
    collector = ApifyCollector(api_token="fake")
    posts = [_make_post("2026-05-10T21:30:00Z")]
    result = collector._filter_by_date(posts, "2026-05-10", "2026-05-10")
    assert len(result) == 1


def test_filter_by_date_warns_when_all_dropped(mocker, caplog):
    """When input is non-empty but everything is filtered out, log a warning."""
    import logging
    mocker.patch("collectors.apify.ApifyClient")
    collector = ApifyCollector(api_token="fake")
    posts = [_make_post("2025-01-01T10:00:00+00:00")]
    with caplog.at_level(logging.WARNING, logger="app.apify"):
        result = collector._filter_by_date(posts, "2026-05-10", "2026-05-10")
    assert result == []
    assert any("dropped all" in r.message for r in caplog.records)


def test_batch_fb_posts_ignores_error_record_for_unscrapeable_page(mocker, caplog):
    """An unscrapeable FB page yields an Apify error record (a `url` but no `postId`
    and no `time`). It must be skipped, not turned into a phantom empty-timestamp post
    that the date filter then drops with a misleading 'dropped all' warning."""
    import logging
    mock_client = MagicMock()
    mock_client.actor.return_value.call.return_value = {
        "defaultDatasetId": "ds", "status": "SUCCEEDED",
    }
    mock_client.dataset.return_value.iterate_items.return_value = iter([
        {"error": "no_posts", "errorDescription": "page not scrapeable",
         "url": "https://www.facebook.com/McDonaldsPolska"},
    ])
    mocker.patch("collectors.apify.ApifyClient", return_value=mock_client)

    collector = ApifyCollector(api_token="fake")
    with caplog.at_level(logging.WARNING, logger="app.apify"):
        result = collector._batch_fb_posts(["McDonaldsPolska"], "2026-05-10", "2026-05-10")

    assert result["McDonaldsPolska"] == []
    assert not any("dropped all" in r.message for r in caplog.records)


def test_get_instagram_followers(mocker):
    mock_client = MagicMock()
    mock_client.actor.return_value.call.return_value = {
        "defaultDatasetId": "ds123",
        "status": "SUCCEEDED",
    }
    mock_client.dataset.return_value.iterate_items.return_value = iter([
        {"userName": "samsung_polska", "followersCount": 890000},
    ])
    mocker.patch("collectors.apify.ApifyClient", return_value=mock_client)

    collector = ApifyCollector(api_token="fake")
    followers = collector.get_instagram_followers("samsung_polska")
    mock_client.actor.assert_called_with("apify/instagram-followers-count-scraper")
    assert followers == 890000


def test_get_instagram_followers_returns_zero_on_error(mocker):
    mock_client = MagicMock()
    mock_client.actor.return_value.call.side_effect = Exception("API error")
    mocker.patch("collectors.apify.ApifyClient", return_value=mock_client)

    collector = ApifyCollector(api_token="fake")
    followers = collector.get_instagram_followers("samsung_polska")
    assert followers == 0


def test_get_tiktok_data(mocker):
    mock_client = MagicMock()
    mock_client.actor.return_value.call.return_value = {
        "defaultDatasetId": "ds456",
        "status": "SUCCEEDED",
    }
    mock_client.dataset.return_value.iterate_items.return_value = iter([
        {"id": "tt1", "text": "test", "createTimeISO": "2026-02-10T10:00:00Z",
         "diggCount": 100, "commentCount": 5, "shareCount": 3, "playCount": 5000,
         "webVideoUrl": "https://tiktok.com/v/1",
         "authorMeta": {"fans": 30500}},
    ])
    mocker.patch("collectors.apify.ApifyClient", return_value=mock_client)

    collector = ApifyCollector(api_token="fake")
    followers, posts = collector.get_tiktok_data("samsungpolska", "2026-02-10", "2026-02-16")
    assert followers == 30500
    assert len(posts) == 1


# --- Batch tests ---

COMPETITORS_CFG = [
    {
        "name": "Samsung Polska",
        "instagram_handle": "samsungpolska",
        "tiktok_handle": "samsungpolska",
        "facebook_page": "SamsungPolska",
    },
    {
        "name": "Motorola Polska",
        "instagram_handle": "motorolapolska",
        "tiktok_handle": "motorola.polska",
        "facebook_page": "MotorolaPoland",
    },
]


def test_fetch_all_competitors_batched(mocker):
    """Each platform should be called exactly once with all handles."""
    mock_client = MagicMock()

    # Track calls per actor
    actor_calls = {}

    def fake_actor(actor_id):
        mock_actor = MagicMock()

        def fake_call(run_input, timeout_secs=None, memory_mbytes=None):
            actor_calls[actor_id] = run_input
            ds_id = f"ds_{actor_id.replace('/', '_')}"
            return {"defaultDatasetId": ds_id, "status": "SUCCEEDED"}

        mock_actor.call.side_effect = fake_call
        return mock_actor

    mock_client.actor.side_effect = fake_actor
    mock_client.dataset.return_value.iterate_items.return_value = iter([])
    mocker.patch("collectors.apify.ApifyClient", return_value=mock_client)

    collector = ApifyCollector(api_token="fake")
    collector.fetch_all_competitors(COMPETITORS_CFG, "2026-02-10", "2026-02-16")

    # Exactly 4 actor calls (IG, TT, FB followers, FB posts)
    assert len(actor_calls) == 4

    # IG: all handles in one call (now uses profile-scraper)
    ig_input = actor_calls["apify/instagram-profile-scraper"]
    assert set(ig_input["usernames"]) == {"samsungpolska", "motorolapolska"}

    # TT: all handles in one call
    tt_input = actor_calls["clockworks/tiktok-scraper"]
    assert set(tt_input["profiles"]) == {"samsungpolska", "motorola.polska"}

    # FB followers: pages scraper, all pages (trailing slash)
    fb_pages_input = actor_calls["apify/facebook-pages-scraper"]
    fb_pages_urls = [u["url"] for u in fb_pages_input["startUrls"]]
    assert "https://www.facebook.com/SamsungPolska/" in fb_pages_urls
    assert "https://www.facebook.com/MotorolaPoland/" in fb_pages_urls

    # FB posts: posts scraper, all pages (+ resultsLimit)
    fb_posts_input = actor_calls["apify/facebook-posts-scraper"]
    fb_posts_urls = [u["url"] for u in fb_posts_input["startUrls"]]
    assert "https://www.facebook.com/SamsungPolska" in fb_posts_urls
    assert fb_posts_input["resultsLimit"] == 30


def test_fetch_all_competitors_maps_results(mocker):
    """Results from batch runs should be mapped back to correct competitors."""
    mock_client = MagicMock()

    ig_items = [
        {"username": "samsungpolska", "followersCount": 890000, "latestPosts": [
            {"id": "ig1", "caption": "samsung ig post", "timestamp": "2026-02-11T10:00:00.000Z",
             "likesCount": 300, "commentsCount": 15, "url": "https://instagram.com/p/abc",
             "type": "Image"},
        ]},
        {"username": "motorolapolska", "followersCount": 120000, "latestPosts": [
            {"id": "ig2", "caption": "moto ig post", "timestamp": "2026-02-12T10:00:00.000Z",
             "likesCount": 50, "commentsCount": 3, "url": "https://instagram.com/p/def",
             "type": "Video", "videoViewCount": 8000},
        ]},
    ]
    tt_items = [
        {"id": "tt1", "text": "samsung vid", "createTimeISO": "2026-02-11T10:00:00Z",
         "diggCount": 100, "commentCount": 5, "shareCount": 3, "playCount": 5000,
         "webVideoUrl": "https://tiktok.com/v/1",
         "authorMeta": {"name": "samsungpolska", "fans": 30500}},
        {"id": "tt2", "text": "moto vid", "createTimeISO": "2026-02-12T10:00:00Z",
         "diggCount": 50, "commentCount": 2, "shareCount": 1, "playCount": 2000,
         "webVideoUrl": "https://tiktok.com/v/2",
         "authorMeta": {"name": "motorola.polska", "fans": 8000}},
    ]
    fb_page_items = [
        {"followers": 163000000, "pageUrl": "https://www.facebook.com/SamsungPolska/",
         "pageName": "SamsungPolska"},
        {"followers": 500000, "pageUrl": "https://www.facebook.com/MotorolaPoland/",
         "pageName": "MotorolaPoland"},
    ]
    fb_post_items = [
        {"postId": "fb1", "url": "https://www.facebook.com/SamsungPolska/posts/1",
         "facebookUrl": "https://www.facebook.com/SamsungPolska", "pageName": "SamsungPolska",
         "text": "samsung post", "time": "2026-02-11T12:00:00Z",
         "likes": 200, "comments": 10, "shares": 5},
    ]

    datasets_map = {}

    def fake_actor(actor_id):
        mock_actor = MagicMock()

        def fake_call(run_input, timeout_secs=None, memory_mbytes=None):
            ds_id = f"ds_{actor_id.replace('/', '_')}"
            if "instagram" in actor_id:
                datasets_map[ds_id] = ig_items
            elif "tiktok" in actor_id:
                datasets_map[ds_id] = tt_items
            elif "facebook-pages" in actor_id:
                datasets_map[ds_id] = fb_page_items
            elif "facebook-posts" in actor_id:
                datasets_map[ds_id] = fb_post_items
            else:
                datasets_map[ds_id] = []
            return {"defaultDatasetId": ds_id, "status": "SUCCEEDED"}

        mock_actor.call.side_effect = fake_call
        return mock_actor

    mock_client.actor.side_effect = fake_actor
    mock_client.dataset.side_effect = lambda ds_id: MagicMock(
        iterate_items=MagicMock(return_value=iter(datasets_map.get(ds_id, [])))
    )
    mocker.patch("collectors.apify.ApifyClient", return_value=mock_client)

    collector = ApifyCollector(api_token="fake")
    result = collector.fetch_all_competitors(COMPETITORS_CFG, "2026-02-10", "2026-02-16")

    # Samsung
    samsung = result["Samsung Polska"]
    assert samsung["ig_followers"] == 890000
    assert samsung["tt_followers"] == 30500
    assert samsung["fb_followers"] == 163000000
    assert len(samsung["ig_posts"]) == 1
    assert samsung["ig_posts"][0].platform == "instagram"
    assert samsung["ig_posts"][0].likes == 300
    assert len(samsung["tt_posts"]) == 1
    assert len(samsung["fb_posts"]) == 1

    # Motorola
    moto = result["Motorola Polska"]
    assert moto["ig_followers"] == 120000
    assert moto["tt_followers"] == 8000
    assert moto["fb_followers"] == 500000
    assert len(moto["ig_posts"]) == 1
    assert moto["ig_posts"][0].views == 8000  # Video post
    assert len(moto["tt_posts"]) == 1
    assert len(moto["fb_posts"]) == 0  # no Motorola posts in fb_items


def test_tiktok_followers_uses_first_nonzero_value(mocker):
    """Bug: zero from first record shouldn't block real value from later record."""
    mock_client = MagicMock()

    tt_items = [
        # First record has authorMeta with fans=0 (e.g. private/empty profile snapshot)
        {"id": "tt1", "text": "first", "createTimeISO": "2026-02-11T10:00:00Z",
         "diggCount": 1, "commentCount": 0, "shareCount": 0, "playCount": 10,
         "webVideoUrl": "https://tiktok.com/v/1",
         "authorMeta": {"uniqueId": "samsungpolska", "fans": 0}},
        # Second record has the actual follower count
        {"id": "tt2", "text": "second", "createTimeISO": "2026-02-12T10:00:00Z",
         "diggCount": 5, "commentCount": 1, "shareCount": 0, "playCount": 100,
         "webVideoUrl": "https://tiktok.com/v/2",
         "authorMeta": {"uniqueId": "samsungpolska", "fans": 12345}},
    ]

    def fake_actor(actor_id):
        mock_actor = MagicMock()

        def fake_call(run_input, timeout_secs=None, memory_mbytes=None):
            return {"defaultDatasetId": "ds_tt", "status": "SUCCEEDED"}

        mock_actor.call.side_effect = fake_call
        return mock_actor

    mock_client.actor.side_effect = fake_actor
    mock_client.dataset.return_value.iterate_items.return_value = iter(tt_items)
    mocker.patch("collectors.apify.ApifyClient", return_value=mock_client)

    collector = ApifyCollector(api_token="fake")
    result = collector._batch_tiktok(["samsungpolska"], "2026-02-10", "2026-02-16")
    followers, posts = result["samsungpolska"]
    assert followers == 12345
    assert len(posts) == 2


def test_fetch_all_competitors_skips_competitors_with_missing_handles(mocker):
    """Missing handle keys must not raise KeyError; competitor is silently zero."""
    competitors_cfg = [
        {
            "name": "Samsung",
            "instagram_handle": "samsung_pl",
            "tiktok_handle": "samsung_pl",
            "facebook_page": "samsung.pl",
        },
        {"name": "Apple"},  # NO handles at all
    ]

    mock_client = MagicMock()

    def fake_actor(actor_id):
        mock_actor = MagicMock()

        def fake_call(run_input, timeout_secs=None, memory_mbytes=None):
            ds_id = f"ds_{actor_id.replace('/', '_')}"
            return {"defaultDatasetId": ds_id, "status": "SUCCEEDED"}

        mock_actor.call.side_effect = fake_call
        return mock_actor

    mock_client.actor.side_effect = fake_actor
    mock_client.dataset.return_value.iterate_items.return_value = iter([])
    mocker.patch("collectors.apify.ApifyClient", return_value=mock_client)

    collector = ApifyCollector(api_token="fake")
    # Must not raise KeyError
    result = collector.fetch_all_competitors(competitors_cfg, "2026-02-10", "2026-02-16")

    # Apple is present in the result, all-zero
    assert "Apple" in result
    assert result["Apple"]["ig_followers"] == 0
    assert result["Apple"]["tt_followers"] == 0
    assert result["Apple"]["fb_followers"] == 0
    assert result["Apple"]["ig_posts"] == []
    assert result["Apple"]["tt_posts"] == []
    assert result["Apple"]["fb_posts"] == []


def test_fetch_all_competitors_handles_error(mocker):
    """If one platform fails, others should still return data."""
    mock_client = MagicMock()
    datasets_map = {}

    def fake_actor(actor_id):
        mock_actor = MagicMock()

        def fake_call(run_input, timeout_secs=None, memory_mbytes=None):
            if "tiktok" in actor_id:
                raise Exception("TikTok API down")
            ds_id = f"ds_{actor_id.replace('/', '_')}"
            if "instagram" in actor_id:
                datasets_map[ds_id] = [
                    {"username": "samsungpolska", "followersCount": 890000, "latestPosts": []},
                ]
            else:
                datasets_map[ds_id] = []
            return {"defaultDatasetId": ds_id, "status": "SUCCEEDED"}

        mock_actor.call.side_effect = fake_call
        return mock_actor

    mock_client.actor.side_effect = fake_actor
    mock_client.dataset.side_effect = lambda ds_id: MagicMock(
        iterate_items=MagicMock(return_value=iter(datasets_map.get(ds_id, [])))
    )
    mocker.patch("collectors.apify.ApifyClient", return_value=mock_client)

    collector = ApifyCollector(api_token="fake")
    result = collector.fetch_all_competitors(COMPETITORS_CFG, "2026-02-10", "2026-02-16")

    # IG still works
    assert result["Samsung Polska"]["ig_followers"] == 890000
    assert result["Samsung Polska"]["ig_posts"] == []
    # TT gracefully zero
    assert result["Samsung Polska"]["tt_followers"] == 0
    assert result["Samsung Polska"]["tt_posts"] == []
