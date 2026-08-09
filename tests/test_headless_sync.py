"""Tests for headless sync: filter settings, sync options, and the CLI."""

import json
import os
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from syncra import cli
from syncra.services.match_filters import MatchFilters
from syncra.services.sync_options import SyncOptions


class FakeCheckBox:
    def __init__(self, checked):
        self._checked = checked

    def isChecked(self):
        return self._checked


class FakeLineEdit:
    def __init__(self, text):
        self._text = text

    def text(self):
        return self._text


class FakeSettingsWidget:
    def __init__(self, **flags):
        self.enable_filters_checkbox = FakeCheckBox(flags.get("enabled", True))
        self.filter_live_checkbox = FakeCheckBox(flags.get("live", True))
        self.filter_compilation_checkbox = FakeCheckBox(flags.get("compilation", True))
        self.filter_remaster_checkbox = FakeCheckBox(flags.get("remaster", False))
        self.filter_deluxe_checkbox = FakeCheckBox(flags.get("deluxe", False))
        self.m3u_smart_matching_radio = FakeCheckBox(flags.get("smart", False))
        self.listenbrainz_token_input = FakeLineEdit(flags.get("token", ""))


class MatchFilterTests(unittest.TestCase):
    def test_defaults_penalise_live_and_compilations_only(self):
        filters = MatchFilters()
        self.assertEqual(filters.penalty_for_album("Live at Wembley"), 15)
        self.assertEqual(filters.penalty_for_album("Greatest Hits"), 12)
        self.assertEqual(filters.penalty_for_album("2011 Remaster"), 0)
        self.assertEqual(filters.penalty_for_album("Deluxe Edition"), 0)

    def test_penalties_stack(self):
        filters = MatchFilters(deprioritize_remaster=True)
        # "Live" + "Greatest Hits" + "Remaster" all present.
        self.assertEqual(
            filters.penalty_for_album("Greatest Hits Live (2011 Remaster)"), 15 + 12 + 8
        )

    def test_disabled_filters_never_penalise(self):
        filters = MatchFilters(enabled=False)
        self.assertEqual(filters.penalty_for_album("Live Greatest Hits Deluxe"), 0)
        self.assertEqual(filters.apply(90, "Live"), 90)

    def test_apply_floors_at_zero(self):
        filters = MatchFilters(deprioritize_remaster=True, deprioritize_deluxe=True)
        self.assertEqual(filters.apply(5, "Live Greatest Hits Deluxe Remaster"), 0.0)

    def test_apply_tolerates_a_non_numeric_score(self):
        self.assertEqual(MatchFilters().apply("not-a-number", "Live"), "not-a-number")

    def test_config_round_trip(self):
        original = MatchFilters(
            enabled=True, avoid_live=False, avoid_compilation=False,
            deprioritize_remaster=True, deprioritize_deluxe=True,
        )
        restored = MatchFilters.from_config({"match_filters": original.to_config()})
        self.assertEqual(original, restored)

    def test_from_config_falls_back_to_defaults(self):
        self.assertEqual(MatchFilters.from_config({}), MatchFilters())
        self.assertEqual(MatchFilters.from_config(None), MatchFilters())

    def test_from_widget_reads_checkboxes(self):
        widget = FakeSettingsWidget(enabled=True, live=False, compilation=True,
                                    remaster=True, deluxe=False)
        filters = MatchFilters.from_widget(widget)
        self.assertTrue(filters.enabled)
        self.assertFalse(filters.avoid_live)
        self.assertTrue(filters.deprioritize_remaster)

    def test_coerce_accepts_every_shape(self):
        widget = FakeSettingsWidget(live=False)
        self.assertFalse(MatchFilters.coerce(widget).avoid_live)
        self.assertFalse(MatchFilters.coerce({"avoid_live": False}).avoid_live)
        self.assertFalse(
            MatchFilters.coerce({"match_filters": {"avoid_live": False}}).avoid_live
        )
        self.assertEqual(MatchFilters.coerce(None), MatchFilters())
        preset = MatchFilters(avoid_live=False)
        self.assertIs(MatchFilters.coerce(preset), preset)


class LegacyPenaltyBridgeTests(unittest.TestCase):
    """The scorer's entry point must keep accepting widgets and now also settings."""

    def test_widget_and_settings_agree(self):
        from syncra.app import legacy_main

        widget = FakeSettingsWidget(enabled=True, live=True)
        filters = MatchFilters.from_widget(widget)
        self.assertEqual(
            legacy_main._apply_smart_filter_penalty(100, "Live in Tokyo", widget),
            legacy_main._apply_smart_filter_penalty(100, "Live in Tokyo", filters),
        )

    def test_none_source_leaves_the_score_untouched(self):
        from syncra.app import legacy_main

        self.assertEqual(
            legacy_main._apply_smart_filter_penalty(77, "Live in Tokyo", None), 77
        )


class SyncOptionsTests(unittest.TestCase):
    def test_from_config(self):
        options = SyncOptions.from_config({
            "m3u_use_smart_matching": True,
            "listenbrainz_token": "  tok  ",
            "match_filters": {"avoid_live": False},
        })
        self.assertTrue(options.use_smart_matching)
        self.assertEqual(options.listenbrainz_token, "tok")
        self.assertFalse(options.match_filters.avoid_live)

    def test_from_widget(self):
        widget = FakeSettingsWidget(smart=True, token="abc", live=False)
        options = SyncOptions.from_widget(widget)
        self.assertTrue(options.use_smart_matching)
        self.assertEqual(options.listenbrainz_token, "abc")
        self.assertFalse(options.match_filters.avoid_live)

    def test_from_widget_handles_none(self):
        options = SyncOptions.from_widget(None)
        self.assertFalse(options.use_smart_matching)
        self.assertEqual(options.match_filters, MatchFilters())


class CliTests(unittest.TestCase):
    def setUp(self):
        from syncra.app import legacy_main

        self.legacy_main = legacy_main
        self._tmpdir = tempfile.TemporaryDirectory()
        self._saved_config = legacy_main.CONFIG_FILE
        self._saved_sync = legacy_main.SYNC_CONFIG_FILE
        legacy_main.CONFIG_FILE = os.path.join(self._tmpdir.name, "app_config.json")
        legacy_main.SYNC_CONFIG_FILE = os.path.join(self._tmpdir.name, "sync_config.json")

    def tearDown(self):
        self.legacy_main.CONFIG_FILE = self._saved_config
        self.legacy_main.SYNC_CONFIG_FILE = self._saved_sync
        self._tmpdir.cleanup()

    def _write_sync_config(self, playlists):
        with open(self.legacy_main.SYNC_CONFIG_FILE, "w", encoding="utf-8") as handle:
            json.dump({"sync_playlists": playlists}, handle)

    def test_no_action_prints_help_and_fails(self):
        self.assertEqual(cli.main([]), cli.EXIT_ERROR)

    def test_list_with_no_configs_succeeds(self):
        self.assertEqual(cli.main(["--list"]), cli.EXIT_OK)

    def test_list_json_reports_configs(self):
        self._write_sync_config({"Road Trip": {"source_url": "https://x", "last_sync": "y"}})
        self.assertEqual(cli.main(["--list", "--json"]), cli.EXIT_OK)

    def test_sync_without_configs_exits_error(self):
        self.assertEqual(cli.main(["--sync-all"]), cli.EXIT_ERROR)

    def test_sync_without_saved_connection_exits_error(self):
        """A configured playlist but no stored Plex credentials must fail loudly."""
        self._write_sync_config({"Road Trip": {"source_url": "https://x"}})
        with open(self.legacy_main.CONFIG_FILE, "w", encoding="utf-8") as handle:
            json.dump({}, handle)
        self.assertEqual(cli.main(["--sync-all"]), cli.EXIT_ERROR)

    def test_parser_accepts_repeated_sync_names(self):
        args = cli.build_parser().parse_args(["--sync", "A", "--sync", "B", "--dry-run"])
        self.assertEqual(args.sync, ["A", "B"])
        self.assertTrue(args.dry_run)

    def test_offscreen_platform_is_forced_for_headless_runs(self):
        self.assertEqual(os.environ.get("QT_QPA_PLATFORM"), "offscreen")


class FakeTrack:
    def __init__(self, rating_key, title, artist="A", album="Al"):
        self.ratingKey = rating_key
        self.title = title
        self.grandparentTitle = artist
        self.parentTitle = album
        self.duration = 200000


class FakePlexPlaylist:
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


class FakeLibrarySection:
    key = "3"
    title = "Music"

    def __init__(self, server):
        self._server = server


class FakeLibrary:
    def __init__(self, server):
        self._server = server

    def sectionByID(self, _section_id):
        return FakeLibrarySection(self._server)


class FakePlexServer:
    machineIdentifier = "headless-test"

    def __init__(self, playlist):
        self._playlist = playlist
        self.library = FakeLibrary(self)

    def playlists(self):
        return [self._playlist]


class CliEndToEndTests(unittest.TestCase):
    """Drive a full run through the CLI with a fake server -- no network, no GUI."""

    def setUp(self):
        from syncra.app import legacy_main

        self.legacy_main = legacy_main
        self._tmpdir = tempfile.TemporaryDirectory()
        self._saved_config = legacy_main.CONFIG_FILE
        self._saved_sync = legacy_main.SYNC_CONFIG_FILE
        legacy_main.CONFIG_FILE = os.path.join(self._tmpdir.name, "app_config.json")
        legacy_main.SYNC_CONFIG_FILE = os.path.join(self._tmpdir.name, "sync_config.json")

        with open(legacy_main.CONFIG_FILE, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "server_ip": "10.0.0.1", "server_port": "32400", "token": "tok",
                    "last_section": 3, "m3u_use_smart_matching": False,
                },
                handle,
            )
        with open(legacy_main.SYNC_CONFIG_FILE, "w", encoding="utf-8") as handle:
            json.dump(
                {"sync_playlists": {
                    "Road Trip": {"source_url": "C:/fake/list.m3u", "library_section": 3}
                }},
                handle,
            )

        self.existing = FakeTrack(1, "Already There")
        self.incoming = FakeTrack(2, "Brand New")
        self.playlist = FakePlexPlaylist("Road Trip", [self.existing])
        self.server = FakePlexServer(self.playlist)

        # Stub the seams: connection, source fetch, and matching.
        self._saved_connect = cli.HeadlessSyncRunner.connect
        cli.HeadlessSyncRunner.connect = lambda runner, config: self.server

        self._saved_m3u = legacy_main.SyncThread.get_m3u_tracks
        legacy_main.SyncThread.get_m3u_tracks = lambda thread, path: [
            {"title": "Brand New", "artist": "A", "album": "Al",
             "parsed": "Brand New - A", "path": None, "source": "m3u"},
            {"title": "Nowhere To Be Found", "artist": "Ghost", "album": "",
             "parsed": "Nowhere To Be Found - Ghost", "path": None, "source": "m3u"},
        ]

        self._saved_match = legacy_main.SyncThread.find_best_match
        legacy_main.SyncThread.find_best_match = (
            lambda thread, section, track: self.incoming
            if track.get("title") == "Brand New" else None
        )

    def tearDown(self):
        cli.HeadlessSyncRunner.connect = self._saved_connect
        self.legacy_main.SyncThread.get_m3u_tracks = self._saved_m3u
        self.legacy_main.SyncThread.find_best_match = self._saved_match
        self.legacy_main.CONFIG_FILE = self._saved_config
        self.legacy_main.SYNC_CONFIG_FILE = self._saved_sync
        self._tmpdir.cleanup()

    def test_dry_run_reports_the_diff_and_writes_nothing(self):
        runner = cli.HeadlessSyncRunner()
        exit_code = runner.run(names=[], dry_run=True)

        self.assertEqual(exit_code, cli.EXIT_OK)
        self.assertEqual(len(runner.previews), 1)
        preview = runner.previews[0]
        self.assertEqual(preview["playlist"], "Road Trip")
        self.assertEqual(preview["added"], 1, "the matched track would be added")
        self.assertEqual(preview["unmatched"], 1, "the unmatchable track is reported")
        self.assertEqual(self.playlist.added, [], "dry run must not write to Plex")
        self.assertEqual(self.playlist.removed, [])

    def test_real_run_writes_to_the_playlist(self):
        runner = cli.HeadlessSyncRunner()
        exit_code = runner.run(names=[], dry_run=False)

        self.assertEqual(exit_code, cli.EXIT_OK)
        self.assertEqual(len(runner.results), 1)
        self.assertEqual(runner.results[0]["added"], 1)
        self.assertIn(self.incoming, self.playlist.added)

    def test_named_sync_selects_only_that_playlist(self):
        runner = cli.HeadlessSyncRunner()
        runner.run(names=["Road Trip"], dry_run=True)
        self.assertEqual(len(runner.previews), 1)

    def test_unknown_name_is_reported_as_an_error(self):
        runner = cli.HeadlessSyncRunner()
        with self.assertRaises(RuntimeError):
            runner.run(names=["Does Not Exist"], dry_run=True)
        self.assertTrue(
            any("Does Not Exist" in message for message in runner.errors)
        )

    def test_main_exits_zero_through_the_full_cli(self):
        self.assertEqual(cli.main(["--sync-all", "--dry-run", "--json"]), cli.EXIT_OK)

    def test_unmatched_tracks_reach_the_missing_tracks_store(self):
        """The headless run must feed the same Missing Tracks list the GUI shows."""
        from syncra.services.library_data_db import LibraryDataDB
        from syncra.services.missing_tracks import MissingTracksStore

        db = LibraryDataDB(os.path.join(self._tmpdir.name, "data.sqlite"))
        store = MissingTracksStore(db)
        saved = self.legacy_main._SYNCRA_MISSING_TRACKS_STORE
        self.legacy_main._SYNCRA_MISSING_TRACKS_STORE = store
        try:
            cli.HeadlessSyncRunner().run(names=[], dry_run=False)
        finally:
            self.legacy_main._SYNCRA_MISSING_TRACKS_STORE = saved

        rows = store.list_tracks("headless-test::3")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "Nowhere To Be Found")
        self.assertIn("Sync: Road Trip", rows[0]["sources"])


class ConsoleAttachmentTests(unittest.TestCase):
    """Frozen --windowed builds have no stdout; output must survive that."""

    def test_tee_tolerates_a_none_stream(self):
        import io

        buffer = io.StringIO()
        tee = cli._Tee(None, buffer)
        tee.write("hello")
        tee.flush()
        self.assertEqual(buffer.getvalue(), "hello")

    def test_tee_survives_a_broken_stream(self):
        import io

        class Broken:
            def write(self, _text):
                raise OSError("closed")

            def flush(self):
                raise OSError("closed")

        buffer = io.StringIO()
        tee = cli._Tee(Broken(), buffer)
        tee.write("still written")
        tee.flush()
        self.assertEqual(buffer.getvalue(), "still written")

    def test_configure_output_creates_a_log_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = os.path.join(tmpdir, "nested", "run.log")
            saved_out, saved_err = sys.stdout, sys.stderr
            try:
                stream = cli.configure_output(log_path)
                self.assertIsNotNone(stream)
                print("recorded")
                sys.stdout.flush()
            finally:
                sys.stdout, sys.stderr = saved_out, saved_err
                if stream:
                    stream.close()
            with open(log_path, encoding="utf-8") as handle:
                self.assertIn("recorded", handle.read())

    def test_attach_is_a_noop_when_streams_already_work(self):
        self.assertFalse(cli.attach_parent_console())


if __name__ == "__main__":
    unittest.main()
