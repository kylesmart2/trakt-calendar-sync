# Builds dist/TraktCalendarSync.exe. Run this ON Windows - PyInstaller does
# not cross-compile from Linux/macOS.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path "resources/credentials.json")) {
    Write-Error "resources/credentials.json is missing. Copy your Google Cloud 'Desktop app' OAuth client there first (see resources/credentials.json.example)."
    exit 1
}

pyinstaller --noconfirm --clean packaging/trakt_calendar_sync.spec
Write-Host "Build output: dist/"
