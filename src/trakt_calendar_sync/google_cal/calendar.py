"""Creates/finds the dedicated "TV Shows" calendar and upserts episode events
into it. Re-syncing updates existing events (matched by a stable key stored
in extendedProperties.private) instead of creating duplicates.
"""

from datetime import datetime, timedelta, timezone

from dateutil import parser as date_parser
from googleapiclient.discovery import build

CALENDAR_NAME = "TV Shows"
CALENDAR_DESCRIPTION = "Upcoming episodes from your Trakt watchlist (managed by Trakt Calendar Sync)"
EPISODE_KEY_PROPERTY = "trakt_calendar_sync_episode_id"
DEFAULT_RUNTIME_MINUTES = 30


def build_service(credentials):
    # static_discovery=False fetches the API discovery doc from Google at
    # call time instead of reading it from googleapiclient's bundled JSON -
    # PyInstaller doesn't reliably package that data file, and the app needs
    # network access anyway to talk to the Calendar API.
    return build("calendar", "v3", credentials=credentials, cache_discovery=False, static_discovery=False)


def find_or_create_tv_shows_calendar(service) -> str:
    page_token = None
    while True:
        response = service.calendarList().list(pageToken=page_token).execute()
        for entry in response.get("items", []):
            if entry.get("summary") == CALENDAR_NAME:
                return entry["id"]
        page_token = response.get("nextPageToken")
        if not page_token:
            break

    created = service.calendars().insert(
        body={"summary": CALENDAR_NAME, "description": CALENDAR_DESCRIPTION}
    ).execute()
    return created["id"]


def upsert_event(service, calendar_id: str, episode) -> None:
    key = _episode_key(episode)
    existing = (
        service.events()
        .list(calendarId=calendar_id, privateExtendedProperty=f"{EPISODE_KEY_PROPERTY}={key}")
        .execute()
    )
    items = existing.get("items", [])
    body = _event_body(episode, key)

    if items:
        service.events().update(calendarId=calendar_id, eventId=items[0]["id"], body=body).execute()
    else:
        service.events().insert(calendarId=calendar_id, body=body).execute()


def prune_stale_events(service, calendar_id: str, current_episodes) -> list:
    """Deletes previously-synced *future* events whose episode isn't in the
    current upcoming set - e.g. a show dropped off the watchlist. Only ever
    touches events with a start time still ahead of now: past events are
    left alone even if they've aged out of the lookahead window, since
    nobody asked for calendar history to be deleted - a show with only past
    synced events is simply left untouched. Only considers events this app
    created (identified by EPISODE_KEY_PROPERTY), never anything else a user
    might add to the calendar directly. Returns the removed events'
    summaries (e.g. "Severance - S02E05") for status reporting.
    """
    current_keys = {_episode_key(episode) for episode in current_episodes}
    now = datetime.now(timezone.utc)
    removed = []
    for event in _list_synced_events(service, calendar_id):
        key = event["extendedProperties"]["private"][EPISODE_KEY_PROPERTY]
        if key in current_keys:
            continue
        if date_parser.isoparse(event["start"]["dateTime"]) <= now:
            continue
        service.events().delete(calendarId=calendar_id, eventId=event["id"]).execute()
        removed.append(event.get("summary", key))
    return removed


def _list_synced_events(service, calendar_id: str) -> list:
    events = []
    page_token = None
    while True:
        response = service.events().list(calendarId=calendar_id, pageToken=page_token).execute()
        events.extend(
            item
            for item in response.get("items", [])
            if item.get("extendedProperties", {}).get("private", {}).get(EPISODE_KEY_PROPERTY)
        )
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return events


def _episode_key(episode) -> str:
    trakt_id = episode.show_ids.get("trakt")
    return f"{trakt_id}-s{episode.season}e{episode.episode_number}"


def _event_body(episode, key: str) -> dict:
    start = episode.air_date
    end = start + timedelta(minutes=episode.runtime or DEFAULT_RUNTIME_MINUTES)
    return {
        "summary": f"{episode.show_title} - S{episode.season:02d}E{episode.episode_number:02d}",
        "description": episode.episode_title,
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": 60}],
        },
        "extendedProperties": {"private": {EPISODE_KEY_PROPERTY: key}},
    }
