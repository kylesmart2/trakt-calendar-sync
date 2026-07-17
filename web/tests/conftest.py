"""Sets TRAKT_CALENDAR_SYNC_WEB_DATA_DIR to a writable temp dir before any
test module (and therefore web.app, which touches storage at import time
for its Flask secret key) gets imported - importing web.app with the
default /data unset/unwritable would break collection entirely.
"""

import os
import shutil
import tempfile

import pytest

_COLLECTION_TIME_TEMP_DIR = tempfile.mkdtemp(prefix="trakt-calendar-sync-web-tests-")
os.environ.setdefault("TRAKT_CALENDAR_SYNC_WEB_DATA_DIR", _COLLECTION_TIME_TEMP_DIR)


@pytest.fixture(autouse=True)
def isolated_data_dir(monkeypatch):
    """Every test gets its own empty data dir - storage.py re-reads the env
    var on every call (nothing cached at import time), so this is enough to
    isolate tests from each other even though web.app itself was already
    imported once against the collection-time dir above."""
    tmp = tempfile.mkdtemp(prefix="trakt-calendar-sync-web-test-")
    monkeypatch.setenv("TRAKT_CALENDAR_SYNC_WEB_DATA_DIR", tmp)
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)
