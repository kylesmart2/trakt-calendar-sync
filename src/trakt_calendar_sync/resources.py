"""Locates bundled read-only resources — currently just the app's shared
Google OAuth credentials.json — both when running from source and when
frozen into a single file/folder by PyInstaller (which unpacks data files
next to sys._MEIPASS at runtime).
"""

import sys
from pathlib import Path


def resource_path(name: str) -> Path:
    if getattr(sys, "frozen", False):
        # Matches the ("resources/credentials.json", "resources") datas entry
        # in packaging/trakt_calendar_sync.spec.
        base = Path(sys._MEIPASS) / "resources"
    else:
        base = Path(__file__).resolve().parents[2] / "resources"
    return base / name


def google_credentials_path() -> Path:
    return resource_path("credentials.json")
