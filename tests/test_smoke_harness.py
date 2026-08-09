import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from syncra.app import legacy_main


class SmokeHarnessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        # Point every config write at a throwaway file. Closing a window triggers
        # closeEvent -> save_config(), which serialises the live widgets; a test window
        # with load_config() stubbed out would otherwise write empty values straight
        # over the developer's real app_config.json.
        self._tmpdir = tempfile.TemporaryDirectory()
        self._saved_config_file = legacy_main.CONFIG_FILE
        self._saved_sync_file = legacy_main.SYNC_CONFIG_FILE
        legacy_main.CONFIG_FILE = os.path.join(self._tmpdir.name, "app_config.json")
        legacy_main.SYNC_CONFIG_FILE = os.path.join(self._tmpdir.name, "sync_config.json")

    def tearDown(self):
        legacy_main.CONFIG_FILE = self._saved_config_file
        legacy_main.SYNC_CONFIG_FILE = self._saved_sync_file
        self._tmpdir.cleanup()

    def test_main_window_smoke_interfaces(self):
        original_load_config = legacy_main.PlexPlaylistManager.load_config
        legacy_main.PlexPlaylistManager.load_config = lambda self: None
        try:
            window = legacy_main.PlexPlaylistManager()
            for name in [
                "connect_to_plex",
                "fetch_playlists",
                "edit_selected_playlist",
                "import_playlist",
                "sync_selected_playlists",
                "create_tools_page",
                "open_metadata_fixer",
            ]:
                self.assertTrue(callable(getattr(window, name, None)), f"Missing callable: {name}")
            window.close()
        finally:
            legacy_main.PlexPlaylistManager.load_config = original_load_config


if __name__ == "__main__":
    unittest.main()
