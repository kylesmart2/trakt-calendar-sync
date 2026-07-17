import time
from unittest.mock import MagicMock

import pytest

from web import app as app_module
from web import scheduler, storage, sync_web


@pytest.fixture
def client():
    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as client:
        yield client
    if scheduler._scheduler.get_job(scheduler.JOB_ID) is not None:
        scheduler._scheduler.remove_job(scheduler.JOB_ID)


def _complete_trakt_setup():
    storage.update(
        **{
            storage.KEY_TRAKT_CLIENT_ID: "cid",
            storage.KEY_TRAKT_CLIENT_SECRET: "csecret",
            storage.KEY_TRAKT_ACCESS_TOKEN: "at",
            storage.KEY_TRAKT_REFRESH_TOKEN: "rt",
        }
    )


def _complete_google_setup():
    storage.set(storage.KEY_GOOGLE_TOKEN, "{}")


def test_dashboard_shows_setup_links_when_not_configured(client):
    response = client.get("/")

    assert b"Connect Trakt" in response.data
    assert b"Connect Google Calendar" in response.data
    assert b"Sync Now" not in response.data


def test_dashboard_shows_sync_controls_when_configured(client, monkeypatch):
    _complete_trakt_setup()
    monkeypatch.setattr(app_module.google_oauth_web, "load_credentials", lambda: object())

    response = client.get("/")

    assert b"Sync Now" in response.data
    assert b"Daily auto-sync" in response.data


def test_trakt_connect_requires_both_fields(client):
    response = client.post("/setup/trakt/connect", data={"client_id": "only-id"}, follow_redirects=True)

    assert b"Enter both" in response.data


def test_trakt_connect_starts_background_auth_and_redirects(client, monkeypatch):
    started = {}

    def fake_run(client_id, client_secret):
        started["client_id"] = client_id
        started["client_secret"] = client_secret

    monkeypatch.setattr(app_module, "_run_trakt_device_auth", fake_run)

    response = client.post(
        "/setup/trakt/connect",
        data={"client_id": "cid", "client_secret": "csecret"},
    )

    assert response.status_code == 302
    assert "/setup/trakt/waiting" in response.location
    time.sleep(0.1)  # let the daemon thread actually invoke the patched function
    assert started == {"client_id": "cid", "client_secret": "csecret"}


def test_trakt_status_reflects_in_memory_state(client):
    with app_module._trakt_auth_lock:
        app_module._trakt_auth_state.clear()
        app_module._trakt_auth_state.update(status="waiting", user_code="ABCD-1234", remaining=42)

    response = client.get("/setup/trakt/status")

    assert response.json == {"status": "waiting", "user_code": "ABCD-1234", "remaining": 42}


def test_oauth_callback_rejects_state_mismatch(client):
    with client.session_transaction() as session:
        session["google_oauth_state"] = "expected"

    response = client.get("/oauth/callback?code=abc&state=wrong", follow_redirects=True)

    assert b"state mismatch" in response.data


def test_oauth_callback_completes_flow_on_valid_state(client, monkeypatch):
    with client.session_transaction() as session:
        session["google_oauth_state"] = "expected"

    monkeypatch.setattr(app_module.google_oauth_web, "build_flow", lambda redirect_uri: MagicMock())
    completed = {}
    monkeypatch.setattr(
        app_module.google_oauth_web,
        "complete_authorization",
        lambda flow, url: completed.setdefault("url", url),
    )

    response = client.get("/oauth/callback?code=abc&state=expected", follow_redirects=True)

    assert b"Connected to Google Calendar" in response.data
    assert "code=abc" in completed["url"]


def test_sync_now_reports_setup_error(client, monkeypatch):
    def raise_setup_error():
        raise sync_web.SyncSetupError("Trakt isn't set up yet")

    monkeypatch.setattr(app_module.sync_web, "run_sync", raise_setup_error)

    response = client.post("/sync", follow_redirects=True)

    assert b"Sync not configured" in response.data


def test_sync_now_logs_result_and_appends_to_status_log(client, monkeypatch):
    fake_result = MagicMock(
        episodes_synced=5, calendar_id="cal-1", removed_events=["Old Show - S01E01"], errors=[]
    )
    monkeypatch.setattr(app_module.sync_web, "run_sync", lambda: fake_result)

    response = client.post("/sync", follow_redirects=True)

    assert b"Synced 5 episode" in response.data
    log = storage.get_log()
    assert any("Synced 5 episode" in entry["message"] for entry in log)


def test_auto_sync_toggle_enables_with_chosen_time(client):
    response = client.post(
        "/auto-sync", data={"enabled": "on", "hour": "9", "minute": "30"}, follow_redirects=True
    )

    assert b"enabled at 09:30" in response.data
    assert scheduler.is_enabled() is True


def test_auto_sync_toggle_disables(client):
    scheduler.enable(9, 0)

    response = client.post("/auto-sync", data={"hour": "9", "minute": "0"}, follow_redirects=True)

    assert b"disabled" in response.data
    assert scheduler.is_enabled() is False
