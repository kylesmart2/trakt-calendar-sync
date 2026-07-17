"""Daily sync via Windows Task Scheduler (schtasks)."""

import subprocess

TASK_NAME = "TraktCalendarSync"


def enable(command: list, hour: int, minute: int) -> None:
    tr_value = subprocess.list2cmdline(command)
    subprocess.run(
        [
            "schtasks",
            "/create",
            "/tn",
            TASK_NAME,
            "/tr",
            tr_value,
            "/sc",
            "daily",
            "/st",
            f"{hour:02d}:{minute:02d}",
            "/f",
        ],
        check=True,
    )


def disable() -> None:
    subprocess.run(["schtasks", "/delete", "/tn", TASK_NAME, "/f"], check=False)


def is_enabled() -> bool:
    result = subprocess.run(["schtasks", "/query", "/tn", TASK_NAME], capture_output=True, text=True)
    return result.returncode == 0
