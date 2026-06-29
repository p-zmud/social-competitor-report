# utils/http_retry.py
"""HTTP GET wrapper with retry on transient failures (5xx, 429, timeouts)."""
import re as _re
import time
import requests

from app_logging import get_logger

_log = get_logger("http_retry")

RETRY_STATUSES = {429, 500, 502, 503, 504}
RETRY_EXCEPTIONS = (requests.Timeout, requests.ConnectionError)


def _mask_url(url: str) -> str:
    """Mask the access_token query parameter in a URL for safe logging."""
    return _re.sub(r"(access_token=)[^&\s]+", r"\1***", url)


def retry_get(url, *, headers=None, params=None, timeout=30.0,
              max_attempts=3, backoff=(1.0, 2.0)):
    """GET with retry on timeouts/connection errors and 5xx/429.

    Returns the final requests.Response. Caller decides what to do with non-200.
    Does NOT retry on 4xx other than 429.
    """
    last_exc = None
    for attempt in range(1, max_attempts + 1):
        try:
            r = requests.get(url, headers=headers, params=params, timeout=timeout)
        except RETRY_EXCEPTIONS as e:
            last_exc = e
            if attempt < max_attempts:
                wait = backoff[attempt - 1]
                _log.warning("%s on %s (attempt %d/%d): %s, retrying in %.1fs",
                             type(e).__name__, _mask_url(url), attempt, max_attempts, e, wait)
                time.sleep(wait)
                continue
            raise
        if r.status_code in RETRY_STATUSES and attempt < max_attempts:
            wait = backoff[attempt - 1]
            _log.warning("HTTP %d on %s (attempt %d/%d), retrying in %.1fs",
                         r.status_code, _mask_url(url), attempt, max_attempts, wait)
            time.sleep(wait)
            continue
        return r
    if last_exc:
        raise last_exc
    raise RuntimeError("retry_get exhausted with no exception captured")
