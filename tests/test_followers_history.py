# tests/test_followers_history.py
import json

import pytest

from processors.followers_history import FollowersHistory


@pytest.fixture
def tmp_history_file(tmp_path):
    return str(tmp_path / "followers_history.json")


def test_get_previous_returns_zero_for_unknown(tmp_history_file):
    h = FollowersHistory(tmp_history_file)
    assert h.get_previous("Samsung Polska", "instagram") == 0


def test_update_and_get_previous(tmp_history_file):
    h = FollowersHistory(tmp_history_file)
    h.update("Samsung Polska", instagram=890000, facebook=1200000, tiktok=45000)
    h.save()
    h2 = FollowersHistory(tmp_history_file)
    assert h2.get_previous("Samsung Polska", "instagram") == 890000
    assert h2.get_previous("Samsung Polska", "facebook") == 1200000


def test_history_persists_multiple_weeks(tmp_history_file):
    h = FollowersHistory(tmp_history_file)
    h.update("Samsung Polska", instagram=880000, facebook=1190000, tiktok=44000)
    h.save()
    h2 = FollowersHistory(tmp_history_file)
    h2.update("Samsung Polska", instagram=890000, facebook=1200000, tiktok=45000)
    h2.save()
    h3 = FollowersHistory(tmp_history_file)
    assert h3.get_previous("Samsung Polska", "instagram") == 890000


def test_save_is_atomic_no_partial_file_on_crash(tmp_path, mocker):
    """If os.replace fails mid-save, the original file must remain intact.

    This guards against the bug where a crash during json.dump would leave
    the target file half-written, causing _load() to swallow JSONDecodeError
    and return {} — wiping all history.
    """
    path = tmp_path / "followers_history.json"
    original = {"Samsung Polska": {"instagram": 100, "facebook": 200, "tiktok": 50}}
    path.write_text(json.dumps(original), encoding="utf-8")

    history = FollowersHistory(str(path))
    history.update("Samsung Polska", instagram=999, facebook=999, tiktok=999)

    # Simulate crash during the atomic-rename step
    mocker.patch("os.replace", side_effect=OSError("disk full"))
    try:
        history.save()
    except OSError:
        pass

    # Original file must remain intact — not corrupted/half-written
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data == original

    # Stale .tmp file must not be left behind on disk
    tmp_path_check = path.parent / (path.name + ".tmp")
    assert not tmp_path_check.exists(), "stale .tmp left on disk after failed os.replace"
