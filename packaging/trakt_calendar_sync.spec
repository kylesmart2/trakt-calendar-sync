# -*- mode: python ; coding: utf-8 -*-
"""Builds one artifact per OS from a single spec, since PyInstaller doesn't
cross-compile - run this ON each target OS (see build.sh / build_windows.ps1):
  Linux:   dist/TraktCalendarSync            (single binary, onefile)
  Windows: dist/TraktCalendarSync.exe        (single binary, onefile)
  macOS:   dist/Trakt Calendar Sync.app       (onedir build wrapped as a .app -
           PyInstaller deprecates onefile+.app: a .app can't be a single file
           and it clashes with macOS code-signing/Gatekeeper expectations)

The scheduler invokes this same binary with --sync for the headless daily
run (see scheduler.sync_command() and main.py) - there's only one artifact
to build and ship, not a separate GUI/CLI pair.

macOS builds are intentionally unsigned (codesign_identity=None below) - no
paid Apple Developer account for this project. PyInstaller still applies the
ad-hoc signature Apple Silicon requires just to execute the binary at all,
but it won't satisfy Gatekeeper on a machine that downloaded/received the
.app (quarantine flag) - see INSTALL_MACOS.md for the first-launch steps to
hand to recipients.
"""

import sys
from pathlib import Path

block_cipher = None

repo_root = Path(SPECPATH).resolve().parent
src_dir = repo_root / "src"
entrypoint = repo_root / "packaging" / "entrypoint.py"
credentials_path = repo_root / "resources" / "credentials.json"

# The shared Google OAuth client - see resources/credentials.json.example.
# build.sh/build_windows.ps1 already refuse to run without this present;
# this check just makes a spec run outside those scripts fail loudly too.
if not credentials_path.exists():
    raise SystemExit(
        f"Missing {credentials_path} - copy your Google Cloud 'Desktop app' "
        "OAuth client there first (see resources/credentials.json.example)."
    )

# keyring picks its backend via entry points at runtime (OS keychain on each
# platform); PyInstaller's static import analysis can't see that, so the
# candidates have to be listed explicitly or the frozen app silently falls
# back to an unencrypted in-memory/plaintext backend.
hiddenimports = [
    "keyring.backends.SecretService",
    "keyring.backends.macOS",
    "keyring.backends.Windows",
    "keyring.backends.kwallet",
    "keyring.backends.chainer",
    "keyring.backends.fail",
]

a = Analysis(
    [str(entrypoint)],
    pathex=[str(src_dir)],
    binaries=[],
    datas=[(str(credentials_path), "resources")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if sys.platform == "darwin":
    # onedir: EXE holds only the launcher, COLLECT gathers the rest into a
    # folder, BUNDLE wraps that folder as Trakt Calendar Sync.app.
    exe = EXE(
        pyz,
        a.scripts,
        [],
        exclude_binaries=True,
        name="TraktCalendarSync",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    coll = COLLECT(
        exe,
        a.binaries,
        a.zipfiles,
        a.datas,
        strip=False,
        upx=True,
        upx_exclude=[],
        name="TraktCalendarSync",
    )
    app = BUNDLE(
        coll,
        name="Trakt Calendar Sync.app",
        bundle_identifier="com.traktcalendarsync.app",
        info_plist={
            "CFBundleName": "Trakt Calendar Sync",
            "CFBundleDisplayName": "Trakt Calendar Sync",
            "NSHighResolutionCapable": True,
            "LSUIElement": False,
        },
    )
else:
    # onefile: everything embedded in a single binary.
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,
        a.zipfiles,
        a.datas,
        [],
        name="TraktCalendarSync",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
