"""Tests for logging configuration and for not saving config during a load.

Both cover things that were visible on the terminal every launch:

    WARNING:root:Skipping save_config(): configuration was never loaded ...
    2026-08-09 16:29:01,986 - WARNING - Skipping save_config(): configuration ...

Two independent faults produced that.

1. `load_config()` populates widgets, whose change signals call `save_config()`. That
   ran before `_config_loaded` was set, so the wipe-protection guard logged a warning
   -- twice, once per radio button.

2. Importing `legacy_main` constructs `SecureCredentialManager` at module scope, which
   logs. A logging call with no handlers installed makes Python run `basicConfig()`
   implicitly, attaching a default stderr handler. `setup_logging()` then called
   `basicConfig(filename=...)`, which is documented to do *nothing* when the root
   logger already has handlers -- so no FileHandler was ever installed (the log file
   was never written) and every record printed twice, once per format.
"""

import logging
import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from syncra.app import legacy_main
from syncra.ui.widgets import playlist_grid as pg


class RootLoggerGuard(unittest.TestCase):
    """setup_logging() reconfigures the process-wide root logger."""

    def setUp(self):
        root = logging.getLogger()
        self._saved_handlers = list(root.handlers)
        self._saved_level = root.level

    def tearDown(self):
        root = logging.getLogger()
        for handler in list(root.handlers):
            if handler not in self._saved_handlers:
                root.removeHandler(handler)
                try:
                    handler.close()
                except Exception:
                    pass
        for handler in self._saved_handlers:
            if handler not in root.handlers:
                root.addHandler(handler)
        root.setLevel(self._saved_level)


class LoggingSetupTests(RootLoggerGuard):
    def test_a_file_handler_is_installed_even_if_handlers_already_exist(self):
        """The regression: basicConfig() is a no-op once a handler is present."""
        root = logging.getLogger()
        root.addHandler(logging.StreamHandler())  # what the import-time log leaves

        legacy_main.setup_logging()

        self.assertTrue(
            any(isinstance(h, logging.FileHandler) for h in root.handlers),
            "no FileHandler: the log file would never be written",
        )

    def test_the_pre_existing_default_handler_is_replaced_not_added_to(self):
        root = logging.getLogger()
        stale = logging.StreamHandler()
        root.addHandler(stale)

        legacy_main.setup_logging()

        self.assertNotIn(stale, root.handlers, "the implicit handler must be dropped")

    def test_console_records_are_not_printed_twice(self):
        legacy_main.setup_logging()
        root = logging.getLogger()
        console = [
            h for h in root.handlers
            if isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.FileHandler)
        ]
        self.assertEqual(len(console), 1, "one console handler, or every line doubles")

    def test_every_handler_uses_the_timestamped_format(self):
        """The duplicate line was recognisable by its bare 'WARNING:root:' format."""
        legacy_main.setup_logging()
        for handler in logging.getLogger().handlers:
            fmt = getattr(handler.formatter, "_fmt", "")
            self.assertIn("%(asctime)s", fmt or "")

    def test_the_file_handler_writes_utf8(self):
        """Syncra logs emoji; cp1252 would drop those records entirely."""
        legacy_main.setup_logging()
        for handler in logging.getLogger().handlers:
            if isinstance(handler, logging.FileHandler):
                self.assertEqual((handler.encoding or "").lower().replace("-", ""), "utf8")


class SaveDuringLoadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._real_request = pg.CoverFetcher.request
        self._real_cached = pg.CoverFetcher.cached_bytes
        pg.CoverFetcher.request = lambda fetcher, url: False
        pg.CoverFetcher.cached_bytes = lambda fetcher, url: None

        original = legacy_main.PlexPlaylistManager.load_config
        legacy_main.PlexPlaylistManager.load_config = lambda self: None
        try:
            self.window = legacy_main.PlexPlaylistManager()
        finally:
            legacy_main.PlexPlaylistManager.load_config = original

    def tearDown(self):
        try:
            self.window.close()
        finally:
            pg.CoverFetcher.request = self._real_request
            pg.CoverFetcher.cached_bytes = self._real_cached

    def test_saving_is_suppressed_while_loading(self):
        self.window._config_loaded = True
        self.window._loading_config = True
        with mock.patch("builtins.open", mock.mock_open()) as opened:
            self.window.save_config()
        self.assertFalse(opened.called, "a load must not write the file back out")

    def test_suppression_is_silent(self):
        """It used to log a warning per widget signal, twice on every launch."""
        self.window._loading_config = True
        with self.assertLogs(level="WARNING") as captured:
            logging.warning("sentinel")  # assertLogs needs at least one record
            self.window.save_config()
        joined = " ".join(captured.output)
        self.assertNotIn("Skipping save_config", joined)

    def test_the_wipe_guard_still_fires_outside_a_load(self):
        """Suppressing during load must not disable the protection itself."""
        self.window._loading_config = False
        self.window._config_loaded = False
        with self.assertLogs(level="WARNING") as captured:
            self.window.save_config()
        self.assertIn("Skipping save_config", " ".join(captured.output))

    def test_the_flag_is_cleared_even_if_loading_raises(self):
        boom = mock.Mock(side_effect=RuntimeError("bad config"))
        with mock.patch.object(self.window, "_load_config_inner", boom):
            with self.assertRaises(RuntimeError):
                self.window.load_config()
        self.assertFalse(
            self.window._loading_config,
            "a failed load must not leave saving disabled for the session",
        )

    def test_a_normal_save_still_works_after_a_load(self):
        self.window._loading_config = False
        self.window._config_loaded = True
        with mock.patch("builtins.open", mock.mock_open()) as opened:
            self.window.save_config()
        self.assertTrue(opened.called)


if __name__ == "__main__":
    unittest.main()
