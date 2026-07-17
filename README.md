# Trakt Calendar Sync

A desktop app that syncs upcoming episodes from your [Trakt.tv](https://trakt.tv)
watchlist into a dedicated Google Calendar, with a popup reminder an hour
before each episode airs.

Built for friends/family who want their Trakt watchlist on their phone's
calendar without installing Python or touching a terminal - the app packages
into a single `.exe` (Windows), `.app` (macOS), or binary (Linux).

## Features

- **Every upcoming episode**, not just the next one - a show with several
  episodes airing soon gets an event for each.
- **Automatic cleanup** - if a show drops off your watchlist (or Trakt no
  longer lists an episode you'd expect), its future calendar event is
  removed on the next sync. Past events are never touched.
- **60-minute popup reminder** on every synced event.
- **On-demand or automatic** - open the app and hit "Sync Now", or turn on
  daily auto-sync and forget about it.
- **Cross-platform scheduling** - a real OS-level scheduled task (systemd
  user timer on Linux, launchd on macOS, Task Scheduler on Windows), not a
  background process that has to stay running.

## How it works

1. **Trakt device auth** - each user creates their own free Trakt API app
   ([app.trakt.tv/settings/apps/api/new](https://app.trakt.tv/settings/apps/api/new))
   and enters its Client ID/Secret in the setup wizard. The wizard then walks
   through Trakt's OAuth *device code* flow: it shows you a short code, you
   enter it at trakt.tv/activate, and the app polls until you approve it.
2. **Google sign-in** - the app ships with one shared Google OAuth client
   (a "Desktop app" credential from Google Cloud Console), but every user
   still signs in with their own Google account via the standard consent
   screen. The app then finds-or-creates a dedicated **"TV Shows"** calendar
   in that account.
3. **Sync** - pulls every episode airing in the next 33 days (Trakt's
   calendar-endpoint limit) for shows on your watchlist, and
   creates/updates/removes events in the "TV Shows" calendar to match.
4. **Scheduling** - the "enable daily auto-sync" toggle registers a real
   scheduled task with the OS that re-runs the sync headlessly once a day,
   invoking the same packaged binary with a `--sync` flag.

Credentials never touch plaintext disk: Trakt/Google tokens and the Trakt
client secret are stored in the OS keychain (via
[`keyring`](https://pypi.org/project/keyring/)); only non-secret settings
(Trakt client ID, auto-sync schedule) live in a small JSON file.

## Using the app

First launch walks you through the setup wizard (Trakt, then Google). After
that you get the main window:

- **Sync Now** - runs a sync immediately, with a status log of what
  happened.
- **Enable daily auto-sync at `HH:MM`** - registers/removes the OS-level
  scheduled task.

## Project layout

```
src/trakt_calendar_sync/
  trakt/          Trakt device auth + API client (watchlist calendar)
  google_cal/      Google OAuth + "TV Shows" calendar/event management
  sync/           Orchestrates one sync run (used by both the GUI and CLI)
  scheduler/      Per-OS daily-task registration (systemd/launchd/schtasks)
  gui/            PySide6 setup wizard + main window
  main.py         GUI entry point (dispatches to --sync for headless runs)
  cli_sync.py     Headless entry point invoked by the OS scheduler
  config.py       Settings (JSON) + secrets (OS keychain via keyring)
resources/        Bundled Google OAuth client (credentials.json, gitignored)
packaging/        PyInstaller spec + per-OS build scripts
tests/            pytest suite (mocked - no real network/account access)
```

## Documentation

- **[BUILDING.md](BUILDING.md)** - dev environment setup, running tests, and
  packaging into a standalone executable for each OS.
- **[MAINTENANCE.md](MAINTENANCE.md)** - rotating credentials, clearing
  cached tokens, managing the scheduled task, and other upkeep.
- **[packaging/INSTALL_MACOS.md](packaging/INSTALL_MACOS.md)** - first-launch
  instructions to hand to anyone you send the (unsigned) macOS build to.

## Status

Functional and in active use: Trakt device auth, Google Calendar sync with
cleanup, cross-platform scheduling, and the PySide6 GUI are all implemented
and tested (mocked unit tests plus manual end-to-end verification against
real Trakt/Google accounts). macOS/Windows builds are unsigned - see
BUILDING.md.
