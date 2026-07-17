"""GUI entry point (console_scripts: trakt-calendar-sync).

When frozen into a single executable, the OS scheduler invokes this same
binary with --sync to run headlessly instead of a separate console-script
(see scheduler.sync_command and cli_sync.py) - so packaging only needs to
ship one artifact.
"""

import sys


def main() -> None:
    if "--sync" in sys.argv[1:]:
        from trakt_calendar_sync.cli_sync import main as sync_main

        sync_main()
        return

    from trakt_calendar_sync.gui.app import run

    run()


if __name__ == "__main__":
    main()
