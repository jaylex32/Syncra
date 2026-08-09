import os
import tempfile
import unittest

from syncra.services.library_data_db import LibraryDataDB
from syncra.services.match_memory import KIND_MATCH, KIND_MISSING, MatchMemoryStore
from syncra.services.missing_tracks import (
    STATUS_IGNORED,
    STATUS_MISSING,
    STATUS_RESOLVED,
    MissingTracksStore,
)
from syncra.services.sync_history import (
    STATUS_SUCCESS,
    SyncHistoryStore,
    diff_snapshots,
)
from syncra.services.track_identity import normalize_artist, normalize_title, track_fingerprint


class FakeTrack:
    def __init__(self, rating_key, title, artist="", album=""):
        self.ratingKey = rating_key
        self.title = title
        self.grandparentTitle = artist
        self.parentTitle = album


class StoreTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db = LibraryDataDB(os.path.join(self._tmpdir.name, "test.sqlite"))

    def tearDown(self):
        self._tmpdir.cleanup()


class TrackIdentityTests(unittest.TestCase):
    def test_fingerprint_is_stable_across_formatting_noise(self):
        a = track_fingerprint("Bohemian Rhapsody (2011 Remaster)", "Queen")
        b = track_fingerprint("bohemian rhapsody", "queen")
        self.assertEqual(a, b)

    def test_fingerprint_ignores_featured_artists(self):
        a = track_fingerprint("Umbrella (feat. JAY-Z)", "Rihanna")
        b = track_fingerprint("Umbrella", "Rihanna feat. JAY-Z")
        self.assertEqual(a, b)

    def test_different_tracks_do_not_collide(self):
        self.assertNotEqual(
            track_fingerprint("Yesterday", "The Beatles"),
            track_fingerprint("Yesterday", "Boyz II Men"),
        )

    def test_title_stripping_never_empties_a_title(self):
        self.assertTrue(normalize_title("(Remastered)"))

    def test_primary_artist_extraction(self):
        self.assertEqual(normalize_artist("Calvin Harris & Dua Lipa"), "calvin harris")

    def test_missing_title_yields_no_fingerprint(self):
        self.assertEqual(track_fingerprint("", "Queen"), "")


class MatchMemoryTests(StoreTestCase):
    def setUp(self):
        super().setUp()
        self.store = MatchMemoryStore(self.db)
        self.track = {"title": "Song One", "artist": "Band", "album": "Record"}

    def test_remember_and_lookup_match(self):
        self.assertTrue(self.store.remember_match("lib1", self.track, "12345"))
        found = self.store.lookup("lib1", self.track)
        self.assertIsNotNone(found)
        self.assertEqual(found["rating_key"], "12345")
        self.assertEqual(found["kind"], KIND_MATCH)

    def test_lookup_survives_formatting_differences(self):
        self.store.remember_match("lib1", self.track, "12345")
        found = self.store.lookup("lib1", {"title": "song one (Remastered)", "artist": "BAND"})
        self.assertIsNotNone(found)
        self.assertEqual(found["rating_key"], "12345")

    def test_overrides_are_scoped_per_library(self):
        self.store.remember_match("lib1", self.track, "12345")
        self.assertIsNone(self.store.lookup("lib2", self.track))

    def test_remember_missing(self):
        self.assertTrue(self.store.remember_missing("lib1", self.track))
        found = self.store.lookup("lib1", self.track)
        self.assertEqual(found["kind"], KIND_MISSING)
        self.assertIsNone(found["rating_key"])

    def test_re_remembering_updates_instead_of_duplicating(self):
        self.store.remember_match("lib1", self.track, "111")
        self.store.remember_match("lib1", self.track, "222")
        self.assertEqual(self.store.count("lib1"), 1)
        self.assertEqual(self.store.lookup("lib1", self.track)["rating_key"], "222")

    def test_forget(self):
        self.store.remember_match("lib1", self.track, "12345")
        fingerprint = track_fingerprint(self.track["title"], self.track["artist"])
        self.assertTrue(self.store.forget("lib1", fingerprint))
        self.assertIsNone(self.store.lookup("lib1", self.track))

    def test_record_hit_increments(self):
        self.store.remember_match("lib1", self.track, "12345")
        fingerprint = track_fingerprint(self.track["title"], self.track["artist"])
        self.store.record_hit("lib1", fingerprint)
        self.store.record_hit("lib1", fingerprint)
        self.assertEqual(self.store.lookup("lib1", self.track)["hit_count"], 2)

    def test_untitled_track_is_rejected(self):
        self.assertFalse(self.store.remember_match("lib1", {"title": "", "artist": "x"}, "1"))


class MissingTracksTests(StoreTestCase):
    def setUp(self):
        super().setUp()
        self.store = MissingTracksStore(self.db)
        self.tracks = [
            {"title": "Alpha", "artist": "A", "album": "One"},
            {"title": "Beta", "artist": "B", "album": "Two"},
        ]

    def test_record_and_list(self):
        self.assertEqual(self.store.record_missing("lib1", self.tracks, "My Playlist"), 2)
        rows = self.store.list_tracks("lib1")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["sources"], ["My Playlist"])

    def test_repeat_records_dedupe_and_accumulate_sources(self):
        self.store.record_missing("lib1", self.tracks, "Playlist A")
        self.store.record_missing("lib1", self.tracks, "Playlist B")
        rows = self.store.list_tracks("lib1")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["times_seen"], 2)
        self.assertCountEqual(rows[0]["sources"], ["Playlist A", "Playlist B"])

    def test_duplicates_within_one_batch_count_once(self):
        self.store.record_missing("lib1", self.tracks + self.tracks, "P")
        self.assertEqual(len(self.store.list_tracks("lib1")), 2)

    def test_resolved_tracks_leave_the_missing_list(self):
        self.store.record_missing("lib1", self.tracks, "P")
        fingerprint = track_fingerprint("Alpha", "A")
        self.assertTrue(self.store.mark_resolved("lib1", fingerprint, "999"))
        self.assertEqual(len(self.store.list_tracks("lib1", status=STATUS_MISSING)), 1)
        resolved = self.store.list_tracks("lib1", status=STATUS_RESOLVED)
        self.assertEqual(resolved[0]["resolved_rating_key"], "999")

    def test_ignored_stays_ignored_when_seen_again(self):
        self.store.record_missing("lib1", self.tracks, "P")
        fingerprint = track_fingerprint("Alpha", "A")
        self.store.mark_ignored("lib1", fingerprint)
        self.store.record_missing("lib1", self.tracks, "P2")
        self.assertEqual(len(self.store.list_tracks("lib1", status=STATUS_IGNORED)), 1)

    def test_resolved_track_going_missing_again_reopens(self):
        self.store.record_missing("lib1", self.tracks, "P")
        fingerprint = track_fingerprint("Alpha", "A")
        self.store.mark_resolved("lib1", fingerprint, "999")
        self.store.record_missing("lib1", self.tracks, "P")
        self.assertEqual(len(self.store.list_tracks("lib1", status=STATUS_MISSING)), 2)

    def test_search_filter(self):
        self.store.record_missing("lib1", self.tracks, "P")
        self.assertEqual(len(self.store.list_tracks("lib1", search="Alph")), 1)

    def test_counts(self):
        self.store.record_missing("lib1", self.tracks, "P")
        self.store.mark_ignored("lib1", track_fingerprint("Alpha", "A"))
        counts = self.store.counts("lib1")
        self.assertEqual(counts[STATUS_MISSING], 1)
        self.assertEqual(counts[STATUS_IGNORED], 1)

    def test_export_csv_and_text(self):
        self.store.record_missing("lib1", self.tracks, "P")
        csv_path = os.path.join(self._tmpdir.name, "out.csv")
        txt_path = os.path.join(self._tmpdir.name, "out.txt")
        self.assertEqual(self.store.export_csv("lib1", csv_path), 2)
        self.assertEqual(self.store.export_text("lib1", txt_path), 2)
        with open(txt_path, encoding="utf-8") as handle:
            self.assertIn("A - Alpha", handle.read())

    def test_untitled_rows_are_skipped(self):
        self.assertEqual(self.store.record_missing("lib1", [{"title": "", "artist": "x"}], "P"), 0)


class SyncHistoryTests(StoreTestCase):
    def setUp(self):
        super().setUp()
        self.store = SyncHistoryStore(self.db)

    def test_run_records_added_and_removed(self):
        before = [{"rating_key": "1", "title": "One"}, {"rating_key": "2", "title": "Two"}]
        after = [{"rating_key": "1", "title": "One"}, {"rating_key": "3", "title": "Three"}]
        run_id = self.store.start_run("lib1", "My Playlist", "spotify", before_snapshot=before)
        self.assertTrue(run_id)
        self.store.finish_run(run_id, after_snapshot=after, unmatched_count=4)

        run = self.store.get_run(run_id)
        self.assertEqual(run["status"], STATUS_SUCCESS)
        self.assertEqual(run["added_count"], 1)
        self.assertEqual(run["removed_count"], 1)
        self.assertEqual(run["unmatched_count"], 4)
        self.assertEqual(run["before_snapshot"], before)

    def test_reorder_is_detected_without_add_or_remove(self):
        before = [{"rating_key": "1"}, {"rating_key": "2"}]
        after = [{"rating_key": "2"}, {"rating_key": "1"}]
        changes = diff_snapshots(before, after)
        self.assertTrue(changes["reordered"])
        self.assertEqual(changes["added"], [])
        self.assertEqual(changes["removed"], [])

    def test_snapshot_from_plex_objects(self):
        from syncra.services.sync_history import snapshot_tracks

        snapshot = snapshot_tracks([FakeTrack(7, "Title", "Artist", "Album")])
        self.assertEqual(snapshot[0]["rating_key"], "7")
        self.assertEqual(snapshot[0]["artist"], "Artist")

    def test_history_is_scoped_and_ordered(self):
        first = self.store.start_run("lib1", "P", before_snapshot=[])
        self.store.finish_run(first, after_snapshot=[])
        second = self.store.start_run("lib1", "P", before_snapshot=[])
        self.store.finish_run(second, after_snapshot=[])
        runs = self.store.list_runs("lib1", "P")
        self.assertEqual(len(runs), 2)
        self.assertEqual(self.store.list_runs("other-lib", "P"), [])

    def test_mark_reverted(self):
        run_id = self.store.start_run("lib1", "P", before_snapshot=[])
        self.store.finish_run(run_id, after_snapshot=[])
        self.store.mark_reverted(run_id)
        self.assertEqual(self.store.get_run(run_id)["status"], "reverted")


class DatabaseResilienceTests(unittest.TestCase):
    def test_corrupt_database_is_recreated_instead_of_raising(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "corrupt.sqlite")
            with open(path, "wb") as handle:
                handle.write(b"this is definitely not a sqlite database")
            db = LibraryDataDB(path)
            store = MatchMemoryStore(db)
            self.assertTrue(store.remember_match("lib1", {"title": "T", "artist": "A"}, "1"))


if __name__ == "__main__":
    unittest.main()
