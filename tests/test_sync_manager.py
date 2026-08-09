"""Tests for playlist renaming, the Sync Manager rebuild, and the flow layout.

Three things worth pinning down here:

* Renaming was missing entirely -- the only "Rename" prompts in the app were
  import-time collision dialogs. Sync configurations are keyed by playlist *name*, so
  a rename that did not carry the configuration over would silently orphan it.
* The Sync Manager's row-building code existed in three near-identical copies; they
  now share `add_sync_config_row`, and the cell *text* has to stay exactly what it was
  because a dozen call sites read the playlist name and source URL back out of it.
* A QHBoxLayout of page actions reports the sum of its children as its minimum width,
  which is what gave the Playlists page a floor wide enough to stop it ever reflowing.
"""

import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QRect, QSize, Qt
from PyQt6.QtWidgets import QApplication, QPushButton, QWidget

from syncra.app import legacy_main
from syncra.ui.widgets import playlist_grid as pg
from syncra.ui.widgets.flow_layout import FlowLayout


class FakePlaylist:
    def __init__(self, title, rating_key=1, leaf_count=10):
        self.title = title
        self.ratingKey = rating_key
        self.playlistType = "audio"
        self.leafCount = leaf_count
        self.thumb = f"/library/metadata/{rating_key}/composite/1"
        self.edits = []
        self.reloaded = 0

    def editTitle(self, title, locked=True):
        self.edits.append({"title": title})
        self.title = title

    def edit(self, **kwargs):
        raise AssertionError("edit() is deprecated in plexapi; use editTitle()")

    def reload(self):
        self.reloaded += 1


class FakeServer:
    def url(self, path, includeToken=False):
        return f"http://plex.local{path}"

    def playlists(self):
        return []


class ServiceBadgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_streaming_services_are_recognised(self):
        cases = {
            "https://open.spotify.com/playlist/abc": "Spotify",
            "https://www.deezer.com/playlist/123": "Deezer",
            "https://tidal.com/browse/playlist/x": "TIDAL",
            "https://listenbrainz.org/user/me/": "ListenBrainz",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                self.assertEqual(pg.identify_service(source)[0], expected)

    def test_a_local_path_is_not_called_a_web_source(self):
        self.assertEqual(pg.identify_service(r"D:\Music\mix.m3u")[0], "Local file")

    def test_an_unknown_url_is_labelled_generically(self):
        self.assertEqual(pg.identify_service("https://example.com/list")[0], "Web")

    def test_empty_source_does_not_raise(self):
        self.assertTrue(pg.identify_service("")[0])
        self.assertTrue(pg.identify_service(None)[0])

    def test_badge_is_square_and_opaque_in_the_middle(self):
        badge = pg.badge_pixmap("Spotify", "#1db954", 24)
        self.assertEqual((badge.width(), badge.height()), (24, 24))
        self.assertGreater(badge.toImage().pixelColor(12, 12).alpha(), 0)


class FlowLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _host(self, count=5, button_width=120):
        host = QWidget()
        layout = FlowLayout(spacing=8)
        for i in range(count):
            button = QPushButton(f"Action {i}")
            button.setFixedSize(button_width, 30)
            layout.addWidget(button)
        host.setLayout(layout)
        self.addCleanup(host.deleteLater)
        return host, layout

    def test_minimum_width_is_one_item_not_the_whole_row(self):
        """This is the property that lets the page narrow at all."""
        _, layout = self._host(count=5, button_width=120)
        self.assertLess(layout.minimumSize().width(), 5 * 120)
        self.assertGreaterEqual(layout.minimumSize().width(), 120)

    def test_everything_fits_on_one_line_when_there_is_room(self):
        host, layout = self._host(count=3, button_width=100)
        host.resize(600, 200)
        host.show()
        self.app.processEvents()
        tops = {layout.itemAt(i).geometry().top() for i in range(layout.count())}
        self.assertEqual(len(tops), 1)

    def test_items_wrap_onto_more_lines_when_narrow(self):
        host, layout = self._host(count=5, button_width=120)
        host.resize(300, 400)
        host.show()
        self.app.processEvents()
        tops = {layout.itemAt(i).geometry().top() for i in range(layout.count())}
        self.assertGreater(len(tops), 1, "buttons should have wrapped")

    def test_height_for_width_grows_as_width_shrinks(self):
        _, layout = self._host(count=6, button_width=120)
        self.assertGreater(layout.heightForWidth(200), layout.heightForWidth(900))

    def test_take_at_removes_items(self):
        _, layout = self._host(count=3)
        self.assertEqual(layout.count(), 3)
        layout.takeAt(0)
        self.assertEqual(layout.count(), 2)

    def test_out_of_range_access_is_none(self):
        _, layout = self._host(count=2)
        self.assertIsNone(layout.itemAt(9))
        self.assertIsNone(layout.takeAt(9))

    def test_an_empty_layout_is_harmless(self):
        host = QWidget()
        layout = FlowLayout()
        host.setLayout(layout)
        self.addCleanup(host.deleteLater)
        self.assertEqual(layout.count(), 0)
        self.assertEqual(layout.heightForWidth(400), 0)


class WindowTestCase(unittest.TestCase):
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
        self.window.plex_server = FakeServer()

    def tearDown(self):
        try:
            self.window.close()
        finally:
            pg.CoverFetcher.request = self._real_request
            pg.CoverFetcher.cached_bytes = self._real_cached


class RenamePlaylistTests(WindowTestCase):
    def setUp(self):
        super().setUp()
        self.playlist = FakePlaylist("Road Trip", rating_key=7)
        self.window.playlists = [self.playlist]
        self.window.playlist_data = [(self.playlist, None)]
        self.window.update_playlist_listwidget()
        self.item = self.window.playlist_listwidget.item(0)

    def _rename_to(self, text, accepted=True):
        with mock.patch.object(
            legacy_main.QInputDialog, "getText", return_value=(text, accepted)
        ):
            return self.window.rename_playlist_item(self.item)

    def test_a_rename_reaches_the_server(self):
        self.assertTrue(self._rename_to("Summer Drive"))
        self.assertEqual(self.playlist.edits, [{"title": "Summer Drive"}])
        self.assertEqual(self.playlist.reloaded, 1)

    def test_the_tile_shows_the_new_name(self):
        self._rename_to("Summer Drive")
        self.assertEqual(self.item.data(pg.TITLE_ROLE), "Summer Drive")
        self.assertEqual(self.item.text(), "Summer Drive")

    def test_cancelling_changes_nothing(self):
        self.assertFalse(self._rename_to("Summer Drive", accepted=False))
        self.assertEqual(self.playlist.edits, [])

    def test_an_unchanged_name_is_not_sent(self):
        self.assertFalse(self._rename_to("Road Trip"))
        self.assertEqual(self.playlist.edits, [])

    def test_a_blank_name_is_rejected(self):
        self.assertFalse(self._rename_to("   "))
        self.assertEqual(self.playlist.edits, [])

    def test_surrounding_whitespace_is_collapsed(self):
        """Plex keeps padding, which makes two playlists look identical in a list."""
        self._rename_to("  Summer   Drive  ")
        self.assertEqual(self.playlist.edits, [{"title": "Summer Drive"}])

    def test_a_duplicate_name_is_refused(self):
        self.window.playlists.append(FakePlaylist("Taken", rating_key=8))
        with mock.patch.object(legacy_main.QMessageBox, "warning") as warned:
            self.assertFalse(self._rename_to("Taken"))
        self.assertTrue(warned.called)
        self.assertEqual(self.playlist.edits, [])

    def test_renaming_to_its_own_name_with_different_case_is_allowed(self):
        self.assertTrue(self._rename_to("ROAD TRIP"))
        self.assertEqual(self.playlist.edits, [{"title": "ROAD TRIP"}])

    def test_the_deprecated_edit_api_is_not_used(self):
        """plexapi 4.17 warns on Playlist.edit(); editTitle() is the supported call."""
        self._rename_to("Summer Drive")
        self.assertEqual(self.playlist.edits, [{"title": "Summer Drive"}])

    def test_a_server_error_is_reported_and_not_swallowed(self):
        self.playlist.editTitle = mock.Mock(side_effect=RuntimeError("403 forbidden"))
        with mock.patch.object(legacy_main.QMessageBox, "critical") as reported:
            self.assertFalse(self._rename_to("Summer Drive"))
        self.assertTrue(reported.called)
        self.assertEqual(self.item.data(pg.TITLE_ROLE), "Road Trip")

    def test_a_missing_playlist_object_warns_instead_of_crashing(self):
        self.item.setData(Qt.ItemDataRole.UserRole, None)
        with mock.patch.object(legacy_main.QMessageBox, "warning") as warned:
            self.assertFalse(self.window.rename_playlist_item(self.item))
        self.assertTrue(warned.called)

    def test_no_item_is_a_no_op(self):
        self.assertFalse(self.window.rename_playlist_item(None))

    def test_the_sync_configuration_follows_the_rename(self):
        """Configs are keyed by name; without this the next sync loses the playlist."""
        self.window.add_sync_config_row("Road Trip", "https://open.spotify.com/x")
        self._rename_to("Summer Drive")
        self.assertEqual(
            self.window.sync_configs_table.item(0, 0).text(), "Summer Drive"
        )

    def test_an_unrelated_sync_configuration_is_left_alone(self):
        self.window.add_sync_config_row("Other List", "https://open.spotify.com/x")
        self._rename_to("Summer Drive")
        self.assertEqual(self.window.sync_configs_table.item(0, 0).text(), "Other List")


class SyncConfigRowTests(WindowTestCase):
    def test_cell_text_is_unchanged_by_the_rebuild(self):
        """A dozen call sites read the name and URL straight out of these cells."""
        self.window.add_sync_config_row(
            "Road Trip", "https://open.spotify.com/playlist/x", "2026-08-08 21:14"
        )
        table = self.window.sync_configs_table
        self.assertEqual(table.item(0, 0).text(), "Road Trip")
        self.assertEqual(table.item(0, 1).text(), "https://open.spotify.com/playlist/x")
        self.assertEqual(table.item(0, 2).text(), "2026-08-08 21:14")

    def test_last_sync_defaults_to_never(self):
        self.window.add_sync_config_row("Road Trip", "src")
        self.assertEqual(self.window.sync_configs_table.item(0, 2).text(), "Never")

    def test_cells_are_not_editable(self):
        self.window.add_sync_config_row("Road Trip", "src")
        table = self.window.sync_configs_table
        for column in (0, 1, 2):
            self.assertFalse(
                bool(table.item(0, column).flags() & Qt.ItemFlag.ItemIsEditable)
            )

    def test_the_source_cell_carries_a_service_badge_and_tooltip(self):
        self.window.add_sync_config_row("Road Trip", "https://open.spotify.com/x")
        source = self.window.sync_configs_table.item(0, 1)
        self.assertFalse(source.icon().isNull())
        self.assertIn("Spotify", source.toolTip())

    def test_the_playlist_cell_always_gets_artwork(self):
        """Even with no matching playlist loaded, a generated tile stands in."""
        self.window.add_sync_config_row("Unknown List", "src")
        self.assertFalse(self.window.sync_configs_table.item(0, 0).icon().isNull())

    def test_the_clear_checkbox_round_trips(self):
        self.window.add_sync_config_row("A", "src", clear_before=True)
        self.window.add_sync_config_row("B", "src", clear_before=False)
        self.assertTrue(self.window._is_clear_before_sync_enabled(0))
        self.assertFalse(self.window._is_clear_before_sync_enabled(1))

    def test_each_row_gets_its_action_buttons(self):
        self.window.add_sync_config_row("Road Trip", "src")
        self.assertIsNotNone(self.window.sync_configs_table.cellWidget(0, 4))

    def test_rows_are_tall_enough_for_the_cover(self):
        self.window.add_sync_config_row("Road Trip", "src")
        self.assertGreaterEqual(
            self.window.sync_configs_table.rowHeight(0),
            self.window.SYNC_COVER_SIZE,
        )

    def test_rows_append_rather_than_replace(self):
        self.window.add_sync_config_row("A", "src")
        self.window.add_sync_config_row("B", "src")
        self.assertEqual(self.window.sync_configs_table.rowCount(), 2)


class SyncMetricsTests(WindowTestCase):
    def test_configured_count_tracks_the_table(self):
        self.assertEqual(self.window.sync_metric_configured._value_label.text(), "0")
        self.window.add_sync_config_row("A", "src")
        self.window.add_sync_config_row("B", "src")
        self.assertEqual(self.window.sync_metric_configured._value_label.text(), "2")

    def test_auto_sync_reads_off_when_disabled(self):
        self.window.auto_sync_checkbox.setChecked(False)
        self.window.refresh_sync_metrics()
        self.assertEqual(self.window.sync_metric_auto._value_label.text(), "Off")

    def test_auto_sync_reports_its_interval_when_enabled(self):
        self.window.sync_interval_spinbox.setValue(45)
        self.window.auto_sync_checkbox.setChecked(True)
        self.window.refresh_sync_metrics()
        self.assertIn("45", self.window.sync_metric_auto._value_label.text())

    def test_last_sync_shows_the_most_recent_real_timestamp(self):
        self.window.add_sync_config_row("A", "src", "2026-08-07 10:00")
        self.window.add_sync_config_row("B", "src", "2026-08-09 08:31")
        self.window.add_sync_config_row("C", "src", "Never")
        self.window.refresh_sync_metrics()
        self.assertEqual(
            self.window.sync_metric_last._value_label.text(), "2026-08-09 08:31"
        )

    def test_last_sync_is_never_when_nothing_has_run(self):
        self.window.add_sync_config_row("A", "src", "Never")
        self.window.refresh_sync_metrics()
        self.assertEqual(self.window.sync_metric_last._value_label.text(), "Never")


class SyncTableLayoutTests(WindowTestCase):
    def test_source_is_the_only_stretch_column(self):
        """Both Source and Actions stretching clipped the Delete button."""
        header = self.window.sync_configs_table.horizontalHeader()
        self.assertFalse(header.stretchLastSection())

    def test_sections_have_a_floor_so_source_cannot_collapse(self):
        header = self.window.sync_configs_table.horizontalHeader()
        self.assertGreaterEqual(header.minimumSectionSize(), 80)

    def test_the_table_shows_icons_at_cover_size(self):
        self.assertEqual(
            self.window.sync_configs_table.iconSize(),
            QSize(self.window.SYNC_COVER_SIZE, self.window.SYNC_COVER_SIZE),
        )


if __name__ == "__main__":
    unittest.main()
