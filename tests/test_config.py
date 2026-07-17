from trakt_calendar_sync import config


def test_load_trakt_credentials_returns_none_when_nothing_configured(monkeypatch):
    monkeypatch.setattr(config, "load_settings", lambda: {})
    monkeypatch.setattr(config, "get_secret", lambda key: None)

    assert config.load_trakt_credentials() is None


def test_load_trakt_credentials_returns_none_when_partially_configured(monkeypatch):
    monkeypatch.setattr(config, "load_settings", lambda: {config.SETTING_TRAKT_CLIENT_ID: "cid"})
    secrets = {config.SECRET_TRAKT_CLIENT_SECRET: "csecret"}  # missing both tokens
    monkeypatch.setattr(config, "get_secret", lambda key: secrets.get(key))

    assert config.load_trakt_credentials() is None


def test_load_trakt_credentials_returns_dict_when_fully_configured(monkeypatch):
    monkeypatch.setattr(config, "load_settings", lambda: {config.SETTING_TRAKT_CLIENT_ID: "cid"})
    secrets = {
        config.SECRET_TRAKT_CLIENT_SECRET: "csecret",
        config.SECRET_TRAKT_ACCESS_TOKEN: "at",
        config.SECRET_TRAKT_REFRESH_TOKEN: "rt",
    }
    monkeypatch.setattr(config, "get_secret", lambda key: secrets.get(key))

    creds = config.load_trakt_credentials()

    assert creds == {
        "client_id": "cid",
        "client_secret": "csecret",
        "access_token": "at",
        "refresh_token": "rt",
    }
