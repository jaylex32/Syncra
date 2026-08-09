"""Tests for the library duplicate scanner.

Timings that motivated the rewrite, measured against a live 14,753-track library:
`track.artist()` cost 25ms and `track.album()` 20ms per track (an HTTP round trip
each, ~11 minutes for the library), while `grandparentTitle` / `parentTitle` carry the
same values from the search response for free. Playlist membership re-fetched all 60
playlists per duplicate track at 71ms each -- 4.2s per track -- and is now indexed once.
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from syncra.app.legacy_main import LibraryDuplicateFinderThread


class FakePart:
    def __init__(self, file="/music/x.flac", size=1000):
        self.file = file
        self.size = size


class FakeMedia:
    def __init__(self, parts=None):
        self.parts = parts if parts is not None else [FakePart()]


class FakeTrack:
    """Mirrors what searchTracks() returns: names present, no lazy lookups needed."""

    def __init__(self, rating_key, title, artist="Artist", album="Album",
                 media=None, bitrate=320):
        self.ratingKey = rating_key
        self.title = title
        self.grandparentTitle = artist
        self.originalTitle = ""
        self.parentTitle = album
        self.duration = 200000
        self.bitrate = bitrate
        self.media = media if media is not None else [FakeMedia()]
        self.artist_calls = 0
        self.album_calls = 0

    # If the scanner ever reaches for these again, the tests below will catch it.
    def artist(self):
        self.artist_calls += 1
        raise AssertionError("artist() is an HTTP round trip; use grandparentTitle")

    def album(self):
        self.album_calls += 1
        raise AssertionError("album() is an HTTP round trip; use parentTitle")


class FakePlaylist:
    def __init__(self, title, tracks, playlist_type="audio"):
        self.title = title
        self.playlistType = playlist_type
        self._tracks = tracks
        self.item_calls = 0

    def items(self):
        self.item_calls += 1
        return list(self._tracks)


class FakeSection:
    type = "artist"

    def __init__(self, title, tracks):
        self.title = title
        self._tracks = tracks
        self.totalSize = len(tracks)

    def searchTracks(self, **kwargs):
        return list(self._tracks)


class FakeLibrary:
    def __init__(self, sections):
        self._sections = sections

    def sections(self):
        return list(self._sections)


class FakeServer:
    def __init__(self, sections, playlists=None):
        self.library = FakeLibrary(sections)
        self._playlists = playlists or []

    def playlists(self):
        return list(self._playlists)


class SignatureTests(unittest.TestCase):
    def setUp(self):
        self.thread = LibraryDuplicateFinderThread(None)

    def test_remaster_and_plain_titles_match(self):
        a = FakeTrack(1, "Bohemian Rhapsody (2011 Remaster)", "Queen")
        b = FakeTrack(2, "bohemian rhapsody", "queen")
        self.assertEqual(
            self.thread.normalize_track_signature(a),
            self.thread.normalize_track_signature(b),
        )

    def test_featured_artist_variants_match(self):
        a = FakeTrack(1, "Umbrella (feat. JAY-Z)", "Rihanna")
        b = FakeTrack(2, "Umbrella", "Rihanna")
        self.assertEqual(
            self.thread.normalize_track_signature(a),
            self.thread.normalize_track_signature(b),
        )

    def test_different_artists_do_not_match(self):
        a = FakeTrack(1, "Umbrella", "Rihanna")
        b = FakeTrack(2, "Umbrella", "Metro Boomin")
        self.assertNotEqual(
            self.thread.normalize_track_signature(a),
            self.thread.normalize_track_signature(b),
        )

    def test_falls_back_to_the_artist_attribute_not_the_method(self):
        track = FakeTrack(1, "Song", artist="")
        track.originalTitle = "Fallback Artist"
        self.thread.normalize_track_signature(track)
        self.assertEqual(track.artist_calls, 0)


class ScanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _run(self, server, include_playlists=True, stop_immediately=False):
        thread = LibraryDuplicateFinderThread(server)
        thread.include_playlist_check = include_playlists
        captured = {}
        thread.duplicates_found.connect(
            lambda groups, cancelled: captured.update(groups=groups, cancelled=cancelled)
        )
        thread.error.connect(lambda message: captured.update(error=message))
        if stop_immediately:
            thread.stop()
        thread.run()
        return captured

    def test_finds_a_duplicate_group(self):
        tracks = [
            FakeTrack(1, "Song", "Band", "Album A"),
            FakeTrack(2, "Song", "Band", "Album B"),
            FakeTrack(3, "Other", "Band"),
        ]
        result = self._run(FakeServer([FakeSection("Music", tracks)]), include_playlists=False)
        self.assertEqual(len(result["groups"]), 1)
        self.assertEqual(len(result["groups"][0]), 2)
        self.assertFalse(result["cancelled"])

    def test_never_calls_the_expensive_lookups(self):
        """artist() and album() are one HTTP request each; the fakes raise if used."""
        tracks = [FakeTrack(1, "Song", "Band"), FakeTrack(2, "Song", "Band")]
        self._run(FakeServer([FakeSection("Music", tracks)]), include_playlists=False)
        self.assertTrue(all(t.artist_calls == 0 and t.album_calls == 0 for t in tracks))

    def test_track_info_is_populated_from_attributes(self):
        tracks = [
            FakeTrack(1, "Song", "Band", "Album A",
                      media=[FakeMedia([FakePart("/music/a.flac", 5000)])]),
            FakeTrack(2, "Song", "Band", "Album B"),
        ]
        result = self._run(FakeServer([FakeSection("Music", tracks)]), include_playlists=False)
        info = result["groups"][0][0]
        self.assertEqual(info["artist"], "Band")
        self.assertEqual(info["album"], "Album A")
        self.assertEqual(info["file_path"], "/music/a.flac")
        self.assertEqual(info["file_size"], 5000)

    def test_missing_media_does_not_break_the_scan(self):
        tracks = [FakeTrack(1, "Song", "Band", media=[]),
                  FakeTrack(2, "Song", "Band", media=None)]
        tracks[1].media = []
        result = self._run(FakeServer([FakeSection("Music", tracks)]), include_playlists=False)
        self.assertEqual(result["groups"][0][0]["file_path"], "Unknown Path")

    def test_biggest_groups_come_first(self):
        tracks = (
            [FakeTrack(1, "Pair", "A"), FakeTrack(2, "Pair", "A")]
            + [FakeTrack(i, "Triple", "B") for i in range(3, 6)]
        )
        result = self._run(FakeServer([FakeSection("Music", tracks)]), include_playlists=False)
        self.assertEqual([len(group) for group in result["groups"]], [3, 2])

    def test_playlists_are_fetched_once_each_not_once_per_track(self):
        tracks = [FakeTrack(i, "Song", "Band") for i in range(1, 6)]
        playlist = FakePlaylist("Road Trip", tracks)
        server = FakeServer([FakeSection("Music", tracks)], [playlist])
        result = self._run(server, include_playlists=True)
        self.assertEqual(
            playlist.item_calls, 1,
            "the playlist index must be built once, not per duplicate track",
        )
        self.assertEqual(result["groups"][0][0]["playlists"], ["Road Trip"])

    def test_non_audio_playlists_are_skipped(self):
        tracks = [FakeTrack(1, "Song", "Band"), FakeTrack(2, "Song", "Band")]
        video = FakePlaylist("Movies", tracks, playlist_type="video")
        server = FakeServer([FakeSection("Music", tracks)], [video])
        self._run(server, include_playlists=True)
        self.assertEqual(video.item_calls, 0)

    def test_skipping_the_playlist_check_leaves_the_lists_empty(self):
        tracks = [FakeTrack(1, "Song", "Band"), FakeTrack(2, "Song", "Band")]
        playlist = FakePlaylist("Road Trip", tracks)
        server = FakeServer([FakeSection("Music", tracks)], [playlist])
        result = self._run(server, include_playlists=False)
        self.assertEqual(playlist.item_calls, 0)
        self.assertEqual(result["groups"][0][0]["playlists"], [])

    def test_cancelling_still_reports_what_was_found(self):
        tracks = [FakeTrack(1, "Song", "Band"), FakeTrack(2, "Song", "Band")]
        result = self._run(
            FakeServer([FakeSection("Music", tracks)]), stop_immediately=True
        )
        self.assertTrue(result["cancelled"], "the cancelled flag must reach the UI")
        self.assertIn("groups", result, "partial results are emitted, not discarded")

    def test_no_music_library_is_an_error(self):
        class VideoSection:
            type = "movie"
            title = "Movies"

        result = self._run(FakeServer([VideoSection()]))
        self.assertIn("No music libraries", result.get("error", ""))

    def test_no_duplicates_emits_an_empty_list(self):
        tracks = [FakeTrack(1, "One", "A"), FakeTrack(2, "Two", "B")]
        result = self._run(FakeServer([FakeSection("Music", tracks)]), include_playlists=False)
        self.assertEqual(result["groups"], [])
        self.assertFalse(result["cancelled"])


if __name__ == "__main__":
    unittest.main()
