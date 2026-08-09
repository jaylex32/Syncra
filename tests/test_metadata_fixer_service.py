import unittest

from syncra.models.metadata import MetadataCandidate, TrackIdentity
from syncra.services.metadata_fixer_service import MetadataFixerService
from syncra.services.metadata_provider import MetadataProvider


class FakeArtist:
    def __init__(self, title):
        self.title = title


class FakeAlbum:
    def __init__(self, title):
        self.title = title


class FakeTrack:
    def __init__(self, rating_key, title, artist, album, year=None):
        self.ratingKey = rating_key
        self.title = title
        self._artist = artist
        self._album = album
        self.year = year
        self.edits = []

    def artist(self):
        return FakeArtist(self._artist)

    def album(self):
        return FakeAlbum(self._album)

    def editTitle(self, value, locked=True):
        self.title = value
        self.edits.append(("title", value, locked))

    def editTrackArtist(self, value, locked=True):
        self._artist = value
        self.edits.append(("artist", value, locked))

    def editField(self, field, value, locked=True):
        self.edits.append((field, value, locked))


class FakeProvider(MetadataProvider):
    def search_track(self, track: TrackIdentity):
        return MetadataCandidate(
            source="musicbrainz",
            title=f"{track.title} (Remastered)",
            artist=track.artist,
            album=track.album,
            year=track.year,
            score=98,
        )

    def get_release_details(self, release_mbid: str):
        return {}


class MetadataFixerServiceTests(unittest.TestCase):
    def test_scan_and_apply(self):
        provider = FakeProvider()
        service = MetadataFixerService(provider=provider, review_threshold=80)

        track = FakeTrack("1", "Song A", "Artist A", "Album A", year=2020)
        proposals = service.scan([track])

        self.assertEqual(len(proposals), 1)
        self.assertIn("title", proposals[0].changes)
        self.assertEqual(proposals[0].confidence, 98)

        results = service.apply(proposals)
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].success)
        self.assertIn("title", results[0].applied_fields)
        self.assertTrue(any(edit[0] == "title" for edit in track.edits))


if __name__ == "__main__":
    unittest.main()
