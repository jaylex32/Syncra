"""Tests that uploading a playlist never modifies the user's own file.

Reported by users: importing a .m3u8 renamed their original file to .m3u on disk.
`upload_playlist()` did this before uploading:

    if path.endswith('.m3u8'):
        new_path = path.rsplit('.', 1)[0] + '.m3u'
        os.rename(path, new_path)

which permanently altered a file the app had only been asked to read -- and for the
bulk directory import, every .m3u8 in the folder. It was never necessary: the direct
upload posts the file under a `f"{playlist_name}.m3u"` filename it builds itself, so
the name on disk never reached Plex. The extension only mattered to the local-server
path fallback, which is now handed a temp copy instead.
"""

import os
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

from syncra.app import legacy_main
from syncra.ui.widgets import playlist_grid as pg

SIMPLE = "#EXTM3U\n/music/Artist/Album/01 Song.mp3\n/music/Artist/Album/02 Other.mp3\n"
NEEDS_NORMALISING = "#EXTM3U\n" + "\\\\NAS\\Music\\Artist\\01 Song.mp3\n"


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
        self.window.path_mappings = []

        self.tmp = tempfile.TemporaryDirectory(prefix="syncra-m3u8-")
        self.addCleanup(self.tmp.cleanup)

        # Keep upload copies out of the project directory.
        self.temp_folder = os.path.join(self.tmp.name, "playlist_temp")
        os.makedirs(self.temp_folder, exist_ok=True)
        self.window._playlist_temp_folder = lambda: self.temp_folder

    def tearDown(self):
        try:
            self.window.close()
        finally:
            pg.CoverFetcher.request = self._real_request
            pg.CoverFetcher.cached_bytes = self._real_cached

    def _write(self, name, body=SIMPLE):
        path = os.path.join(self.tmp.name, name)
        with open(path, "w", encoding="utf-8", newline="") as handle:
            handle.write(body)
        return path


class OriginalFileIsUntouchedTests(WindowTestCase):
    """The reported bug."""

    def test_the_original_m3u8_still_exists_afterwards(self):
        source = self._write("My Mix.m3u8")
        self.window._prepare_playlist_for_upload(source)
        self.assertTrue(os.path.exists(source), "the user's .m3u8 was renamed away")

    def test_no_m3u_appears_beside_the_original(self):
        source = self._write("My Mix.m3u8")
        self.window._prepare_playlist_for_upload(source)
        self.assertNotIn("My Mix.m3u", os.listdir(self.tmp.name))

    def test_the_original_bytes_are_untouched(self):
        source = self._write("My Mix.m3u8")
        with open(source, "rb") as handle:
            before = handle.read()
        self.window._prepare_playlist_for_upload(source)
        with open(source, "rb") as handle:
            self.assertEqual(handle.read(), before)

    def test_a_whole_folder_of_m3u8_files_survives(self):
        """The bulk directory import renamed every .m3u8 in the folder."""
        names = ["Mix %d.m3u8" % i for i in range(5)]
        for name in names:
            self._write(name)
        for name in names:
            self.window._prepare_playlist_for_upload(os.path.join(self.tmp.name, name))
        found = sorted(n for n in os.listdir(self.tmp.name) if n.endswith(".m3u8"))
        self.assertEqual(found, sorted(names))

    def test_normalising_an_m3u8_also_leaves_it_in_place(self):
        source = self._write("UNC Mix.m3u8", NEEDS_NORMALISING)
        self.window._prepare_playlist_for_upload(source)
        self.assertTrue(os.path.exists(source))

    def test_an_m3u_needing_normalisation_keeps_its_original(self):
        source = self._write("UNC.m3u", NEEDS_NORMALISING)
        temp = self.window._prepare_playlist_for_upload(source)
        self.assertIsNotNone(temp)
        self.assertTrue(os.path.exists(source))


class UploadCopyTests(WindowTestCase):
    """What the upload is actually handed instead."""

    def test_a_clean_m3u8_still_yields_a_temp_copy(self):
        """Without one, the local-server fallback would be given a .m3u8 path."""
        source = self._write("My Mix.m3u8")
        temp = self.window._prepare_playlist_for_upload(source)
        self.assertIsNotNone(temp)
        self.assertTrue(temp.lower().endswith(".m3u"))
        self.assertTrue(os.path.exists(temp))

    def test_the_copy_is_byte_identical_for_a_clean_playlist(self):
        source = self._write("My Mix.m3u8")
        temp = self.window._prepare_playlist_for_upload(source)
        with open(temp, "rb") as copied, open(source, "rb") as original:
            self.assertEqual(copied.read(), original.read())

    def test_the_copy_lives_in_the_temp_folder(self):
        source = self._write("My Mix.m3u8")
        temp = self.window._prepare_playlist_for_upload(source)
        self.assertEqual(os.path.dirname(temp), self.temp_folder)

    def test_a_normalised_m3u8_is_written_as_m3u(self):
        source = self._write("UNC Mix.m3u8", NEEDS_NORMALISING)
        temp = self.window._prepare_playlist_for_upload(source)
        self.assertTrue(temp.lower().endswith(".m3u"))

    def test_extension_matching_is_case_insensitive(self):
        source = self._write("Shouty.M3U8")
        temp = self.window._prepare_playlist_for_upload(source)
        self.assertIsNotNone(temp, ".M3U8 must be handled like .m3u8")
        self.assertTrue(os.path.exists(source))

    def test_a_plain_m3u_needing_nothing_still_uploads_from_the_original(self):
        """Unchanged behaviour: no temp file when there is nothing to do."""
        source = self._write("Plain.m3u")
        self.assertIsNone(self.window._prepare_playlist_for_upload(source))

    def test_relative_entries_resolve_against_the_originals_folder(self):
        """Repointing `path` at the temp copy before normalising would break this."""
        media_dir = os.path.join(self.tmp.name, "Album")
        os.makedirs(media_dir, exist_ok=True)
        open(os.path.join(media_dir, "01 Song.mp3"), "wb").close()

        source = self._write("Relative.m3u8", "#EXTM3U\nAlbum/01 Song.mp3\n")
        temp = self.window._prepare_playlist_for_upload(source)
        with open(temp, encoding="utf-8") as handle:
            body = handle.read()
        self.assertIn(media_dir.replace("\\", "/"), body)


class CopyFailureTests(WindowTestCase):
    def test_a_failed_copy_falls_back_without_touching_the_original(self):
        source = self._write("My Mix.m3u8")

        def boom():
            raise OSError("no disk")

        self.window._playlist_temp_folder = boom
        self.assertIsNone(self.window._copy_playlist_to_temp(source))
        self.assertTrue(os.path.exists(source))

    def test_copying_onto_itself_is_refused(self):
        """Guards the case where the temp folder resolves to the playlist's own."""
        source = self._write("Self.m3u")
        self.window._playlist_temp_folder = lambda: self.tmp.name
        self.assertIsNone(self.window._copy_playlist_to_temp(source))
        self.assertTrue(os.path.exists(source))

    def test_a_missing_source_does_not_raise(self):
        missing = os.path.join(self.tmp.name, "gone.m3u8")
        self.assertIsNone(self.window._copy_playlist_to_temp(missing))


class TempFolderPruningTests(WindowTestCase):
    def test_stale_m3u8_copies_are_pruned_too(self):
        """Older builds left .m3u8 copies behind; cleanup only ever matched .m3u."""
        import sys as _sys

        # The real helper derives its folder from the running script's directory.
        saved_argv0 = _sys.argv[0]
        _sys.argv[0] = os.path.join(self.tmp.name, "syncra.py")
        try:
            for index in range(6):
                stale = os.path.join(self.temp_folder, "old %d.m3u8" % index)
                with open(stale, "w") as handle:
                    handle.write(SIMPLE)
                time.sleep(0.01)

            folder = legacy_main.PlexPlaylistManager._playlist_temp_folder(self.window)
            self.assertEqual(folder, self.temp_folder)
        finally:
            _sys.argv[0] = saved_argv0

        remaining = [
            name for name in os.listdir(self.temp_folder)
            if name.lower().endswith((".m3u", ".m3u8"))
        ]
        self.assertLessEqual(len(remaining), 3, "stale .m3u8 copies were not pruned")


if __name__ == "__main__":
    unittest.main()
