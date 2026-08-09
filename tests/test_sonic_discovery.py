"""Tests for sonic discovery.

Behaviour verified against a live Plex 1.43.3 server before these were written:
track-level sonicallySimilar and section-level sonicAdventure work; artist-level
station/popularTracks/sonicallySimilar return nothing usable. Nothing here relies on
the artist-level calls.
"""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from syncra.services import sonic_discovery
from syncra.services.sonic_discovery import SonicUnavailable


class FakeTrack:
    def __init__(self, rating_key, title, artist="Artist", album="Album", similar=None,
                 raises=None):
        self.ratingKey = rating_key
        self.title = title
        self.grandparentTitle = artist
        self.parentTitle = album
        self.duration = 180000
        self._similar = similar if similar is not None else []
        self._raises = raises
        self.last_call = None

    def sonicallySimilar(self, limit=None, maxDistance=None, **kwargs):
        self.last_call = {"limit": limit, "maxDistance": maxDistance}
        if self._raises:
            raise self._raises
        return list(self._similar)[: (limit or len(self._similar))]


class FakeSection:
    def __init__(self, path=None, raises=None):
        self._path = path or []
        self._raises = raises
        self.last_args = None

    def sonicAdventure(self, start, end, **kwargs):
        self.last_args = (start, end)
        if self._raises:
            raise self._raises
        return list(self._path)


class FakeServer:
    def __init__(self):
        self.created = []

    def createPlaylist(self, name, items=None):
        self.created.append((name, list(items or [])))
        return f"playlist:{name}"


class LabelTests(unittest.TestCase):
    def test_label_includes_artist(self):
        self.assertEqual(
            sonic_discovery.track_label(FakeTrack(1, "Song", "Band")), "Band - Song"
        )

    def test_label_without_artist(self):
        track = FakeTrack(1, "Song")
        track.grandparentTitle = ""
        track.originalTitle = ""
        self.assertEqual(sonic_discovery.track_label(track), "Song")

    def test_label_tolerates_missing_title(self):
        track = FakeTrack(1, "")
        track.title = ""
        self.assertIn("Unknown", sonic_discovery.track_label(track))


class SupportProbeTests(unittest.TestCase):
    def test_supported_when_neighbours_come_back(self):
        track = FakeTrack(1, "A", similar=[FakeTrack(2, "B")])
        self.assertTrue(sonic_discovery.is_supported(track))

    def test_unsupported_when_empty(self):
        self.assertFalse(sonic_discovery.is_supported(FakeTrack(1, "A", similar=[])))

    def test_unsupported_when_server_errors(self):
        track = FakeTrack(1, "A", raises=RuntimeError("no analysis"))
        self.assertFalse(sonic_discovery.is_supported(track))


class SimilarTrackTests(unittest.TestCase):
    def setUp(self):
        self.neighbours = [FakeTrack(i, f"N{i}") for i in range(2, 7)]
        self.seed = FakeTrack(1, "Seed", similar=self.neighbours)

    def test_seed_is_first_and_neighbours_follow(self):
        result = sonic_discovery.similar_tracks(self.seed)
        self.assertIs(result.tracks[0], self.seed)
        self.assertEqual(len(result.tracks), 6)

    def test_seed_can_be_excluded(self):
        result = sonic_discovery.similar_tracks(self.seed, include_seed=False)
        self.assertNotIn(self.seed, result.tracks)
        self.assertEqual(len(result.tracks), 5)

    def test_limit_is_clamped_into_range(self):
        sonic_discovery.similar_tracks(self.seed, limit=99999)
        self.assertEqual(self.seed.last_call["limit"], sonic_discovery.MAX_RESULTS)
        sonic_discovery.similar_tracks(self.seed, limit=1)
        self.assertEqual(self.seed.last_call["limit"], sonic_discovery.MIN_RESULTS)

    def test_bad_limit_falls_back_to_default(self):
        sonic_discovery.similar_tracks(self.seed, limit="lots")
        self.assertEqual(self.seed.last_call["limit"], sonic_discovery.DEFAULT_RESULTS)

    def test_max_distance_is_passed_through(self):
        sonic_discovery.similar_tracks(self.seed, max_distance=0.8)
        self.assertEqual(self.seed.last_call["maxDistance"], 0.8)

    def test_duplicates_are_dropped(self):
        repeat = FakeTrack(2, "N2")
        seed = FakeTrack(1, "Seed", similar=[repeat, FakeTrack(2, "N2 again")])
        result = sonic_discovery.similar_tracks(seed)
        keys = [t.ratingKey for t in result.tracks]
        self.assertEqual(keys, [1, 2])

    def test_empty_result_explains_how_to_fix_it(self):
        with self.assertRaises(SonicUnavailable) as ctx:
            sonic_discovery.similar_tracks(FakeTrack(1, "Seed", similar=[]))
        self.assertIn("analysed", str(ctx.exception))

    def test_server_error_is_wrapped(self):
        track = FakeTrack(1, "Seed", raises=RuntimeError("boom"))
        with self.assertRaises(SonicUnavailable):
            sonic_discovery.similar_tracks(track)

    def test_description_names_the_seed(self):
        result = sonic_discovery.similar_tracks(self.seed)
        self.assertIn("Artist - Seed", result.description)
        self.assertIn("Artist - Seed", result.title)


class MultiSeedTests(unittest.TestCase):
    """Blending several seeds is done client-side; /nearest is per-track."""

    def test_single_seed_delegates_to_the_simple_path(self):
        seed = FakeTrack(1, "Seed", similar=[FakeTrack(2, "N")])
        result = sonic_discovery.similar_to_tracks([seed])
        self.assertIs(result.tracks[0], seed, "single seed keeps the seed-first shape")

    def test_no_seeds_is_rejected(self):
        with self.assertRaises(SonicUnavailable):
            sonic_discovery.similar_to_tracks([])
        with self.assertRaises(SonicUnavailable):
            sonic_discovery.similar_to_tracks([None])

    def test_a_track_near_several_seeds_outranks_one_near_a_single_seed(self):
        shared = FakeTrack(100, "Shared")
        # 'shared' is 2nd for both seeds; 'only_a' is 1st but for one seed only.
        seed_a = FakeTrack(1, "A", similar=[FakeTrack(200, "OnlyA"), shared])
        seed_b = FakeTrack(2, "B", similar=[FakeTrack(300, "OnlyB"), FakeTrack(100, "Shared")])
        result = sonic_discovery.similar_to_tracks(
            [seed_a, seed_b], limit=10, include_seeds=False
        )
        self.assertEqual(result.tracks[0].ratingKey, 100)

    def test_seeds_lead_the_list_by_default(self):
        seed_a = FakeTrack(1, "A", similar=[FakeTrack(3, "C")])
        seed_b = FakeTrack(2, "B", similar=[FakeTrack(3, "C")])
        result = sonic_discovery.similar_to_tracks([seed_a, seed_b])
        self.assertEqual([t.ratingKey for t in result.tracks[:2]], [1, 2])

    def test_seeds_can_be_excluded(self):
        """Seeds appearing in each other's neighbourhoods must not sneak back in."""
        seed_a = FakeTrack(1, "A", similar=[FakeTrack(2, "B"), FakeTrack(3, "C")])
        seed_b = FakeTrack(2, "B", similar=[FakeTrack(1, "A"), FakeTrack(3, "C")])
        result = sonic_discovery.similar_to_tracks(
            [seed_a, seed_b], include_seeds=False
        )
        keys = [t.ratingKey for t in result.tracks]
        self.assertNotIn(1, keys)
        self.assertNotIn(2, keys)
        self.assertIn(3, keys)

    def test_a_failing_seed_does_not_sink_the_whole_mix(self):
        good = FakeTrack(1, "Good", similar=[FakeTrack(9, "N")])
        bad = FakeTrack(2, "Bad", raises=RuntimeError("unanalysed"))
        result = sonic_discovery.similar_to_tracks(
            [good, bad], include_seeds=False
        )
        self.assertEqual([t.ratingKey for t in result.tracks], [9])
        self.assertIn("1 seed(s) returned nothing", result.description)

    def test_all_seeds_failing_raises_with_detail(self):
        bad_a = FakeTrack(1, "A", raises=RuntimeError("boom"))
        bad_b = FakeTrack(2, "B", raises=RuntimeError("boom"))
        with self.assertRaises(SonicUnavailable) as ctx:
            sonic_discovery.similar_to_tracks([bad_a, bad_b])
        self.assertIn("boom", str(ctx.exception))

    def test_limit_caps_the_blended_result(self):
        seed_a = FakeTrack(1, "A", similar=[FakeTrack(i, f"N{i}") for i in range(10, 40)])
        seed_b = FakeTrack(2, "B", similar=[FakeTrack(i, f"M{i}") for i in range(40, 70)])
        result = sonic_discovery.similar_to_tracks(
            [seed_a, seed_b], limit=7, include_seeds=False
        )
        self.assertEqual(len(result.tracks), 7)

    def test_description_names_the_seeds_and_counts_them(self):
        seeds = [FakeTrack(i, f"S{i}", similar=[FakeTrack(90 + i, f"N{i}")])
                 for i in range(1, 6)]
        result = sonic_discovery.similar_to_tracks(seeds)
        self.assertIn("blended from 5 seed(s)", result.description)
        self.assertIn("and 2 more", result.description)


class DuplicateCollapseTests(unittest.TestCase):
    """The same recording on a single, an album and a compilation is one song."""

    def test_same_title_and_artist_collapses_across_albums(self):
        tracks = [
            FakeTrack(1, "Umbrella", "Rihanna", "Good Girl Gone Bad"),
            FakeTrack(2, "Umbrella", "Rihanna", "Reloaded"),
            FakeTrack(3, "Umbrella", "Rihanna", "Greatest Hits"),
        ]
        kept = sonic_discovery.collapse_duplicates(tracks)
        self.assertEqual([t.ratingKey for t in kept], [1])

    def test_same_title_by_different_artists_is_kept(self):
        tracks = [
            FakeTrack(1, "Umbrella", "Rihanna"),
            FakeTrack(2, "Umbrella", "Metro Boomin"),
        ]
        self.assertEqual(len(sonic_discovery.collapse_duplicates(tracks)), 2)

    def test_generate_hides_repeats_by_default(self):
        dupes = [FakeTrack(10, "Song", "Band", "Album A"),
                 FakeTrack(11, "Song", "Band", "Album B"),
                 FakeTrack(12, "Other", "Band")]
        seed = FakeTrack(1, "Seed", "Seeder", similar=dupes)
        result = sonic_discovery.generate_mix([seed], limit=10, include_seeds=False)
        titles = [t.title for t in result.tracks]
        self.assertEqual(titles.count("Song"), 1)

    def test_repeats_can_be_allowed(self):
        dupes = [FakeTrack(10, "Song", "Band", "A"), FakeTrack(11, "Song", "Band", "B")]
        seed = FakeTrack(1, "Seed", "Seeder", similar=dupes)
        result = sonic_discovery.generate_mix(
            [seed], limit=10, include_seeds=False, collapse_same_song=False
        )
        self.assertEqual(len([t for t in result.tracks if t.title == "Song"]), 2)


class VarietyTests(unittest.TestCase):
    def setUp(self):
        self.pool = [(FakeTrack(i, f"T{i}"), 1.0 / i) for i in range(1, 31)]

    def test_zero_variety_is_the_deterministic_top_n(self):
        first = sonic_discovery.select_from_pool(self.pool, 5, variety=0.0)
        second = sonic_discovery.select_from_pool(self.pool, 5, variety=0.0)
        self.assertEqual([t.ratingKey for t in first], [1, 2, 3, 4, 5])
        self.assertEqual([t.ratingKey for t in first], [t.ratingKey for t in second])

    def test_variety_changes_the_result_between_runs(self):
        import random

        runs = {
            tuple(
                t.ratingKey for t in sonic_discovery.select_from_pool(
                    self.pool, 8, variety=0.8, rng=random.Random(seed)
                )
            )
            for seed in range(6)
        }
        self.assertGreater(len(runs), 1, "variety should produce different mixes")

    def test_selection_never_repeats_a_track(self):
        import random

        picked = sonic_discovery.select_from_pool(
            self.pool, 12, variety=1.0, rng=random.Random(7)
        )
        keys = [t.ratingKey for t in picked]
        self.assertEqual(len(keys), len(set(keys)))

    def test_asking_for_more_than_the_pool_returns_the_pool(self):
        picked = sonic_discovery.select_from_pool(self.pool[:3], 10, variety=0.5)
        self.assertEqual(len(picked), 3)

    def test_empty_pool_is_safe(self):
        self.assertEqual(sonic_discovery.select_from_pool([], 5, variety=0.5), [])


class LockedTrackTests(unittest.TestCase):
    def setUp(self):
        self.neighbours = [FakeTrack(i, f"N{i}", f"Artist{i}") for i in range(10, 40)]
        self.seed = FakeTrack(1, "Seed", "Seeder", similar=self.neighbours)

    def test_locked_tracks_are_kept(self):
        keeper = FakeTrack(999, "Keeper", "Pinned")
        result = sonic_discovery.generate_mix(
            [self.seed], limit=6, include_seeds=False, locked=[keeper]
        )
        self.assertIn(999, [t.ratingKey for t in result.tracks])

    def test_locked_tracks_lead_the_result(self):
        keeper = FakeTrack(999, "Keeper", "Pinned")
        result = sonic_discovery.generate_mix(
            [self.seed], limit=6, include_seeds=False, locked=[keeper]
        )
        self.assertEqual(result.tracks[0].ratingKey, 999)

    def test_locked_tracks_count_towards_the_limit(self):
        locked = [FakeTrack(900 + i, f"L{i}", f"P{i}") for i in range(3)]
        result = sonic_discovery.generate_mix(
            [self.seed], limit=5, include_seeds=False, locked=locked
        )
        self.assertEqual(len(result.tracks), 5)

    def test_a_locked_track_is_not_also_drawn_from_the_pool(self):
        """Locking a track that is also a candidate must not duplicate it."""
        duplicate_of_candidate = self.neighbours[0]
        result = sonic_discovery.generate_mix(
            [self.seed], limit=8, include_seeds=False, locked=[duplicate_of_candidate]
        )
        keys = [t.ratingKey for t in result.tracks]
        self.assertEqual(keys.count(duplicate_of_candidate.ratingKey), 1)

    def test_locks_survive_regeneration_while_the_rest_changes(self):
        import random

        keeper = FakeTrack(999, "Keeper", "Pinned")
        runs = []
        for seed_value in range(5):
            result = sonic_discovery.generate_mix(
                [self.seed], limit=8, include_seeds=False, locked=[keeper],
                variety=0.8, rng=random.Random(seed_value),
            )
            keys = [t.ratingKey for t in result.tracks]
            self.assertEqual(keys[0], 999, "the lock holds on every run")
            runs.append(tuple(keys[1:]))
        self.assertGreater(len(set(runs)), 1, "the unlocked remainder should vary")

    def test_description_mentions_the_locks(self):
        result = sonic_discovery.generate_mix(
            [self.seed], limit=6, locked=[FakeTrack(999, "Keeper")]
        )
        self.assertIn("1 locked", result.description)


class DurationHelperTests(unittest.TestCase):
    def test_totals_milliseconds(self):
        tracks = [FakeTrack(1, "A"), FakeTrack(2, "B")]
        tracks[0].duration = 60000
        tracks[1].duration = 90000
        self.assertEqual(sonic_discovery.total_duration_ms(tracks), 150000)

    def test_ignores_missing_durations(self):
        track = FakeTrack(1, "A")
        track.duration = None
        self.assertEqual(sonic_discovery.total_duration_ms([track]), 0)

    def test_formats_minutes_and_hours(self):
        self.assertEqual(sonic_discovery.format_duration(150000), "2:30")
        self.assertEqual(sonic_discovery.format_duration(3_725_000), "1:02:05")
        self.assertEqual(sonic_discovery.format_duration(0), "0:00")


class SonicAdventureTests(unittest.TestCase):
    def setUp(self):
        self.start = FakeTrack(1, "Start")
        self.end = FakeTrack(9, "End")
        self.path = [self.start, FakeTrack(4, "Mid"), self.end]

    def test_returns_the_path(self):
        section = FakeSection(path=self.path)
        result = sonic_discovery.sonic_adventure(section, self.start, self.end)
        self.assertEqual(len(result), 3)
        self.assertEqual(section.last_args, (self.start, self.end))

    def test_same_track_is_rejected(self):
        section = FakeSection(path=self.path)
        with self.assertRaises(SonicUnavailable):
            sonic_discovery.sonic_adventure(section, self.start, FakeTrack(1, "Start"))

    def test_missing_endpoint_is_rejected(self):
        section = FakeSection(path=self.path)
        with self.assertRaises(SonicUnavailable):
            sonic_discovery.sonic_adventure(section, self.start, None)

    def test_empty_path_explains_itself(self):
        with self.assertRaises(SonicUnavailable) as ctx:
            sonic_discovery.sonic_adventure(FakeSection(path=[]), self.start, self.end)
        self.assertIn("analysed", str(ctx.exception))

    def test_server_error_is_wrapped(self):
        section = FakeSection(raises=RuntimeError("nope"))
        with self.assertRaises(SonicUnavailable):
            sonic_discovery.sonic_adventure(section, self.start, self.end)

    def test_description_names_both_ends(self):
        result = sonic_discovery.sonic_adventure(
            FakeSection(path=self.path), self.start, self.end
        )
        self.assertIn("Start", result.description)
        self.assertIn("End", result.description)


class CreatePlaylistTests(unittest.TestCase):
    def test_creates_with_the_given_tracks(self):
        server = FakeServer()
        tracks = [FakeTrack(1, "A"), FakeTrack(2, "B")]
        sonic_discovery.create_playlist(server, "My Mix", tracks)
        self.assertEqual(server.created[0][0], "My Mix")
        self.assertEqual(len(server.created[0][1]), 2)

    def test_blank_name_is_rejected(self):
        with self.assertRaises(ValueError):
            sonic_discovery.create_playlist(FakeServer(), "   ", [FakeTrack(1, "A")])

    def test_empty_track_list_is_rejected(self):
        with self.assertRaises(ValueError):
            sonic_discovery.create_playlist(FakeServer(), "Mix", [])


class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication

        cls.app = QApplication.instance() or QApplication([])

    def test_similar_mode_hides_the_end_track_row(self):
        from syncra.ui.dialogs.sonic_discovery_dialog import (
            MODE_SIMILAR, SonicDiscoveryDialog,
        )

        dialog = SonicDiscoveryDialog(FakeServer(), FakeSection(), mode=MODE_SIMILAR)
        try:
            self.assertTrue(dialog.target_picker.isHidden())
            self.assertFalse(dialog.limit_spin.isHidden())
        finally:
            dialog.close()

    def test_adventure_mode_shows_end_track_and_hides_tuning(self):
        from syncra.ui.dialogs.sonic_discovery_dialog import (
            MODE_ADVENTURE, SonicDiscoveryDialog,
        )

        dialog = SonicDiscoveryDialog(FakeServer(), FakeSection(), mode=MODE_ADVENTURE)
        try:
            self.assertFalse(dialog.target_picker.isHidden())
            # Plex controls the length and spacing of an adventure itself.
            self.assertTrue(dialog.limit_spin.isHidden())
        finally:
            dialog.close()

    def test_seed_track_prefills_the_picker(self):
        from syncra.ui.dialogs.sonic_discovery_dialog import SonicDiscoveryDialog

        seed = FakeTrack(1, "Seed", "Band")
        dialog = SonicDiscoveryDialog(FakeServer(), FakeSection(), seed_track=seed)
        try:
            self.assertIs(dialog.seed_picker.selected_track(), seed)
        finally:
            dialog.close()

    def test_results_populate_the_table_and_enable_save(self):
        from syncra.ui.dialogs.sonic_discovery_dialog import SonicDiscoveryDialog

        dialog = SonicDiscoveryDialog(FakeServer(), FakeSection())
        try:
            self.assertFalse(dialog.save_btn.isEnabled())
            result = sonic_discovery.SonicResult(
                title="Like X", description="d",
                tracks=[FakeTrack(1, "A"), FakeTrack(2, "B")],
            )
            dialog._on_generated(result)
            self.assertEqual(dialog.table.rowCount(), 2)
            self.assertTrue(dialog.save_btn.isEnabled())
            self.assertEqual(dialog.name_input.text(), "Like X")
        finally:
            dialog.close()


if __name__ == "__main__":
    unittest.main()
