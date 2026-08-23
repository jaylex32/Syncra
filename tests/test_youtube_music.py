"""Tests for importing public YouTube / YouTube Music playlists.

Every title and channel name below was taken from a real 185-track public playlist,
because the failure modes here are not hypothetical:

* **40% of titles carry upload furniture** -- "(Official Music Video)",
  "(Official 4K Video)", "[HD Remaster]", a trailing bare "HD". Handing those to the
  matcher makes it miss tracks the library actually has.
* **Blanket bracket-stripping is wrong.** The same playlist contains "(dub mix)",
  "(Rah Mix)", "(Naive Melody)", "(No Can Do)" and "(Are Made Of This)", all part of
  the real song title.
* **The "artists" field is often the uploader, not the performer.** "Prince - Purple
  Rain" was credited to "The Codfather" and "George Benson - Give Me The Night" to
  "RHINO". Trusting it would make those unmatchable, so a dash-prefixed title wins.

No network access: the client is injected.
"""

import unittest

from syncra.services.youtube_music import (
    clean_track_title,
    fetch_playlist,
    is_youtube_url,
    parse_playlist_id,
    resolve_artist_and_title,
    split_artist_from_title,
)


class UrlParsingTests(unittest.TestCase):
    def test_a_youtube_music_playlist_url(self):
        self.assertEqual(
            parse_playlist_id("https://music.youtube.com/playlist?list=PLabc123456"),
            "PLabc123456",
        )

    def test_a_regular_youtube_playlist_url(self):
        self.assertEqual(
            parse_playlist_id("https://www.youtube.com/playlist?list=PLabc123456"),
            "PLabc123456",
        )

    def test_extra_query_parameters_are_ignored(self):
        self.assertEqual(
            parse_playlist_id("https://youtube.com/playlist?list=PLabc123456&si=xyz"),
            "PLabc123456",
        )

    def test_a_watch_url_with_a_list_still_works(self):
        self.assertEqual(
            parse_playlist_id("https://www.youtube.com/watch?v=aaa&list=PLabc123456"),
            "PLabc123456",
        )

    def test_a_browse_url_drops_the_vl_prefix(self):
        self.assertEqual(
            parse_playlist_id("https://music.youtube.com/browse/VLPLabc123456"),
            "PLabc123456",
        )

    def test_a_bare_playlist_id_is_accepted(self):
        self.assertEqual(parse_playlist_id("PLabc123456"), "PLabc123456")

    def test_a_url_without_a_playlist_is_rejected(self):
        self.assertIsNone(parse_playlist_id("https://www.youtube.com/watch?v=abc"))

    def test_empty_input_is_rejected(self):
        self.assertIsNone(parse_playlist_id(""))
        self.assertIsNone(parse_playlist_id(None))

    def test_host_detection(self):
        self.assertTrue(is_youtube_url("https://music.youtube.com/playlist?list=X"))
        self.assertTrue(is_youtube_url("https://youtu.be/abc"))
        self.assertFalse(is_youtube_url("https://open.spotify.com/playlist/x"))


class TitleCleaningTests(unittest.TestCase):
    """All inputs are real titles from a live playlist."""

    def test_official_music_video_is_removed(self):
        self.assertEqual(
            clean_track_title("Everybody Wants To Rule The World (Official Music Video)"),
            "Everybody Wants To Rule The World",
        )

    def test_resolution_markers_are_removed(self):
        self.assertEqual(
            clean_track_title("I Wanna Dance With Somebody (Official 4K Video)"),
            "I Wanna Dance With Somebody",
        )
        self.assertEqual(
            clean_track_title("How Will I Know (Official HD Video)"), "How Will I Know"
        )

    def test_remaster_markers_are_removed(self):
        self.assertEqual(clean_track_title("Ain't Nobody (HD Remaster)"), "Ain't Nobody")
        self.assertEqual(
            clean_track_title("Once in a Lifetime (2006 Remaster)"), "Once in a Lifetime"
        )
        self.assertEqual(
            clean_track_title("Here I Go Again (1987 Version; 2007 Remaster)"),
            "Here I Go Again",
        )

    def test_multiple_groups_are_all_removed(self):
        self.assertEqual(
            clean_track_title("Give Me The Night (Official Music Video) [HD Remaster]"),
            "Give Me The Night",
        )

    def test_a_trailing_bare_noise_word_is_removed(self):
        self.assertEqual(
            clean_track_title("Every Breath You Take Video"), "Every Breath You Take"
        )

    def test_noise_glued_on_by_punctuation_is_removed(self):
        self.assertEqual(clean_track_title("Forever Young ~Official"), "Forever Young")

    def test_a_bare_year_group_is_removed(self):
        self.assertEqual(clean_track_title("I Feel for You (1984)"), "I Feel for You")

    def test_official_plus_media_wins_over_other_words(self):
        """"(Official Video - Top Gun)" is furniture despite the film name."""
        self.assertEqual(
            clean_track_title("Take My Breath Away (Official Video - Top Gun)"),
            "Take My Breath Away",
        )

    # -- the groups that must survive --------------------------------------

    def test_a_remix_marker_is_kept(self):
        title = "What's Love Got to Do With It (dub mix)"
        self.assertEqual(clean_track_title(title), title)

    def test_part_of_the_real_title_is_kept(self):
        for title in (
            "This Must Be the Place (Naive Melody)",
            "Sweet Dreams (Are Made Of This)",
            "I Can't Go For That (No Can Do)",
            "Caribbean Queen (No More Love on the Run)",
            "Pour some sugar on me (US version)",
        ):
            with self.subTest(title=title):
                self.assertEqual(clean_track_title(title), title)

    def test_a_featured_artist_is_kept(self):
        title = "Let's Dance (feat. Stevie Ray Vaughan)"
        self.assertEqual(clean_track_title(title), title)

    def test_a_clean_title_is_untouched(self):
        self.assertEqual(clean_track_title("Take On Me"), "Take On Me")

    def test_an_empty_title_is_safe(self):
        self.assertEqual(clean_track_title(""), "")
        self.assertEqual(clean_track_title(None), "")

    def test_a_title_that_is_entirely_noise_is_not_emptied(self):
        """Better to keep something matchable than to return nothing."""
        self.assertTrue(clean_track_title("(Official Video)"))

    def test_a_known_artist_prefix_is_removed(self):
        self.assertEqual(
            clean_track_title("Talk Talk - It's My Life (Official Video)", "Talk Talk"),
            "It's My Life",
        )


class ArtistResolutionTests(unittest.TestCase):
    def test_the_title_prefix_beats_an_uploader_channel(self):
        """The real bug: "Prince - Purple Rain" credited to "The Codfather"."""
        artist, title = resolve_artist_and_title(
            "Prince - Purple Rain (Official Video)", "The Codfather"
        )
        self.assertEqual((artist, title), ("Prince", "Purple Rain"))

    def test_another_real_uploader_case(self):
        artist, title = resolve_artist_and_title(
            "George Benson - Give Me The Night (Official Music Video) [HD Remaster]",
            "RHINO",
        )
        self.assertEqual((artist, title), ("George Benson", "Give Me The Night"))

    def test_a_matching_channel_is_kept_as_the_artist(self):
        artist, title = resolve_artist_and_title(
            "Talk Talk - It's My Life (Official Video)", "Talk Talk"
        )
        self.assertEqual((artist, title), ("Talk Talk", "It's My Life"))

    def test_a_youtube_music_entry_keeps_its_artist_field(self):
        """No dash prefix, so the (correct) artist field is used as-is."""
        artist, title = resolve_artist_and_title("Take On Me", "a-ha")
        self.assertEqual((artist, title), ("a-ha", "Take On Me"))

    def test_a_dash_inside_brackets_is_not_a_split_point(self):
        artist, title = resolve_artist_and_title(
            "Danger Zone (Official Video - Top Gun)", "Kenny Loggins"
        )
        self.assertEqual((artist, title), ("Kenny Loggins", "Danger Zone"))

    def test_a_hyphenated_title_is_not_split(self):
        """"Blue Monday-88" and "Go-Go" have no spaces around the hyphen."""
        artist, title = resolve_artist_and_title("Blue Monday-88", "New Order")
        self.assertEqual(title, "Blue Monday-88")

    def test_no_artist_anywhere_still_yields_a_title(self):
        artist, title = resolve_artist_and_title("Some Song", "")
        self.assertEqual((artist, title), ("", "Some Song"))

    def test_split_helper_ignores_bracketed_dashes(self):
        self.assertEqual(
            split_artist_from_title("Take My Breath Away (Official Video - Top Gun)"),
            ("", "Take My Breath Away (Official Video - Top Gun)"),
        )


class FakeYTMusic:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.calls = []

    def get_playlist(self, playlist_id, limit=None):
        self.calls.append((playlist_id, limit))
        if self.error:
            raise self.error
        return self.payload


def entry(title, artists=None, album=None):
    return {
        "title": title,
        "artists": [{"name": a} for a in (artists or [])],
        "album": {"name": album} if album else None,
    }


class FetchTests(unittest.TestCase):
    def _payload(self, entries, name="80s Music Hits"):
        return {
            "title": name,
            "tracks": entries,
            "thumbnails": [{"url": "http://img/small"}, {"url": "http://img/large"}],
        }

    def test_tracks_use_the_shared_importer_shape(self):
        client = FakeYTMusic(self._payload([entry("Take On Me", ["a-ha"], "Hunting High")]))
        result = fetch_playlist("PLabc123456", client=client)
        track = result["tracks"][0]
        self.assertEqual(
            set(track), {"title", "artist", "album", "parsed", "path", "source"}
        )
        self.assertEqual(track["source"], "youtube")
        self.assertEqual(track["parsed"], "Take On Me - a-ha")

    def test_the_playlist_name_and_largest_thumbnail_come_back(self):
        client = FakeYTMusic(self._payload([entry("Take On Me", ["a-ha"])]))
        result = fetch_playlist("PLabc123456", client=client)
        self.assertEqual(result["name"], "80s Music Hits")
        self.assertEqual(result["image_url"], "http://img/large")

    def test_titles_are_cleaned_on_the_way_through(self):
        client = FakeYTMusic(self._payload([
            entry("Everybody Wants To Rule The World (Official Music Video)",
                  ["Tears For Fears"]),
        ]))
        track = fetch_playlist("PLabc123456", client=client)["tracks"][0]
        self.assertEqual(track["title"], "Everybody Wants To Rule The World")

    def test_uploader_channels_are_corrected_on_the_way_through(self):
        client = FakeYTMusic(self._payload([
            entry("Prince - Purple Rain (Official Video)", ["The Codfather"]),
        ]))
        track = fetch_playlist("PLabc123456", client=client)["tracks"][0]
        self.assertEqual(track["artist"], "Prince")
        self.assertEqual(track["title"], "Purple Rain")

    def test_unavailable_entries_are_dropped(self):
        client = FakeYTMusic(self._payload([
            entry("Song Unavailable"), entry("Take On Me", ["a-ha"]),
        ]))
        titles = [t["title"] for t in fetch_playlist("PL1", client=client)["tracks"]]
        self.assertEqual(titles, ["Take On Me"])

    def test_untitled_entries_are_dropped(self):
        client = FakeYTMusic(self._payload([entry(""), entry("Take On Me", ["a-ha"])]))
        self.assertEqual(len(fetch_playlist("PL1", client=client)["tracks"]), 1)

    def test_view_counts_masquerading_as_artists_are_ignored(self):
        """Some responses put durations and view counts in the artists list."""
        client = FakeYTMusic(self._payload([entry("Take On Me", ["1,234,567 views"])]))
        track = fetch_playlist("PL1", client=client)["tracks"][0]
        self.assertEqual(track["artist"], "")

    def test_a_url_is_reduced_to_its_playlist_id(self):
        client = FakeYTMusic(self._payload([entry("Take On Me", ["a-ha"])]))
        fetch_playlist("https://music.youtube.com/playlist?list=PLabc123456", client=client)
        self.assertEqual(client.calls[0][0], "PLabc123456")

    def test_a_bad_link_is_rejected_before_any_request(self):
        client = FakeYTMusic(self._payload([]))
        with self.assertRaises(ValueError):
            fetch_playlist("https://www.youtube.com/watch?v=abc", client=client)
        self.assertEqual(client.calls, [])

    def test_a_private_or_album_playlist_gives_a_readable_error(self):
        client = FakeYTMusic(error=KeyError("contents"))
        with self.assertRaises(RuntimeError) as caught:
            fetch_playlist("OLAK5uy_something", client=client)
        self.assertIn("private", str(caught.exception).lower())

    def test_an_empty_playlist_is_not_an_error(self):
        client = FakeYTMusic(self._payload([]))
        self.assertEqual(fetch_playlist("PL1", client=client)["tracks"], [])


if __name__ == "__main__":
    unittest.main()
