"""Session-wide protection for the developer's real configuration files.

Closing a Syncra window runs closeEvent() -> save_config(), which serialises the live
widget values to CONFIG_FILE. Any test that builds a window therefore writes config,
and a test whose window outlives its own CONFIG_FILE monkeypatch will write to the
real file in the project root -- wiping credentials, server profiles, tokens and
feature flags.

Individual tests still redirect CONFIG_FILE themselves; this is the backstop that makes
a mistake in one of them harmless. It repoints the module globals for the entire test
session, so the real app_config.json and sync_config.json are never writable from tests
no matter what order fixtures tear down in.
"""

import os
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session", autouse=True)
def isolate_config_files():
    from syncra.app import legacy_main

    real_config = legacy_main.CONFIG_FILE
    real_sync = legacy_main.SYNC_CONFIG_FILE
    real_cache = getattr(legacy_main, "CACHE_FILE", None)

    with tempfile.TemporaryDirectory(prefix="syncra-tests-") as tmpdir:
        legacy_main.CONFIG_FILE = os.path.join(tmpdir, "app_config.json")
        legacy_main.SYNC_CONFIG_FILE = os.path.join(tmpdir, "sync_config.json")
        if real_cache is not None:
            legacy_main.CACHE_FILE = os.path.join(tmpdir, "playlist_cache.json")
        try:
            yield tmpdir
        finally:
            legacy_main.CONFIG_FILE = real_config
            legacy_main.SYNC_CONFIG_FILE = real_sync
            if real_cache is not None:
                legacy_main.CACHE_FILE = real_cache
