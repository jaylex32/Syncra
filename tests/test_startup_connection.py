"""Regression tests for the startup hang on stale Plex credentials.

The original bug: load_config() scheduled connect_to_plex() with QTimer.singleShot(0),
and the next splash progress update called QApplication.processEvents(), which dispatched
that zero-timer while __init__ was still running. connect_to_plex() then raised on a
rejected token and opened QMessageBox.critical() parented to a not-yet-shown window --
a nested modal loop behind the always-on-top splash. __init__ never returned, so the
window was never shown and the splash could never close.
"""

import json
import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import requests
from PyQt6.QtWidgets import QApplication

from syncra.app import legacy_main


class RecordingSplash:
    """Stands in for StartupSplashScreen, including its processEvents() call."""

    def __init__(self):
        self.messages = []

    def update_progress(self, message, value=None):
        self.messages.append(message)
        QApplication.processEvents()

    def finish_for(self, window=None):
        pass


class StartupConnectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_config_file = legacy_main.CONFIG_FILE
        config_path = os.path.join(self._tmpdir.name, "app_config.json")
        # A saved token plus an address that cannot answer -- the exact state a user is
        # left in after changing their Plex password or after the server IP changes.
        with open(config_path, "w") as handle:
            json.dump(
                {
                    "plex_username": "",
                    "server_ip": "127.0.0.1",
                    "server_port": "1",
                    "token": "stale-token-value",
                    "selected_user_name": "Someone",
                },
                handle,
            )
        legacy_main.CONFIG_FILE = config_path

        self._critical_calls = []
        self._original_critical = legacy_main.QMessageBox.critical
        legacy_main.QMessageBox.critical = lambda *args, **kwargs: self._critical_calls.append(args)

        self._window = None

    def tearDown(self):
        legacy_main.QMessageBox.critical = self._original_critical
        # Close the window BEFORE restoring CONFIG_FILE. closeEvent() calls
        # save_config(), so restoring the path first makes the window serialise its
        # test state straight into the real app_config.json.
        if self._window is not None:
            self._window.close()
        legacy_main.CONFIG_FILE = self._original_config_file
        self._tmpdir.cleanup()

    def _build_window(self):
        splash = RecordingSplash()
        self._window = legacy_main.PlexPlaylistManager(startup_splash=splash)
        return self._window, splash

    def test_auto_connect_does_not_run_during_init(self):
        """__init__ must complete without ever touching the network."""
        connect_calls = []
        original_connect = legacy_main.PlexPlaylistManager.connect_to_plex
        legacy_main.PlexPlaylistManager.connect_to_plex = (
            lambda self, from_startup=False: connect_calls.append(from_startup)
        )
        try:
            window, _ = self._build_window()
        finally:
            legacy_main.PlexPlaylistManager.connect_to_plex = original_connect

        self.assertEqual(
            connect_calls,
            [],
            "connect_to_plex ran during __init__ -- the splash-processEvents reentrancy is back",
        )
        self.assertTrue(
            window._pending_auto_connect,
            "auto-connect intent should be recorded for main() to trigger after show()",
        )

    def test_startup_failure_is_non_modal_and_shows_banner(self):
        """A failed startup connect reports into the banner, never a blocking dialog."""
        window, _ = self._build_window()
        window._startup_splash_active = False

        window.start_pending_auto_connect()

        self.assertEqual(
            self._critical_calls,
            [],
            "startup connection failure must not open a modal dialog",
        )
        # isVisible() is False for any child of an unshown window, so assert on the
        # widget's own hidden flag instead.
        self.assertFalse(
            window.connection_banner.isHidden(),
            "the Connection page banner should explain the failure",
        )
        self.assertIn("Plex", window.connection_banner.text())

    def test_start_pending_auto_connect_runs_once(self):
        window, _ = self._build_window()
        window._startup_splash_active = False

        calls = []
        window.connect_to_plex = lambda from_startup=False: calls.append(from_startup)

        window.start_pending_auto_connect()
        window.start_pending_auto_connect()

        self.assertEqual(calls, [True], "auto-connect should fire exactly once, flagged as startup")

    def test_rejected_token_is_classified_and_cleared(self):
        window, _ = self._build_window()
        title, message, token_is_stale = window._describe_plex_connection_error(
            legacy_main.Unauthorized("(401) unauthorized")
        )
        self.assertTrue(token_is_stale)
        self.assertIn("password", message.lower())
        self.assertEqual(title, "Plex Login Rejected")

    def test_unreachable_server_is_classified_without_blaming_credentials(self):
        window, _ = self._build_window()
        title, message, token_is_stale = window._describe_plex_connection_error(
            requests.exceptions.ConnectionError("connection refused")
        )
        self.assertFalse(token_is_stale, "a network failure must not discard a good token")
        self.assertIn("Cannot Reach", title)

    def test_timeout_is_classified_separately(self):
        window, _ = self._build_window()
        title, _message, token_is_stale = window._describe_plex_connection_error(
            requests.exceptions.ConnectTimeout("timed out")
        )
        self.assertFalse(token_is_stale)
        self.assertIn("Timed Out", title)


class ConfigPreservationTests(unittest.TestCase):
    """Closing a window must never blank a saved account.

    closeEvent() calls save_config(), which serialises the live connection fields. When
    those fields were never populated -- load_config() skipped or failed -- saving used
    to write empty strings over the real credentials, server profiles, ListenBrainz
    tokens, feature flags and metadata settings, forcing a fresh sign-in every launch.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_config_file = legacy_main.CONFIG_FILE
        self._original_sync_file = legacy_main.SYNC_CONFIG_FILE
        self.config_path = os.path.join(self._tmpdir.name, "app_config.json")
        self.populated = {
            "plex_username": "Real User",
            "server_ip": "10.0.0.5",
            "server_port": "32400",
            "token": "a-real-token",
            "listenbrainz_user": "someone",
            "plex_server_profiles": [{"name": "Main", "base_url": "http://10.0.0.5:32400"}],
            "selected_user_name": "Real User",
            "features": {"metadata_fixer": True},
        }
        with open(self.config_path, "w") as handle:
            json.dump(self.populated, handle)
        legacy_main.CONFIG_FILE = self.config_path
        legacy_main.SYNC_CONFIG_FILE = os.path.join(self._tmpdir.name, "sync_config.json")

    def tearDown(self):
        legacy_main.CONFIG_FILE = self._original_config_file
        legacy_main.SYNC_CONFIG_FILE = self._original_sync_file
        self._tmpdir.cleanup()

    def _read(self):
        with open(self.config_path) as handle:
            return json.load(handle)

    def test_unpopulated_window_does_not_wipe_saved_config(self):
        original_load_config = legacy_main.PlexPlaylistManager.load_config
        legacy_main.PlexPlaylistManager.load_config = lambda self: None
        try:
            window = legacy_main.PlexPlaylistManager()
            window.close()          # -> closeEvent -> save_config()
            window.save_config()    # and an explicit call, for good measure
        finally:
            legacy_main.PlexPlaylistManager.load_config = original_load_config

        saved = self._read()
        self.assertEqual(saved["plex_username"], "Real User")
        self.assertEqual(saved["server_ip"], "10.0.0.5")
        self.assertEqual(saved["token"], "a-real-token")
        self.assertEqual(saved["plex_server_profiles"], self.populated["plex_server_profiles"])
        self.assertEqual(saved["listenbrainz_user"], "someone")
        self.assertTrue(saved["features"]["metadata_fixer"])

    def test_real_load_then_save_round_trips_credentials(self):
        """The guard must not block a legitimate save."""
        window = legacy_main.PlexPlaylistManager()
        try:
            self.assertTrue(window._config_loaded)
            window.save_config()
            saved = self._read()
            self.assertEqual(saved["plex_username"], "Real User")
            self.assertEqual(saved["server_ip"], "10.0.0.5")
            self.assertEqual(saved["token"], "a-real-token")
        finally:
            window.close()


if __name__ == "__main__":
    unittest.main()
