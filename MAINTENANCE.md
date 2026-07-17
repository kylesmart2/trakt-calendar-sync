# Maintenance & Upkeep

Practical runbook for the recurring things that come up after the initial
build: rotating credentials, clearing a stuck token, managing the scheduled
task, and troubleshooting.

## Rotating the shared Google OAuth client (`resources/credentials.json`)

Do this if the client secret leaks, or your organization requires periodic
rotation.

1. Go to Google Cloud Console → **APIs & Services → Credentials**.
2. Find the **Desktop app** OAuth 2.0 Client ID this project uses.
3. Either **Reset secret** on it, or delete it and create a fresh Desktop-app
   client (name it clearly, e.g. "Trakt Calendar Sync").
4. Download the new client JSON and overwrite `resources/credentials.json`.
5. Rebuild for each platform (see [BUILDING.md](BUILDING.md)) and
   redistribute.
6. **Everyone's already-cached Google token stops working once the secret
   changes** - Google's token-refresh call requires the client secret, so a
   changed secret invalidates every previously-issued refresh token tied to
   it. No manual cleanup needed on each user's machine, though:
   `google_cal.auth.load_credentials()` already detects the failed refresh,
   returns `None`, and the app will fall back to showing the Google sign-in
   step again on next launch.
7. Leave the old client visible in Cloud Console for a while in case an old
   build is still out there, then delete it once you're confident nobody
   needs it.

## Rotating a user's Trakt API app

Each user creates and owns their own Trakt Client ID/Secret, so this is
entirely self-service - there's nothing for you to rotate centrally:

1. They go to <https://app.trakt.tv/settings/apps/api>, delete or regenerate
   their app.
2. They re-enter the new Client ID/Secret on the wizard's Trakt page and
   reconnect. (There's no dedicated "forget Trakt" button today - the stored
   client ID/secret/tokens just get overwritten by whatever they enter next
   and a fresh device-auth flow.)

## Manually clearing cached credentials

Secrets live in the OS keychain via `keyring`, under service name
`trakt-calendar-sync`. Non-secret settings (Trakt client ID, auto-sync
schedule) live in a small JSON file:

| OS      | Settings path                                              |
|---------|--------------------------------------------------------------|
| Linux   | `~/.config/TraktCalendarSync/settings.json`                  |
| macOS   | `~/Library/Application Support/TraktCalendarSync/settings.json` |
| Windows | `%LOCALAPPDATA%\TraktCalendarSync\settings.json`              |

To fully reset one user's setup (e.g. a corrupted token, or wiping a test
machine), from a Python shell with the venv active:

```python
from trakt_calendar_sync import config
config.delete_secret(config.SECRET_TRAKT_CLIENT_SECRET)
config.delete_secret(config.SECRET_TRAKT_ACCESS_TOKEN)
config.delete_secret(config.SECRET_TRAKT_REFRESH_TOKEN)
config.delete_secret(config.SECRET_GOOGLE_TOKEN)
```

Or remove them by hand:

- **Linux**: Seahorse/GNOME Keyring (or `secret-tool`) - look for service
  `trakt-calendar-sync`.
- **macOS**: Keychain Access - search `trakt-calendar-sync`.
- **Windows**: Credential Manager → Generic Credentials.

## Managing the daily auto-sync schedule

The GUI checkbox is the normal way to enable/disable this. To inspect or
remove it directly:

**Linux (systemd --user timer):**

```bash
systemctl --user status trakt-calendar-sync.timer
systemctl --user list-timers trakt-calendar-sync.timer
journalctl --user -u trakt-calendar-sync.service   # sync run logs
systemctl --user disable --now trakt-calendar-sync.timer   # remove
```

**macOS (launchd user agent):**

```bash
launchctl list | grep traktcalendarsync
cat ~/Library/Logs/trakt-calendar-sync.log          # sync run logs
launchctl unload -w ~/Library/LaunchAgents/com.traktcalendarsync.sync.plist  # remove
```

**Windows (Task Scheduler):**

```powershell
schtasks /query /tn TraktCalendarSync
schtasks /delete /tn TraktCalendarSync /f
```

Logs show up in Task Scheduler's own history for that task (Task Scheduler
→ find the task → History tab).

## Updating dependencies

```bash
pip list --outdated
```

Bump versions in `pyproject.toml`, reinstall (`pip install -e ".[dev]"`),
rerun the full test suite, and rebuild/spot-check on each platform before
shipping a new release - version bumps in `PySide6` or
`google-api-python-client` in particular have changed PyInstaller's
bundling behavior before (see BUILDING.md's packaging gotchas).

## If the Trakt "create an app" link 404s again

Trakt has changed this URL before - `gui/setup_wizard.py`'s
`TRAKT_NEW_APP_URL` currently points at
`https://app.trakt.tv/settings/apps/api/new`. If users report a 404, check
<https://app.trakt.tv/settings/apps/api> directly (click the **+** icon
there) for the current flow, and update `TRAKT_NEW_APP_URL` plus the
matching comment in `scripts/manual_test_trakt_auth.py`.

## Trakt calendar lookahead window

`trakt/client.py`'s `MAX_CALENDAR_DAYS = 33` is Trakt's documented cap on
the `days` parameter for `/calendars/my/shows`. If Trakt changes that limit,
update the constant - `get_upcoming_episodes()` already clamps any
caller-requested value down to it, so nothing else needs to change.

## Transient Trakt-side staleness

Trakt's calendar endpoint can lag a few minutes behind a watchlist change
(add/remove a show) - this has been observed in practice and is on Trakt's
side, not this app's. If a sync doesn't reflect a just-made watchlist
change, running Sync Now again shortly after usually resolves it.
