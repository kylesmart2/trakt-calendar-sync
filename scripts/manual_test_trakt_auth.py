"""Exercise the real Trakt device auth flow from the terminal, no GUI needed.

Usage:
    TRAKT_CLIENT_ID=xxx TRAKT_CLIENT_SECRET=yyy python scripts/manual_test_trakt_auth.py

Create a client_id/secret at https://app.trakt.tv/settings/apps/api/new first
(any redirect_uri works, e.g. urn:ietf:wg:oauth:2.0:oob - device auth ignores it).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from trakt_calendar_sync.trakt.auth import TraktDeviceAuth
from trakt_calendar_sync.trakt.client import TraktClient
from trakt_calendar_sync.trakt.exceptions import TraktAuthError


def main():
    client_id = os.environ["TRAKT_CLIENT_ID"]
    client_secret = os.environ["TRAKT_CLIENT_SECRET"]

    auth = TraktDeviceAuth(client_id, client_secret)
    device_code = auth.request_device_code()

    print(f"\nGo to {device_code.verification_url} and enter code: {device_code.user_code}\n")
    print(f"Waiting up to {device_code.expires_in}s (polling every {device_code.interval}s)...")

    try:
        tokens = auth.poll_for_tokens(
            device_code, on_wait=lambda remaining: print(f"  ...still waiting ({remaining}s left)")
        )
    except TraktAuthError as e:
        print(f"Auth failed: {e}")
        return

    print(f"\nAuthorized. access_token={tokens.access_token[:10]}... refresh_token={tokens.refresh_token[:10]}...")

    client = TraktClient(client_id, client_secret, tokens.access_token, tokens.refresh_token)
    upcoming = client.get_upcoming_episodes()

    print(f"\n{len(upcoming)} upcoming episode(s) from your watchlist:")
    for ep in upcoming:
        print(f"  {ep.air_date.isoformat()}  {ep.show_title} S{ep.season:02d}E{ep.episode_number:02d} - {ep.episode_title}")


if __name__ == "__main__":
    main()
