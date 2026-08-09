"""Stable identity keys for source tracks.

A fingerprint has to survive the trip from a Spotify payload to an M3U line to a sync
re-run, so it is deliberately built from normalized title + artist only. Album is
excluded: the same recording routinely arrives tagged with a single, an album, and a
compilation, and treating those as three different tracks would defeat both match memory
and missing-track deduplication.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any, Mapping

_FEATURE_PATTERN = re.compile(
    r"\s*(?:\(|\[)?\s*(?:feat|ft|featuring|with)\.?\s[^)\]]*(?:\)|\])?\s*",
    re.IGNORECASE,
)
_BRACKET_NOISE_PATTERN = re.compile(
    r"[\(\[]\s*(?:album|lp|radio|single|club|extended|remaster(?:ed)?|"
    r"re[\s-]?recorded|mono|stereo|bonus track|digital remaster|"
    r"\d{4}\s+remaster(?:ed)?)[^)\]]*[\)\]]",
    re.IGNORECASE,
)


def normalize_text(value: Any) -> str:
    """Lowercase, strip accents, and collapse to alphanumeric words."""
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    text = text.lower().replace("&", " and ").replace("_", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_title(value: Any) -> str:
    """Normalize a track title, dropping edition noise and featured-artist suffixes."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    stripped = _BRACKET_NOISE_PATTERN.sub(" ", raw)
    stripped = _FEATURE_PATTERN.sub(" ", stripped)
    normalized = normalize_text(stripped)
    # Never let aggressive stripping erase the title entirely.
    return normalized or normalize_text(raw)


def normalize_artist(value: Any) -> str:
    """Normalize an artist name, keeping only the primary credited artist."""
    raw = str(value or "").strip()
    if not raw:
        return ""
    primary = re.split(r"\s*(?:,|;|/|\bfeat\b|\bft\b|\bwith\b|&|\band\b)\s*", raw, maxsplit=1, flags=re.IGNORECASE)[0]
    normalized = normalize_text(primary)
    return normalized or normalize_text(raw)


def track_fingerprint(title: Any, artist: Any = "") -> str:
    """Return a stable 16-hex-char identity for a title/artist pair.

    Returns an empty string when there is no usable title, so callers can skip rather
    than store junk rows keyed on nothing.
    """
    norm_title = normalize_title(title)
    if not norm_title:
        return ""
    norm_artist = normalize_artist(artist)
    payload = f"{norm_title}\x1f{norm_artist}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def fingerprint_source_track(track: Mapping[str, Any]) -> str:
    """Fingerprint one of the app's normalized source-track dicts."""
    if not isinstance(track, Mapping):
        return ""
    return track_fingerprint(track.get("title", ""), track.get("artist", ""))


def display_name(title: Any, artist: Any = "") -> str:
    """Human-readable 'Artist - Title', tolerating a missing artist."""
    title_text = str(title or "").strip() or "Unknown Title"
    artist_text = str(artist or "").strip()
    return f"{artist_text} - {title_text}" if artist_text else title_text
