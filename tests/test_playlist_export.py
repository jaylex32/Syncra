"""Tests for exporting a playlist as real audio files.

The existing export writes an .m3u full of server-side paths like
``\\\\Desktop-u78huhb\\f\\Music Masters\\...``; on a USB stick nothing plays. This
export copies the audio and writes relative paths beside it.

Most of the risk is in naming. Destinations are usually FAT32/exFAT sticks, which
reject characters Plex is perfectly happy with -- "AC/DC" and "What?" are ordinary
music metadata and illegal filenames. Windows also silently strips trailing dots and
spaces, which can turn two different titles into one file, so collisions are resolved
while planning rather than discovered at write time.
"""

import os
import tempfile
import unittest

from syncra.services.playlist_export import (
    album_cover_url,
    fetch_album_year,
    fetch_cover_bytes,
    write_mp3_tags,
    STRUCTURES,
    STRUCTURE_ALBUM,
    STRUCTURE_ARTIST,
    STRUCTURE_PLAYLIST_ARTIST,
    STRUCTURE_PLAYLIST_ARTIST_ALBUM,
    STRUCTURE_PLAYLIST_FLAT,
    FORMAT_MP3_128,
    FORMAT_MP3_192,
    FORMAT_MP3_320,
    FORMAT_ORIGINAL,
    STRUCTURE_ARTIST_ALBUM,
    STRUCTURE_FLAT,
    estimate_total_bytes,
    export_playlist,
    format_bytes,
    plan_export,
    sanitize_component,
    track_extension,
    track_size_estimate,
)


class FakePart:
    def __init__(self, file="/music/song.flac", size=32_000_000, key="/library/parts/1"):
        self.file = file
        self.size = size
        self.key = key


class FakeMedia:
    def __init__(self, parts=None):
        self.parts = parts if parts is not None else [FakePart()]


class FakeTrack:
    def __init__(self, title="Song", artist="Artist", album="Album", index=1,
                 duration=240000, media=None, rating_key=1):
        self.title = title
        self.grandparentTitle = artist
        self.originalTitle = ""
        self.parentTitle = album
        self.index = index
        self.duration = duration
        self.ratingKey = rating_key
        self.media = media if media is not None else [FakeMedia()]


class SanitizeTests(unittest.TestCase):
    def test_illegal_characters_are_replaced(self):
        self.assertEqual(sanitize_component('AC/DC: Back?'), "AC_DC_ Back_")

    def test_backslashes_do_not_create_folders(self):
        self.assertNotIn("\\", sanitize_component(r"Artist\Album"))

    def test_trailing_dots_and_spaces_are_stripped(self):
        """Windows drops these silently, collapsing two names into one."""
        self.assertEqual(sanitize_component("Song... "), "Song")

    def test_reserved_device_names_are_escaped(self):
        self.assertEqual(sanitize_component("CON"), "_CON")
        self.assertEqual(sanitize_component("COM1"), "_COM1")

    def test_control_characters_are_removed(self):
        self.assertNotIn("\n", sanitize_component("Line\nBreak"))

    def test_long_names_are_truncated(self):
        self.assertLessEqual(len(sanitize_component("x" * 400)), 100)

    def test_an_empty_name_falls_back(self):
        self.assertEqual(sanitize_component(""), "Unknown")
        self.assertEqual(sanitize_component("///"), "___")

    def test_unicode_is_preserved(self):
        self.assertEqual(sanitize_component("Björk – Jóga"), "Björk – Jóga")


class SizeTests(unittest.TestCase):
    def test_original_size_comes_from_the_part(self):
        track = FakeTrack(media=[FakeMedia([FakePart(size=25_000_000)])])
        self.assertEqual(track_size_estimate(track, FORMAT_ORIGINAL), 25_000_000)

    def test_mp3_size_is_derived_from_duration_and_bitrate(self):
        track = FakeTrack(duration=240_000)  # 4 minutes
        # 320kbps * 240s / 8 = 9.6MB
        self.assertAlmostEqual(
            track_size_estimate(track, FORMAT_MP3_320) / 1_000_000, 9.6, places=1
        )

    def test_a_lower_bitrate_estimates_smaller(self):
        track = FakeTrack(duration=240_000)
        self.assertLess(
            track_size_estimate(track, FORMAT_MP3_128),
            track_size_estimate(track, FORMAT_MP3_320),
        )

    def test_transcoding_flac_is_a_large_saving(self):
        """The whole point: 32MB FLAC tracks do not fit on a stick."""
        tracks = [FakeTrack(duration=240_000) for _ in range(24)]
        original = estimate_total_bytes(tracks, FORMAT_ORIGINAL)
        mp3 = estimate_total_bytes(tracks, FORMAT_MP3_192)
        self.assertLess(mp3, original / 3)

    def test_missing_media_does_not_raise(self):
        track = FakeTrack(media=[])
        self.assertEqual(track_size_estimate(track, FORMAT_ORIGINAL), 0)

    def test_format_bytes_scales(self):
        self.assertEqual(format_bytes(512), "512 B")
        self.assertIn("MB", format_bytes(5 * 1024 ** 2))
        self.assertIn("GB", format_bytes(3 * 1024 ** 3))


class ExtensionTests(unittest.TestCase):
    def test_originals_keep_their_extension(self):
        track = FakeTrack(media=[FakeMedia([FakePart(file="/music/a.flac")])])
        self.assertEqual(track_extension(track, FORMAT_ORIGINAL), ".flac")

    def test_transcodes_are_mp3(self):
        track = FakeTrack(media=[FakeMedia([FakePart(file="/music/a.flac")])])
        self.assertEqual(track_extension(track, FORMAT_MP3_320), ".mp3")

    def test_a_missing_file_falls_back(self):
        track = FakeTrack(media=[])
        self.assertEqual(track_extension(track, FORMAT_ORIGINAL), ".mp3")


class PlanTests(unittest.TestCase):
    def test_flat_layout_numbers_in_play_order(self):
        tracks = [FakeTrack(title="B", index=9), FakeTrack(title="A", index=3)]
        items = plan_export(tracks, structure=STRUCTURE_FLAT)
        self.assertTrue(items[0].relative_path.startswith("001 - "))
        self.assertTrue(items[1].relative_path.startswith("002 - "))

    def test_artist_album_layout_uses_subfolders(self):
        tracks = [FakeTrack(artist="Queen", album="A Night at the Opera", index=1)]
        item = plan_export(tracks, structure=STRUCTURE_ARTIST_ALBUM)[0]
        parts = item.relative_path.replace("\\", "/").split("/")
        self.assertEqual(parts[0], "Queen")
        self.assertEqual(parts[1], "A Night at the Opera")

    def test_illegal_characters_never_reach_the_path(self):
        tracks = [FakeTrack(title="What?", artist="AC/DC", album='B:est')]
        item = plan_export(tracks, structure=STRUCTURE_ARTIST_ALBUM)[0]
        for bad in '<>:"|?*':
            self.assertNotIn(bad, item.relative_path)

    def test_identical_names_do_not_overwrite_each_other(self):
        tracks = [FakeTrack(title="Song", artist="A", album="X", index=1) for _ in range(3)]
        items = plan_export(tracks, structure=STRUCTURE_ARTIST_ALBUM)
        paths = {item.relative_path for item in items}
        self.assertEqual(len(paths), 3, "collisions would silently lose tracks")

    def test_collisions_differing_only_by_trailing_dot_are_caught(self):
        tracks = [
            FakeTrack(title="Song", artist="A", album="X", index=1),
            FakeTrack(title="Song.", artist="A", album="X", index=1),
        ]
        items = plan_export(tracks, structure=STRUCTURE_ARTIST_ALBUM)
        self.assertNotEqual(items[0].relative_path, items[1].relative_path)

    def test_every_track_is_planned(self):
        tracks = [FakeTrack(title=f"T{i}") for i in range(30)]
        self.assertEqual(len(plan_export(tracks)), 30)


class FolderStructureTests(unittest.TestCase):
    """Every layout offered in the dialog must produce the path it advertises."""

    def _path(self, structure, **kwargs):
        track = FakeTrack(title="Song", artist="Queen", album="Opera", index=4, **kwargs)
        items = plan_export([track], structure=structure, playlist_name="Road Trip")
        return items[0].relative_path.replace("\\", "/")

    def test_flat(self):
        self.assertEqual(self._path(STRUCTURE_FLAT), "001 - Queen - Song.flac")

    def test_artist_only(self):
        self.assertEqual(self._path(STRUCTURE_ARTIST), "Queen/001 - Song.flac")

    def test_album_only(self):
        self.assertEqual(self._path(STRUCTURE_ALBUM), "Opera/04 - Song.flac")

    def test_artist_album(self):
        self.assertEqual(self._path(STRUCTURE_ARTIST_ALBUM), "Queen/Opera/04 - Song.flac")

    def test_playlist_flat(self):
        self.assertEqual(
            self._path(STRUCTURE_PLAYLIST_FLAT), "Road Trip/001 - Queen - Song.flac"
        )

    def test_playlist_artist(self):
        self.assertEqual(
            self._path(STRUCTURE_PLAYLIST_ARTIST), "Road Trip/Queen/001 - Song.flac"
        )

    def test_playlist_artist_album(self):
        self.assertEqual(
            self._path(STRUCTURE_PLAYLIST_ARTIST_ALBUM),
            "Road Trip/Queen/Opera/04 - Song.flac",
        )

    def test_the_playlist_folder_name_is_sanitised(self):
        track = FakeTrack(title="Song", artist="A", album="B", index=1)
        item = plan_export([track], structure=STRUCTURE_PLAYLIST_FLAT,
                           playlist_name="AC/DC: Best?")[0]
        head = item.relative_path.replace("\\", "/").split("/")[0]
        for bad in '<>:"/|?*':
            self.assertNotIn(bad, head)

    def test_every_advertised_structure_is_usable(self):
        track = FakeTrack(title="Song", artist="A", album="B", index=1)
        for key, label, example in STRUCTURES:
            with self.subTest(structure=key):
                items = plan_export([track], structure=key, playlist_name="P")
                self.assertTrue(items[0].relative_path)
                depth = items[0].relative_path.replace("\\", "/").count("/")
                self.assertEqual(depth, example.count("/"),
                                 f"{label}: folder depth must match its example")


class ExportRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="syncra-export-")
        self.addCleanup(self.tmp.cleanup)
        self.fetched = []

    def _fetch(self, payload=b"AUDIO"):
        def fetch(track, audio_format, destination):
            self.fetched.append(destination)
            with open(destination, "wb") as handle:
                handle.write(payload)
            return len(payload)
        return fetch

    def test_files_and_a_playlist_are_written(self):
        tracks = [FakeTrack(title=f"T{i}", index=i + 1) for i in range(3)]
        report = export_playlist(
            tracks, self.tmp.name, playlist_name="Road Trip", fetch=self._fetch()
        )
        self.assertEqual(len(report.exported), 3)
        self.assertTrue(os.path.exists(report.playlist_file))

    def test_the_playlist_uses_relative_paths(self):
        """Absolute paths are exactly what makes the current export useless."""
        tracks = [FakeTrack(title="Song", index=1)]
        report = export_playlist(
            tracks, self.tmp.name, playlist_name="Mix", fetch=self._fetch()
        )
        body = open(report.playlist_file, encoding="utf-8").read()
        self.assertNotIn(self.tmp.name, body)
        self.assertIn("001 - ", body)

    def test_the_playlist_carries_extinf_metadata(self):
        tracks = [FakeTrack(title="Song", artist="Band", duration=185000)]
        report = export_playlist(
            tracks, self.tmp.name, playlist_name="Mix", fetch=self._fetch()
        )
        body = open(report.playlist_file, encoding="utf-8").read()
        self.assertIn("#EXTM3U", body)
        self.assertIn("#EXTINF:185,Band - Song", body)

    def test_subfolders_are_created(self):
        tracks = [FakeTrack(artist="Queen", album="Opera", index=1)]
        export_playlist(tracks, self.tmp.name, playlist_name="Mix",
                        structure=STRUCTURE_ARTIST_ALBUM, fetch=self._fetch())
        self.assertTrue(os.path.isdir(os.path.join(self.tmp.name, "Queen", "Opera")))

    def test_a_size_limit_stops_the_big_files(self):
        """Budgeting counts bytes actually written, so the fake must write them."""
        size = 10_000_000
        tracks = [FakeTrack(title=f"T{i}", media=[FakeMedia([FakePart(size=size)])])
                  for i in range(5)]

        def sized(track, audio_format, destination):
            # Sparse file: real length without writing 10MB in a test.
            with open(destination, "wb") as handle:
                handle.truncate(size)
            return size

        report = export_playlist(
            tracks, self.tmp.name, playlist_name="Mix",
            max_bytes=25_000_000, fetch=sized
        )
        self.assertEqual(len(report.exported), 2, "a 25MB budget fits two 10MB tracks")
        self.assertEqual(len(report.skipped), 3)

    def test_a_failing_track_does_not_abort_the_export(self):
        tracks = [FakeTrack(title=f"T{i}", index=i + 1) for i in range(3)]

        def flaky(track, audio_format, destination):
            if track.title == "T1":
                raise OSError("network dropped")
            with open(destination, "wb") as handle:
                handle.write(b"AUDIO")
            return 5

        report = export_playlist(tracks, self.tmp.name, playlist_name="Mix", fetch=flaky)
        self.assertEqual(len(report.exported), 2)
        self.assertEqual(len(report.failed), 1)

    def test_existing_files_are_skipped_unless_overwriting(self):
        tracks = [FakeTrack(title="Song", index=1)]
        export_playlist(tracks, self.tmp.name, playlist_name="Mix", fetch=self._fetch())
        self.fetched.clear()
        report = export_playlist(tracks, self.tmp.name, playlist_name="Mix",
                                 fetch=self._fetch())
        self.assertEqual(self.fetched, [])
        self.assertEqual(len(report.skipped), 1)

    def test_overwrite_rewrites_the_file(self):
        tracks = [FakeTrack(title="Song", index=1)]
        export_playlist(tracks, self.tmp.name, playlist_name="Mix", fetch=self._fetch())
        self.fetched.clear()
        export_playlist(tracks, self.tmp.name, playlist_name="Mix",
                        overwrite=True, fetch=self._fetch())
        self.assertEqual(len(self.fetched), 1)

    def test_cancelling_stops_early_and_is_reported(self):
        tracks = [FakeTrack(title=f"T{i}", index=i + 1) for i in range(10)]
        state = {"n": 0}

        def counting(track, audio_format, destination):
            state["n"] += 1
            with open(destination, "wb") as handle:
                handle.write(b"AUDIO")
            return 5

        report = export_playlist(
            tracks, self.tmp.name, playlist_name="Mix", fetch=counting,
            should_cancel=lambda: state["n"] >= 3,
        )
        self.assertTrue(report.cancelled)
        self.assertLess(len(report.exported), 10)

    def test_a_playlist_is_still_written_after_cancelling(self):
        """Whatever made it onto the stick should still be playable."""
        tracks = [FakeTrack(title=f"T{i}", index=i + 1) for i in range(10)]
        state = {"n": 0}

        def counting(track, audio_format, destination):
            state["n"] += 1
            with open(destination, "wb") as handle:
                handle.write(b"AUDIO")
            return 5

        report = export_playlist(
            tracks, self.tmp.name, playlist_name="Mix", fetch=counting,
            should_cancel=lambda: state["n"] >= 3,
        )
        self.assertTrue(report.playlist_file)
        self.assertTrue(os.path.exists(report.playlist_file))

    def test_the_destination_is_created_if_missing(self):
        target = os.path.join(self.tmp.name, "new", "folder")
        export_playlist([FakeTrack()], target, playlist_name="Mix", fetch=self._fetch())
        self.assertTrue(os.path.isdir(target))

    def test_the_playlist_filename_is_sanitised(self):
        report = export_playlist([FakeTrack()], self.tmp.name,
                                 playlist_name="AC/DC: Best?", fetch=self._fetch())
        name = os.path.basename(report.playlist_file)
        for bad in '<>:"/\\|?*':
            self.assertNotIn(bad, name)


# A JPEG starts FF D8 FF; enough for the tagger to pick a mime type.
JPEG_BYTES = bytes([255, 216, 255]) + b"-not-really-a-jpeg"


class FakeAlbum:
    def __init__(self, year=1984):
        self.year = year


class FakeServerForTags:
    def __init__(self, cover=JPEG_BYTES, year=1984):
        self.cover = cover
        self.year = year
        self.url_calls = 0
        self.fetch_calls = 0

    def url(self, path, includeToken=False):
        self.url_calls += 1
        return "http://plex.local" + path

    def fetchItem(self, rating_key):
        self.fetch_calls += 1
        return FakeAlbum(self.year)


class TaggingTests(unittest.TestCase):
    """Plex's transcoder returns a bare stream: the only frame it sets is TSSE.

    Without tagging, every exported MP3 has no title, artist, album or artwork -- which
    is what users reported.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="syncra-tags-")
        self.addCleanup(self.tmp.cleanup)

    def _silent_mp3(self, name="a.mp3"):
        """A tiny but structurally valid MP3 so mutagen will write tags to it."""
        path = os.path.join(self.tmp.name, name)
        # One silent MPEG-1 Layer III frame, repeated so mutagen finds a stream.
        frame = bytes([0xFF, 0xFB, 0x90, 0x00]) + bytes(400)
        with open(path, "wb") as handle:
            handle.write(frame * 40)
        return path

    def _read(self, path):
        # ID3 rather than MP3: the tag is what is under test, and reading through MP3
        # would additionally require a decodable audio stream.
        from mutagen.id3 import ID3
        return ID3(path)

    def test_the_core_tags_are_written(self):
        path = self._silent_mp3()
        track = FakeTrack(title="Uptown Girl", artist="Billy Joel",
                          album="The Essential Billy Joel", index=3)
        self.assertTrue(write_mp3_tags(path, track))
        tags = self._read(path)
        self.assertEqual(str(tags["TIT2"].text[0]), "Uptown Girl")
        self.assertEqual(str(tags["TPE1"].text[0]), "Billy Joel")
        self.assertEqual(str(tags["TALB"].text[0]), "The Essential Billy Joel")
        self.assertEqual(str(tags["TRCK"].text[0]), "3")

    def test_cover_art_is_embedded(self):
        path = self._silent_mp3()
        write_mp3_tags(path, FakeTrack(), JPEG_BYTES)
        tags = self._read(path)
        apic = [k for k in tags.keys() if str(k).startswith("APIC")]
        self.assertTrue(apic, "no embedded artwork")
        self.assertEqual(tags[apic[0]].type, 3)  # front cover

    def test_png_artwork_gets_the_right_mime(self):
        path = self._silent_mp3()
        png = bytes([137, 80, 78, 71]) + b"rest"
        write_mp3_tags(path, FakeTrack(), png)
        tags = self._read(path)
        apic = [k for k in tags.keys() if str(k).startswith("APIC")][0]
        self.assertEqual(tags[apic].mime, "image/png")

    def test_tags_are_saved_as_id3v2_3(self):
        """v2.4 is ignored by many car head units, which is where exports end up."""
        path = self._silent_mp3()
        write_mp3_tags(path, FakeTrack())
        self.assertEqual(self._read(path).version[:2], (2, 3))

    def test_the_year_is_written_when_supplied(self):
        path = self._silent_mp3()
        write_mp3_tags(path, FakeTrack(), b"", 1982)
        self.assertEqual(str(self._read(path)["TDRC"].text[0]), "1982")

    def test_genres_are_joined(self):
        class Genre:
            def __init__(self, tag): self.tag = tag

        path = self._silent_mp3()
        track = FakeTrack()
        track.genres = [Genre("Pop/Rock"), Genre("R&B")]
        write_mp3_tags(path, track)
        self.assertIn("R&B", str(self._read(path)["TCON"].text[0]))

    def test_tagging_a_missing_file_does_not_raise(self):
        self.assertFalse(write_mp3_tags(os.path.join(self.tmp.name, "gone.mp3"),
                                        FakeTrack()))

    def test_album_art_is_fetched_once_per_album(self):
        """A 12-track album must not download its cover twelve times."""
        server = FakeServerForTags()
        cache = {}
        tracks = [FakeTrack(album="Same", rating_key=i) for i in range(5)]
        for track in tracks:
            track.parentThumb = "/library/metadata/1/thumb/1"

        for track in tracks:
            fetch_cover_bytes(server, track, cache)

        self.assertEqual(len(cache), 1, "one cover entry per album, not per track")

    def test_the_album_year_is_looked_up_once(self):
        server = FakeServerForTags(year=1987)
        cache = {}
        tracks = [FakeTrack(rating_key=i) for i in range(4)]
        for track in tracks:
            track.parentRatingKey = 99
        years = [fetch_album_year(server, t, cache) for t in tracks]
        self.assertEqual(years, [1987] * 4)
        self.assertEqual(server.fetch_calls, 1, "one lookup per album, not per track")

    def test_a_track_with_no_artwork_yields_no_url(self):
        track = FakeTrack()
        track.parentThumb = None
        track.thumb = None
        track.grandparentThumb = None
        self.assertEqual(album_cover_url(FakeServerForTags(), track), "")

    def test_a_failed_year_lookup_is_survivable(self):
        class Broken:
            def fetchItem(self, key):
                raise RuntimeError("gone")

        track = FakeTrack()
        track.parentRatingKey = 5
        self.assertIsNone(fetch_album_year(Broken(), track, {}))


if __name__ == "__main__":
    unittest.main()
