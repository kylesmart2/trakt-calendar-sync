"""In-process daily sync scheduling via APScheduler - the web app's
equivalent of trakt_calendar_sync.scheduler, but registering a job inside
this long-lived process instead of with the OS's own service manager
(systemd/launchd/schtasks don't apply inside a container, and mixing that
facade's "register with the OS" model with "run a background thread in this
process" would be a mismatch, not a reuse).

APScheduler's default in-memory jobstore doesn't survive a process restart,
so the enabled/hour/minute choice is persisted via storage.py and re-armed
by init_from_storage() once at app startup.
"""

import logging
import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from . import storage
from .sync_web import run_sync

JOB_ID = "daily-sync"

logger = logging.getLogger(__name__)


def _resolve_timezone() -> ZoneInfo:
    # APScheduler defaults to tzlocal's system-detected timezone, which is
    # UTC in a container unless TZ is both set and backed by an installed
    # tzdata package (see web/Dockerfile) - read it explicitly so the daily
    # sync fires at the hour the user actually picked, not UTC's.
    tz_name = os.environ.get("TZ", "UTC")
    try:
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown TZ %r, falling back to UTC", tz_name)
        return ZoneInfo("UTC")


_scheduler = BackgroundScheduler(timezone=_resolve_timezone())
_scheduler.start()


def enable(hour: int, minute: int) -> None:
    _scheduler.add_job(
        _run_sync_job,
        trigger=CronTrigger(hour=hour, minute=minute),
        id=JOB_ID,
        replace_existing=True,
    )
    storage.update(
        **{
            storage.KEY_AUTO_SYNC_ENABLED: True,
            storage.KEY_AUTO_SYNC_HOUR: hour,
            storage.KEY_AUTO_SYNC_MINUTE: minute,
        }
    )


def disable() -> None:
    if _scheduler.get_job(JOB_ID) is not None:
        _scheduler.remove_job(JOB_ID)
    storage.set(storage.KEY_AUTO_SYNC_ENABLED, False)


def is_enabled() -> bool:
    return _scheduler.get_job(JOB_ID) is not None


def init_from_storage() -> None:
    """Call once at app startup - re-arms the job if it was enabled before
    the process last restarted (container restart/rebuild, etc.)."""
    if storage.get(storage.KEY_AUTO_SYNC_ENABLED, False):
        hour = storage.get(storage.KEY_AUTO_SYNC_HOUR, 9)
        minute = storage.get(storage.KEY_AUTO_SYNC_MINUTE, 0)
        enable(hour, minute)


def _run_sync_job() -> None:
    result = run_sync()
    if result.ok:
        logger.info(
            "Scheduled sync: synced %d episode(s), removed %d stale event(s)",
            result.episodes_synced,
            len(result.removed_events),
        )
    else:
        logger.error("Scheduled sync completed with errors: %s", result.errors)
