"""Cross-platform daily-sync scheduling: systemd --user timers on Linux and
launchd user agents on macOS are the primary, well-tested paths; Task
Scheduler on Windows is supported too. Each backend only has to implement
enable(command, hour, minute) / disable() / is_enabled() - this module picks
the right one for the current OS and works out what argv the scheduler
should invoke daily.
"""

import sys


def sync_command() -> list:
    """The argv the scheduler should invoke once a day.

    When frozen by PyInstaller into a single executable, that same binary is
    invoked with --sync (see main.py) rather than shelling out to a second
    console-script entry point, so there's only one artifact to package.
    """
    if getattr(sys, "frozen", False):
        return [sys.executable, "--sync"]
    return [sys.executable, "-m", "trakt_calendar_sync.cli_sync"]


def enable_auto_sync(hour: int, minute: int) -> None:
    _backend().enable(sync_command(), hour, minute)


def disable_auto_sync() -> None:
    _backend().disable()


def is_auto_sync_enabled() -> bool:
    return _backend().is_enabled()


def _backend():
    if sys.platform.startswith("linux"):
        from . import linux

        return linux
    if sys.platform == "darwin":
        from . import macos

        return macos
    if sys.platform == "win32":
        from . import windows

        return windows
    raise RuntimeError(f"Unsupported platform for scheduling: {sys.platform}")
