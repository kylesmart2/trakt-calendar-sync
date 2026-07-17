# Trakt Calendar Sync - Web/Docker

A containerized alternative to the native PySide6 app: a small Flask web UI
plus an in-process APScheduler job, instead of a desktop GUI and an OS-level
scheduled task. Reuses the native app's Trakt/Google Calendar logic
unchanged (see `sync_web.py`'s docstring for exactly what's reused vs. new).

This directory is fully self-contained - nothing outside `web/` is modified
by anything here, and nothing inside `web/` is required by the native app.

## Setup

1. Get a Google OAuth client (Google Cloud Console → APIs & Services →
   Credentials) and save it as `web/credentials.json` (see
   `credentials.json.example` for the shape). Confirmed working: the same
   **Desktop app**-type client the native app uses
   (`resources/credentials.json`) - Google accepts
   `http://localhost:6969/oauth/callback` as a redirect URI for it without
   needing a separate "Web application" client.
2. From the repo root:
   ```bash
   cd web
   docker compose up --build
   ```
3. Open `http://localhost:6969` and follow the on-screen setup (Trakt device
   code, then Google sign-in).

Trakt setup can reuse the exact same Trakt API app (Client ID/Secret) you
already created for the native app - it uses the same device-code flow
either way, which never involves a redirect URI at all.

Google sign-in only works over plain HTTP here because
`google_oauth_web.py` sets `OAUTHLIB_INSECURE_TRANSPORT=1` - see that
module's docstring for why that's safe for a localhost-only deployment but
worth revisiting if this ever sits behind a real public endpoint.

## Persistent data

Everything that needs to survive a restart/rebuild - Trakt credentials,
Google tokens, the auto-sync schedule, the sync log - lives in `/data`
inside the container, mounted as a named Docker volume
(`trakt-calendar-sync-data`) by `docker-compose.yml`. Removing the container
(`docker compose down`) keeps the volume; `docker compose down -v` deletes it.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `TRAKT_CALENDAR_SYNC_WEB_DATA_DIR` | `/data` | Where settings/secrets/log are stored |
| `TRAKT_CALENDAR_SYNC_WEB_GOOGLE_CREDENTIALS` | `web/credentials.json` | Path to the Google OAuth client |

## Running locally without Docker (dev)

```bash
cd web
python3 -m venv .venv
source .venv/bin/activate
pip install --no-deps -e ..     # the core trakt_calendar_sync package, no PySide6
pip install -r requirements.txt
pip install pytest              # for running tests/
TRAKT_CALENDAR_SYNC_WEB_DATA_DIR=./devdata python -m app
```

## Tests

```bash
cd web
pytest tests/
```

Kept under `web/tests/` rather than the root `tests/` directory, so the two
test suites (and their differing dependencies - Flask/APScheduler vs.
PySide6) stay fully independent.
