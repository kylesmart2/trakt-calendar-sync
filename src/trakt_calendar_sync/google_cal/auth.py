"""Google OAuth using the app's shared credentials.json (bundled resource,
same for every user — see resources.google_credentials_path). Each user still
authorizes individually: run_authorization_flow() pops the system browser
against their own Google account and consents to their own calendar.

credentials.json must be a "Desktop app" OAuth client from Google Cloud
Console (top-level "installed" key) — the loopback redirect flow
(run_local_server) relies on Desktop-app clients accepting any localhost
port, unlike "Web application" clients which require exact redirect URIs.
"""

import json

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from .. import config, resources

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def load_credentials() -> Credentials | None:
    """Cached credentials for a returning user, refreshing the access token
    if it's expired. Returns None if there's nothing cached, or the refresh
    token itself was revoked — either way the caller should fall back to
    run_authorization_flow().
    """
    raw = config.get_secret(config.SECRET_GOOGLE_TOKEN)
    if raw is None:
        return None

    creds = Credentials.from_authorized_user_info(json.loads(raw), SCOPES)
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


def run_authorization_flow(credentials_path=None) -> Credentials:
    """Blocking call: pops the system browser for the user to sign in and
    consent, catches the redirect on an ephemeral localhost port, then caches
    the resulting tokens. Run this off the GUI thread.
    """
    path = credentials_path or resources.google_credentials_path()
    flow = InstalledAppFlow.from_client_secrets_file(str(path), SCOPES)
    creds = flow.run_local_server(port=0)
    _save_credentials(creds)
    return creds


def sign_out() -> None:
    config.delete_secret(config.SECRET_GOOGLE_TOKEN)


def _save_credentials(creds: Credentials) -> None:
    config.set_secret(config.SECRET_GOOGLE_TOKEN, creds.to_json())
