from web import storage


def test_get_returns_default_when_missing():
    assert storage.get("nope", "fallback") == "fallback"


def test_set_then_get_roundtrip():
    storage.set("k", "v")
    assert storage.get("k") == "v"


def test_delete_removes_key():
    storage.set("k", "v")
    storage.delete("k")
    assert storage.get("k") is None


def test_delete_missing_key_is_a_noop():
    storage.delete("never-existed")  # must not raise


def test_update_merges_multiple_keys():
    storage.set("existing", "kept")
    result = storage.update(a=1, b=2)
    assert result["a"] == 1
    assert result["b"] == 2
    assert result["existing"] == "kept"
    assert storage.get("a") == 1


def test_load_trakt_credentials_none_when_nothing_stored():
    assert storage.load_trakt_credentials() is None


def test_load_trakt_credentials_none_when_partially_stored():
    storage.set(storage.KEY_TRAKT_CLIENT_ID, "cid")
    storage.set(storage.KEY_TRAKT_CLIENT_SECRET, "csecret")
    assert storage.load_trakt_credentials() is None


def test_load_trakt_credentials_returns_dict_when_complete():
    storage.set(storage.KEY_TRAKT_CLIENT_ID, "cid")
    storage.set(storage.KEY_TRAKT_CLIENT_SECRET, "csecret")
    storage.set(storage.KEY_TRAKT_ACCESS_TOKEN, "at")
    storage.set(storage.KEY_TRAKT_REFRESH_TOKEN, "rt")

    assert storage.load_trakt_credentials() == {
        "client_id": "cid",
        "client_secret": "csecret",
        "access_token": "at",
        "refresh_token": "rt",
    }


def test_append_log_and_get_log_order():
    storage.append_log("first")
    storage.append_log("second")

    log = storage.get_log()

    assert [entry["message"] for entry in log] == ["first", "second"]
    assert all("timestamp" in entry for entry in log)


def test_append_log_caps_at_max_entries():
    for i in range(storage.MAX_LOG_ENTRIES + 5):
        storage.append_log(f"entry-{i}")

    log = storage.get_log()

    assert len(log) == storage.MAX_LOG_ENTRIES
    assert log[-1]["message"] == f"entry-{storage.MAX_LOG_ENTRIES + 4}"
