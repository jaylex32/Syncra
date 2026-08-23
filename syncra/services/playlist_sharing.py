"""Copy playlists to the other Plex accounts on a server.

Plex playlists belong to the account that made them. Nothing in Plex's own interface
hands a playlist to another member of the household, so on a server with several users
every playlist the admin builds is invisible to everyone else.

This module addresses each user's own view of the same server. `MyPlexUser.get_token()`
returns that user's access token, a `PlexServer` built with it sees their playlists, and
rating keys are server-global -- so the admin's track list can be written straight into
someone else's account without re-resolving anything.

Everything here is deliberately Qt-free so it can be exercised without a UI, and every
write is per-user and reported individually: one person's failure never aborts the rest,
and nothing belonging to another user is deleted unless MODE_REPLACE is chosen.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional, Sequence

from plexapi import utils as plex_utils

# How an existing playlist of the same name on the target account is treated.
MODE_CREATE = "create"    # leave theirs alone, skip
MODE_MERGE = "merge"      # add only the tracks they are missing
MODE_REPLACE = "replace"  # delete theirs and write a fresh copy

MODES = (MODE_CREATE, MODE_MERGE, MODE_REPLACE)

STATUS_CREATED = "created"
STATUS_UPDATED = "updated"
STATUS_SKIPPED = "skipped"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"


@dataclass
class HouseholdUser:
    """One account that shares this server."""

    user_id: str
    title: str
    is_home: bool = False
    email: str = ""
    account_user: object = None

    @property
    def kind(self) -> str:
        return "Home user" if self.is_home else "Shared user"


@dataclass
class ShareOutcome:
    user: str
    status: str
    message: str = ""
    added: int = 0
    total: int = 0

    @property
    def ok(self) -> bool:
        return self.status in (STATUS_CREATED, STATUS_UPDATED, STATUS_SKIPPED)


@dataclass
class ShareReport:
    outcomes: list = field(default_factory=list)

    @property
    def succeeded(self) -> int:
        return sum(1 for o in self.outcomes if o.status in (STATUS_CREATED, STATUS_UPDATED))

    @property
    def failed(self) -> int:
        return sum(1 for o in self.outcomes if o.status == STATUS_FAILED)

    @property
    def skipped(self) -> int:
        return sum(1 for o in self.outcomes if o.status == STATUS_SKIPPED)


def list_household_users(account) -> list:
    """Everyone who shares this server, admin excluded (they already own the source)."""
    if account is None:
        return []
    try:
        raw = account.users()
    except Exception as error:
        logging.warning(f"Could not list Plex users: {error}")
        return []

    users = []
    for entry in raw:
        try:
            users.append(
                HouseholdUser(
                    user_id=str(getattr(entry, "id", "") or ""),
                    title=str(getattr(entry, "title", "") or "").strip() or "Unknown",
                    is_home=bool(getattr(entry, "home", False)),
                    email=str(getattr(entry, "email", "") or ""),
                    account_user=entry,
                )
            )
        except Exception:
            continue
    users.sort(key=lambda u: (not u.is_home, u.title.lower()))
    return users


def playlist_rating_keys(playlist) -> list:
    """Rating keys of a playlist's tracks, in order.

    One request for the whole playlist. Resolving each track individually on the
    target account instead would be an HTTP round trip per track per user.
    """
    keys = []
    for item in playlist.items():
        key = getattr(item, "ratingKey", None)
        if key is not None:
            keys.append(str(key))
    return keys


def create_playlist_from_rating_keys(server, title, rating_keys, list_type="audio"):
    """Create a playlist from rating keys with a single POST.

    Mirrors what plexapi's Playlist._create does, minus the requirement to hold a
    fetched object for every track -- the endpoint only ever wanted the keys.
    """
    keys = [str(k) for k in rating_keys if str(k).strip()]
    if not keys:
        raise ValueError("Cannot create an empty playlist.")

    uri = f"{server._uriRoot()}/library/metadata/{','.join(keys)}"
    args = {"uri": uri, "type": list_type, "title": title, "smart": 0}
    server.query(f"/playlists{plex_utils.joinArgs(args)}", method=server._session.post)


def add_rating_keys_to_playlist(playlist, server, rating_keys):
    """Append rating keys to an existing playlist with a single PUT."""
    keys = [str(k) for k in rating_keys if str(k).strip()]
    if not keys:
        return
    uri = f"{server._uriRoot()}/library/metadata/{','.join(keys)}"
    args = {"uri": uri}
    server.query(f"{playlist.key}/items{plex_utils.joinArgs(args)}",
                 method=server._session.put)


def find_playlist(server, title):
    """The target account's own playlist of this name, if they have one."""
    wanted = str(title or "").strip().lower()
    for playlist in server.playlists():
        if str(getattr(playlist, "title", "")).strip().lower() == wanted:
            return playlist
    return None


def share_playlist(
    *,
    account,
    base_url: str,
    machine_identifier: str,
    title: str,
    rating_keys: Sequence,
    targets: Iterable,
    mode: str = MODE_CREATE,
    server_factory: Optional[Callable] = None,
    progress: Optional[Callable] = None,
    should_cancel: Optional[Callable] = None,
) -> ShareReport:
    """Write `title` into each target account.

    `server_factory(base_url, token)` is injected so this can be tested without a
    server. Each user is handled independently: a failure is recorded and the run
    continues, because a half-shared playlist with a clear report is far more useful
    than an abort with no record of who got what.
    """
    if mode not in MODES:
        raise ValueError(f"Unknown share mode: {mode}")

    from plexapi.server import PlexServer  # imported lazily; tests inject a factory

    factory = server_factory or (lambda url, token: PlexServer(url, token, timeout=30))
    keys = [str(k) for k in rating_keys if str(k).strip()]
    report = ShareReport()

    def cancelled() -> bool:
        return bool(should_cancel and should_cancel())

    for target in targets:
        if cancelled():
            report.outcomes.append(
                ShareOutcome(target.title, STATUS_CANCELLED, "Cancelled before sharing.")
            )
            continue

        if progress:
            progress(target.title)

        try:
            token = target.account_user.get_token(machine_identifier)
            if not token:
                raise RuntimeError("Plex returned no access token for this user.")

            user_server = factory(base_url, token)
            existing = find_playlist(user_server, title)

            if existing is None:
                create_playlist_from_rating_keys(user_server, title, keys)
                report.outcomes.append(
                    ShareOutcome(target.title, STATUS_CREATED,
                                 f"Created with {len(keys)} track(s).",
                                 added=len(keys), total=len(keys))
                )
                continue

            if mode == MODE_CREATE:
                report.outcomes.append(
                    ShareOutcome(target.title, STATUS_SKIPPED,
                                 "They already have a playlist with this name.")
                )
                continue

            if mode == MODE_REPLACE:
                existing.delete()
                create_playlist_from_rating_keys(user_server, title, keys)
                report.outcomes.append(
                    ShareOutcome(target.title, STATUS_UPDATED,
                                 f"Replaced with {len(keys)} track(s).",
                                 added=len(keys), total=len(keys))
                )
                continue

            # MODE_MERGE: only add what they do not already have, preserving order.
            theirs = {str(getattr(item, "ratingKey", "")) for item in existing.items()}
            missing = [key for key in keys if key not in theirs]
            if not missing:
                report.outcomes.append(
                    ShareOutcome(target.title, STATUS_SKIPPED,
                                 "Already has every track.", total=len(keys))
                )
                continue

            add_rating_keys_to_playlist(existing, user_server, missing)
            report.outcomes.append(
                ShareOutcome(target.title, STATUS_UPDATED,
                             f"Added {len(missing)} missing track(s).",
                             added=len(missing), total=len(keys))
            )

        except Exception as error:
            logging.warning(f"Sharing '{title}' to {target.title} failed: {error}")
            report.outcomes.append(
                ShareOutcome(target.title, STATUS_FAILED, str(error))
            )

    return report
