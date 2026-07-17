"""First-run setup wizard: Trakt device auth, then Google sign-in.

Both auth flows are network calls that block for a while (Trakt polls for up
to the device code's expires_in, ~10 minutes; Google's run_local_server
blocks until the browser redirect lands), so each runs on its own QThread to
keep the wizard responsive and cancellable.
"""

import threading

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from .. import config
from ..google_cal import auth as google_auth
from ..trakt.auth import TraktDeviceAuth
from ..trakt.exceptions import TraktAuthError

TRAKT_NEW_APP_URL = "https://app.trakt.tv/settings/apps/api/new"


def is_setup_complete() -> bool:
    return config.load_trakt_credentials() is not None and google_auth.load_credentials() is not None


class _DeviceAuthWorker(QThread):
    device_code_ready = Signal(object)
    waiting = Signal(int)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, client_id: str, client_secret: str):
        super().__init__()
        self.client_id = client_id
        self.client_secret = client_secret
        self._cancel_event = threading.Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    def run(self) -> None:
        auth = TraktDeviceAuth(self.client_id, self.client_secret)
        try:
            device_code = auth.request_device_code()
        except TraktAuthError as e:
            self.failed.emit(str(e))
            return

        self.device_code_ready.emit(device_code)
        try:
            tokens = auth.poll_for_tokens(
                device_code,
                on_wait=self.waiting.emit,
                cancel_event=self._cancel_event,
            )
        except TraktAuthError as e:
            self.failed.emit(str(e))
            return
        self.succeeded.emit(tokens)


class TraktSetupPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Connect Trakt")
        self._ready = False
        self._worker = None
        self._base_status = ""

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Create your own Trakt API app, then paste its Client ID and "
            f'Client Secret below: <a href="{TRAKT_NEW_APP_URL}">{TRAKT_NEW_APP_URL}</a>'
        )
        intro.setOpenExternalLinks(True)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.client_id_input = QLineEdit()
        self.client_id_input.setPlaceholderText("Client ID")
        layout.addWidget(self.client_id_input)

        self.client_secret_input = QLineEdit()
        self.client_secret_input.setPlaceholderText("Client Secret")
        self.client_secret_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.client_secret_input)

        self.connect_button = QPushButton("Connect to Trakt")
        self.connect_button.clicked.connect(self._start_device_auth)
        layout.addWidget(self.connect_button)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setOpenExternalLinks(True)
        layout.addWidget(self.status_label)

        creds = config.load_trakt_credentials()
        if creds is not None:
            self.client_id_input.setText(creds["client_id"])
            self.status_label.setText("Already connected to Trakt.")
            self._ready = True

    def isComplete(self) -> bool:
        return self._ready

    def _start_device_auth(self) -> None:
        client_id = self.client_id_input.text().strip()
        client_secret = self.client_secret_input.text().strip()
        if not client_id or not client_secret:
            self.status_label.setText("Enter both the Client ID and Client Secret first.")
            return

        self.connect_button.setEnabled(False)
        self.status_label.setText("Requesting a device code from Trakt...")

        self._worker = _DeviceAuthWorker(client_id, client_secret)
        self._worker.device_code_ready.connect(self._on_device_code_ready)
        self._worker.waiting.connect(self._on_waiting)
        self._worker.succeeded.connect(lambda tokens: self._on_succeeded(client_id, client_secret, tokens))
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_device_code_ready(self, device_code) -> None:
        self._base_status = (
            f'Go to <a href="{device_code.verification_url}">{device_code.verification_url}</a> '
            f"and enter code: <b>{device_code.user_code}</b>"
        )
        self.status_label.setText(self._base_status)

    def _on_waiting(self, remaining: int) -> None:
        self.status_label.setText(f"{self._base_status}<br>Waiting for approval... ({remaining}s left)")

    def _on_succeeded(self, client_id: str, client_secret: str, tokens) -> None:
        try:
            config.update_settings(**{config.SETTING_TRAKT_CLIENT_ID: client_id})
            config.set_secret(config.SECRET_TRAKT_CLIENT_SECRET, client_secret)
            config.set_secret(config.SECRET_TRAKT_ACCESS_TOKEN, tokens.access_token)
            config.set_secret(config.SECRET_TRAKT_REFRESH_TOKEN, tokens.refresh_token)
        except Exception as e:  # noqa: BLE001 - Trakt approved us; don't silently strand the wizard if saving fails
            self.status_label.setText(f"Trakt approved the request, but saving credentials failed: {e}")
            self.connect_button.setEnabled(True)
            return

        self.status_label.setText("Connected to Trakt.")
        self.connect_button.setEnabled(True)
        self._ready = True
        self.completeChanged.emit()

    def _on_failed(self, message: str) -> None:
        self.status_label.setText(f"Failed: {message}")
        self.connect_button.setEnabled(True)

    def _stop_worker(self) -> None:
        """Called when the wizard is closing - tells the poll loop to stop
        and silences its signals so it can't fire into this (possibly about
        to be destroyed) page. The thread itself winds down within one poll
        interval on its own; nothing here needs to block waiting for it.
        """
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self._worker.blockSignals(True)


class _GoogleAuthWorker(QThread):
    succeeded = Signal()
    failed = Signal(str)

    def run(self) -> None:
        try:
            google_auth.run_authorization_flow()
        except Exception as e:  # noqa: BLE001 - surface any failure to the wizard, not a crash
            self.failed.emit(str(e))
            return
        self.succeeded.emit()


class GoogleSetupPage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("Connect Google Calendar")
        self._ready = False
        self._worker = None

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Sign in with your Google account. A browser window will open - "
            'grant access and a "TV Shows" calendar will be created automatically.'
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.signin_button = QPushButton("Sign in with Google")
        self.signin_button.clicked.connect(self._start_google_auth)
        layout.addWidget(self.signin_button)

        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        if google_auth.load_credentials() is not None:
            self.status_label.setText("Already connected to Google Calendar.")
            self._ready = True

    def isComplete(self) -> bool:
        return self._ready

    def _start_google_auth(self) -> None:
        self.signin_button.setEnabled(False)
        self.status_label.setText("Opening your browser to sign in...")

        self._worker = _GoogleAuthWorker()
        self._worker.succeeded.connect(self._on_succeeded)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _on_succeeded(self) -> None:
        self.status_label.setText("Connected to Google Calendar.")
        self.signin_button.setEnabled(True)
        self._ready = True
        self.completeChanged.emit()

    def _on_failed(self, message: str) -> None:
        self.status_label.setText(f"Failed: {message}")
        self.signin_button.setEnabled(True)

    def _stop_worker(self) -> None:
        # run_local_server() has no cancellation hook of its own, so this
        # can't stop the underlying blocking call - it just silences its
        # signals so a late succeeded/failed can't fire into this page.
        if self._worker is not None and self._worker.isRunning():
            self._worker.blockSignals(True)


class SetupWizard(QWizard):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Trakt Calendar Sync Setup")
        self.addPage(TraktSetupPage())
        self.addPage(GoogleSetupPage())

    def _stop_all_workers(self) -> None:
        for page_id in self.pageIds():
            page = self.page(page_id)
            stop_worker = getattr(page, "_stop_worker", None)
            if stop_worker is not None:
                stop_worker()

    def closeEvent(self, event) -> None:
        self._stop_all_workers()
        super().closeEvent(event)

    def reject(self) -> None:
        self._stop_all_workers()
        super().reject()
