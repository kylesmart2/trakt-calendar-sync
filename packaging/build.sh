#!/usr/bin/env bash
# Builds a standalone executable for the current OS: a single binary on
# Linux, or that same binary wrapped as a .app on macOS (see
# trakt_calendar_sync.spec). Run this ON each target OS - PyInstaller does
# not cross-compile from Linux to macOS or vice versa.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f resources/credentials.json ]; then
    echo "error: resources/credentials.json is missing." >&2
    echo "       Copy your Google Cloud 'Desktop app' OAuth client there first" >&2
    echo "       (see resources/credentials.json.example)." >&2
    exit 1
fi

pyinstaller --noconfirm --clean packaging/trakt_calendar_sync.spec
echo "Build output: dist/"

if [ "$(uname)" = "Darwin" ]; then
    echo "Unsigned build - see packaging/INSTALL_MACOS.md for first-launch instructions to hand to recipients."
fi
