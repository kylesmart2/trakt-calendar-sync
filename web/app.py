"""Flask web UI - the containerized alternative to the PySide6 GUI. Reuses
trakt_calendar_sync's Trakt/Google Calendar logic unchanged (see sync_web.py
for how); only the web-specific glue (routes, the in-memory device-auth
progress tracker, the redirect-based Google flow) lives here.
"""

import logging
import secrets
import threading

from flask import Flask, flash, jsonify, redirect, render_template, request, session, url_for

from trakt_calendar_sync.trakt.auth import TraktDeviceAuth
from trakt_calendar_sync.trakt.exceptions import TraktAuthError

from . import google_oauth_web, scheduler, storage, sync_web

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.secret_key = storage.get(storage.KEY_FLASK_SECRET_KEY) or storage.update(
    **{storage.KEY_FLASK_SECRET_KEY: secrets.token_hex(32)}
)[storage.KEY_FLASK_SECRET_KEY]

DEFAULT_AUTO_SYNC_HOUR = 9
DEFAULT_AUTO_SYNC_MINUTE = 0

# Single-user app, single worker process assumed (see storage.py) - the
# in-flight Trakt device-auth attempt is tracked here rather than per-session,
# same spirit as the native GUI tracking one _worker at a time.
_trakt_auth_state = {"status": "idle"}
_trakt_auth_lock = threading.Lock()


def is_setup_complete() -> bool:
    return storage.load_trakt_credentials() is not None and google_oauth_web.load_credentials() is not None


@app.route("/")
def dashboard():
    trakt_connected = storage.load_trakt_credentials() is not None
    google_connected = google_oauth_web.load_credentials() is not None

    settings_hour = storage.get(storage.KEY_AUTO_SYNC_HOUR, DEFAULT_AUTO_SYNC_HOUR)
    settings_minute = storage.get(storage.KEY_AUTO_SYNC_MINUTE, DEFAULT_AUTO_SYNC_MINUTE)

    return render_template(
        "dashboard.html",
        trakt_connected=trakt_connected,
        google_connected=google_connected,
        setup_complete=trakt_connected and google_connected,
        auto_sync_enabled=scheduler.is_enabled(),
        auto_sync_hour=settings_hour,
        auto_sync_minute=settings_minute,
        log=list(reversed(storage.get_log())),
    )


# --- Trakt device auth ---


@app.route("/setup/trakt")
def setup_trakt():
    creds = storage.load_trakt_credentials()
    return render_template("setup_trakt.html", client_id=creds["client_id"] if creds else "")


@app.route("/setup/trakt/connect", methods=["POST"])
def trakt_connect():
    client_id = request.form.get("client_id", "").strip()
    client_secret = request.form.get("client_secret", "").strip()
    if not client_id or not client_secret:
        flash("Enter both the Client ID and Client Secret.")
        return redirect(url_for("setup_trakt"))

    with _trakt_auth_lock:
        _trakt_auth_state.clear()
        _trakt_auth_state["status"] = "requesting"

    threading.Thread(target=_run_trakt_device_auth, args=(client_id, client_secret), daemon=True).start()
    return redirect(url_for("setup_trakt_waiting"))


@app.route("/setup/trakt/waiting")
def setup_trakt_waiting():
    return render_template("trakt_waiting.html")


@app.route("/setup/trakt/status")
def trakt_status():
    with _trakt_auth_lock:
        return jsonify(dict(_trakt_auth_state))


def _run_trakt_device_auth(client_id: str, client_secret: str) -> None:
    auth = TraktDeviceAuth(client_id, client_secret)
    try:
        device_code = auth.request_device_code()
    except TraktAuthError as e:
        with _trakt_auth_lock:
            _trakt_auth_state.clear()
            _trakt_auth_state.update(status="failed", error=str(e))
        return

    with _trakt_auth_lock:
        _trakt_auth_state.clear()
        _trakt_auth_state.update(
            status="waiting",
            user_code=device_code.user_code,
            verification_url=device_code.verification_url,
            remaining=device_code.expires_in,
        )

    def on_wait(remaining: int) -> None:
        with _trakt_auth_lock:
            if _trakt_auth_state.get("status") == "waiting":
                _trakt_auth_state["remaining"] = remaining

    try:
        tokens = auth.poll_for_tokens(device_code, on_wait=on_wait)
    except TraktAuthError as e:
        with _trakt_auth_lock:
            _trakt_auth_state.clear()
            _trakt_auth_state.update(status="failed", error=str(e))
        return

    storage.update(
        **{
            storage.KEY_TRAKT_CLIENT_ID: client_id,
            storage.KEY_TRAKT_CLIENT_SECRET: client_secret,
            storage.KEY_TRAKT_ACCESS_TOKEN: tokens.access_token,
            storage.KEY_TRAKT_REFRESH_TOKEN: tokens.refresh_token,
        }
    )
    with _trakt_auth_lock:
        _trakt_auth_state.clear()
        _trakt_auth_state["status"] = "succeeded"


# --- Google redirect OAuth ---


@app.route("/setup/google")
def setup_google():
    return render_template("setup_google.html")


@app.route("/setup/google/authorize")
def google_authorize():
    redirect_uri = url_for("oauth_callback", _external=True)
    flow = google_oauth_web.build_flow(redirect_uri)
    auth_url, state = google_oauth_web.authorization_url(flow)
    session["google_oauth_state"] = state
    session["google_oauth_code_verifier"] = flow.code_verifier
    return redirect(auth_url)


@app.route("/oauth/callback")
def oauth_callback():
    expected_state = session.pop("google_oauth_state", None)
    code_verifier = session.pop("google_oauth_code_verifier", None)
    if expected_state is None or request.args.get("state") != expected_state:
        flash("Google sign-in failed: state mismatch - please try again.")
        return redirect(url_for("dashboard"))

    if "error" in request.args:
        flash(f"Google sign-in was not completed: {request.args['error']}")
        return redirect(url_for("dashboard"))

    redirect_uri = url_for("oauth_callback", _external=True)
    flow = google_oauth_web.build_flow(redirect_uri, code_verifier=code_verifier)
    try:
        google_oauth_web.complete_authorization(flow, request.url)
    except Exception as e:  # noqa: BLE001 - surface any failure, don't crash the request
        flash(f"Google sign-in failed: {e}")
        return redirect(url_for("dashboard"))

    flash("Connected to Google Calendar.")
    return redirect(url_for("dashboard"))


# --- Sync + auto-sync ---


@app.route("/sync", methods=["POST"])
def sync_now():
    try:
        result = sync_web.run_sync()
    except sync_web.SyncSetupError as e:
        flash(f"Sync not configured: {e}")
        return redirect(url_for("dashboard"))

    message = f"Synced {result.episodes_synced} episode(s) to calendar {result.calendar_id}"
    if result.removed_events:
        message += f" - removed {len(result.removed_events)} stale event(s): {', '.join(result.removed_events)}"
    storage.append_log(message)
    flash(message)
    for error in result.errors:
        storage.append_log(f"error: {error}")
        flash(f"Error: {error}")
    return redirect(url_for("dashboard"))


@app.route("/auto-sync", methods=["POST"])
def auto_sync_toggle():
    enabled = request.form.get("enabled") == "on"
    hour = int(request.form.get("hour", DEFAULT_AUTO_SYNC_HOUR))
    minute = int(request.form.get("minute", DEFAULT_AUTO_SYNC_MINUTE))

    if enabled:
        scheduler.enable(hour, minute)
        flash(f"Daily auto-sync enabled at {hour:02d}:{minute:02d}")
    else:
        scheduler.disable()
        flash("Daily auto-sync disabled")
    return redirect(url_for("dashboard"))


def main() -> None:
    scheduler.init_from_storage()
    app.run(host="0.0.0.0", port=6969, debug=False)


if __name__ == "__main__":
    main()
