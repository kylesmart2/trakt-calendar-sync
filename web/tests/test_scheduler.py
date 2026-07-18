from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

from web import scheduler, storage


def teardown_function():
    # the module-level _scheduler is a shared singleton across tests (that's
    # the real runtime design - one BackgroundScheduler per process) - make
    # sure no test leaves a job registered for the next one.
    if scheduler._scheduler.get_job(scheduler.JOB_ID) is not None:
        scheduler._scheduler.remove_job(scheduler.JOB_ID)


def test_enable_registers_job_and_persists_settings():
    scheduler.enable(9, 30)

    assert scheduler.is_enabled() is True
    assert storage.get(storage.KEY_AUTO_SYNC_ENABLED) is True
    assert storage.get(storage.KEY_AUTO_SYNC_HOUR) == 9
    assert storage.get(storage.KEY_AUTO_SYNC_MINUTE) == 30


def test_disable_removes_job_and_persists_disabled():
    scheduler.enable(9, 30)

    scheduler.disable()

    assert scheduler.is_enabled() is False
    assert storage.get(storage.KEY_AUTO_SYNC_ENABLED) is False


def test_disable_when_never_enabled_is_a_noop():
    scheduler.disable()  # must not raise
    assert scheduler.is_enabled() is False


def test_is_enabled_false_by_default():
    assert scheduler.is_enabled() is False


def test_init_from_storage_rearms_previously_enabled_schedule():
    storage.update(
        **{
            storage.KEY_AUTO_SYNC_ENABLED: True,
            storage.KEY_AUTO_SYNC_HOUR: 14,
            storage.KEY_AUTO_SYNC_MINUTE: 45,
        }
    )

    scheduler.init_from_storage()

    assert scheduler.is_enabled() is True
    job = scheduler._scheduler.get_job(scheduler.JOB_ID)
    assert "hour='14'" in str(job.trigger)
    assert "minute='45'" in str(job.trigger)


def test_init_from_storage_noop_when_never_enabled():
    scheduler.init_from_storage()

    assert scheduler.is_enabled() is False


def test_run_sync_job_logs_success(monkeypatch):
    fake_result = MagicMock(ok=True, episodes_synced=3, removed_events=["Show - S01E02"], errors=[])
    monkeypatch.setattr(scheduler, "run_sync", lambda: fake_result)

    scheduler._run_sync_job()  # must not raise


def test_run_sync_job_logs_errors(monkeypatch):
    fake_result = MagicMock(ok=False, episodes_synced=0, removed_events=[], errors=["boom"])
    monkeypatch.setattr(scheduler, "run_sync", lambda: fake_result)

    scheduler._run_sync_job()  # must not raise


def test_resolve_timezone_defaults_to_utc(monkeypatch):
    monkeypatch.delenv("TZ", raising=False)

    assert scheduler._resolve_timezone() == ZoneInfo("UTC")


def test_resolve_timezone_honors_tz_env_var(monkeypatch):
    monkeypatch.setenv("TZ", "America/New_York")

    assert scheduler._resolve_timezone() == ZoneInfo("America/New_York")


def test_resolve_timezone_falls_back_on_unknown_tz(monkeypatch):
    # Regression: a typo'd TZ (e.g. "America/Not_A_City") must not crash the
    # whole app at import time - fall back to UTC and keep running.
    monkeypatch.setenv("TZ", "Not/A_Real_Zone")

    assert scheduler._resolve_timezone() == ZoneInfo("UTC")
