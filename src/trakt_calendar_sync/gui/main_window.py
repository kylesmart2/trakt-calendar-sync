"""Main window: on-demand "Sync Now" plus the daily auto-sync toggle.
Sync itself runs on a QThread since sync.engine.run_sync() blocks on network
calls to Trakt and Google.
"""

from PySide6.QtCore import QThread, QTime, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from .. import config, scheduler
from ..sync.engine import SyncSetupError, run_sync

DEFAULT_AUTO_SYNC_HOUR = 9
DEFAULT_AUTO_SYNC_MINUTE = 0


class _SyncWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)

    def run(self) -> None:
        try:
            result = run_sync()
        except SyncSetupError as e:
            self.failed.emit(str(e))
            return
        self.finished_ok.emit(result)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Trakt Calendar Sync")
        self._worker = None

        central = QWidget()
        layout = QVBoxLayout(central)

        self.sync_button = QPushButton("Sync Now")
        self.sync_button.clicked.connect(self._start_sync)
        layout.addWidget(self.sync_button)

        self.status_log = QPlainTextEdit()
        self.status_log.setReadOnly(True)
        layout.addWidget(self.status_log)

        auto_sync_row = QHBoxLayout()
        self.auto_sync_checkbox = QCheckBox("Enable daily auto-sync at")
        self.auto_sync_time = QTimeEdit()
        self.auto_sync_time.setDisplayFormat("HH:mm")
        auto_sync_row.addWidget(self.auto_sync_checkbox)
        auto_sync_row.addWidget(self.auto_sync_time)
        layout.addLayout(auto_sync_row)

        self.setCentralWidget(central)

        self._load_auto_sync_state()
        self.auto_sync_checkbox.toggled.connect(self._on_auto_sync_toggled)

    def _load_auto_sync_state(self) -> None:
        settings = config.load_settings()
        hour = settings.get(config.SETTING_AUTO_SYNC_HOUR, DEFAULT_AUTO_SYNC_HOUR)
        minute = settings.get(config.SETTING_AUTO_SYNC_MINUTE, DEFAULT_AUTO_SYNC_MINUTE)
        self.auto_sync_time.setTime(QTime(hour, minute))

        self.auto_sync_checkbox.blockSignals(True)
        self.auto_sync_checkbox.setChecked(scheduler.is_auto_sync_enabled())
        self.auto_sync_checkbox.blockSignals(False)

    def _on_auto_sync_toggled(self, checked: bool) -> None:
        time = self.auto_sync_time.time()
        hour, minute = time.hour(), time.minute()

        try:
            if checked:
                scheduler.enable_auto_sync(hour, minute)
            else:
                scheduler.disable_auto_sync()
        except Exception as e:  # noqa: BLE001 - report scheduler failures, don't crash the GUI
            self._log(f"Failed to update auto-sync schedule: {e}")
            self.auto_sync_checkbox.blockSignals(True)
            self.auto_sync_checkbox.setChecked(not checked)
            self.auto_sync_checkbox.blockSignals(False)
            return

        config.update_settings(
            **{
                config.SETTING_AUTO_SYNC_ENABLED: checked,
                config.SETTING_AUTO_SYNC_HOUR: hour,
                config.SETTING_AUTO_SYNC_MINUTE: minute,
            }
        )
        self._log(f"Daily auto-sync {'enabled' if checked else 'disabled'} at {hour:02d}:{minute:02d}")

    def _start_sync(self) -> None:
        self.sync_button.setEnabled(False)
        self._log("Starting sync...")

        self._worker = _SyncWorker()
        self._worker.finished_ok.connect(self._on_sync_finished)
        self._worker.failed.connect(self._on_sync_failed)
        self._worker.start()

    def _on_sync_finished(self, result) -> None:
        self.sync_button.setEnabled(True)
        self._log(f"Synced {result.episodes_synced} episode(s) to calendar {result.calendar_id}")
        if result.removed_events:
            names = ", ".join(result.removed_events)
            self._log(f"Removed {len(result.removed_events)} stale event(s): {names}")
        for error in result.errors:
            self._log(f"  error: {error}")

    def _on_sync_failed(self, message: str) -> None:
        self.sync_button.setEnabled(True)
        self._log(f"Sync failed: {message}")

    def _log(self, message: str) -> None:
        self.status_log.appendPlainText(message)
