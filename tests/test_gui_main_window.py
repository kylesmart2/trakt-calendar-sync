from PySide6.QtCore import QTime

from trakt_calendar_sync import config, scheduler
from trakt_calendar_sync.gui import main_window as main_window_module
from trakt_calendar_sync.gui.main_window import MainWindow
from trakt_calendar_sync.sync.engine import SyncResult


def _make_window(qtbot, monkeypatch, auto_sync_enabled=False):
    monkeypatch.setattr(scheduler, "is_auto_sync_enabled", lambda: auto_sync_enabled)
    monkeypatch.setattr(config, "load_settings", lambda: {})
    window = MainWindow()
    qtbot.addWidget(window)
    return window


def test_loads_auto_sync_state_disabled_by_default(qtbot, monkeypatch):
    window = _make_window(qtbot, monkeypatch, auto_sync_enabled=False)

    assert window.auto_sync_checkbox.isChecked() is False


def test_loads_auto_sync_state_enabled(qtbot, monkeypatch):
    window = _make_window(qtbot, monkeypatch, auto_sync_enabled=True)

    assert window.auto_sync_checkbox.isChecked() is True


def test_toggling_on_calls_scheduler_enable_with_chosen_time(qtbot, monkeypatch):
    window = _make_window(qtbot, monkeypatch)
    enabled_with = {}
    monkeypatch.setattr(
        scheduler, "enable_auto_sync", lambda hour, minute: enabled_with.update(hour=hour, minute=minute)
    )
    monkeypatch.setattr(config, "update_settings", lambda **kw: kw)
    window.auto_sync_time.setTime(QTime(9, 30))

    window.auto_sync_checkbox.setChecked(True)

    assert enabled_with == {"hour": 9, "minute": 30}


def test_toggling_off_calls_scheduler_disable(qtbot, monkeypatch):
    window = _make_window(qtbot, monkeypatch, auto_sync_enabled=True)
    disabled = []
    monkeypatch.setattr(scheduler, "disable_auto_sync", lambda: disabled.append(True))
    monkeypatch.setattr(config, "update_settings", lambda **kw: kw)

    window.auto_sync_checkbox.setChecked(False)

    assert disabled == [True]


def test_scheduler_failure_reverts_checkbox_and_logs(qtbot, monkeypatch):
    window = _make_window(qtbot, monkeypatch)

    def boom(hour, minute):
        raise RuntimeError("systemctl not found")

    monkeypatch.setattr(scheduler, "enable_auto_sync", boom)

    window.auto_sync_checkbox.setChecked(True)

    assert window.auto_sync_checkbox.isChecked() is False
    assert "systemctl not found" in window.status_log.toPlainText()


def test_on_sync_finished_logs_result_and_reenables_button(qtbot, monkeypatch):
    window = _make_window(qtbot, monkeypatch)
    window.sync_button.setEnabled(False)

    window._on_sync_finished(SyncResult(episodes_synced=3, calendar_id="cal-1", errors=["oops"]))

    assert window.sync_button.isEnabled() is True
    text = window.status_log.toPlainText()
    assert "Synced 3 episode(s)" in text
    assert "oops" in text


def test_on_sync_finished_logs_removed_event_names(qtbot, monkeypatch):
    window = _make_window(qtbot, monkeypatch)

    window._on_sync_finished(
        SyncResult(
            episodes_synced=3,
            calendar_id="cal-1",
            removed_events=["American Horror Story - S13E01", "Cancelled Show - S01E02"],
        )
    )

    text = window.status_log.toPlainText()
    assert "Removed 2 stale event(s)" in text
    assert "American Horror Story - S13E01" in text
    assert "Cancelled Show - S01E02" in text


def test_on_sync_finished_omits_removed_line_when_empty(qtbot, monkeypatch):
    window = _make_window(qtbot, monkeypatch)

    window._on_sync_finished(SyncResult(episodes_synced=3, calendar_id="cal-1", removed_events=[]))

    assert "Removed" not in window.status_log.toPlainText()


def test_on_sync_failed_logs_message_and_reenables_button(qtbot, monkeypatch):
    window = _make_window(qtbot, monkeypatch)
    window.sync_button.setEnabled(False)

    window._on_sync_failed("Trakt isn't set up yet")

    assert window.sync_button.isEnabled() is True
    assert "Trakt isn't set up yet" in window.status_log.toPlainText()


def test_start_sync_disables_button_and_spawns_worker(qtbot, monkeypatch):
    window = _make_window(qtbot, monkeypatch)
    # Never let the worker thread reach the real run_sync() - it would hit
    # real Trakt/Google credentials from this machine's keyring otherwise.
    monkeypatch.setattr(main_window_module, "run_sync", lambda: SyncResult(0, ""))

    window._start_sync()

    assert window.sync_button.isEnabled() is False
    assert "Starting sync..." in window.status_log.toPlainText()
    assert window._worker is not None
    qtbot.waitUntil(lambda: window.sync_button.isEnabled() is True, timeout=2000)
