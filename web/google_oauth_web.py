"""Redirect-based Google OAuth flow for the web app.

The native GUI uses a different flow (google_cal.auth.run_authorization_flow,
a loopback/"installed app" flow that blocks on a throwaway local server on a
random port) which can't be reused here - this app owns a real route
(see app.py's /oauth/callback) to receive the redirect instead, so it talks
to google-auth-oauthlib's Flow class directly.

Uses web/credentials.json for the OAuth client - can be the same file as the
native app's resources/credentials.json, or a dedicated "Web application"
type client if a "Desktop app" client's redirect URI rules turn out not to
accept a fixed localhost:6969 callback (untested - cross that bridge if it
comes up).
"""

import json
import os
from pathlib import Path

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from . import storage

SCOPES = ["https://www.googleapis.com/auth/calendar"]

DEFAULT_CREDENTIALS_PATH = Path(__file__).resolve().parent / "credentials.json"


def credentials_path() -> Path:
    return Path(os.environ.get("TRAKT_CALENDAR_SYNC_WEB_GOOGLE_CREDENTIALS", str(DEFAULT_CREDENTIALS_PATH)))


def load_credentials() -> Credentials | None:
    raw = storage.get(storage.KEY_GOOGLE_TOKEN)
    if raw is None:
        return None

    try:
        creds = Credentials.from_authorized_user_info(json.loads(raw), SCOPES)
    except (ValueError, json.JSONDecodeError):
        # Stored token is malformed/incomplete (corrupted write, manual edit,
        # an old incompatible shape) - treat it the same as "not authorized
        # yet" instead of 500ing the whole dashboard.
        return None

    if creds.valid:
        return creds

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except RefreshError:
            return None
        _save_credentials(creds)
        return creds

    return None


def build_flow(redirect_uri: str) -> Flow:
    return Flow.from_client_secrets_file(str(credentials_path()), scopes=SCOPES, redirect_uri=redirect_uri)


def authorization_url(flow: Flow) -> tuple:
    """Returns (url, state) - stash `state` (e.g. in the Flask session) and
    verify it matches on the callback to guard against CSRF. access_type and
    prompt are required to reliably get a refresh_token back, not just a
    short-lived access token."""
    return flow.authorization_url(access_type="offline", include_granted_scopes="true", prompt="consent")


def complete_authorization(flow: Flow, authorization_response: str) -> None:
    """authorization_response is the full callback URL Google redirected to,
    including the ?code=...&state=... query string."""
    flow.fetch_token(authorization_response=authorization_response)
    _save_credentials(flow.credentials)


def sign_out() -> None:
    storage.delete(storage.KEY_GOOGLE_TOKEN)


def _save_credentials(creds: Credentials) -> None:
    storage.set(storage.KEY_GOOGLE_TOKEN, creds.to_json())
