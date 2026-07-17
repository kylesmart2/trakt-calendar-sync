from datetime import datetime, timezone
from unittest.mock import MagicMock

from trakt_calendar_sync.google_cal import calendar
from trakt_calendar_sync.trakt.client import UpcomingEpisode


def _episode(**overrides) -> UpcomingEpisode:
    defaults = dict(
        show_title="Severance",
        show_ids={"trakt": 123, "slug": "severance"},
        season=2,
        episode_number=5,
        episode_title="The Trojan's Horse",
        air_date=datetime(2026, 7, 20, 21, 0, tzinfo=timezone.utc),
        runtime=55,
    )
    defaults.update(overrides)
    return UpcomingEpisode(**defaults)


def _service_with_calendar_list(items, next_page_token=None):
    service = MagicMock()
    service.calendarList().list().execute.return_value = {
        "items": items,
        **({"nextPageToken": next_page_token} if next_page_token else {}),
    }
    return service


def test_find_or_create_returns_existing_calendar():
    service = _service_with_calendar_list([{"summary": "TV Shows", "id": "cal-123"}])

    calendar_id = calendar.find_or_create_tv_shows_calendar(service)

    assert calendar_id == "cal-123"
    service.calendars().insert.assert_not_called()


def test_find_or_create_creates_when_missing():
    service = _service_with_calendar_list([{"summary": "Other Calendar", "id": "cal-999"}])
    service.calendars().insert().execute.return_value = {"id": "cal-new"}

    calendar_id = calendar.find_or_create_tv_shows_calendar(service)

    assert calendar_id == "cal-new"
    service.calendars().insert.assert_called_with(
        body={"summary": calendar.CALENDAR_NAME, "description": calendar.CALENDAR_DESCRIPTION}
    )


def test_upsert_event_inserts_when_no_existing_event():
    service = MagicMock()
    service.events().list().execute.return_value = {"items": []}

    calendar.upsert_event(service, "cal-123", _episode())

    service.events().insert.assert_called_once()
    _, kwargs = service.events().insert.call_args
    assert kwargs["calendarId"] == "cal-123"
    body = kwargs["body"]
    assert body["summary"] == "Severance - S02E05"
    assert body["start"] == {"dateTime": "2026-07-20T21:00:00+00:00"}
    assert body["end"] == {"dateTime": "2026-07-20T21:55:00+00:00"}
    assert body["reminders"] == {
        "useDefault": False,
        "overrides": [{"method": "popup", "minutes": 60}],
    }
    assert body["extendedProperties"]["private"][calendar.EPISODE_KEY_PROPERTY] == "123-s2e5"
    service.events().update.assert_not_called()


def test_upsert_event_updates_when_already_synced():
    service = MagicMock()
    service.events().list().execute.return_value = {"items": [{"id": "evt-existing"}]}

    calendar.upsert_event(service, "cal-123", _episode())

    service.events().update.assert_called_once()
    _, kwargs = service.events().update.call_args
    assert kwargs["calendarId"] == "cal-123"
    assert kwargs["eventId"] == "evt-existing"
    service.events().insert.assert_not_called()


def test_upsert_event_uses_default_runtime_when_missing():
    service = MagicMock()
    service.events().list().execute.return_value = {"items": []}

    calendar.upsert_event(service, "cal-123", _episode(runtime=None))

    _, kwargs = service.events().insert.call_args
    assert kwargs["body"]["end"] == {"dateTime": "2026-07-20T21:30:00+00:00"}


FUTURE = "2099-01-01T00:00:00+00:00"
PAST = "2000-01-01T00:00:00+00:00"


def _synced_event(key: str, event_id: str, start: str = FUTURE, summary: str = "Show - S01E01") -> dict:
    return {
        "id": event_id,
        "summary": summary,
        "start": {"dateTime": start},
        "extendedProperties": {"private": {calendar.EPISODE_KEY_PROPERTY: key}},
    }


def test_prune_stale_events_deletes_future_events_not_in_current_set():
    service = MagicMock()
    service.events().list().execute.return_value = {
        "items": [
            _synced_event("123-s2e5", "evt-keep", summary="Severance - S02E05"),
            _synced_event("999-s1e1", "evt-stale", summary="American Horror Story - S13E01"),
        ]
    }
    current = [_episode(show_ids={"trakt": 123, "slug": "severance"}, season=2, episode_number=5)]

    removed = calendar.prune_stale_events(service, "cal-123", current)

    assert removed == ["American Horror Story - S13E01"]
    service.events().delete.assert_called_once_with(calendarId="cal-123", eventId="evt-stale")


def test_prune_stale_events_keeps_events_still_current():
    service = MagicMock()
    service.events().list().execute.return_value = {"items": [_synced_event("123-s2e5", "evt-keep")]}
    current = [_episode(show_ids={"trakt": 123, "slug": "severance"}, season=2, episode_number=5)]

    removed = calendar.prune_stale_events(service, "cal-123", current)

    assert removed == []
    service.events().delete.assert_not_called()


def test_prune_stale_events_never_deletes_past_events_even_if_stale():
    service = MagicMock()
    service.events().list().execute.return_value = {
        "items": [_synced_event("999-s1e1", "evt-past", start=PAST)]
    }

    removed = calendar.prune_stale_events(service, "cal-123", [])

    assert removed == []
    service.events().delete.assert_not_called()


def test_prune_stale_events_ignores_events_without_episode_key_property():
    service = MagicMock()
    service.events().list().execute.return_value = {
        "items": [
            {"id": "evt-manual", "extendedProperties": {"private": {"other_key": "x"}}},
            {"id": "evt-bare"},
        ]
    }

    removed = calendar.prune_stale_events(service, "cal-123", [])

    assert removed == []
    service.events().delete.assert_not_called()


def test_prune_stale_events_paginates_through_all_events():
    service = MagicMock()
    service.events().list().execute.side_effect = [
        {"items": [_synced_event("stale-1", "evt-1", summary="Show A - S01E01")], "nextPageToken": "p2"},
        {"items": [_synced_event("stale-2", "evt-2", summary="Show B - S01E01")]},
    ]

    removed = calendar.prune_stale_events(service, "cal-123", [])

    assert removed == ["Show A - S01E01", "Show B - S01E01"]
