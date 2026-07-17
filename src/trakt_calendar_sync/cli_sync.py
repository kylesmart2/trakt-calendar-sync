"""Headless entry point invoked by the OS scheduler (Task Scheduler /
launchd), e.g. `trakt-calendar-sync-cli`. Runs sync.engine.run_sync() with no
GUI and exits non-zero on failure so the scheduler's log shows it needs
attention.
"""

import sys


def main() -> None:
    from trakt_calendar_sync.sync.engine import SyncSetupError, run_sync

    try:
        result = run_sync()
    except SyncSetupError as e:
        print(f"Sync not configured: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Synced {result.episodes_synced} episode(s) to calendar {result.calendar_id}")
    if result.removed_events:
        names = ", ".join(result.removed_events)
        print(f"Removed {len(result.removed_events)} stale event(s): {names}")
    for error in result.errors:
        print(f"  error: {error}", file=sys.stderr)

    if not result.ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
