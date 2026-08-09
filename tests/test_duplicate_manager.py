"""Tests for the duplicate manager dialog.

The dialog was rebuilt around a QTreeWidget. The old version created a QFrame with
five stacked labels per track, all up front, which for a real result set (1,976 groups
/ 4,411 tracks) meant tens of thousands of widgets in hardcoded light colours.
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from syncra.app.legacy_main import LibraryDuplicateManagerDialog as Manager


def make_track(rating_key, title="Song", artist="Band", album="Album",
               bitrate=900, size=20_000_000, playlists=None):
    return {
        "track": None,
        "title": title,
        "artist": artist,
        "album": album,
        "duration": 200000,
        "bitrate": bitrate,
        "codec": "flac",
        "file_path": f"/music/{rating_key}.flac",
        "file_size": size,
        "rating_key": rating_key,
        "playlists": playlists or [],
    }


class FormattingTests(unittest.TestCase):
    def test_sizes_step_up_through_units(self):
        self.assertEqual(Manager._format_size(512), "512 B")
        self.assertEqual(Manager._format_size(2048), "2 KB")
        self.assertEqual(Manager._format_size(5 * 1024 ** 2), "5.0 MB")
        self.assertEqual(Manager._format_size(3 * 1024 ** 3), "3.0 GB")

    def test_large_totals_read_as_gigabytes_not_megabytes(self):
        """104,199 MB was being shown as '~104199.7MB'."""
        self.assertIn("GB", Manager._format_size(109_000_000_000))

    def test_zero_size_is_safe(self):
        self.assertEqual(Manager._format_size(0), "0 B")
        self.assertEqual(Manager._format_size(None), "0 B")

    def test_time_formatting(self):
        self.assertEqual(Manager._format_time(158000), "2:38")
        self.assertEqual(Manager._format_time(0), "-")

    def test_quality_text_combines_bitrate_and_codec(self):
        self.assertEqual(Manager._quality_text(make_track(1)), "900 kbps · FLAC")

    def test_quality_text_without_bitrate(self):
        track = make_track(1, bitrate=0)
        track["codec"] = ""
        self.assertEqual(Manager._quality_text(track), "Unknown")


class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.groups = [
            [make_track(1, bitrate=1000, size=30_000_000, playlists=["All Music"]),
             make_track(2, bitrate=800, size=20_000_000),
             make_track(3, bitrate=500, size=10_000_000)],
            [make_track(4, "Other", "Act", bitrate=900, size=25_000_000),
             make_track(5, "Other", "Act", bitrate=950, size=26_000_000)],
        ]
        self.dialog = Manager(self.groups, None)

    def tearDown(self):
        self.dialog.close()

    def test_tree_has_one_row_per_group_and_track(self):
        self.assertEqual(self.dialog.tree.topLevelItemCount(), 2)
        self.assertEqual(self.dialog.tree.topLevelItem(0).childCount(), 3)
        self.assertEqual(self.dialog.tree.topLevelItem(1).childCount(), 2)

    def test_best_copy_is_marked_keep_and_cannot_be_ticked(self):
        first = self.dialog.tree.topLevelItem(0).child(0)
        self.assertIn("KEEP", first.text(Manager.COL_NAME))
        self.assertFalse(bool(first.flags() & Qt.ItemFlag.ItemIsUserCheckable))

    def test_best_copy_is_chosen_by_bitrate_not_position(self):
        """The second group's best copy is the second track."""
        best = self.dialog._best_in_group(self.groups[1])
        self.assertEqual(best["rating_key"], 5)

    def test_nothing_is_selected_initially(self):
        self.assertEqual(self.dialog.selected_for_deletion, set())
        self.assertFalse(self.dialog.delete_btn.isEnabled())

    def test_auto_select_ticks_every_copy_but_the_best(self):
        self.dialog.auto_select_best_quality()
        self.assertEqual(self.dialog.selected_for_deletion, {2, 3, 4})

    def test_auto_select_actually_updates_the_checkboxes(self):
        """update_ui_selections used to be a no-op, so the boxes never moved."""
        self.dialog.auto_select_best_quality()
        group = self.dialog.tree.topLevelItem(0)
        states = [
            group.child(i).checkState(Manager.COL_NAME)
            for i in range(1, group.childCount())
        ]
        self.assertTrue(all(state == Qt.CheckState.Checked for state in states))

    def test_clear_selection_unticks_everything(self):
        self.dialog.auto_select_best_quality()
        self.dialog.clear_selection()
        self.assertEqual(self.dialog.selected_for_deletion, set())
        group = self.dialog.tree.topLevelItem(0)
        self.assertEqual(
            group.child(1).checkState(Manager.COL_NAME), Qt.CheckState.Unchecked
        )

    def test_ticking_a_row_updates_the_selection(self):
        child = self.dialog.tree.topLevelItem(0).child(1)
        child.setCheckState(Manager.COL_NAME, Qt.CheckState.Checked)
        self.assertIn(2, self.dialog.selected_for_deletion)
        self.assertTrue(self.dialog.delete_btn.isEnabled())

    def test_unticking_removes_it_again(self):
        child = self.dialog.tree.topLevelItem(0).child(1)
        child.setCheckState(Manager.COL_NAME, Qt.CheckState.Checked)
        child.setCheckState(Manager.COL_NAME, Qt.CheckState.Unchecked)
        self.assertNotIn(2, self.dialog.selected_for_deletion)
        self.assertFalse(self.dialog.delete_btn.isEnabled())

    def test_status_line_reports_count_and_reclaimed_space(self):
        self.dialog.auto_select_best_quality()
        text = self.dialog.selection_info.text()
        self.assertIn("3 track(s) selected", text)
        self.assertIn("MB", text)

    def test_filter_hides_non_matching_groups(self):
        self.dialog.apply_filter("Other")
        self.assertTrue(self.dialog.tree.topLevelItem(0).isHidden())
        self.assertFalse(self.dialog.tree.topLevelItem(1).isHidden())

    def test_clearing_the_filter_shows_everything(self):
        self.dialog.apply_filter("Other")
        self.dialog.apply_filter("")
        self.assertFalse(self.dialog.tree.topLevelItem(0).isHidden())
        self.assertFalse(self.dialog.tree.topLevelItem(1).isHidden())

    def test_filter_matches_album_names_too(self):
        self.dialog.apply_filter("album")
        self.assertFalse(self.dialog.tree.topLevelItem(0).isHidden())

    def test_playlists_column_is_populated(self):
        keep_row = self.dialog.tree.topLevelItem(0).child(0)
        self.assertEqual(keep_row.text(Manager.COL_PLAYLISTS), "All Music")


class ScaleTests(unittest.TestCase):
    """Bulk insertion matters: per-item parenting fired a model signal per row."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_a_realistic_result_set_builds_quickly(self):
        import time

        groups = [
            [make_track(i * 3 + j, f"Song {i}", f"Artist {i}", bitrate=900 + j)
             for j in range(3)]
            for i in range(1976)
        ]
        started = time.perf_counter()
        dialog = Manager(groups, None)
        elapsed = time.perf_counter() - started
        try:
            self.assertEqual(dialog.tree.topLevelItemCount(), 1976)
            self.assertLess(elapsed, 3.0, f"building took {elapsed:.1f}s")
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()
