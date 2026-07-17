from trakt_calendar_sync import config
from trakt_calendar_sync.google_cal import auth as google_auth
from trakt_calendar_sync.gui.setup_wizard import (
    GoogleSetupPage,
    TraktSetupPage,
    is_setup_complete,
)
from trakt_calendar_sync.trakt.auth import DeviceCode, TraktTokens


def _no_existing_credentials(monkeypatch):
    """Pages check config/keyring in __init__ to prefill an already-connected
    state - tests that don't care about that need to pin it to "nothing
    configured yet", or they'd pass/fail based on whatever machine runs them.
    """
    monkeypatch.setattr(config, "load_settings", lambda: {})
    monkeypatch.setattr(config, "get_secret", lambda key: None)
    monkeypatch.setattr(google_auth, "load_credentials", lambda: None)


def test_trakt_page_incomplete_until_connected(qtbot, monkeypatch):
    _no_existing_credentials(monkeypatch)
    page = TraktSetupPage()
    qtbot.addWidget(page)

    assert page.isComplete() is False


def test_trakt_page_prefills_and_completes_when_already_connected(qtbot, monkeypatch):
    monkeypatch.setattr(config, "load_settings", lambda: {config.SETTING_TRAKT_CLIENT_ID: "cid"})
    secrets = {
        config.SECRET_TRAKT_CLIENT_SECRET: "s",
        config.SECRET_TRAKT_ACCESS_TOKEN: "a",
        config.SECRET_TRAKT_REFRESH_TOKEN: "r",
    }
    monkeypatch.setattr(config, "get_secret", lambda key: secrets.get(key))

    page = TraktSetupPage()
    qtbot.addWidget(page)

    assert page.isComplete() is True
    assert page.client_id_input.text() == "cid"
    assert "Already connected" in page.status_label.text()


def test_trakt_page_shows_device_code(qtbot, monkeypatch):
    _no_existing_credentials(monkeypatch)
    page = TraktSetupPage()
    qtbot.addWidget(page)
    device_code = DeviceCode("dc", "ABCD-1234", "https://trakt.tv/activate", 600, 5)

    page._on_device_code_ready(device_code)

    assert "ABCD-1234" in page.status_label.text()
    assert "trakt.tv/activate" in page.status_label.text()


def test_trakt_page_waiting_appends_countdown(qtbot, monkeypatch):
    _no_existing_credentials(monkeypatch)
    page = TraktSetupPage()
    qtbot.addWidget(page)
    page._on_device_code_ready(DeviceCode("dc", "ABCD-1234", "https://trakt.tv/activate", 600, 5))

    page._on_waiting(42)

    assert "42s left" in page.status_label.text()
    assert "ABCD-1234" in page.status_label.text()


def test_trakt_page_becomes_complete_on_success(qtbot, monkeypatch):
    _no_existing_credentials(monkeypatch)
    page = TraktSetupPage()
    qtbot.addWidget(page)
    saved_settings = {}
    saved_secrets = {}
    monkeypatch.setattr(config, "update_settings", lambda **kw: saved_settings.update(kw))
    monkeypatch.setattr(config, "set_secret", lambda key, value: saved_secrets.setdefault(key, value))

    tokens = TraktTokens("at", "rt", 7776000, 0, "public", "bearer")
    with qtbot.waitSignal(page.completeChanged, timeout=1000):
        page._on_succeeded("cid", "csecret", tokens)

    assert page.isComplete() is True
    assert saved_settings[config.SETTING_TRAKT_CLIENT_ID] == "cid"
    assert saved_secrets[config.SECRET_TRAKT_CLIENT_SECRET] == "csecret"
    assert saved_secrets[config.SECRET_TRAKT_ACCESS_TOKEN] == "at"
    assert saved_secrets[config.SECRET_TRAKT_REFRESH_TOKEN] == "rt"


def test_trakt_page_stays_incomplete_on_failure(qtbot, monkeypatch):
    _no_existing_credentials(monkeypatch)
    page = TraktSetupPage()
    qtbot.addWidget(page)

    page._on_failed("denied")

    assert page.isComplete() is False
    assert "denied" in page.status_label.text()


def test_trakt_page_requires_both_fields_before_connecting(qtbot, monkeypatch):
    _no_existing_credentials(monkeypatch)
    page = TraktSetupPage()
    qtbot.addWidget(page)
    page.client_id_input.setText("only-id")

    page._start_device_auth()

    assert page._worker is None
    assert "Enter both" in page.status_label.text()


def test_google_page_incomplete_until_connected(qtbot, monkeypatch):
    monkeypatch.setattr(google_auth, "load_credentials", lambda: None)
    page = GoogleSetupPage()
    qtbot.addWidget(page)

    assert page.isComplete() is False


def test_google_page_completes_when_already_connected(qtbot, monkeypatch):
    monkeypatch.setattr(google_auth, "load_credentials", lambda: object())

    page = GoogleSetupPage()
    qtbot.addWidget(page)

    assert page.isComplete() is True
    assert "Already connected" in page.status_label.text()


def test_google_page_becomes_complete_on_success(qtbot, monkeypatch):
    monkeypatch.setattr(google_auth, "load_credentials", lambda: None)
    page = GoogleSetupPage()
    qtbot.addWidget(page)

    with qtbot.waitSignal(page.completeChanged, timeout=1000):
        page._on_succeeded()

    assert page.isComplete() is True


def test_google_page_stays_incomplete_on_failure(qtbot, monkeypatch):
    monkeypatch.setattr(google_auth, "load_credentials", lambda: None)
    page = GoogleSetupPage()
    qtbot.addWidget(page)

    page._on_failed("access_denied")

    assert page.isComplete() is False
    assert "access_denied" in page.status_label.text()


def test_is_setup_complete_false_when_nothing_configured(monkeypatch):
    _no_existing_credentials(monkeypatch)

    assert is_setup_complete() is False


def test_is_setup_complete_true_when_both_configured(monkeypatch):
    monkeypatch.setattr(config, "load_settings", lambda: {config.SETTING_TRAKT_CLIENT_ID: "cid"})
    secrets = {
        config.SECRET_TRAKT_CLIENT_SECRET: "s",
        config.SECRET_TRAKT_ACCESS_TOKEN: "a",
        config.SECRET_TRAKT_REFRESH_TOKEN: "r",
    }
    monkeypatch.setattr(config, "get_secret", lambda key: secrets.get(key))
    monkeypatch.setattr(google_auth, "load_credentials", lambda: object())

    assert is_setup_complete() is True
