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
   `credentials.json.example` for the shape). This can be the same file as
   the native app's `resources/credentials.json` - or a fresh one if you hit
   the OAuth-client-type issue below.
2. From the repo root:
   ```bash
   cd web
   docker compose up --build
   ```
3. Open `http://localhost:6969` and follow the on-screen setup (Trakt device
   code, then Google sign-in).

## A known open question

The Google OAuth client type matters here. `resources/credentials.json` (native
app) is a **Desktop app** client, which uses a *loopback* flow with a
dynamically chosen port - not the fixed `http://localhost:6969/oauth/callback`
this app needs. Google's loopback spec (RFC 8252) is lenient about Desktop
clients using arbitrary localhost ports/paths without pre-registration, so
the same file *may* just work - but this hasn't been verified. If sign-in
fails with a redirect_uri mismatch, create a **Web application**-type OAuth
client in Google Cloud Console instead, with
`http://localhost:6969/oauth/callback` added to its Authorized redirect URIs,
and use that as `web/credentials.json`.

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
