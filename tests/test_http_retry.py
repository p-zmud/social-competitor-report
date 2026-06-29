# tests/test_http_retry.py
from unittest.mock import MagicMock
import requests
import pytest

from utils.http_retry import retry_get


def _mock_response(status, text="ok"):
    r = MagicMock()
    r.status_code = status
    r.text = text
    return r


def test_returns_immediately_on_200(mocker):
    mock_get = mocker.patch("utils.http_retry.requests.get",
                            return_value=_mock_response(200))
    sleep = mocker.patch("utils.http_retry.time.sleep")
    r = retry_get("https://example.com")
    assert r.status_code == 200
    assert mock_get.call_count == 1
    sleep.assert_not_called()


def test_retries_on_503_then_succeeds(mocker):
    mock_get = mocker.patch("utils.http_retry.requests.get",
                            side_effect=[_mock_response(503), _mock_response(200)])
    mocker.patch("utils.http_retry.time.sleep")
    r = retry_get("https://example.com", max_attempts=3, backoff=(0.1, 0.2, 0.4))
    assert r.status_code == 200
    assert mock_get.call_count == 2


def test_retries_on_timeout_then_raises(mocker):
    mocker.patch("utils.http_retry.requests.get",
                 side_effect=requests.Timeout("slow"))
    mocker.patch("utils.http_retry.time.sleep")
    with pytest.raises(requests.Timeout):
        retry_get("https://example.com", max_attempts=3, backoff=(0.0, 0.0, 0.0))


def test_does_not_retry_on_401(mocker):
    mock_get = mocker.patch("utils.http_retry.requests.get",
                            return_value=_mock_response(401, "unauthorized"))
    sleep = mocker.patch("utils.http_retry.time.sleep")
    r = retry_get("https://example.com")
    assert r.status_code == 401
    assert mock_get.call_count == 1
    sleep.assert_not_called()


def test_passes_headers_and_timeout(mocker):
    mock_get = mocker.patch("utils.http_retry.requests.get",
                            return_value=_mock_response(200))
    retry_get("https://example.com", headers={"X": "1"}, timeout=5.0)
    args, kwargs = mock_get.call_args
    assert args[0] == "https://example.com"
    assert kwargs["headers"] == {"X": "1"}
    assert kwargs["timeout"] == 5.0


def test_mask_url_redacts_access_token():
    from utils.http_retry import _mask_url
    url = "https://graph.facebook.com/v18.0/ads?access_token=SECRET123&q=foo"
    assert "SECRET123" not in _mask_url(url)
    assert "access_token=***" in _mask_url(url)
