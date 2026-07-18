# Trakt Calendar Sync - Web/Docker

A containerized alternative to the native PySide6 app: a small Flask web UI
plus an in-process APScheduler job, instead of a desktop GUI and an OS-level
scheduled task. Reuses the native app's Trakt/Google Calendar logic
unchanged (see `sync_web.py`'s docstring for exactly what's reused vs. new).

This directory is fully self-contained - nothing outside `web/` is modified
by anything here, and nothing inside `web/` is required by the native app.

## Setup

The published image (`ghcr.io/kylesmart2/trakt-calendar-sync-web`) already
has the project's shared Google OAuth client baked in - same as the native
app, every user still signs in with their own Google account via the
standard consent screen.

1. From the repo root:
   ```bash
   cd web
   docker compose up -d
   ```
   This pulls `ghcr.io/kylesmart2/trakt-calendar-sync-web:latest` (built by
   [`.github/workflows/docker-publish.yml`](../.github/workflows/docker-publish.yml)
   on every push to `main`) rather than building anything locally.
2. Open `http://localhost:6969` and follow the on-screen setup (Trakt device
   code, then Google sign-in).

### Building from source instead

If you're changing `web/` code yourself and want to test it before it's
published, build locally instead of pulling:

```bash
cd web
docker compose up -d --build
```

This uses the same `build:` section already in `docker-compose.yml`, tagged
with the same image name. In that case you'll need your own Google OAuth
client (Google Cloud Console → APIs & Services → Credentials) saved as
`web/credentials.json` (see `credentials.json.example` for the shape) -
Google accepts `http://localhost:6969/oauth/callback` as a redirect URI for
a **Desktop app**-type client without needing a separate "Web application"
client.

### Image tags

`:latest` always points at whatever was most recently published - either an
ordinary push to `main` ([`docker-publish.yml`](../.github/workflows/docker-publish.yml),
also tagged with that commit's SHA), or a deliberately cut version (below).
Pulling `:latest` always gets the newest image; there's nothing to "update"
on older tags when a new one ships; they just stop being what `:latest`
points at and keep existing under their own tag until someone deletes them
from the repo's Packages page.

To cut a permanent, pinnable version instead of tracking `:latest`:

```bash
git tag web-v1.2.0
git push origin web-v1.2.0
```

This runs [`docker-publish-versioned.yml`](../.github/workflows/docker-publish-versioned.yml),
which publishes `ghcr.io/kylesmart2/trakt-calendar-sync-web:1.2.0` *and* moves
`:latest` to that same build. Pin `image:` in `docker-compose.yml` to a
specific version (e.g. `:1.2.0`) instead of `:latest` if you want a
deployment that never changes underneath you until you explicitly bump it.

Versioning here is independent of the native app's `v*` release tags (this
directory's own philosophy - see the top of this file) - use `web-v*` so the
two don't collide.

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
| `TRAKT_CALENDAR_SYNC_WEB_DATA_DIR` | `/data` | Where settings/secrets/log are stored (inside the container) |
| `TRAKT_CALENDAR_SYNC_WEB_GOOGLE_CREDENTIALS` | `web/credentials.json` | Path to the Google OAuth client (inside the container) |
| `TZ` | `UTC` if unset (`web/docker-compose.yml` ships with it defaulted to `America/New_York` instead) | Timezone the daily auto-sync's `HH:MM` and status log timestamps are interpreted in - otherwise a 9:00 schedule fires at 9:00 UTC regardless of where the host machine actually is |
| `DATA_VOLUME_NAME` | `trakt-calendar-sync-data` | *(docker-compose.yml only)* The actual Docker volume name created on the host (visible in `docker volume ls`) - not read by the app itself |

`TRAKT_CALENDAR_SYNC_WEB_DATA_DIR` and `TRAKT_CALENDAR_SYNC_WEB_GOOGLE_CREDENTIALS`
are paths *inside the container*. To point them at a specific directory on
the host instead of a named volume, bind-mount it in `docker-compose.yml` and
leave the env vars at their defaults - see the bind-mount example below.

## docker-compose.yml examples

Default (pulls the published image, named volume for persistent data) - this
is exactly what's checked into `web/docker-compose.yml`:

```yaml
services:
  trakt-calendar-sync-web:
    image: ghcr.io/kylesmart2/trakt-calendar-sync-web:latest
    build:
      context: ..
      dockerfile: web/Dockerfile
    ports:
      - "6969:6969"
    environment:
      - TZ=America/New_York
    volumes:
      - trakt-calendar-sync-data:/data
    restart: unless-stopped

volumes:
  trakt-calendar-sync-data:
    name: ${DATA_VOLUME_NAME:-trakt-calendar-sync-data}
```

`docker compose up` (or `docker compose pull`) uses the `image:` line and
pulls from GHCR; `docker compose up --build` uses the `build:` section
instead and builds from source, tagging the result with that same image
name. Both can stay in the file at once - see "Building from source instead"
above.

Set `TZ` inline as above, or export `DATA_VOLUME_NAME`/`TZ` in a `.env` file
next to `docker-compose.yml` (Compose loads it automatically) instead of
editing the file.

Bind mount instead of a named volume (data lands in a directory you choose
on the host, e.g. for easier backups):

```yaml
services:
  trakt-calendar-sync-web:
    image: ghcr.io/kylesmart2/trakt-calendar-sync-web:latest
    build:
      context: ..
      dockerfile: web/Dockerfile
    ports:
      - "6969:6969"
    environment:
      - TZ=America/New_York
    volumes:
      - /home/you/trakt-calendar-sync-data:/data
    restart: unless-stopped
```

If you're building from source instead of pulling (see above) and want your
own Google OAuth client rather than the one baked into the published image,
bind-mount it too:
`- /home/you/credentials.json:/app/web/credentials.json:ro`.

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
