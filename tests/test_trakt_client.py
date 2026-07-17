from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

from trakt_calendar_sync.trakt.client import MAX_CALENDAR_DAYS, TraktClient, UpcomingEpisode
from trakt_calendar_sync.trakt.exceptions import TraktAPIError


def _response(status_code=200, json_data=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.ok = 200 <= status_code < 300
    resp.json.return_value = json_data if json_data is not None else []
    resp.text = "error body"
    return resp


def _calendar_entry(
    show_title="Severance",
    trakt_id=1,
    season=2,
    number=5,
    title="Ep",
    first_aired="2026-07-20T21:00:00.000Z",
    runtime=55,
):
    return {
        "first_aired": first_aired,
        "episode": {"season": season, "number": number, "title": title, "runtime": runtime},
        "show": {"title": show_title, "ids": {"trakt": trakt_id, "slug": show_title.lower()}},
    }


@pytest.fixture
def client():
    return TraktClient("cid", "csecret", "at", "rt", session=MagicMock())


def test_upcoming_episode_label_matches_calendar_event_and_error_message_format():
    episode = UpcomingEpisode(
        show_title="Severance",
        show_ids={"trakt": 1},
        season=2,
        episode_number=5,
        episode_title="Ep",
        air_date=datetime(2026, 7, 20, 21, 0, tzinfo=timezone.utc),
        runtime=55,
    )

    assert episode.label == "Severance - S02E05"


def test_get_upcoming_episodes_requests_calendar_with_today_and_watchlist_filters(client, monkeypatch):
    monkeypatch.setattr(
        "trakt_calendar_sync.trakt.client.date", MagicMock(today=lambda: date(2026, 7, 17))
    )
    client._session.request.return_value = _response(json_data=[])

    client.get_upcoming_episodes()

    args, kwargs = client._session.request.call_args
    assert args[0] == "GET"
    assert args[1] == "https://api.trakt.tv/calendars/my/shows/2026-07-17/33"
    assert kwargs["params"] == {"extended": "full", "ignore_watched": "true", "ignore_collected": "true"}


def test_get_upcoming_episodes_caps_days_at_trakt_maximum(client, monkeypatch):
    monkeypatch.setattr(
        "trakt_calendar_sync.trakt.client.date", MagicMock(today=lambda: date(2026, 7, 17))
    )
    client._session.request.return_value = _response(json_data=[])

    client.get_upcoming_episodes(days=999)

    _, url = client._session.request.call_args.args
    assert url.endswith(f"/{MAX_CALENDAR_DAYS}")


def test_get_upcoming_episodes_returns_every_episode_not_just_the_next(client):
    client._session.request.return_value = _response(
        json_data=[
            _calendar_entry(number=5, first_aired="2026-07-20T21:00:00.000Z"),
            _calendar_entry(number=6, first_aired="2026-07-27T21:00:00.000Z"),
            _calendar_entry(number=7, first_aired="2026-08-03T21:00:00.000Z"),
        ]
    )

    episodes = client.get_upcoming_episodes()

    assert len(episodes) == 3
    assert [ep.episode_number for ep in episodes] == [5, 6, 7]
    assert all(ep.show_title == "Severance" for ep in episodes)


def test_get_upcoming_episodes_sorts_across_shows_by_air_date(client):
    client._session.request.return_value = _response(
        json_data=[
            _calendar_entry(show_title="B Show", trakt_id=2, first_aired="2026-08-01T00:00:00.000Z"),
            _calendar_entry(show_title="A Show", trakt_id=1, first_aired="2026-07-18T00:00:00.000Z"),
        ]
    )

    episodes = client.get_upcoming_episodes()

    assert [ep.show_title for ep in episodes] == ["A Show", "B Show"]


def test_get_upcoming_episodes_defaults_missing_title_and_runtime(client):
    entry = _calendar_entry()
    del entry["episode"]["title"]
    del entry["episode"]["runtime"]
    client._session.request.return_value = _response(json_data=[entry])

    episodes = client.get_upcoming_episodes()

    assert episodes[0].episode_title == "Episode 5"
    assert episodes[0].runtime is None


def test_get_upcoming_episodes_raises_on_api_error(client):
    client._session.request.return_value = _response(status_code=500)

    with pytest.raises(TraktAPIError):
        client.get_upcoming_episodes()


def test_request_refreshes_token_once_on_401_then_retries(client, monkeypatch):
    client._session.request.side_effect = [_response(status_code=401), _response(json_data=[])]

    refreshed_tokens = MagicMock(access_token="new-at", refresh_token="new-rt")
    monkeypatch.setattr(client._device_auth, "refresh_tokens", MagicMock(return_value=refreshed_tokens))
    on_refreshed = MagicMock()
    client._on_tokens_refreshed = on_refreshed

    episodes = client.get_upcoming_episodes()

    assert episodes == []
    assert client.access_token == "new-at"
    assert client.refresh_token == "new-rt"
    on_refreshed.assert_called_once_with(refreshed_tokens)
    assert client._session.request.call_count == 2
