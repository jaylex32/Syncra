"""Tests for the search-as-you-type track picker.

Timings measured against a live library drove the design: hubSearch answered in ~67ms
and covered artists, albums and tracks, where filtering tracks by artist.title took
~1270ms. The picker leads with hubSearch and expands artist/album hits into tracks.
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from syncra.ui.widgets import track_picker
from syncra.ui.widgets.track_picker import LibrarySearchThread, TrackPicker


class FakeTrack:
    def __init__(self, rating_key, title, artist="Artist", album="Album"):
        self.ratingKey = rating_key
        self.title = title
        self.grandparentTitle = artist
        self.parentTitle = album
        self.type = "track"


class FakeAlbum:
    type = "album"

    def __init__(self, title, tracks):
        self.title = title
        self._tracks = tracks

    def tracks(self):
        return list(self._tracks)


class FakeArtist:
    type = "artist"

    def __init__(self, title, tracks):
        self.title = title
        self._tracks = tracks

    def tracks(self):
        return list(self._tracks)


class FakeSection:
    def __init__(self, hub=None, title_hits=None, hub_raises=None, title_raises=None):
        self._hub = hub or []
        self._title_hits = title_hits or []
        self._hub_raises = hub_raises
        self._title_raises = title_raises
        self.hub_calls = []

    def hubSearch(self, query, limit=None):
        self.hub_calls.append(query)
        if self._hub_raises:
            raise self._hub_raises
        return list(self._hub)

    def searchTracks(self, title=None, maxresults=None):
        if self._title_raises:
            raise self._title_raises
        return list(self._title_hits)


class SearchThreadTests(unittest.TestCase):
    """_search() is plain Python; call it directly rather than starting a thread."""

    def test_track_hits_are_returned(self):
        section = FakeSection(hub=[FakeTrack(1, "Song")])
        results = LibrarySearchThread(section, "song", 1)._search()
        self.assertEqual([t.ratingKey for t, _ in results], [1])
        self.assertEqual(results[0][1], "track")

    def test_album_hits_expand_into_their_tracks(self):
        album = FakeAlbum("Cosa Nuestra", [FakeTrack(10, "A"), FakeTrack(11, "B")])
        section = FakeSection(hub=[album])
        results = LibrarySearchThread(section, "cosa", 1)._search()
        self.assertEqual([t.ratingKey for t, _ in results], [10, 11])
        self.assertTrue(all(reason == "album" for _, reason in results))

    def test_artist_hits_expand_into_their_tracks(self):
        artist = FakeArtist("Bad Bunny", [FakeTrack(20, "X"), FakeTrack(21, "Y")])
        section = FakeSection(hub=[artist])
        results = LibrarySearchThread(section, "bad bunny", 1)._search()
        self.assertEqual([t.ratingKey for t, _ in results], [20, 21])
        self.assertTrue(all(reason == "artist" for _, reason in results))

    def test_direct_track_hits_rank_before_expanded_ones(self):
        album = FakeAlbum("Album", [FakeTrack(10, "From album")])
        section = FakeSection(hub=[FakeTrack(1, "Direct"), album])
        results = LibrarySearchThread(section, "q", 1)._search()
        self.assertEqual([t.ratingKey for t, _ in results], [1, 10])

    def test_duplicates_across_sources_are_dropped(self):
        shared = FakeTrack(5, "Shared")
        album = FakeAlbum("Album", [FakeTrack(5, "Shared again")])
        section = FakeSection(hub=[shared, album], title_hits=[FakeTrack(5, "Yet again")])
        results = LibrarySearchThread(section, "q", 1)._search()
        self.assertEqual([t.ratingKey for t, _ in results], [5])

    def test_title_search_supplements_hub_results(self):
        section = FakeSection(hub=[FakeTrack(1, "Hub")], title_hits=[FakeTrack(2, "Title")])
        results = LibrarySearchThread(section, "q", 1)._search()
        self.assertEqual(sorted(t.ratingKey for t, _ in results), [1, 2])

    def test_hub_failure_falls_back_to_title_search(self):
        """hubSearch is the fast path, not the only one."""
        section = FakeSection(hub_raises=RuntimeError("no hubs"),
                              title_hits=[FakeTrack(3, "Fallback")])
        results = LibrarySearchThread(section, "q", 1)._search()
        self.assertEqual([t.ratingKey for t, _ in results], [3])

    def test_both_sources_failing_yields_no_results_not_an_error(self):
        section = FakeSection(hub_raises=RuntimeError("a"), title_raises=RuntimeError("b"))
        self.assertEqual(LibrarySearchThread(section, "q", 1)._search(), [])

    def test_expansion_is_capped(self):
        albums = [FakeAlbum(f"A{i}", [FakeTrack(100 + i, f"T{i}")]) for i in range(8)]
        section = FakeSection(hub=albums)
        results = LibrarySearchThread(section, "q", 1)._search()
        self.assertEqual(len(results), track_picker.MAX_ALBUMS_EXPANDED)

    def test_total_results_are_capped(self):
        big = FakeArtist("Big", [FakeTrack(i, f"T{i}") for i in range(500)])
        section = FakeSection(hub=[big])
        results = LibrarySearchThread(section, "q", 1)._search()
        self.assertLessEqual(len(results), track_picker.MAX_RESULTS)


class PickerWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.section = FakeSection(hub=[FakeTrack(1, "Song", "Band", "Record")])
        self.picker = TrackPicker(self.section)

    def tearDown(self):
        self.picker.shutdown()
        self.picker.deleteLater()

    def test_short_queries_do_not_search(self):
        self.picker.search_input.setText("a")
        self.assertFalse(self.picker._debounce.isActive())
        self.assertEqual(self.section.hub_calls, [])

    def test_typing_starts_the_debounce_rather_than_searching_immediately(self):
        self.picker.search_input.setText("song")
        self.assertTrue(self.picker._debounce.isActive())
        self.assertEqual(self.section.hub_calls, [], "must wait for the pause in typing")

    def test_rapid_typing_collapses_into_one_search(self):
        for text in ("so", "son", "song"):
            self.picker.search_input.setText(text)
        self.picker._run_search()
        self.picker._thread.wait(3000)
        self.assertEqual(
            self.section.hub_calls, ["song"],
            "only the final query should reach the server",
        )

    def test_results_populate_and_select_the_first_row(self):
        track = FakeTrack(7, "Chosen", "Band", "Record")
        self.picker._sequence = 3
        self.picker._on_found([(track, "track")], "chosen", 3)
        self.assertEqual(self.picker.results.count(), 1)
        self.assertIs(self.picker.selected_track(), track)
        self.assertIn("Record", self.picker.results.item(0).text())

    def test_stale_results_are_ignored(self):
        """A slow earlier query must not overwrite a newer one's results."""
        self.picker._sequence = 5
        self.picker._on_found([(FakeTrack(9, "Old"), "track")], "old", 4)
        self.assertEqual(self.picker.results.count(), 0)
        self.assertIsNone(self.picker.selected_track())

    def test_empty_results_report_the_query(self):
        self.picker._sequence = 1
        self.picker._on_found([], "nothing", 1)
        self.assertIn("nothing", self.picker.status.text())
        self.assertIsNone(self.picker.selected_track())

    def test_set_track_preselects_without_searching(self):
        track = FakeTrack(4, "Seeded", "Band")
        self.picker.set_track(track)
        self.assertIs(self.picker.selected_track(), track)
        self.assertEqual(self.section.hub_calls, [])
        self.assertEqual(self.picker.search_input.text(), "Seeded")
        self.assertFalse(self.picker._debounce.isActive(),
                         "seeding must not trigger a search")

    def test_clearing_the_box_clears_the_selection(self):
        self.picker.set_track(FakeTrack(4, "Seeded"))
        self.picker.search_input.setText("")
        self.assertIsNone(self.picker.selected_track())

    def test_match_reason_is_surfaced_as_a_tooltip(self):
        self.picker._sequence = 1
        self.picker._on_found([(FakeTrack(1, "T"), "artist")], "q", 1)
        self.assertIn("artist", self.picker.results.item(0).toolTip().lower())


if __name__ == "__main__":
    unittest.main()
