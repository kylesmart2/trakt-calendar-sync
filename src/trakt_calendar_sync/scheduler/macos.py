"""Daily sync via a launchd user agent (~/Library/LaunchAgents/)."""

import plistlib
import subprocess
from pathlib import Path

LABEL = "com.traktcalendarsync.sync"
PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LOG_PATH = Path.home() / "Library" / "Logs" / "trakt-calendar-sync.log"


def enable(command: list, hour: int, minute: int) -> None:
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    plist = {
        "Label": LABEL,
        "ProgramArguments": list(command),
        "StartCalendarInterval": {"Hour": hour, "Minute": minute},
        "StandardOutPath": str(LOG_PATH),
        "StandardErrorPath": str(LOG_PATH),
    }
    with PLIST_PATH.open("wb") as f:
        plistlib.dump(plist, f)

    subprocess.run(["launchctl", "unload", str(PLIST_PATH)], check=False)
    subprocess.run(["launchctl", "load", "-w", str(PLIST_PATH)], check=True)


def disable() -> None:
    subprocess.run(["launchctl", "unload", "-w", str(PLIST_PATH)], check=False)
    PLIST_PATH.unlink(missing_ok=True)


def is_enabled() -> bool:
    if not PLIST_PATH.exists():
        return False
    result = subprocess.run(["launchctl", "list", LABEL], capture_output=True, text=True)
    return result.returncode == 0
