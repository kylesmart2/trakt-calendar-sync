"""Exercise the real Google OAuth + calendar flow from the terminal.

Drop your Google Cloud "Desktop app" OAuth client at resources/credentials.json
(see resources/credentials.json.example for the shape) before running this.

Usage:
    python scripts/manual_test_google_calendar.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from trakt_calendar_sync.google_cal import auth, calendar


def main():
    creds = auth.load_credentials()
    if creds is None:
        print("No cached credentials found - opening the browser to sign in...")
        creds = auth.run_authorization_flow()
    else:
        print("Using cached credentials.")

    service = calendar.build_service(creds)
    calendar_id = calendar.find_or_create_tv_shows_calendar(service)
    print(f"'TV Shows' calendar id: {calendar_id}")


if __name__ == "__main__":
    main()
