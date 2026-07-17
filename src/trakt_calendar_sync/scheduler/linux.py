"""Daily sync via a systemd --user timer (~/.config/systemd/user/).

Primary target platform alongside macOS: most desktop Linux distros run a
per-user systemd instance that needs no root and persists across logins.
`Persistent=true` on the timer catches up a missed run (e.g. laptop was
asleep at the scheduled time) the next time the user session is active.
"""

import shlex
import subprocess
from pathlib import Path

UNIT_NAME = "trakt-calendar-sync"
SYSTEMD_USER_DIR = Path.home() / ".config" / "systemd" / "user"
SERVICE_PATH = SYSTEMD_USER_DIR / f"{UNIT_NAME}.service"
TIMER_PATH = SYSTEMD_USER_DIR / f"{UNIT_NAME}.timer"


def enable(command: list, hour: int, minute: int) -> None:
    SYSTEMD_USER_DIR.mkdir(parents=True, exist_ok=True)

    exec_start = " ".join(shlex.quote(part) for part in command)
    SERVICE_PATH.write_text(
        "[Unit]\n"
        "Description=Trakt Calendar Sync\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"ExecStart={exec_start}\n"
    )
    TIMER_PATH.write_text(
        "[Unit]\n"
        "Description=Daily Trakt Calendar Sync\n"
        "\n"
        "[Timer]\n"
        f"OnCalendar=*-*-* {hour:02d}:{minute:02d}:00\n"
        "Persistent=true\n"
        "\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", f"{UNIT_NAME}.timer"], check=True)


def disable() -> None:
    subprocess.run(["systemctl", "--user", "disable", "--now", f"{UNIT_NAME}.timer"], check=False)
    SERVICE_PATH.unlink(missing_ok=True)
    TIMER_PATH.unlink(missing_ok=True)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=False)


def is_enabled() -> bool:
    result = subprocess.run(
        ["systemctl", "--user", "is-enabled", f"{UNIT_NAME}.timer"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() == "enabled"
