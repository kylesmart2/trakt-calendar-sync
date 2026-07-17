import json
from unittest.mock import MagicMock, patch

from google.auth.exceptions import RefreshError

from trakt_calendar_sync import config
from trakt_calendar_sync.google_cal import auth


def test_load_credentials_returns_none_when_nothing_cached(monkeypatch):
    monkeypatch.setattr(config, "get_secret", lambda key: None)

    assert auth.load_credentials() is None


def test_load_credentials_returns_cached_when_still_valid(monkeypatch):
    monkeypatch.setattr(config, "get_secret", lambda key: "{}")

    fake_creds = MagicMock(valid=True)
    with patch.object(auth.Credentials, "from_authorized_user_info", return_value=fake_creds):
        result = auth.load_credentials()

    assert result is fake_creds
    fake_creds.refresh.assert_not_called()


def test_load_credentials_refreshes_expired_creds(monkeypatch):
    monkeypatch.setattr(config, "get_secret", lambda key: "{}")
    saved = {}
    monkeypatch.setattr(config, "set_secret", lambda key, value: saved.setdefault(key, value))

    fake_creds = MagicMock(valid=False, expired=True, refresh_token="rt")
    fake_creds.to_json.return_value = json.dumps({"refreshed": True})
    with patch.object(auth.Credentials, "from_authorized_user_info", return_value=fake_creds):
        result = auth.load_credentials()

    assert result is fake_creds
    fake_creds.refresh.assert_called_once()
    assert saved[config.SECRET_GOOGLE_TOKEN] == json.dumps({"refreshed": True})


def test_load_credentials_returns_none_when_refresh_fails(monkeypatch):
    monkeypatch.setattr(config, "get_secret", lambda key: "{}")

    fake_creds = MagicMock(valid=False, expired=True, refresh_token="rt")
    fake_creds.refresh.side_effect = RefreshError("revoked")
    with patch.object(auth.Credentials, "from_authorized_user_info", return_value=fake_creds):
        result = auth.load_credentials()

    assert result is None


def test_run_authorization_flow_saves_credentials(monkeypatch, tmp_path):
    saved = {}
    monkeypatch.setattr(config, "set_secret", lambda key, value: saved.setdefault(key, value))

    fake_creds = MagicMock()
    fake_creds.to_json.return_value = json.dumps({"ok": True})
    fake_flow = MagicMock()
    fake_flow.run_local_server.return_value = fake_creds

    creds_path = tmp_path / "credentials.json"
    creds_path.write_text("{}")

    with patch.object(auth.InstalledAppFlow, "from_client_secrets_file", return_value=fake_flow) as from_file:
        result = auth.run_authorization_flow(credentials_path=creds_path)

    from_file.assert_called_once_with(str(creds_path), auth.SCOPES)
    fake_flow.run_local_server.assert_called_once_with(port=0)
    assert result is fake_creds
    assert saved[config.SECRET_GOOGLE_TOKEN] == json.dumps({"ok": True})


def test_sign_out_deletes_secret(monkeypatch):
    deleted = []
    monkeypatch.setattr(config, "delete_secret", lambda key: deleted.append(key))

    auth.sign_out()

    assert deleted == [config.SECRET_GOOGLE_TOKEN]
