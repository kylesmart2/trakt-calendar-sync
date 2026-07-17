"""Thin equivalent of trakt_calendar_sync.sync.engine.run_sync() for the web
app. Reuses the actual Trakt/Google Calendar logic (TraktClient, the
google_cal.calendar functions) completely unchanged; only the "where do
credentials come from" glue is written fresh here, since that's inherently
tied to storage, which differs between the native app (OS keychain) and this
one (a JSON file in the mounted volume). The orchestration shape below
deliberately mirrors sync/engine.py's run_sync() - that shape already had
its bugs found and fixed during a code review, so it's worth keeping intact
rather than re-deriving something new.
"""

from dataclasses import dataclass, field

from trakt_calendar_sync.google_cal import calendar as google_calendar
from trakt_calendar_sync.trakt.client import TraktClient
from trakt_calendar_sync.trakt.exceptions import TraktAPIError, TraktAuthError

from . import google_oauth_web, storage


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
    creds = storage.load_trakt_credentials()
    if creds is None:
        raise SyncSetupError("Trakt isn't set up yet - complete setup first.")

    def on_tokens_refreshed(tokens):
        storage.set(storage.KEY_TRAKT_ACCESS_TOKEN, tokens.access_token)
        storage.set(storage.KEY_TRAKT_REFRESH_TOKEN, tokens.refresh_token)

    return TraktClient(
        creds["client_id"],
        creds["client_secret"],
        creds["access_token"],
        creds["refresh_token"],
        on_tokens_refreshed=on_tokens_refreshed,
    )


def _load_google_service():
    creds = google_oauth_web.load_credentials()
    if creds is None:
        raise SyncSetupError("Google isn't authorized yet - complete setup first.")
    return google_calendar.build_service(creds)
