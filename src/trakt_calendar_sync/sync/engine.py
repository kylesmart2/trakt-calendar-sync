"""Orchestrates one sync run: Trakt watchlist -> Google Calendar events.
Shared by the GUI's "Sync Now" button and the headless scheduled task
(cli_sync.py). Never launches an interactive auth flow itself - if either
service isn't set up yet, it raises SyncSetupError so the caller can send the
user through the setup wizard instead of hanging a background task waiting
on a browser that will never appear.
"""

from dataclasses import dataclass, field

from .. import config
from ..google_cal import auth as google_auth
from ..google_cal import calendar as google_calendar
from ..trakt.client import TraktClient
from ..trakt.exceptions import TraktAPIError, TraktAuthError


class SyncSetupError(Exception):
    """Trakt or Google isn't configured/authorized yet."""


@dataclass
class SyncResult:
    episodes_synced: int
    calendar_id: str
    removed_events: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def run_sync() -> SyncResult:
    trakt_client = _load_trakt_client()
    service = _load_google_service()

    try:
        episodes = trakt_client.get_upcoming_episodes()
    except (TraktAPIError, TraktAuthError) as e:
        return SyncResult(episodes_synced=0, calendar_id="", errors=[f"Trakt: {e}"])

    try:
        calendar_id = google_calendar.find_or_create_tv_shows_calendar(service)
    except Exception as e:  # noqa: BLE001 - report a calendar-lookup failure instead of crashing the sync
        return SyncResult(episodes_synced=0, calendar_id="", errors=[f"Google Calendar: {e}"])

    synced = 0
    errors = []
    for episode in episodes:
        try:
            google_calendar.upsert_event(service, calendar_id, episode)
            synced += 1
        except Exception as e:  # noqa: BLE001 - isolate one bad episode from the rest of the run
            errors.append(f"{episode.label}: {e}")

    try:
        removed_events = google_calendar.prune_stale_events(service, calendar_id, episodes)
    except Exception as e:  # noqa: BLE001 - a cleanup failure shouldn't hide a successful sync
        removed_events = []
        errors.append(f"Cleanup: {e}")

    return SyncResult(
        episodes_synced=synced, calendar_id=calendar_id, removed_events=removed_events, errors=errors
    )


def _load_trakt_client() -> TraktClient:
    creds = config.load_trakt_credentials()
    if creds is None:
        raise SyncSetupError("Trakt isn't set up yet - run the setup wizard first.")

    def on_tokens_refreshed(tokens):
        config.set_secret(config.SECRET_TRAKT_ACCESS_TOKEN, tokens.access_token)
        config.set_secret(config.SECRET_TRAKT_REFRESH_TOKEN, tokens.refresh_token)

    return TraktClient(
        creds["client_id"],
        creds["client_secret"],
        creds["access_token"],
        creds["refresh_token"],
        on_tokens_refreshed=on_tokens_refreshed,
    )


def _load_google_service():
    creds = google_auth.load_credentials()
    if creds is None:
        raise SyncSetupError("Google isn't authorized yet - run the setup wizard first.")
    return google_calendar.build_service(creds)
