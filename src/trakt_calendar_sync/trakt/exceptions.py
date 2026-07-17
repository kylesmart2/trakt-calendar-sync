class TraktAuthError(Exception):
    """Base class for errors during the OAuth device flow."""


class DeviceAuthDenied(TraktAuthError):
    """The user denied the app on trakt.tv/activate."""


class DeviceAuthExpired(TraktAuthError):
    """The user_code expired before the user entered it."""


class TraktAPIError(Exception):
    """Non-2xx response from a Trakt API call, outside of the auth flow."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"Trakt API error {status_code}: {message}")
