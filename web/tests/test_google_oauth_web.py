import json
import os
from unittest.mock import MagicMock, patch

from google.auth.exceptions import RefreshError

from web import google_oauth_web, storage


def test_module_disables_oauthlib_https_enforcement():
    # Regression: without this, flow.fetch_token() raises oauthlib's
    # InsecureTransportError against the plain-http callback URL this app
    # actually receives (confirmed against the real container - Google's
    # server accepted the redirect fine and sent back a real code, the
    # failure was oauthlib's own client-side check on the callback URL).
    assert os.environ.get("OAUTHLIB_INSECURE_TRANSPORT") == "1"


def test_load_credentials_returns_none_when_nothing_cached():
    assert google_oauth_web.load_credentials() is None


def test_load_credentials_returns_none_when_stored_token_is_malformed():
    # Regression: a corrupted/incomplete stored token (partial write, manual
    # edit, old incompatible shape) used to raise ValueError uncaught,
    # 500ing every page that checks Google's connection status.
    storage.set(storage.KEY_GOOGLE_TOKEN, "{}")

    assert google_oauth_web.load_credentials() is None


def test_load_credentials_returns_none_when_stored_token_is_invalid_json():
    storage.set(storage.KEY_GOOGLE_TOKEN, "not json at all")

    assert google_oauth_web.load_credentials() is None


def test_load_credentials_returns_cached_when_still_valid():
    storage.set(storage.KEY_GOOGLE_TOKEN, "{}")
    fake_creds = MagicMock(valid=True)
    with patch.object(google_oauth_web.Credentials, "from_authorized_user_info", return_value=fake_creds):
        result = google_oauth_web.load_credentials()

    assert result is fake_creds
    fake_creds.refresh.assert_not_called()


def test_load_credentials_refreshes_expired_creds():
    storage.set(storage.KEY_GOOGLE_TOKEN, "{}")
    fake_creds = MagicMock(valid=False, expired=True, refresh_token="rt")
    fake_creds.to_json.return_value = json.dumps({"refreshed": True})
    with patch.object(google_oauth_web.Credentials, "from_authorized_user_info", return_value=fake_creds):
        result = google_oauth_web.load_credentials()

    assert result is fake_creds
    fake_creds.refresh.assert_called_once()
    assert storage.get(storage.KEY_GOOGLE_TOKEN) == json.dumps({"refreshed": True})


def test_load_credentials_returns_none_when_refresh_fails():
    storage.set(storage.KEY_GOOGLE_TOKEN, "{}")
    fake_creds = MagicMock(valid=False, expired=True, refresh_token="rt")
    fake_creds.refresh.side_effect = RefreshError("revoked")
    with patch.object(google_oauth_web.Credentials, "from_authorized_user_info", return_value=fake_creds):
        assert google_oauth_web.load_credentials() is None


def test_authorization_url_requests_offline_access_and_consent_prompt():
    flow = MagicMock()
    flow.authorization_url.return_value = ("https://accounts.google.com/...", "state123")

    url, state = google_oauth_web.authorization_url(flow)

    assert url == "https://accounts.google.com/..."
    assert state == "state123"
    flow.authorization_url.assert_called_once_with(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )


def test_complete_authorization_fetches_token_and_saves_credentials():
    flow = MagicMock()
    flow.credentials.to_json.return_value = json.dumps({"ok": True})

    google_oauth_web.complete_authorization(flow, "http://localhost:6969/oauth/callback?code=abc&state=xyz")

    flow.fetch_token.assert_called_once_with(
        authorization_response="http://localhost:6969/oauth/callback?code=abc&state=xyz"
    )
    assert storage.get(storage.KEY_GOOGLE_TOKEN) == json.dumps({"ok": True})


def test_sign_out_deletes_stored_token():
    storage.set(storage.KEY_GOOGLE_TOKEN, "{}")

    google_oauth_web.sign_out()

    assert storage.get(storage.KEY_GOOGLE_TOKEN) is None


def test_build_flow_uses_credentials_path_and_scopes():
    with patch.object(google_oauth_web.Flow, "from_client_secrets_file") as from_file:
        google_oauth_web.build_flow("http://localhost:6969/oauth/callback")

    from_file.assert_called_once_with(
        str(google_oauth_web.credentials_path()),
        scopes=google_oauth_web.SCOPES,
        redirect_uri="http://localhost:6969/oauth/callback",
        code_verifier=None,
    )


def test_build_flow_passes_through_code_verifier():
    # Regression: PKCE's code_verifier is generated on the Flow instance
    # that builds the authorization URL, but the callback request builds a
    # *different* Flow instance to exchange the code - without passing the
    # same code_verifier back in, Google rejects the exchange with
    # "invalid_grant: Missing code verifier".
    with patch.object(google_oauth_web.Flow, "from_client_secrets_file") as from_file:
        google_oauth_web.build_flow("http://localhost:6969/oauth/callback", code_verifier="abc123")

    from_file.assert_called_once_with(
        str(google_oauth_web.credentials_path()),
        scopes=google_oauth_web.SCOPES,
        redirect_uri="http://localhost:6969/oauth/callback",
        code_verifier="abc123",
    )
