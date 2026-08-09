"""Discovery built on Plex's own sonic analysis.

Plex Media Server analyses the audio of tracks it has scanned and can answer two
questions no playlist-transfer tool can: which tracks sound like this one, and what is
the gradual path between two tracks. Both run entirely against the local server -- no
external API, no rate limit, no catalog that has to contain your music.

Probed against Plex 1.43.3: track-level `sonicallySimilar` and section-level
`sonicAdventure` both work. Artist-level `station()`, `popularTracks()` and
`sonicallySimilar()` do not return usable data, so nothing here depends on them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

# Plex rejects or ignores absurd limits; keep requests inside a sane band.
MIN_RESULTS = 5
MAX_RESULTS = 200
DEFAULT_RESULTS = 30

# maxDistance is Plex's sonic-distance ceiling, 0.0 (identical) to 1.0 (unrelated).
# The server's own default is 0.25 per the PMS API docs for
# /library/metadata/{id}/nearest, so that is what "Close" means here.
DEFAULT_MAX_DISTANCE = 0.25

# Presets offered in the UI, bracketing the server default.
DISTANCE_PRESETS = (
    ("Very close", 0.15),
    ("Close (Plex default)", DEFAULT_MAX_DISTANCE),
    ("Loose", 0.45),
    ("Adventurous", 0.70),
)


class SonicUnavailable(RuntimeError):
    """Raised when the server cannot answer sonic queries for this library."""


@dataclass
class SonicResult:
    """A generated track list plus a human-readable description of its origin."""

    title: str
    description: str
    tracks: List[Any] = field(default_factory=list)

    def __len__(self):
        return len(self.tracks)


def _clamp_limit(limit):
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = DEFAULT_RESULTS
    return max(MIN_RESULTS, min(MAX_RESULTS, limit))


def track_label(track) -> str:
    """'Artist - Title' for any Plex track, tolerating missing fields."""
    title = str(getattr(track, "title", "") or "Unknown")
    artist = str(
        getattr(track, "grandparentTitle", "") or getattr(track, "originalTitle", "") or ""
    ).strip()
    return f"{artist} - {title}" if artist else title


def is_supported(track) -> bool:
    """Cheap probe: does this track have sonic neighbours the server can return?

    There is no capability flag to read, so the only honest test is to ask for one
    neighbour and see whether anything comes back.
    """
    try:
        return bool(track.sonicallySimilar(limit=1))
    except Exception as error:
        logging.info(f"Sonic analysis unavailable for '{track_label(track)}': {error}")
        return False


def similar_tracks(track, limit=DEFAULT_RESULTS, max_distance=DEFAULT_MAX_DISTANCE,
                   include_seed=True) -> SonicResult:
    """Tracks that sound like `track`, seed first."""
    limit = _clamp_limit(limit)
    try:
        neighbours = track.sonicallySimilar(limit=limit, maxDistance=max_distance) or []
    except Exception as error:
        raise SonicUnavailable(
            f"Plex could not return sonically similar tracks: {error}"
        ) from error

    if not neighbours:
        raise SonicUnavailable(
            "Plex returned no sonically similar tracks. The library may not have been "
            "analysed yet -- run 'Analyze' on it from Plex, or loosen the similarity."
        )

    tracks = ([track] if include_seed else []) + list(neighbours)
    return SonicResult(
        title=f"Like {track_label(track)}",
        description=(
            f"{len(neighbours)} track(s) sonically similar to "
            f"{track_label(track)} (max distance {max_distance:g})."
        ),
        tracks=_dedupe(tracks),
    )


# Reciprocal-rank-fusion constant. Higher flattens the curve so a track ranked 1st for
# one seed does not automatically beat a track ranked 3rd for three seeds; 60 is the
# value the IR literature settled on and it behaves well at these list lengths.
RRF_K = 60


def track_key(track) -> str:
    """Plex's identity for a track."""
    return str(getattr(track, "ratingKey", "") or "")


def track_identity(track) -> str:
    """Identity by title+artist, so the same song on three albums collapses to one.

    Deduplicating on ratingKey alone is not enough: a library commonly holds the same
    recording on the single, the album and a compilation, each with its own key, and
    Plex will happily return several of them as neighbours of each other.
    """
    from syncra.services.track_identity import track_fingerprint

    fingerprint = track_fingerprint(
        getattr(track, "title", ""),
        getattr(track, "grandparentTitle", "") or getattr(track, "originalTitle", ""),
    )
    return fingerprint or track_key(track)


def collapse_duplicates(tracks) -> list:
    """Keep the first appearance of each distinct song."""
    seen, unique = set(), []
    for track in tracks or []:
        identity = track_identity(track)
        if identity and identity in seen:
            continue
        if identity:
            seen.add(identity)
        unique.append(track)
    return unique


def total_duration_ms(tracks) -> int:
    total = 0
    for track in tracks or []:
        try:
            total += int(getattr(track, "duration", 0) or 0)
        except (TypeError, ValueError):
            continue
    return total


def format_duration(milliseconds) -> str:
    seconds = max(0, int(milliseconds or 0)) // 1000
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def select_from_pool(pool, count, variety=0.0, rng=None) -> list:
    """Choose `count` tracks from a scored pool.

    `pool` is [(track, score)] ordered best first. With variety 0 this is simply the
    top N, which is reproducible. Above 0 it samples without replacement, weighted by
    score, from a window that widens with variety -- so pressing Generate again gives a
    different mix while still favouring the strongest candidates.
    """
    if not pool:
        return []
    count = max(0, int(count))
    if count == 0:
        return []

    variety = max(0.0, min(1.0, float(variety or 0.0)))
    if variety <= 0:
        return [track for track, _ in pool[:count]]

    import random

    rng = rng or random.Random()
    # Widen the draw window with variety: at 1.0 we consider three times as many
    # candidates as we need, so repeated runs diverge meaningfully.
    window = pool[: max(count, int(count * (1 + 2 * variety)))]
    remaining = list(window)
    chosen = []
    while remaining and len(chosen) < count:
        weights = [max(score, 1e-9) for _, score in remaining]
        pick = rng.choices(range(len(remaining)), weights=weights, k=1)[0]
        chosen.append(remaining.pop(pick)[0])
    return chosen


def build_candidate_pool(seeds, limit=DEFAULT_RESULTS, max_distance=DEFAULT_MAX_DISTANCE,
                         pool_size=None):
    """Query every seed and merge their neighbours into one scored candidate list.

    Returns (pool, contributing_seeds, failures) where pool is [(track, score)] sorted
    best first. Kept separate from selection so the dialog can re-select repeatedly --
    honouring locked rows and variety -- without re-querying the server.
    """
    seeds = [track for track in (seeds or []) if track is not None]
    if not seeds:
        raise SonicUnavailable("Pick at least one seed track.")

    limit = _clamp_limit(limit)
    # Ask for more than we intend to show so variety and locks have room to work.
    ask = _clamp_limit(pool_size or limit * 3)

    scores, candidates = {}, {}
    contributing_seeds = 0
    failures = []

    for seed in seeds:
        try:
            neighbours = seed.sonicallySimilar(limit=ask, maxDistance=max_distance) or []
        except Exception as error:
            failures.append(f"{track_label(seed)}: {error}")
            continue
        if not neighbours:
            continue
        contributing_seeds += 1
        for rank, track in enumerate(neighbours):
            key = track_key(track)
            if not key:
                continue
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank)
            candidates.setdefault(key, track)

    pool = sorted(
        ((track, scores[key]) for key, track in candidates.items()),
        key=lambda item: item[1],
        reverse=True,
    )
    return pool, contributing_seeds, failures


def similar_to_tracks(seeds, limit=DEFAULT_RESULTS, max_distance=DEFAULT_MAX_DISTANCE,
                      include_seeds=True) -> SonicResult:
    """Blend the sonic neighbourhoods of several seed tracks into one playlist.

    Plex's /nearest endpoint answers for a single track, so a multi-seed mix has to be
    assembled client-side. Neighbours are merged with reciprocal rank fusion: each
    candidate scores sum(1 / (RRF_K + rank)) across the seeds it appears for. That
    rewards tracks sitting near *several* seeds over one sitting very near a single
    seed, which is what makes the result sound like the set rather than like whichever
    seed happened to be queried first.
    """
    seeds = [track for track in (seeds or []) if track is not None]
    if not seeds:
        raise SonicUnavailable("Pick at least one seed track.")
    if len(seeds) == 1:
        return similar_tracks(
            seeds[0], limit=limit, max_distance=max_distance, include_seed=include_seeds
        )

    limit = _clamp_limit(limit)
    seed_keys = {str(getattr(track, "ratingKey", "") or "") for track in seeds}

    scores = {}
    candidates = {}
    contributing_seeds = 0
    failures = []

    for seed in seeds:
        try:
            neighbours = seed.sonicallySimilar(limit=limit, maxDistance=max_distance) or []
        except Exception as error:
            failures.append(f"{track_label(seed)}: {error}")
            continue
        if not neighbours:
            continue
        contributing_seeds += 1
        for rank, track in enumerate(neighbours):
            key = str(getattr(track, "ratingKey", "") or "")
            if not key:
                continue
            if key in seed_keys and not include_seeds:
                continue
            scores[key] = scores.get(key, 0.0) + 1.0 / (RRF_K + rank)
            candidates.setdefault(key, track)

    if not candidates:
        detail = f" ({'; '.join(failures)})" if failures else ""
        raise SonicUnavailable(
            "Plex returned no sonically similar tracks for those seeds. The library may "
            f"not have been analysed yet, or the similarity is too tight.{detail}"
        )

    ordered = sorted(candidates.values(),
                     key=lambda t: scores[str(t.ratingKey)], reverse=True)[:limit]

    if include_seeds:
        ordered = _dedupe(list(seeds) + ordered)

    names = ", ".join(track_label(track) for track in seeds[:3])
    if len(seeds) > 3:
        names += f" and {len(seeds) - 3} more"

    note = ""
    if contributing_seeds < len(seeds):
        note = f" {len(seeds) - contributing_seeds} seed(s) returned nothing."

    return SonicResult(
        title=f"Like {len(seeds)} tracks",
        description=(
            f"{len(ordered)} track(s) blended from {contributing_seeds} seed(s): "
            f"{names} (max distance {max_distance:g}).{note}"
        ),
        tracks=ordered,
    )


def generate_mix(seeds, limit=DEFAULT_RESULTS, max_distance=DEFAULT_MAX_DISTANCE,
                 include_seeds=True, locked=(), variety=0.0,
                 collapse_same_song=True, rng=None) -> SonicResult:
    """Build a mix, keeping locked tracks and filling the rest around them.

    This is the generator behind the dialog's Generate button. Locked tracks are
    carried through unchanged and excluded from the candidate pool, so pressing
    Generate repeatedly reshuffles only the unlocked remainder.
    """
    seeds = [track for track in (seeds or []) if track is not None]
    locked = [track for track in (locked or []) if track is not None]
    if not seeds:
        raise SonicUnavailable("Pick at least one seed track.")

    limit = _clamp_limit(limit)
    pool, contributing_seeds, failures = build_candidate_pool(
        seeds, limit=limit, max_distance=max_distance
    )

    if not pool:
        detail = f" ({'; '.join(failures)})" if failures else ""
        raise SonicUnavailable(
            "Plex returned no sonically similar tracks for those seeds. The library may "
            f"not have been analysed yet, or the similarity is too tight.{detail}"
        )

    # Anything already pinned -- and optionally the seeds -- is fixed up front.
    fixed = list(locked)
    if include_seeds:
        fixed = _dedupe(fixed + list(seeds))

    taken_keys = {track_key(track) for track in fixed}
    taken_identities = {track_identity(track) for track in fixed} if collapse_same_song else set()

    available = []
    for track, score in pool:
        if track_key(track) in taken_keys:
            continue
        if collapse_same_song:
            identity = track_identity(track)
            if identity in taken_identities:
                continue
            taken_identities.add(identity)
        available.append((track, score))

    filler = select_from_pool(available, max(0, limit - len(fixed)), variety=variety, rng=rng)
    tracks = _dedupe(fixed + filler)

    names = ", ".join(track_label(track) for track in seeds[:3])
    if len(seeds) > 3:
        names += f" and {len(seeds) - 3} more"

    notes = []
    if contributing_seeds < len(seeds):
        notes.append(f"{len(seeds) - contributing_seeds} seed(s) returned nothing")
    if locked:
        notes.append(f"{len(locked)} locked")
    suffix = f" ({'; '.join(notes)})" if notes else ""

    title = (
        f"Like {track_label(seeds[0])}" if len(seeds) == 1
        else f"Like {len(seeds)} tracks"
    )
    return SonicResult(
        title=title,
        description=(
            f"{len(tracks)} track(s) from {contributing_seeds} seed(s): {names} "
            f"(max distance {max_distance:g}){suffix}."
        ),
        tracks=tracks,
    )


def sonic_adventure(library_section, start_track, end_track) -> SonicResult:
    """The gradual path Plex plots from one track to another."""
    if start_track is None or end_track is None:
        raise SonicUnavailable("Pick both a start and an end track.")
    if getattr(start_track, "ratingKey", None) == getattr(end_track, "ratingKey", None):
        raise SonicUnavailable("Pick two different tracks.")

    try:
        path = library_section.sonicAdventure(start_track, end_track) or []
    except Exception as error:
        raise SonicUnavailable(
            f"Plex could not build a sonic adventure between those tracks: {error}"
        ) from error

    if not path:
        raise SonicUnavailable(
            "Plex returned an empty path. Both tracks need to have been analysed."
        )

    return SonicResult(
        title=f"{track_label(start_track)} to {track_label(end_track)}",
        description=(
            f"{len(path)} step journey from {track_label(start_track)} "
            f"to {track_label(end_track)}."
        ),
        tracks=_dedupe(path),
    )


def _dedupe(tracks) -> list:
    """Preserve order, drop repeats by ratingKey."""
    seen = set()
    unique = []
    for track in tracks or []:
        key = str(getattr(track, "ratingKey", "") or "")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        unique.append(track)
    return unique


def create_playlist(plex_server, name, tracks, progress: Optional[Callable] = None):
    """Save a generated result as a real Plex playlist."""
    name = str(name or "").strip()
    if not name:
        raise ValueError("Give the playlist a name.")
    if not tracks:
        raise ValueError("There are no tracks to save.")
    if progress:
        progress(f"Creating '{name}' with {len(tracks)} track(s)...")
    return plex_server.createPlaylist(name, items=list(tracks))


def append_to_playlist(plex_server, name, tracks, skip_existing=True):
    """Append to an existing Plex playlist, returning how many were added."""
    name = str(name or "").strip()
    if not name:
        raise ValueError("Pick a playlist to add to.")
    if not tracks:
        raise ValueError("There are no tracks to add.")

    target = next(
        (p for p in plex_server.playlists() if p.title == name), None
    )
    if target is None:
        raise ValueError(f"No playlist named '{name}' on this server.")

    additions = list(tracks)
    if skip_existing:
        # Adding a track Plex already holds would silently duplicate the row.
        existing = {track_key(item) for item in target.items()}
        additions = [track for track in additions if track_key(track) not in existing]
    if not additions:
        return 0
    target.addItems(additions)
    return len(additions)
