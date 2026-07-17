"""Thin wrapper around the parts of the Trakt API this app needs: every
upcoming episode airing for shows on the user's watchlist.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Callable

import requests
from dateutil import parser as date_parser

from .auth import API_BASE, REQUEST_TIMEOUT, TraktDeviceAuth, TraktTokens
from .exceptions import TraktAPIError

# Trakt caps the calendar endpoints' `days` window at 33 -
# https://docs.trakt.tv/reference/getcalendarsshows
MAX_CALENDAR_DAYS = 33


@dataclass
class UpcomingEpisode:
    show_title: str
    show_ids: dict
    season: int
    episode_number: int
    episode_title: str
    air_date: datetime  # tz-aware, UTC
    runtime: int | None

    @property
    def label(self) -> str:
        """The one canonical "which episode is this" string shown to users -
        in calendar event titles and in sync error/status messages alike."""
        return f"{self.show_title} - S{self.season:02d}E{self.episode_number:02d}"


class TraktClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        access_token: str,
        refresh_token: str,
        on_tokens_refreshed: Callable[[TraktTokens], None] | None = None,
        session: requests.Session | None = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = access_token
        self.refresh_token = refresh_token
        self._on_tokens_refreshed = on_tokens_refreshed
        self._session = session or requests.Session()
        self._device_auth = TraktDeviceAuth(client_id, client_secret, session=self._session)

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "trakt-api-version": "2",
            "trakt-api-key": self.client_id,
            "Authorization": f"Bearer {self.access_token}",
        }

    def _request(self, method: str, path: str, *, retry_on_401: bool = True, **kwargs) -> requests.Response:
        response = self._session.request(
            method,
            f"{API_BASE}{path}",
            headers=self._headers(),
            timeout=REQUEST_TIMEOUT,
            **kwargs,
        )
        if response.status_code == 401 and retry_on_401:
            self._refresh()
            return self._request(method, path, retry_on_401=False, **kwargs)
        if not response.ok:
            raise TraktAPIError(response.status_code, response.text)
        return response

    def _refresh(self) -> None:
        tokens = self._device_auth.refresh_tokens(self.refresh_token)
        self.access_token = tokens.access_token
        self.refresh_token = tokens.refresh_token
        if self._on_tokens_refreshed is not None:
            self._on_tokens_refreshed(tokens)

    def get_upcoming_episodes(self, days: int = MAX_CALENDAR_DAYS) -> list[UpcomingEpisode]:
        """Every episode airing in the next `days` days for shows on the
        watchlist - one entry per episode, so a show with several upcoming
        airings appears multiple times (unlike /shows/:id/next_episode,
        which only ever returns the single next one).

        ignore_watched/ignore_collected narrow Trakt's "my shows" calendar
        (which by default also includes watched/collected shows) down to
        just what's on the watchlist.
        """
        start_date = date.today().isoformat()
        days = min(days, MAX_CALENDAR_DAYS)
        response = self._request(
            "GET",
            f"/calendars/my/shows/{start_date}/{days}",
            params={"extended": "full", "ignore_watched": "true", "ignore_collected": "true"},
        )

        upcoming = [
            UpcomingEpisode(
                show_title=entry["show"]["title"],
                show_ids=entry["show"]["ids"],
                season=entry["episode"]["season"],
                episode_number=entry["episode"]["number"],
                episode_title=entry["episode"].get("title") or f"Episode {entry['episode']['number']}",
                air_date=date_parser.isoparse(entry["first_aired"]),
                runtime=entry["episode"].get("runtime"),
            )
            for entry in response.json()
        ]
        upcoming.sort(key=lambda ep: ep.air_date)
        return upcoming
