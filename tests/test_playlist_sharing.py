"""Tests for sharing a playlist with the other accounts on a Plex server.

Plex playlists belong to the account that created them, so on a server with a household
the admin's playlists are invisible to everyone else. This writes into other people's
accounts, so the rules that matter most are the destructive ones: nothing belonging to
another user is removed unless MODE_REPLACE was explicitly chosen, and one user's
failure never aborts the rest of the run.

The efficiency constraint is also pinned here. Creating a playlist needs only rating
keys, so it is one request per user; resolving each track against each account instead
would be a round trip per track per user -- roughly a thousand for a 138-track playlist
across seven people.
"""

import unittest

from syncra.services.playlist_sharing import (
    MODE_CREATE,
    MODE_MERGE,
    MODE_REPLACE,
    STATUS_CANCELLED,
    STATUS_CREATED,
    STATUS_FAILED,
    STATUS_SKIPPED,
    STATUS_UPDATED,
    HouseholdUser,
    list_household_users,
    playlist_rating_keys,
    share_playlist,
)


class FakeTrack:
    def __init__(self, rating_key):
        self.ratingKey = rating_key
        self.listType = "audio"


class FakePlaylist:
    def __init__(self, title, rating_keys, owner=None):
        self.title = title
        self.playlistType = "audio"
        self.key = f"/playlists/{abs(hash(title)) % 1000}"
        self._keys = [str(k) for k in rating_keys]
        self.deleted = False
        self.owner = owner

    def items(self):
        return [FakeTrack(k) for k in self._keys]

    def delete(self):
        self.deleted = True
        if self.owner is not None:
            self.owner.playlists_list = [
                p for p in self.owner.playlists_list if p is not self
            ]


class FakeSession:
    def __init__(self):
        self.post = "POST"
        self.put = "PUT"


class FakeUserServer:
    """One account's view of the server."""

    def __init__(self, machine_id="MID", playlists=None):
        self.machineIdentifier = machine_id
        self._session = FakeSession()
        self.playlists_list = list(playlists or [])
        self.queries = []

    def _uriRoot(self):
        return f"server://{self.machineIdentifier}/com.plexapp.plugins.library"

    def playlists(self):
        return list(self.playlists_list)

    def query(self, key, method=None, **kwargs):
        self.queries.append((key, method))
        if key.startswith("/playlists?") or key.startswith("/playlists%"):
            self.playlists_list.append(FakePlaylist("created", [], owner=self))
        return None


class FakeAccountUser:
    def __init__(self, title, token="tok", raises=None):
        self.title = title
        self.id = abs(hash(title)) % 100000
        self.home = True
        self.email = f"{title.lower()}@example.com"
        self._token = token
        self._raises = raises
        self.token_calls = 0

    def get_token(self, machine_identifier):
        self.token_calls += 1
        if self._raises:
            raise self._raises
        return self._token


class FakeAccount:
    def __init__(self, users):
        self._users = users

    def users(self):
        return list(self._users)


def make_target(title, **kwargs):
    account_user = FakeAccountUser(title, **kwargs)
    return HouseholdUser(
        user_id=str(account_user.id),
        title=title,
        is_home=True,
        account_user=account_user,
    )


class ListUsersTests(unittest.TestCase):
    def test_users_are_listed(self):
        account = FakeAccount([FakeAccountUser("Jaslyn"), FakeAccountUser("Joseph")])
        users = list_household_users(account)
        self.assertEqual([u.title for u in users], ["Jaslyn", "Joseph"])

    def test_home_users_sort_before_shared_users(self):
        home = FakeAccountUser("Zoe")
        shared = FakeAccountUser("Adam")
        shared.home = False
        users = list_household_users(FakeAccount([shared, home]))
        self.assertEqual([u.title for u in users], ["Zoe", "Adam"])

    def test_kind_labels_each_account(self):
        users = list_household_users(FakeAccount([FakeAccountUser("Jaslyn")]))
        self.assertEqual(users[0].kind, "Home user")

    def test_no_account_is_an_empty_list_not_an_error(self):
        self.assertEqual(list_household_users(None), [])

    def test_a_failing_account_lookup_is_survivable(self):
        class Broken:
            def users(self):
                raise RuntimeError("network down")

        self.assertEqual(list_household_users(Broken()), [])


class RatingKeyTests(unittest.TestCase):
    def test_keys_are_read_in_order(self):
        playlist = FakePlaylist("Road Trip", [3, 1, 2])
        self.assertEqual(playlist_rating_keys(playlist), ["3", "1", "2"])


class ShareTestCase(unittest.TestCase):
    def setUp(self):
        self.servers = {}

    def _factory(self, existing_by_user=None):
        existing_by_user = existing_by_user or {}
        created = self.servers

        def factory(base_url, token):
            server = FakeUserServer(playlists=existing_by_user.get(token, []))
            created[token] = server
            return server

        return factory

    def _share(self, targets, mode=MODE_CREATE, keys=("1", "2", "3"),
               existing_by_user=None, should_cancel=None, title="Road Trip"):
        return share_playlist(
            account=None,
            base_url="http://plex.local:32400",
            machine_identifier="MID",
            title=title,
            rating_keys=list(keys),
            targets=targets,
            mode=mode,
            server_factory=self._factory(existing_by_user),
            should_cancel=should_cancel,
        )


class CreateTests(ShareTestCase):
    def test_a_playlist_is_created_for_each_user(self):
        targets = [make_target("Jaslyn", token="a"), make_target("Joseph", token="b")]
        report = self._share(targets)
        self.assertEqual(report.succeeded, 2)
        self.assertEqual([o.status for o in report.outcomes],
                         [STATUS_CREATED, STATUS_CREATED])

    def test_creation_is_one_request_per_user(self):
        """Resolving tracks per account would be a round trip per track per user."""
        targets = [make_target("Jaslyn", token="a")]
        self._share(targets, keys=[str(i) for i in range(200)])
        self.assertEqual(len(self.servers["a"].queries), 1)

    def test_the_rating_keys_are_sent_in_the_uri(self):
        targets = [make_target("Jaslyn", token="a")]
        self._share(targets, keys=["7", "8"])
        key, _ = self.servers["a"].queries[0]
        self.assertIn("7%2C8", key.replace(",", "%2C"))

    def test_the_outcome_counts_the_tracks(self):
        report = self._share([make_target("Jaslyn", token="a")], keys=["1", "2", "3"])
        self.assertEqual(report.outcomes[0].added, 3)

    def test_each_user_gets_their_own_token(self):
        target = make_target("Jaslyn", token="a")
        self._share([target])
        self.assertEqual(target.account_user.token_calls, 1)


class ExistingPlaylistTests(ShareTestCase):
    def _existing(self, token="a", title="Road Trip", keys=("1",)):
        server_playlists = {token: [FakePlaylist(title, keys)]}
        return server_playlists

    def test_create_mode_leaves_their_playlist_alone(self):
        existing = self._existing()
        report = self._share([make_target("Jaslyn", token="a")],
                             mode=MODE_CREATE, existing_by_user=existing)
        self.assertEqual(report.outcomes[0].status, STATUS_SKIPPED)
        self.assertFalse(existing["a"][0].deleted)

    def test_create_mode_writes_nothing(self):
        existing = self._existing()
        self._share([make_target("Jaslyn", token="a")],
                    mode=MODE_CREATE, existing_by_user=existing)
        self.assertEqual(self.servers["a"].queries, [])

    def test_merge_adds_only_the_missing_tracks(self):
        existing = self._existing(keys=("1", "2"))
        report = self._share([make_target("Jaslyn", token="a")],
                             mode=MODE_MERGE, keys=["1", "2", "3"],
                             existing_by_user=existing)
        self.assertEqual(report.outcomes[0].status, STATUS_UPDATED)
        self.assertEqual(report.outcomes[0].added, 1)

    def test_merge_never_deletes_their_playlist(self):
        existing = self._existing(keys=("1",))
        self._share([make_target("Jaslyn", token="a")],
                    mode=MODE_MERGE, existing_by_user=existing)
        self.assertFalse(existing["a"][0].deleted)

    def test_merge_skips_when_they_already_have_everything(self):
        existing = self._existing(keys=("1", "2", "3"))
        report = self._share([make_target("Jaslyn", token="a")],
                             mode=MODE_MERGE, keys=["1", "2", "3"],
                             existing_by_user=existing)
        self.assertEqual(report.outcomes[0].status, STATUS_SKIPPED)
        self.assertEqual(self.servers["a"].queries, [])

    def test_replace_deletes_and_recreates(self):
        existing = self._existing(keys=("9",))
        report = self._share([make_target("Jaslyn", token="a")],
                             mode=MODE_REPLACE, existing_by_user=existing)
        self.assertEqual(report.outcomes[0].status, STATUS_UPDATED)
        self.assertTrue(existing["a"][0].deleted)

    def test_replace_is_the_only_mode_that_deletes(self):
        for mode in (MODE_CREATE, MODE_MERGE):
            with self.subTest(mode=mode):
                existing = self._existing(keys=("9",))
                self._share([make_target("Jaslyn", token="a")],
                            mode=mode, existing_by_user=existing)
                self.assertFalse(existing["a"][0].deleted)

    def test_matching_a_name_is_case_insensitive(self):
        existing = {"a": [FakePlaylist("road trip", ["1"])]}
        report = self._share([make_target("Jaslyn", token="a")],
                             mode=MODE_CREATE, existing_by_user=existing,
                             title="Road Trip")
        self.assertEqual(report.outcomes[0].status, STATUS_SKIPPED)

    def test_an_unrelated_playlist_of_theirs_is_untouched(self):
        theirs = FakePlaylist("Their Mix", ["5"])
        report = self._share([make_target("Jaslyn", token="a")],
                             mode=MODE_REPLACE, existing_by_user={"a": [theirs]})
        self.assertEqual(report.outcomes[0].status, STATUS_CREATED)
        self.assertFalse(theirs.deleted)


class FailureTests(ShareTestCase):
    def test_one_users_failure_does_not_stop_the_others(self):
        targets = [
            make_target("Broken", raises=RuntimeError("no access")),
            make_target("Jaslyn", token="b"),
        ]
        report = self._share(targets)
        self.assertEqual(report.failed, 1)
        self.assertEqual(report.succeeded, 1)

    def test_the_failure_reason_is_reported(self):
        targets = [make_target("Broken", raises=RuntimeError("no access"))]
        report = self._share(targets)
        self.assertEqual(report.outcomes[0].status, STATUS_FAILED)
        self.assertIn("no access", report.outcomes[0].message)

    def test_a_missing_token_is_a_failure_not_a_silent_skip(self):
        targets = [make_target("Tokenless", token="")]
        report = self._share(targets)
        self.assertEqual(report.outcomes[0].status, STATUS_FAILED)

    def test_cancelling_stops_before_the_next_user(self):
        targets = [make_target("A", token="a"), make_target("B", token="b")]
        seen = []

        def cancel():
            return len(seen) >= 1

        report = share_playlist(
            account=None,
            base_url="http://plex.local:32400",
            machine_identifier="MID",
            title="Road Trip",
            rating_keys=["1"],
            targets=targets,
            mode=MODE_CREATE,
            server_factory=self._factory(),
            progress=seen.append,
            should_cancel=cancel,
        )
        self.assertEqual(report.outcomes[-1].status, STATUS_CANCELLED)
        self.assertEqual(report.succeeded, 1)

    def test_an_unknown_mode_is_rejected_up_front(self):
        with self.assertRaises(ValueError):
            self._share([make_target("Jaslyn")], mode="obliterate")

    def test_no_targets_is_an_empty_report(self):
        report = self._share([])
        self.assertEqual(report.outcomes, [])


if __name__ == "__main__":
    unittest.main()
