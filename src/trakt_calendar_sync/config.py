"""App-wide settings and secret storage.

Non-secret settings (Trakt client ID, calendar ID, auto-sync toggle) live in a
JSON file under the OS config dir. Secrets (Trakt client secret, OAuth tokens)
live in the OS keychain via `keyring` so they survive as a packaged .exe/.app
without ever touching plaintext disk.
"""

import json
from pathlib import Path

import keyring
import platformdirs

APP_NAME = "TraktCalendarSync"
KEYRING_SERVICE = "trakt-calendar-sync"

# Keys used with keyring.set_password/get_password.
SECRET_TRAKT_CLIENT_SECRET = "trakt_client_secret"
SECRET_TRAKT_ACCESS_TOKEN = "trakt_access_token"
SECRET_TRAKT_REFRESH_TOKEN = "trakt_refresh_token"
SECRET_GOOGLE_TOKEN = "google_token"  # serialized google.oauth2.credentials.Credentials

# Keys used with load_settings()/save_settings() (non-secret).
SETTING_TRAKT_CLIENT_ID = "trakt_client_id"
SETTING_AUTO_SYNC_HOUR = "auto_sync_hour"
SETTING_AUTO_SYNC_MINUTE = "auto_sync_minute"


def config_dir() -> Path:
    path = Path(platformdirs.user_config_dir(APP_NAME, appauthor=False))
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    return config_dir() / "settings.json"


def load_settings() -> dict:
    path = settings_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_settings(settings: dict) -> None:
    settings_path().write_text(json.dumps(settings, indent=2), encoding="utf-8")


def update_settings(**changes) -> dict:
    settings = load_settings()
    settings.update(changes)
    save_settings(settings)
    return settings


def set_secret(key: str, value: str) -> None:
    keyring.set_password(KEYRING_SERVICE, key, value)


def get_secret(key: str) -> str | None:
    return keyring.get_password(KEYRING_SERVICE, key)


def delete_secret(key: str) -> None:
    try:
        keyring.delete_password(KEYRING_SERVICE, key)
    except keyring.errors.PasswordDeleteError:
        pass


def load_trakt_credentials() -> dict | None:
    """The single source of truth for "is Trakt fully configured" - returns
    None if any piece is missing, otherwise the client ID/secret and tokens
    needed to build a TraktClient.
    """
    settings = load_settings()
    client_id = settings.get(SETTING_TRAKT_CLIENT_ID)
    client_secret = get_secret(SECRET_TRAKT_CLIENT_SECRET)
    access_token = get_secret(SECRET_TRAKT_ACCESS_TOKEN)
    refresh_token = get_secret(SECRET_TRAKT_REFRESH_TOKEN)

    if not all([client_id, client_secret, access_token, refresh_token]):
        return None

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "access_token": access_token,
        "refresh_token": refresh_token,
    }
