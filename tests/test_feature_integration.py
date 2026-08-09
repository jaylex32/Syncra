"""Integration tests for match memory, missing tracks, and sync history.

These exercise the seams where the new stores meet the legacy app: the matcher's
override short-circuit, the revert path, and the dialogs' ability to construct and
populate against a real store.
"""

import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QTableWidgetItem

from syncra.app import legacy_main
from syncra.services.library_data_db import LibraryDataDB
from syncra.services.match_memory import MatchMemoryStore
from syncra.services.missing_tracks import STATUS_MISSING, MissingTracksStore
from syncra.services.sync_history import SyncHistoryStore
from syncra.services.track_identity import track_fingerprint
from syncra.ui.dialogs.match_memory_dialog import MatchMemoryDialog
from syncra.ui.dialogs.missing_tracks_dialog import MissingTracksDialog
from syncra.ui.dialogs.sync_history_dialog import SyncHistoryDialog


class FakeServer:
    machineIdentifier = "test-machine"


class FakeSection:
    """Minimal stand-in for a plexapi library section."""

    def __init__(self):
        self._server = FakeServer()
        self.key = "3"
        self.title = "Music"


class FakePlaylist:
    def __init__(self, title, tracks):
        self.title = title
        self._tracks = list(tracks)
        self.removed = []
        self.added = []

    def items(self):
        return list(self._tracks)

    def removeItems(self, items):
        self.removed.extend(items)
        for item in items:
            if item in self._tracks:
                self._tracks.remove(item)

    def addItems(self, items):
        self.added.extend(items)
        self._tracks.extend(items)


class FakeTrack:
    def __init__(self, rating_key, title="T", artist="A", album="Al"):
        self.ratingKey = rating_key
        self.title = title
        self.grandparentTitle = artist
        self.parentTitle = album


def redirect_config_files(test_case, directory):
    """Send config writes to a temp dir for the duration of a test.

    Closing a window runs closeEvent -> save_config(), which serialises the live
    widgets. Any test that builds a window with load_config() stubbed would otherwise
    persist empty values over the developer's real app_config.json.
    """
    test_case._saved_config_file = legacy_main.CONFIG_FILE
    test_case._saved_sync_file = legacy_main.SYNC_CONFIG_FILE
    legacy_main.CONFIG_FILE = os.path.join(directory, "app_config.json")
    legacy_main.SYNC_CONFIG_FILE = os.path.join(directory, "sync_config.json")


def restore_config_files(test_case):
    legacy_main.CONFIG_FILE = test_case._saved_config_file
    legacy_main.SYNC_CONFIG_FILE = test_case._saved_sync_file


class StoreBackedTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        redirect_config_files(self, self._tmpdir.name)
        self.db = LibraryDataDB(os.path.join(self._tmpdir.name, "t.sqlite"))
        self.match_store = MatchMemoryStore(self.db)
        self.missing_store = MissingTracksStore(self.db)
        self.history_store = SyncHistoryStore(self.db)
        self.library_key = "test-machine::3"

    def tearDown(self):
        restore_config_files(self)
        self._tmpdir.cleanup()


class MatcherOverrideTests(StoreBackedTestCase):
    def setUp(self):
        super().setUp()
        self.section = FakeSection()
        self.track = {"title": "Song", "artist": "Band", "album": "Rec"}

        # Point the app's lazy singletons at the temp database.
        self._saved = (
            legacy_main._SYNCRA_MATCH_MEMORY_STORE,
            legacy_main._SYNCRA_MISSING_TRACKS_STORE,
            legacy_main._SYNCRA_SYNC_HISTORY_STORE,
        )
        legacy_main._SYNCRA_MATCH_MEMORY_STORE = self.match_store
        legacy_main._SYNCRA_MISSING_TRACKS_STORE = self.missing_store
        legacy_main._SYNCRA_SYNC_HISTORY_STORE = self.history_store

        self._saved_rows_fn = legacy_main._get_library_match_rows_by_key_cached
        self._saved_candidates_fn = legacy_main._collect_plex_track_candidates

    def tearDown(self):
        (
            legacy_main._SYNCRA_MATCH_MEMORY_STORE,
            legacy_main._SYNCRA_MISSING_TRACKS_STORE,
            legacy_main._SYNCRA_SYNC_HISTORY_STORE,
        ) = self._saved
        legacy_main._get_library_match_rows_by_key_cached = self._saved_rows_fn
        legacy_main._collect_plex_track_candidates = self._saved_candidates_fn
        super().tearDown()

    def test_library_key_matches_store_scope(self):
        self.assertEqual(
            legacy_main._get_library_match_session_key(self.section), self.library_key
        )

    def test_forced_match_short_circuits_scoring(self):
        self.match_store.remember_match(self.library_key, self.track, "555")
        legacy_main._get_library_match_rows_by_key_cached = lambda section: {
            "555": {"title": "Song", "artist": "Band", "album": "Rec"}
        }
        legacy_main._collect_plex_track_candidates = lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("scoring should not run when an override exists")
        )

        ranked = legacy_main._rank_plex_track_matches(self.section, self.track)
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["rating_key"], "555")
        self.assertEqual(ranked[0]["score"], 100.0)
        self.assertTrue(ranked[0]["from_override"])

    def test_known_missing_returns_no_candidates(self):
        self.match_store.remember_missing(self.library_key, self.track)
        legacy_main._collect_plex_track_candidates = lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("scoring should not run for a known-missing track")
        )
        self.assertEqual(legacy_main._rank_plex_track_matches(self.section, self.track), [])

    def test_stale_override_falls_back_to_normal_scoring(self):
        """A remembered ratingKey that left the library must not win."""
        self.match_store.remember_match(self.library_key, self.track, "999")
        # Index is populated but no longer contains 999.
        legacy_main._get_library_match_rows_by_key_cached = lambda section: {
            "111": {"title": "Other", "artist": "Other", "album": ""}
        }
        called = {"scored": False}

        def fake_candidates(*args, **kwargs):
            called["scored"] = True
            return []

        legacy_main._collect_plex_track_candidates = fake_candidates
        legacy_main._get_library_match_rows_cached = lambda section: []

        ranked = legacy_main._rank_plex_track_matches(self.section, self.track)
        self.assertTrue(called["scored"], "should fall through to normal scoring")
        self.assertEqual(ranked, [])

    def test_cold_index_does_not_discard_a_valid_override(self):
        """An empty index means 'not built yet', not 'track deleted'."""
        self.match_store.remember_match(self.library_key, self.track, "555")
        legacy_main._get_library_match_rows_by_key_cached = lambda section: {}
        ranked = legacy_main._rank_plex_track_matches(self.section, self.track)
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0]["rating_key"], "555")

    def test_override_use_is_counted(self):
        self.match_store.remember_match(self.library_key, self.track, "555")
        legacy_main._get_library_match_rows_by_key_cached = lambda section: {"555": {}}
        legacy_main._rank_plex_track_matches(self.section, self.track)
        stored = self.match_store.lookup(self.library_key, self.track)
        self.assertEqual(stored["hit_count"], 1)


class RevertTests(StoreBackedTestCase):
    def setUp(self):
        super().setUp()
        original_load_config = legacy_main.PlexPlaylistManager.load_config
        legacy_main.PlexPlaylistManager.load_config = lambda self: None
        try:
            self.window = legacy_main.PlexPlaylistManager()
        finally:
            legacy_main.PlexPlaylistManager.load_config = original_load_config

        self.old_track = FakeTrack(1, "Old")
        self.new_track = FakeTrack(2, "New")
        self.playlist = FakePlaylist("My Playlist", [self.new_track])

        class Server:
            def __init__(self, playlist):
                self._playlist = playlist

            def playlists(self):
                return [self._playlist]

        self.window.plex_server = Server(self.playlist)
        self.window._current_smart_match_library_section = lambda: FakeSection()

        self._saved_hydrate = legacy_main._hydrate_plex_tracks_by_rating_keys

    def tearDown(self):
        legacy_main._hydrate_plex_tracks_by_rating_keys = self._saved_hydrate
        self.window.close()
        super().tearDown()

    def test_revert_restores_previous_snapshot(self):
        legacy_main._hydrate_plex_tracks_by_rating_keys = lambda section, keys: [self.old_track]
        run = {
            "playlist_name": "My Playlist",
            "before_snapshot": [{"rating_key": "1", "title": "Old"}],
        }
        ok, message = self.window._revert_sync_run(run)
        self.assertTrue(ok, message)
        self.assertIn(self.new_track, self.playlist.removed)
        self.assertIn(self.old_track, self.playlist.added)

    def test_revert_reports_tracks_no_longer_in_library(self):
        legacy_main._hydrate_plex_tracks_by_rating_keys = lambda section, keys: [self.old_track]
        run = {
            "playlist_name": "My Playlist",
            "before_snapshot": [
                {"rating_key": "1", "title": "Old"},
                {"rating_key": "77", "title": "Deleted"},
            ],
        }
        ok, message = self.window._revert_sync_run(run)
        self.assertTrue(ok)
        self.assertIn("no longer in the library", message)

    def test_revert_aborts_when_nothing_can_be_restored(self):
        legacy_main._hydrate_plex_tracks_by_rating_keys = lambda section, keys: []
        run = {
            "playlist_name": "My Playlist",
            "before_snapshot": [{"rating_key": "77", "title": "Deleted"}],
        }
        ok, _message = self.window._revert_sync_run(run)
        self.assertFalse(ok)
        self.assertEqual(self.playlist.removed, [], "must not clear the playlist it cannot restore")

    def test_revert_fails_cleanly_for_a_deleted_playlist(self):
        run = {"playlist_name": "Gone", "before_snapshot": []}
        ok, message = self.window._revert_sync_run(run)
        self.assertFalse(ok)
        self.assertIn("no longer exists", message)

    def test_revert_requires_a_connection(self):
        self.window.plex_server = None
        ok, message = self.window._revert_sync_run({"playlist_name": "X", "before_snapshot": []})
        self.assertFalse(ok)
        self.assertIn("Connect to Plex", message)


class DialogConstructionTests(StoreBackedTestCase):
    def test_missing_tracks_dialog_populates(self):
        self.missing_store.record_missing(
            self.library_key,
            [{"title": "Alpha", "artist": "A"}, {"title": "Beta", "artist": "B"}],
            "Playlist X",
        )
        dialog = MissingTracksDialog(
            self.missing_store, self.library_key, None, None, None
        )
        self.assertEqual(dialog.table.rowCount(), 2)
        self.assertIn("2 still missing", dialog.status_label.text())
        # No library section available -> re-check must be disabled, not crash.
        self.assertFalse(dialog.recheck_btn.isEnabled())
        dialog.close()

    def test_missing_tracks_dialog_status_filter(self):
        self.missing_store.record_missing(self.library_key, [{"title": "Alpha", "artist": "A"}], "P")
        self.missing_store.mark_ignored(self.library_key, track_fingerprint("Alpha", "A"))
        dialog = MissingTracksDialog(self.missing_store, self.library_key, None, None, None)
        self.assertEqual(dialog.table.rowCount(), 0)
        dialog.status_combo.setCurrentIndex(dialog.status_combo.findData(None))  # All
        self.assertEqual(dialog.table.rowCount(), 1)
        dialog.close()

    def test_match_memory_dialog_populates(self):
        self.match_store.remember_match(
            self.library_key, {"title": "Song", "artist": "Band"}, "42", "Song", "Band", "Album"
        )
        self.match_store.remember_missing(self.library_key, {"title": "Gone", "artist": "Nobody"})
        dialog = MatchMemoryDialog(self.match_store, self.library_key)
        self.assertEqual(dialog.table.rowCount(), 2)
        dialog.close()

    def test_sync_history_dialog_shows_diff(self):
        run_id = self.history_store.start_run(
            self.library_key,
            "My Playlist",
            "spotify",
            before_snapshot=[{"rating_key": "1", "title": "Old", "artist": "A"}],
        )
        self.history_store.finish_run(
            run_id, after_snapshot=[{"rating_key": "2", "title": "New", "artist": "B"}]
        )
        dialog = SyncHistoryDialog(self.history_store, self.library_key, lambda run: (True, "ok"))
        self.assertEqual(dialog.table.rowCount(), 1)
        dialog.table.selectRow(0)
        detail = dialog.detail.toPlainText()
        self.assertIn("+ B - New", detail)
        self.assertIn("- A - Old", detail)
        self.assertTrue(dialog.revert_btn.isEnabled())
        dialog.close()

    def test_sync_history_revert_disabled_without_callback(self):
        run_id = self.history_store.start_run(self.library_key, "P", before_snapshot=[{"rating_key": "1"}])
        self.history_store.finish_run(run_id, after_snapshot=[])
        dialog = SyncHistoryDialog(self.history_store, self.library_key, None)
        dialog.table.selectRow(0)
        self.assertFalse(dialog.revert_btn.isEnabled())
        dialog.close()


class PlaylistEditorRowMenuTests(unittest.TestCase):
    """The overflow (⋮) column must stay complete and centred.

    PlaylistTrackTable.dropEvent rebuilds a dragged row with removeRow/insertRow, which
    discards that row's cell widget -- so a drag reorder used to leave a row with no
    overflow button at all.
    """

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        redirect_config_files(self, self._tmpdir.name)

        class FakePlaylist:
            title = "T"
            ratingKey = 1

            def items(self):
                return []

        self._original_loader = legacy_main.PlaylistEditorDialog.start_background_loading
        legacy_main.PlaylistEditorDialog.start_background_loading = lambda self: None
        self.dialog = legacy_main.PlaylistEditorDialog(FakePlaylist(), None, None)

        table = self.dialog.tracks_table
        table.setRowCount(5)
        for row in range(5):
            for col in range(4):
                table.setItem(row, col, QTableWidgetItem(f"r{row}c{col}"))
            self.dialog._install_row_menu_button(row)

    def tearDown(self):
        legacy_main.PlaylistEditorDialog.start_background_loading = self._original_loader
        self.dialog.close()
        restore_config_files(self)
        self._tmpdir.cleanup()

    def _widget_flags(self):
        table = self.dialog.tracks_table
        return [table.cellWidget(row, 4) is not None for row in range(table.rowCount())]

    def test_every_row_starts_with_an_overflow_button(self):
        self.assertTrue(all(self._widget_flags()))

    def test_reorder_rebuild_loses_then_restores_the_button(self):
        table = self.dialog.tracks_table
        table.removeRow(2)
        table.insertRow(2)
        for col in range(4):
            table.setItem(2, col, QTableWidgetItem("moved"))
        self.assertFalse(self._widget_flags()[2], "precondition: rebuild drops the widget")

        self.dialog._refresh_row_menu_buttons()
        self.assertTrue(all(self._widget_flags()), "refresh must fill every gap")

    def test_button_is_centred_and_reachable_from_its_holder(self):
        from PyQt6.QtWidgets import QPushButton

        holder = self.dialog.tracks_table.cellWidget(0, 4)
        button = holder.findChild(QPushButton)
        self.assertIsNotNone(button)
        self.assertTrue(holder.isAncestorOf(button), "row lookup walks holder -> button")
        self.assertEqual(
            holder.layout().itemAt(0).alignment(), Qt.AlignmentFlag.AlignCenter
        )


class MainWindowWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        redirect_config_files(self, self._tmpdir.name)

    def tearDown(self):
        restore_config_files(self)
        self._tmpdir.cleanup()

    def test_new_entry_points_exist(self):
        original_load_config = legacy_main.PlexPlaylistManager.load_config
        legacy_main.PlexPlaylistManager.load_config = lambda self: None
        try:
            window = legacy_main.PlexPlaylistManager()
            for name in [
                "open_missing_tracks_dialog",
                "open_match_memory_dialog",
                "open_sync_history_dialog",
                "preview_selected_playlists",
                "_revert_sync_run",
                "_current_library_key",
                "_collect_sync_configs",
            ]:
                self.assertTrue(callable(getattr(window, name, None)), f"missing: {name}")
            for widget in [
                "missing_tracks_btn",
                "match_memory_btn",
                "preview_sync_btn",
                "sync_history_btn",
                "metric_missing",
            ]:
                self.assertIsNotNone(getattr(window, widget, None), f"missing widget: {widget}")
            # Without a Plex connection these must degrade, not raise.
            self.assertIsNone(window._current_library_key())
            self.assertEqual(window._missing_track_count(), 0)
            window.close()
        finally:
            legacy_main.PlexPlaylistManager.load_config = original_load_config


if __name__ == "__main__":
    unittest.main()
