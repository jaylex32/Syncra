"""Read public YouTube / YouTube Music playlists so they can be matched into Plex.

Only metadata is read -- titles, artists, albums -- and it is used to find tracks that
are already in the user's own library. Nothing is downloaded from YouTube.

Public playlists need no sign-in, which keeps this as low-friction as the Deezer and
Tidal importers.

The interesting problem is titles. Measured on a real 185-track playlist, **40% of
titles carry video furniture**: "(Official Music Video)", "(Official 4K Video)",
"[HD Remaster]", a trailing bare "HD". Feeding those to the matcher wrecks it.

Blanket bracket-stripping is not the answer, because the same playlist also contains
"(dub mix)", "(Rah Mix)", "(Edit)", "(Naive Melody)" and "(Are Made Of This)" -- all
part of the actual song. So a bracketed group is removed only when *every* meaningful
word inside it is production noise; anything else is left alone.
"""

from __future__ import annotations

import logging
import re
from typing import Optional
from urllib.parse import parse_qs, urlparse

# Words that only ever describe how a video was produced or encoded.
_NOISE_WORDS = {
    "official", "video", "videos", "audio", "music", "lyric", "lyrics", "lyricvideo",
    "hd", "hq", "sd", "uhd", "4k", "8k", "1080p", "720p", "60fps",
    "remaster", "remastered", "remasterizado", "mv", "m/v", "pv",
    "visualizer", "visualiser", "clip", "videoclip", "fullhd", "hdvideo",
    "explicit", "clean", "promo", "teaser", "trailer",
    "vevo", "youtube", "release", "reissue",
}

# Words that carry no meaning on their own inside a bracket.
_FILLER = {"the", "a", "an", "of", "in", "on", "and", "with", "version", "ver"}

_YEAR = re.compile(r"^(19|20)\d{2}$")
_BRACKETS = re.compile(r"[\(\[\{]([^\(\)\[\]\{\}]*)[\)\]\}]")
_TOKEN = re.compile(r"[0-9a-z]+", re.IGNORECASE)


_MEDIA_WORDS = {"video", "audio", "music", "hd", "4k", "mv", "visualizer", "clip"}


def _is_noise_group(inner: str) -> bool:
    """True when a bracketed group is only production furniture.

    "(Official Music Video)" and "(2025 Remaster)" are noise; "(dub mix)" and
    "(Naive Melody)" are not, because "mix", "dub" and "melody" are real words about
    the recording rather than about the upload.
    """
    tokens = [t.lower() for t in _TOKEN.findall(inner or "")]
    meaningful = [t for t in tokens if t not in _FILLER and not _YEAR.match(t)]
    if not meaningful:
        # Nothing but a year or filler -- "(1984)" is upload metadata, not a title.
        return bool(tokens)

    # "Official" plus a media word is an upload marker no matter what else is in the
    # group -- "(Official Video - Top Gun)" is furniture, not part of the song title.
    if "official" in meaningful and any(w in meaningful for w in _MEDIA_WORDS):
        return True

    return all(token in _NOISE_WORDS for token in meaningful)


def _strip_trailing_noise(text: str) -> str:
    """Remove dangling noise words left after a bracket was removed ("... HD")."""
    result = text
    while True:
        stripped = result.rstrip(" -–—_|·.~*'\"")
        match = re.search(r"(?:^|[\s~\-–—_|·])([0-9a-zA-Z/]+)$", stripped)
        if not match:
            return stripped
        word = match.group(1).lower()
        if word in _NOISE_WORDS:
            result = stripped[: match.start(1)]
            continue
        return stripped


def clean_track_title(title: str, artist: str = "") -> str:
    """Strip upload furniture from a YouTube title without touching the song name."""
    text = str(title or "").strip()
    if not text:
        return ""

    # Remove only the bracketed groups that are pure noise.
    def replace(match):
        return "" if _is_noise_group(match.group(1)) else match.group(0)

    previous = None
    while previous != text:
        previous = text
        text = _BRACKETS.sub(replace, text)

    text = _strip_trailing_noise(text)

    # "Prince - Purple Rain" where the artist is already known separately.
    artist_name = str(artist or "").strip()
    if artist_name:
        prefix = re.compile(
            r"^\s*" + re.escape(artist_name) + r"\s*[-–—:|]\s*", re.IGNORECASE
        )
        text = prefix.sub("", text, count=1)

    text = re.sub(r"\s{2,}", " ", text).strip(" -–—_|·")
    return text or str(title or "").strip()


_SEPARATORS = (" - ", " – ", " — ", " | ")


def _split_outside_brackets(text: str) -> tuple:
    """Split on the first " - " that is not inside brackets.

    "Take My Breath Away (Official Video - Top Gun)" must not be split on the dash
    inside the parentheses.
    """
    depth = 0
    for index, char in enumerate(text):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        elif depth == 0:
            for separator in _SEPARATORS:
                if text.startswith(separator, index):
                    left = text[:index].strip()
                    right = text[index + len(separator):].strip()
                    if left and right:
                        return left, right
    return "", text


def split_artist_from_title(title: str) -> tuple:
    """Best-effort "Artist - Title" split, for playlists with no artist field."""
    return _split_outside_brackets(str(title or "").strip())


def _normalise(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def resolve_artist_and_title(raw_title: str, artists_field: str = "") -> tuple:
    """Work out the real artist and title for one entry.

    On regular YouTube playlists the "artists" field is the *uploader channel*, not the
    performer: measured on a real playlist, "Prince - Purple Rain" was credited to
    "The Codfather" and "George Benson - Give Me The Night" to "RHINO". Trusting that
    field would make those tracks unmatchable.

    So when the title itself carries an "Artist - Title" prefix, the prefix wins --
    unless the channel agrees with it, in which case either is fine. YouTube Music
    playlists have no such prefix and keep their (correct) artist field.
    """
    cleaned = clean_track_title(raw_title, artists_field)
    channel = str(artists_field or "").strip()

    prefix, rest = _split_outside_brackets(cleaned)
    if not prefix:
        return channel, cleaned

    if channel and _normalise(channel) == _normalise(prefix):
        return channel, rest

    # A dash-prefixed title is a stronger signal than the channel name.
    return prefix, rest


def parse_playlist_id(url_or_id: str) -> Optional[str]:
    """Accept a YouTube/YouTube Music playlist URL, or a bare playlist id."""
    text = str(url_or_id or "").strip()
    if not text:
        return None

    if "://" not in text and "/" not in text:
        # Bare identifier: PL..., OLAK5uy_..., RDCLAK5uy_..., VL...
        return text[2:] if text.startswith("VL") else text

    try:
        parsed = urlparse(text)
    except Exception:
        return None

    query = parse_qs(parsed.query or "")
    for key in ("list", "playlist"):
        values = query.get(key)
        if values and values[0].strip():
            value = values[0].strip()
            return value[2:] if value.startswith("VL") else value

    # music.youtube.com/browse/VLPL...
    match = re.search(r"/(?:browse|playlist)/(VL)?([A-Za-z0-9_-]{10,})", parsed.path or "")
    if match:
        return match.group(2)
    return None


def is_youtube_url(url: str) -> bool:
    text = str(url or "").lower()
    return any(host in text for host in ("music.youtube.com", "youtube.com", "youtu.be"))


def build_client(client=None):
    """A YTMusic client. Unauthenticated is enough for public playlists."""
    if client is not None:
        return client
    try:
        from ytmusicapi import YTMusic
    except ImportError as error:  # pragma: no cover - depends on the environment
        raise RuntimeError(
            "YouTube import needs the 'ytmusicapi' package. "
            "Install it with: pip install ytmusicapi"
        ) from error
    return YTMusic()


def _artist_names(entry) -> str:
    artists = entry.get("artists") or []
    names = []
    for artist in artists:
        if isinstance(artist, dict):
            name = str(artist.get("name") or "").strip()
        else:
            name = str(artist or "").strip()
        # ytmusicapi puts durations and view counts in this list on some responses.
        if name and not re.fullmatch(r"[\d:,.]+( views)?", name, re.IGNORECASE):
            names.append(name)
    return ", ".join(names)


def _album_name(entry) -> str:
    album = entry.get("album")
    if isinstance(album, dict):
        return str(album.get("name") or "").strip()
    return str(album or "").strip()


def fetch_playlist(url_or_id: str, *, limit: Optional[int] = None, client=None) -> dict:
    """Fetch a public playlist and return its name, artwork and cleaned tracks.

    Returns a dict with `name`, `image_url` and `tracks`, where each track uses the
    same shape as the other importers: title/artist/album/parsed/path/source.
    """
    playlist_id = parse_playlist_id(url_or_id)
    if not playlist_id:
        raise ValueError(
            "That does not look like a YouTube playlist link. Use the 'Share' link "
            "for a playlist, which contains 'list=...'."
        )

    yt = build_client(client)
    try:
        raw = yt.get_playlist(playlist_id, limit=limit)
    except Exception as error:
        # Album-style playlists (OLAK5uy_...) and private playlists fail here, and the
        # underlying parse errors are not user-readable.
        raise RuntimeError(
            f"Could not read that YouTube playlist. It may be private, deleted, or an "
            f"album link rather than a playlist. ({type(error).__name__})"
        ) from error

    entries = raw.get("tracks") or []
    tracks = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        raw_title = str(entry.get("title") or "").strip()
        if not raw_title or raw_title.lower() == "song unavailable":
            continue

        artist, title = resolve_artist_and_title(raw_title, _artist_names(entry))
        if not title:
            continue

        parsed = f"{title} - {artist}" if artist else title
        tracks.append({
            "title": title,
            "artist": artist,
            "album": _album_name(entry),
            "parsed": parsed,
            "path": None,
            "source": "youtube",
        })

    thumbnails = raw.get("thumbnails") or []
    image_url = ""
    if thumbnails:
        try:
            image_url = str(thumbnails[-1].get("url") or "")
        except Exception:
            image_url = ""

    name = str(raw.get("title") or "").strip() or "YouTube Playlist"
    logging.info(f"Fetched {len(tracks)} track(s) from YouTube playlist '{name}'")
    return {"name": name, "image_url": image_url, "tracks": tracks}


def fetch_playlist_name(url_or_id: str, client=None) -> str:
    """Just the playlist's name, for the import preview."""
    return fetch_playlist(url_or_id, limit=1, client=client)["name"]
