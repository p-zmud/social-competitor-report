# processors/followers_history.py
import json
import os


class FollowersHistory:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self._data: dict = self._load()
        self._pending: dict = {}

    def _load(self) -> dict:
        if os.path.exists(self.filepath):
            try:
                with open(self.filepath) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def get_previous(self, competitor_name: str, platform: str) -> int:
        return self._data.get(competitor_name, {}).get(platform, 0)

    def update(self, competitor_name: str, instagram: int, facebook: int, tiktok: int):
        self._pending[competitor_name] = {
            "instagram": instagram,
            "facebook": facebook,
            "tiktok": tiktok,
        }

    def save(self):
        self._data.update(self._pending)
        dirpath = os.path.dirname(self.filepath)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        # Atomic write: dump to temp file, then rename. If anything fails
        # mid-write, the original file remains intact rather than being
        # left half-written (which _load() would silently swallow as {}).
        # On failure, unlink the .tmp so stale files don't accumulate
        # (e.g. cross-device replace, permission errors).
        tmp = self.filepath + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.filepath)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
