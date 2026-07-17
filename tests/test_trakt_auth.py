from unittest.mock import MagicMock, patch

import pytest

from trakt_calendar_sync.trakt.auth import DeviceCode, TraktDeviceAuth
from trakt_calendar_sync.trakt.exceptions import (
    DeviceAuthDenied,
    DeviceAuthExpired,
    TraktAuthError,
)


def _response(status_code: int, json_data: dict | None = None, text: str = ""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


@pytest.fixture
def auth():
    return TraktDeviceAuth("client-id", "client-secret", session=MagicMock())


def test_request_device_code_success(auth):
    auth._session.post.return_value = _response(
        200,
        {
            "device_code": "dc123",
            "user_code": "ABCD1234",
            "verification_url": "https://trakt.tv/activate",
            "expires_in": 600,
            "interval": 5,
        },
    )

    code = auth.request_device_code()

    assert code == DeviceCode(
        device_code="dc123",
        user_code="ABCD1234",
        verification_url="https://trakt.tv/activate",
        expires_in=600,
        interval=5,
    )
    auth._session.post.assert_called_once()


def test_request_device_code_failure(auth):
    auth._session.post.return_value = _response(403, text="forbidden")

    with pytest.raises(TraktAuthError):
        auth.request_device_code()


@patch("trakt_calendar_sync.trakt.auth.time.sleep")
def test_poll_for_tokens_pending_then_success(mock_sleep, auth):
    device_code = DeviceCode("dc123", "ABCD1234", "https://trakt.tv/activate", 600, 1)
    auth._session.post.side_effect = [
        _response(400),  # pending
        _response(400),  # still pending
        _response(
            200,
            {
                "access_token": "at",
                "refresh_token": "rt",
                "expires_in": 7776000,
                "created_at": 1234567890,
                "scope": "public",
                "token_type": "bearer",
            },
        ),
    ]

    tokens = auth.poll_for_tokens(device_code)

    assert tokens.access_token == "at"
    assert tokens.refresh_token == "rt"
    assert auth._session.post.call_count == 3
    assert mock_sleep.call_count == 2


@patch("trakt_calendar_sync.trakt.auth.time.sleep")
def test_poll_for_tokens_denied(mock_sleep, auth):
    device_code = DeviceCode("dc123", "ABCD1234", "https://trakt.tv/activate", 600, 1)
    auth._session.post.return_value = _response(418)

    with pytest.raises(DeviceAuthDenied):
        auth.poll_for_tokens(device_code)


@patch("trakt_calendar_sync.trakt.auth.time.sleep")
def test_poll_for_tokens_expired(mock_sleep, auth):
    device_code = DeviceCode("dc123", "ABCD1234", "https://trakt.tv/activate", 600, 1)
    auth._session.post.return_value = _response(410)

    with pytest.raises(DeviceAuthExpired):
        auth.poll_for_tokens(device_code)


def test_refresh_tokens_success(auth):
    auth._session.post.return_value = _response(
        200,
        {
            "access_token": "new-at",
            "refresh_token": "new-rt",
            "expires_in": 7776000,
            "created_at": 1234567890,
            "scope": "public",
            "token_type": "bearer",
        },
    )

    tokens = auth.refresh_tokens("old-rt")

    assert tokens.access_token == "new-at"
    assert tokens.refresh_token == "new-rt"
