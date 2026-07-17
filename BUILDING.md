# Building Trakt Calendar Sync

## Requirements

- **Python 3.10+**. Some OSes ship an older stub as `python3` (macOS's
  Command Line Tools pin `/usr/bin/python3` at 3.9.6) - install a newer
  version separately if needed, e.g. `brew install python@3.12` on macOS.
- **`resources/credentials.json`** - the shared Google OAuth "Desktop app"
  client (see `resources/credentials.json.example` for the shape). This is
  gitignored and must be created from your own Google Cloud Console project
  before packaging - the build scripts refuse to run without it.

## Dev environment setup

```bash
python3 -m venv .venv
source .venv/bin/activate        # .venv\Scripts\activate on Windows
pip install --upgrade pip
pip install -e ".[dev]"
```

## Running from source

```bash
python -m trakt_calendar_sync.main       # GUI
python -m trakt_calendar_sync.cli_sync   # headless sync (setup must already be done)
```

## Running tests

```bash
QT_QPA_PLATFORM=offscreen python -m pytest tests/ -v
```

`QT_QPA_PLATFORM=offscreen` lets the PySide6 GUI tests run without a real
display (CI, SSH sessions, etc.) - drop it if you have a display and want to
watch windows flash by.

The suite is fully mocked: no test hits a real Trakt/Google endpoint or
touches your OS keychain.

## Packaging (PyInstaller)

PyInstaller does not cross-compile - run the build **on** each target OS.

### Linux / macOS

```bash
./packaging/build.sh
```

- Linux → `dist/TraktCalendarSync` (single binary, onefile)
- macOS → `dist/Trakt Calendar Sync.app` (onedir build wrapped as a `.app` -
  PyInstaller deprecates onefile+`.app` bundling, since a `.app` can't
  actually be a single file)

### Windows

```powershell
packaging\build_windows.ps1
```

Produces `dist/TraktCalendarSync.exe` (onefile).

### macOS code signing

Builds are **unsigned** - no paid Apple Developer Program membership for
this project. PyInstaller still applies the ad-hoc signature Apple Silicon
requires just to execute a binary at all, but it won't satisfy Gatekeeper
once the `.app` has a quarantine flag (i.e. it was downloaded or received
rather than built locally). Send **[packaging/INSTALL_MACOS.md](packaging/INSTALL_MACOS.md)**
to anyone you hand the app to.

If a Developer ID Application certificate is added later, wire it in via the
`codesign_identity` / `entitlements_file` parameters already present (and
currently `None`) in `packaging/trakt_calendar_sync.spec`, and add a
`notarytool submit` + `stapler staple` step to `build.sh`.

## What's bundled vs. what's per-user

- `resources/credentials.json` (the shared Google OAuth client) is baked
  into every build - identical for every user.
- Trakt Client ID/Secret is per-user, entered in the setup wizard - never
  bundled or shared.
- All tokens/secrets are written to the OS keychain (`keyring`) at runtime,
  never to plaintext disk and never embedded in the binary.

## Known packaging gotchas

These are already handled in `packaging/trakt_calendar_sync.spec` /
`google_cal/calendar.py` / `resources.py` - noted here so a future change
doesn't accidentally undo them:

- **`keyring` backends** are discovered via entry points at runtime.
  PyInstaller's static analysis can't see that, so
  `SecretService`/`macOS`/`Windows`/`kwallet` are listed as explicit
  `hiddenimports` - otherwise the frozen app can silently fall back to a
  non-secure backend.
- **`google-api-python-client`'s discovery document** isn't reliably bundled
  by PyInstaller. `build_service()` passes `static_discovery=False` so it
  fetches the doc live from Google instead of relying on a bundled file.
- **Bundled resource path**: `resources.py` looks for `credentials.json`
  under `sys._MEIPASS/resources` when frozen - this must keep matching the
  `datas=[(..., "resources")]` entry in the spec.
