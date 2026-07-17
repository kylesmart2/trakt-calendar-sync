"""Trakt OAuth device code flow.

Trakt's device flow (https://trakt.docs.apiary.io -> Authentication -> Device
Code) has no redirect URI, which is why it's a good fit for a desktop app:

1. POST /oauth/device/code with the user's client_id -> get back a
   short-lived `device_code` (kept secret, used for polling) and a
   `user_code` (shown to the user).
2. The user visits `verification_url` (trakt.tv/activate) and types in the
   `user_code`.
3. Meanwhile we poll POST /oauth/device/token with the device_code every
   `interval` seconds until the user finishes step 2 (or the code expires).

Each Trakt user brings their own client_id/client_secret (their personal API
app), so both are passed in here rather than baked into this module.
"""

import threading
import time
from dataclasses import dataclass

import requests

from .exceptions import DeviceAuthDenied, DeviceAuthExpired, TraktAuthError

API_BASE = "https://api.trakt.tv"
DEVICE_CODE_URL = f"{API_BASE}/oauth/device/code"
DEVICE_TOKEN_URL = f"{API_BASE}/oauth/device/token"
TOKEN_URL = f"{API_BASE}/oauth/token"

REQUEST_TIMEOUT = 15  # seconds


@dataclass
class DeviceCode:
    device_code: str
    user_code: str
    verification_url: str
    expires_in: int
    interval: int


@dataclass
class TraktTokens:
    access_token: str
    refresh_token: str
    expires_in: int
    created_at: int
    scope: str
    token_type: str

    @classmethod
    def from_response(cls, data: dict) -> "TraktTokens":
        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_in=data["expires_in"],
            created_at=data["created_at"],
            scope=data["scope"],
            token_type=data["token_type"],
        )


class TraktDeviceAuth:
    def __init__(self, client_id: str, client_secret: str, session: requests.Session | None = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self._session = session or requests.Session()

    def request_device_code(self) -> DeviceCode:
        response = self._session.post(
            DEVICE_CODE_URL,
            json={"client_id": self.client_id},
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code != 200:
            raise TraktAuthError(
                f"Failed to request device code (HTTP {response.status_code}): {response.text}"
            )
        data = response.json()
        return DeviceCode(
            device_code=data["device_code"],
            user_code=data["user_code"],
            verification_url=data["verification_url"],
            expires_in=data["expires_in"],
            interval=data["interval"],
        )

    def poll_for_tokens(
        self,
        device_code: DeviceCode,
        on_wait: "callable | None" = None,
        cancel_event: threading.Event | None = None,
    ) -> TraktTokens:
        """Block until the user approves the code, it expires, or it's denied.

        `on_wait(seconds_elapsed)` is called once per poll so a GUI can update
        a countdown/status label. Pass a `cancel_event` to abort early from
        another thread (e.g. the user closes the setup dialog).
        """
        deadline = time.monotonic() + device_code.expires_in
        interval = device_code.interval

        while time.monotonic() < deadline:
            if cancel_event is not None and cancel_event.is_set():
                raise TraktAuthError("Device authorization cancelled")

            response = self._session.post(
                DEVICE_TOKEN_URL,
                json={
                    "code": device_code.device_code,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code == 200:
                return TraktTokens.from_response(response.json())
            if response.status_code == 400:
                pass  # Pending - user hasn't entered the code yet
            elif response.status_code == 404:
                raise TraktAuthError("Invalid device code")
            elif response.status_code == 409:
                raise TraktAuthError("Device code already used")
            elif response.status_code == 410:
                raise DeviceAuthExpired("Device code expired before it was approved")
            elif response.status_code == 418:
                raise DeviceAuthDenied("User denied the authorization request")
            elif response.status_code == 429:
                interval += 5  # Trakt: back off when polling too fast
            else:
                raise TraktAuthError(
                    f"Unexpected response while polling (HTTP {response.status_code}): {response.text}"
                )

            if on_wait is not None:
                on_wait(int(deadline - time.monotonic()))
            time.sleep(interval)

        raise DeviceAuthExpired("Device code expired before it was approved")

    def refresh_tokens(self, refresh_token: str) -> TraktTokens:
        response = self._session.post(
            TOKEN_URL,
            json={
                "refresh_token": refresh_token,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
                "grant_type": "refresh_token",
            },
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code != 200:
            raise TraktAuthError(
                f"Failed to refresh tokens (HTTP {response.status_code}): {response.text}"
            )
        return TraktTokens.from_response(response.json())
