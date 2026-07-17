from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from trakt_calendar_sync import config
from trakt_calendar_sync.google_cal import auth as google_auth
from trakt_calendar_sync.google_cal import calendar as google_calendar
from trakt_calendar_sync.sync import engine
from trakt_calendar_sync.trakt.client import TraktClient, UpcomingEpisode
from trakt_calendar_sync.trakt.exceptions import TraktAPIError


def _episode(show_title="Severance", episode_number=5) -> UpcomingEpisode:
    return UpcomingEpisode(
        show_title=show_title,
        show_ids={"trakt": 1},
        season=2,
        episode_number=episode_number,
        episode_title="Ep",
        air_date=datetime(2026, 7, 20, tzinfo=timezone.utc),
        runtime=55,
    )


def _configure_trakt(monkeypatch):
    monkeypatch.setattr(
        config, "load_settings", lambda: {config.SETTING_TRAKT_CLIENT_ID: "cid"}
    )
    secrets = {
        config.SECRET_TRAKT_CLIENT_SECRET: "csecret",
        config.SECRET_TRAKT_ACCESS_TOKEN: "at",
        config.SECRET_TRAKT_REFRESH_TOKEN: "rt",
    }
    monkeypatch.setattr(config, "get_secret", lambda key: secrets.get(key))


def _configure_google(monkeypatch, calendar_id="cal-1"):
    monkeypatch.setattr(google_auth, "load_credentials", lambda: MagicMock())
    monkeypatch.setattr(google_calendar, "build_service", lambda creds: MagicMock())
    monkeypatch.setattr(
        google_calendar, "find_or_create_tv_shows_calendar", lambda service: calendar_id
    )
    monkeypatch.setattr(google_calendar, "prune_stale_events", lambda service, cal_id, episodes: [])


def test_run_sync_raises_setup_error_when_trakt_not_configured(monkeypatch):
    monkeypatch.setattr(config, "load_settings", lambda: {})
    monkeypatch.setattr(config, "get_secret", lambda key: None)

    with pytest.raises(engine.SyncSetupError):
        engine.run_sync()


def test_run_sync_raises_setup_error_when_google_not_authorized(monkeypatch):
    _configure_trakt(monkeypatch)
    monkeypatch.setattr(google_auth, "load_credentials", lambda: None)

    with pytest.raises(engine.SyncSetupError):
        engine.run_sync()


def test_run_sync_success(monkeypatch):
    _configure_trakt(monkeypatch)
    _configure_google(monkeypatch)

    episodes = [_episode("Severance", 5), _episode("Other Show", 1)]
    monkeypatch.setattr(TraktClient, "get_upcoming_episodes", lambda self: episodes)
    upserted = []
    monkeypatch.setattr(
        google_calendar, "upsert_event", lambda service, cal_id, ep: upserted.append((cal_id, ep))
    )

    result = engine.run_sync()

    assert result.ok
    assert result.episodes_synced == 2
    assert result.calendar_id == "cal-1"
    assert [ep for _, ep in upserted] == episodes


def test_run_sync_reports_trakt_api_error_without_touching_calendar(monkeypatch):
    _configure_trakt(monkeypatch)
    _configure_google(monkeypatch)

    def raise_error(self):
        raise TraktAPIError(500, "boom")

    monkeypatch.setattr(TraktClient, "get_upcoming_episodes", raise_error)
    find_or_create = MagicMock()
    monkeypatch.setattr(google_calendar, "find_or_create_tv_shows_calendar", find_or_create)

    result = engine.run_sync()

    assert not result.ok
    assert result.episodes_synced == 0
    assert "boom" in result.errors[0]
    find_or_create.assert_not_called()


def test_run_sync_isolates_a_single_bad_episode(monkeypatch):
    _configure_trakt(monkeypatch)
    _configure_google(monkeypatch)

    episodes = [_episode("Bad Show", 1), _episode("Good Show", 1)]
    monkeypatch.setattr(TraktClient, "get_upcoming_episodes", lambda self: episodes)

    def upsert(service, cal_id, ep):
        if ep.show_title == "Bad Show":
            raise RuntimeError("quota exceeded")

    monkeypatch.setattr(google_calendar, "upsert_event", upsert)

    result = engine.run_sync()

    assert result.episodes_synced == 1
    assert len(result.errors) == 1
    assert "Bad Show" in result.errors[0]
    assert "quota exceeded" in result.errors[0]


def test_run_sync_reports_removed_events(monkeypatch):
    _configure_trakt(monkeypatch)
    _configure_google(monkeypatch)
    monkeypatch.setattr(TraktClient, "get_upcoming_episodes", lambda self: [])
    monkeypatch.setattr(
        google_calendar,
        "prune_stale_events",
        lambda service, cal_id, episodes: ["American Horror Story - S13E01"],
    )

    result = engine.run_sync()

    assert result.ok
    assert result.removed_events == ["American Horror Story - S13E01"]


def test_run_sync_prune_failure_reported_without_losing_synced_count(monkeypatch):
    _configure_trakt(monkeypatch)
    _configure_google(monkeypatch)
    monkeypatch.setattr(TraktClient, "get_upcoming_episodes", lambda self: [_episode()])
    monkeypatch.setattr(google_calendar, "upsert_event", lambda service, cal_id, ep: None)

    def prune(service, cal_id, episodes):
        raise RuntimeError("calendar API down")

    monkeypatch.setattr(google_calendar, "prune_stale_events", prune)

    result = engine.run_sync()

    assert not result.ok
    assert result.episodes_synced == 1
    assert result.removed_events == []
    assert any("Cleanup" in e and "calendar API down" in e for e in result.errors)


def test_run_sync_persists_refreshed_trakt_tokens(monkeypatch):
    _configure_trakt(monkeypatch)
    _configure_google(monkeypatch)
    monkeypatch.setattr(TraktClient, "get_upcoming_episodes", lambda self: [])

    saved = {}
    monkeypatch.setattr(config, "set_secret", lambda key, value: saved.setdefault(key, value))

    client = engine._load_trakt_client()
    fake_tokens = MagicMock(access_token="new-at", refresh_token="new-rt")
    client._on_tokens_refreshed(fake_tokens)

    assert saved[config.SECRET_TRAKT_ACCESS_TOKEN] == "new-at"
    assert saved[config.SECRET_TRAKT_REFRESH_TOKEN] == "new-rt"
