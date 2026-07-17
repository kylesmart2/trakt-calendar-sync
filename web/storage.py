"""Persists settings and secrets for the web app as plain JSON in the
mounted volume - no OS keychain (containers don't have one) and no
encryption layer (protection comes from volume/host permissions, the same
model most self-hosted apps' config files use).

Assumes a single worker process (the Flask dev server, or gunicorn with
--workers 1) - the in-process lock only protects against concurrent threads,
not concurrent processes. Fine for a single-user tool; if this ever needs
multiple workers, swap the lock for a file lock (fcntl) or move to sqlite.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

_LOCK = Lock()

KEY_TRAKT_CLIENT_ID = "trakt_client_id"
KEY_TRAKT_CLIENT_SECRET = "trakt_client_secret"
KEY_TRAKT_ACCESS_TOKEN = "trakt_access_token"
KEY_TRAKT_REFRESH_TOKEN = "trakt_refresh_token"
KEY_GOOGLE_TOKEN = "google_token"  # serialized google.oauth2.credentials.Credentials
KEY_AUTO_SYNC_ENABLED = "auto_sync_enabled"
KEY_AUTO_SYNC_HOUR = "auto_sync_hour"
KEY_AUTO_SYNC_MINUTE = "auto_sync_minute"
KEY_FLASK_SECRET_KEY = "flask_secret_key"
KEY_SYNC_LOG = "sync_log"

MAX_LOG_ENTRIES = 20


def data_dir() -> Path:
    path = Path(os.environ.get("TRAKT_CALENDAR_SYNC_WEB_DATA_DIR", "/data"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def get(key: str, default=None):
    with _LOCK:
        return _load().get(key, default)


def set(key: str, value) -> None:
    with _LOCK:
        store = _load()
        store[key] = value
        _save(store)


def delete(key: str) -> None:
    with _LOCK:
        store = _load()
        store.pop(key, None)
        _save(store)


def update(**changes) -> dict:
    with _LOCK:
        store = _load()
        store.update(changes)
        _save(store)
        return store


def load_trakt_credentials() -> dict | None:
    """Mirrors config.load_trakt_credentials()'s shape in the native app,
    just backed by this module's storage instead of settings.json+keyring."""
    with _LOCK:
        store = _load()
    client_id = store.get(KEY_TRAKT_CLIENT_ID)
    client_secret = store.get(KEY_TRAKT_CLIENT_SECRET)
    access_token = store.get(KEY_TRAKT_ACCESS_TOKEN)
    refresh_token = store.get(KEY_TRAKT_REFRESH_TOKEN)

    if not all([client_id, client_secret, access_token, refresh_token]):
        return None

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


def append_log(message: str) -> None:
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "message": message}
    with _LOCK:
        store = _load()
        log = store.get(KEY_SYNC_LOG, [])
        log.append(entry)
        store[KEY_SYNC_LOG] = log[-MAX_LOG_ENTRIES:]
        _save(store)


def get_log() -> list:
    with _LOCK:
        return _load().get(KEY_SYNC_LOG, [])


def _store_path() -> Path:
    return data_dir() / "store.json"


def _load() -> dict:
    path = _store_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _save(store: dict) -> None:
    _store_path().write_text(json.dumps(store, indent=2), encoding="utf-8")
