"""Export a playlist as real audio files, not just an .m3u of server paths.

The existing export writes a playlist file full of paths like
``\\\\Desktop-u78huhb\\f\\Music Masters\\...`` -- meaningful only to the Plex server.
Put that on a USB stick and nothing plays.

This copies the audio itself into a folder, alongside a playlist whose entries are
relative, so the result works in a car, on a phone, or on any player pointed at the
folder. Two things make it practical:

* **The server transcodes.** A FLAC library is roughly 32MB a track, so a 24-track
  playlist is 771MB; asking Plex for MP3 through
  ``/music/:/transcode/universal/start.mp3`` brings that down by an order of magnitude
  and needs no ffmpeg installed locally (measured: it answers audio/mpeg directly).
* **Names are sanitised for FAT32**, because USB sticks and SD cards are usually not
  NTFS and will reject the characters Plex is perfectly happy with.

Network and filesystem access go through injectable callables so the planning and
naming logic can be tested without a server.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

FORMAT_ORIGINAL = "original"
FORMAT_MP3_320 = "mp3_320"
FORMAT_MP3_192 = "mp3_192"
FORMAT_MP3_128 = "mp3_128"

FORMATS = {
    FORMAT_ORIGINAL: ("Original files (no conversion)", 0),
    FORMAT_MP3_320: ("MP3 320 kbps", 320),
    FORMAT_MP3_192: ("MP3 192 kbps", 192),
    FORMAT_MP3_128: ("MP3 128 kbps", 128),
}

STRUCTURE_FLAT = "flat"
STRUCTURE_ARTIST = "artist"
STRUCTURE_ALBUM = "album"
STRUCTURE_ARTIST_ALBUM = "artist_album"
STRUCTURE_PLAYLIST_FLAT = "playlist_flat"
STRUCTURE_PLAYLIST_ARTIST = "playlist_artist"
STRUCTURE_PLAYLIST_ARTIST_ALBUM = "playlist_artist_album"

# label -> what the resulting path looks like, so the dialog can show an example.
STRUCTURES = (
    (STRUCTURE_FLAT, "One flat folder", "001 - Artist - Title.mp3"),
    (STRUCTURE_ARTIST, "Artist", "Artist/001 - Title.mp3"),
    (STRUCTURE_ALBUM, "Album", "Album/01 - Title.mp3"),
    (STRUCTURE_ARTIST_ALBUM, "Artist / Album", "Artist/Album/01 - Title.mp3"),
    (STRUCTURE_PLAYLIST_FLAT, "Playlist", "Playlist/001 - Artist - Title.mp3"),
    (STRUCTURE_PLAYLIST_ARTIST, "Playlist / Artist", "Playlist/Artist/001 - Title.mp3"),
    (STRUCTURE_PLAYLIST_ARTIST_ALBUM, "Playlist / Artist / Album",
     "Playlist/Artist/Album/01 - Title.mp3"),
)

# Characters Windows and FAT32 refuse. Plex track titles contain plenty of them
# ("AC/DC", 'Song: Part 2', "What?").
_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
MAX_COMPONENT = 100


def sanitize_component(name: str, fallback: str = "Unknown") -> str:
    """Make one path component safe for FAT32/exFAT as well as NTFS."""
    cleaned = _ILLEGAL.sub("_", str(name or ""))
    cleaned = cleaned.replace("\t", " ").strip()
    # Trailing dots and spaces are silently dropped by Windows, which turns two
    # different track titles into the same filename.
    cleaned = cleaned.rstrip(". ")
    if len(cleaned) > MAX_COMPONENT:
        cleaned = cleaned[:MAX_COMPONENT].rstrip(". ")
    if cleaned.upper().split(".")[0] in _RESERVED:
        cleaned = f"_{cleaned}"
    return cleaned or fallback


def track_extension(track, audio_format: str) -> str:
    if audio_format != FORMAT_ORIGINAL:
        return ".mp3"
    try:
        part = track.media[0].parts[0]
        ext = os.path.splitext(str(getattr(part, "file", "") or ""))[1]
        return ext or ".mp3"
    except Exception:
        return ".mp3"


def track_size_estimate(track, audio_format: str) -> int:
    """Bytes this track will occupy once exported."""
    if audio_format == FORMAT_ORIGINAL:
        try:
            return int(getattr(track.media[0].parts[0], "size", 0) or 0)
        except Exception:
            return 0
    bitrate = FORMATS.get(audio_format, ("", 0))[1]
    duration_ms = int(getattr(track, "duration", 0) or 0)
    # kbps -> bytes: bitrate * 1000 / 8 per second.
    return int((duration_ms / 1000.0) * bitrate * 125)


@dataclass
class ExportItem:
    track: object
    relative_path: str
    estimated_bytes: int = 0
    title: str = ""
    artist: str = ""
    duration_ms: int = 0


@dataclass
class ExportReport:
    exported: list = field(default_factory=list)
    skipped: list = field(default_factory=list)
    failed: list = field(default_factory=list)
    bytes_written: int = 0
    cancelled: bool = False
    playlist_file: str = ""

    @property
    def total(self) -> int:
        return len(self.exported) + len(self.skipped) + len(self.failed)


def _track_fields(track):
    title = str(getattr(track, "title", "") or "Unknown Title")
    artist = str(
        getattr(track, "grandparentTitle", "")
        or getattr(track, "originalTitle", "")
        or "Unknown Artist"
    )
    album = str(getattr(track, "parentTitle", "") or "Unknown Album")
    try:
        index = int(getattr(track, "index", 0) or 0)
    except (TypeError, ValueError):
        index = 0
    return title, artist, album, index


def _folder_parts(structure: str, playlist_name: str, artist: str, album: str) -> list:
    """Subfolders for one track under the chosen layout."""
    parts = []
    if structure.startswith("playlist"):
        parts.append(sanitize_component(playlist_name, "Playlist"))
    if "artist" in structure:
        parts.append(sanitize_component(artist))
    if "album" in structure:
        parts.append(sanitize_component(album))
    return parts


def plan_export(tracks: Sequence, *, audio_format: str = FORMAT_ORIGINAL,
                structure: str = STRUCTURE_FLAT, playlist_name: str = "Playlist") -> list:
    """Work out the destination path for every track before writing anything.

    Collisions are resolved here rather than at write time, so two tracks with the
    same name in a flat folder do not silently overwrite one another.
    """
    items = []
    used = set()

    for position, track in enumerate(tracks, start=1):
        title, artist, album, index = _track_fields(track)
        extension = track_extension(track, audio_format)
        folders = _folder_parts(structure, playlist_name, artist, album)

        if "album" in structure:
            # Inside an album folder the track's own number is the meaningful one.
            stem = f"{(index or position):02d} - {sanitize_component(title)}"
        elif "artist" in structure:
            stem = f"{position:03d} - {sanitize_component(title)}"
        else:
            stem = (f"{position:03d} - {sanitize_component(artist)}"
                    f" - {sanitize_component(title)}")

        stem = sanitize_component(stem)
        relative = os.path.join(*folders, stem) if folders else stem

        candidate = relative + extension
        counter = 2
        while candidate.lower() in used:
            candidate = f"{relative} ({counter}){extension}"
            counter += 1
        used.add(candidate.lower())

        items.append(
            ExportItem(
                track=track,
                relative_path=candidate,
                estimated_bytes=track_size_estimate(track, audio_format),
                title=title,
                artist=artist,
                duration_ms=int(getattr(track, "duration", 0) or 0),
            )
        )
    return items


def estimate_total_bytes(tracks, audio_format=FORMAT_ORIGINAL) -> int:
    return sum(track_size_estimate(t, audio_format) for t in tracks)


def format_bytes(size) -> str:
    value = float(size or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{value:.0f} {unit}" if unit in ("B", "KB") else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


# Cover art embedded in a transcoded file. 600px keeps a 24-track export a few
# hundred KB heavier in total while still looking right on a car head unit.
TAG_COVER_SIZE = 600

# First four bytes of a PNG file, used to pick the APIC mime type.
PNG_MAGIC = bytes([137, 80, 78, 71])


def album_cover_url(server, track, size: int = TAG_COVER_SIZE) -> str:
    """Transcoded album art for embedding, or "" when the track has none."""
    key = (
        str(getattr(track, "parentThumb", "") or "")
        or str(getattr(track, "thumb", "") or "")
        or str(getattr(track, "grandparentThumb", "") or "")
    )
    if not key:
        return ""
    if key.startswith("http://") or key.startswith("https://"):
        return key
    import urllib.parse

    encoded = urllib.parse.quote(key, safe="")
    path = (
        f"/photo/:/transcode?width={size}&height={size}"
        f"&minSize=1&upscale=1&url={encoded}"
    )
    return server.url(path, includeToken=True)


def fetch_cover_bytes(server, track, cache: Optional[dict] = None) -> bytes:
    """Album art bytes, fetched once per album.

    A playlist usually draws on many albums but repeats each one; without the cache a
    12-track album would download the same cover twelve times.
    """
    url = album_cover_url(server, track)
    if not url:
        return b""
    cache_id = f"cover:{url}"
    if cache is not None and cache_id in cache:
        return cache[cache_id]

    data = b""
    try:
        import requests

        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.content or b""
    except Exception as error:
        logging.debug(f"Could not fetch cover art: {error}")
        data = b""

    if cache is not None:
        cache[cache_id] = data
    return data


def fetch_album_year(server, track, cache: Optional[dict] = None):
    """Release year for a track's album, looked up once per album.

    Tracks carry no year of their own, so this is the only way to tag one. It costs a
    request per album (36ms measured), which is why the result is cached.
    """
    rating_key = getattr(track, "parentRatingKey", None)
    if not rating_key or server is None:
        return None

    cache_id = f"year:{rating_key}"
    if cache is not None and cache_id in cache:
        return cache[cache_id]

    year = None
    try:
        album = server.fetchItem(int(rating_key))
        year = getattr(album, "year", None)
    except Exception as error:
        logging.debug(f"Could not read album year: {error}")

    if cache is not None:
        cache[cache_id] = year
    return year


def write_mp3_tags(path: str, track, cover_bytes: bytes = b"", year=None) -> bool:
    """Write ID3 tags onto a transcoded file.

    Plex's transcoder returns a bare stream -- the only frame it sets is TSSE naming
    the encoder -- so an exported MP3 arrives with no title, artist, album or artwork.
    Everything written here is already on the track object, so no extra requests are
    needed beyond the album art.

    Tags are saved as ID3v2.3, which is what older car head units and cheap players
    understand; v2.4 is frequently ignored by them.
    """
    try:
        from mutagen.id3 import (
            APIC, ID3, ID3NoHeaderError, TALB, TCON, TDRC, TIT2, TPE1, TPE2, TPOS, TRCK,
        )
    except ImportError as error:  # pragma: no cover - mutagen is a hard dependency
        logging.warning(f"Cannot tag export, mutagen unavailable: {error}")
        return False

    try:
        try:
            tags = ID3(path)
        except ID3NoHeaderError:
            tags = ID3()

        title, artist, album, index = _track_fields(track)
        tags.setall("TIT2", [TIT2(encoding=3, text=title)])
        tags.setall("TPE1", [TPE1(encoding=3, text=artist)])
        tags.setall("TALB", [TALB(encoding=3, text=album)])
        tags.setall("TPE2", [TPE2(encoding=3, text=artist)])

        if index:
            tags.setall("TRCK", [TRCK(encoding=3, text=str(index))])
        disc = getattr(track, "parentIndex", None)
        if disc:
            tags.setall("TPOS", [TPOS(encoding=3, text=str(disc))])

        genres = []
        for genre in (getattr(track, "genres", None) or []):
            name = str(getattr(genre, "tag", "") or genre or "").strip()
            if name:
                genres.append(name)
        if genres:
            tags.setall("TCON", [TCON(encoding=3, text="; ".join(genres[:3]))])

        year = year or getattr(track, "year", None) or getattr(track, "parentYear", None)
        if year:
            tags.setall("TDRC", [TDRC(encoding=3, text=str(year))])

        if cover_bytes:
            mime = "image/png" if cover_bytes[:4] == PNG_MAGIC else "image/jpeg"
            tags.setall("APIC", [APIC(encoding=3, mime=mime, type=3,
                                      desc="Cover", data=cover_bytes)])

        tags.save(path, v2_version=3)
        return True
    except Exception as error:
        logging.warning(f"Could not tag {os.path.basename(path)}: {error}")
        return False


def transcode_url(server, track, audio_format: str) -> tuple:
    """URL and params for a server-side MP3 of this track.

    Uses Plex's own transcoder, so no local ffmpeg is required.
    """
    bitrate = FORMATS.get(audio_format, ("", 0))[1]
    params = {
        "path": f"/library/metadata/{track.ratingKey}",
        "mediaIndex": 0,
        "partIndex": 0,
        "protocol": "http",
        "audioCodec": "mp3",
        "maxAudioBitrate": bitrate,
        "musicBitrate": bitrate,
        "directPlay": 0,
        "directStream": 0,
        "X-Plex-Token": server._token,
        "X-Plex-Client-Identifier": "syncra-export",
        "X-Plex-Product": "Syncra",
        "X-Plex-Platform": "Windows",
        "X-Plex-Device": "PC",
    }
    return f"{server._baseurl}/music/:/transcode/universal/start.mp3", params


def original_url(server, track) -> str:
    part = track.media[0].parts[0]
    return server.url(part.key, includeToken=True)


def default_fetch(server, track, audio_format, destination, chunk_size=262144,
                  should_cancel=None, cover_cache=None):
    """Stream one track to disk, transcoded by the server when asked for MP3.

    A transcoded file is tagged afterwards: Plex hands back a bare stream, so without
    this step every exported MP3 would have no title, artist, album or artwork.
    """
    import requests

    if audio_format == FORMAT_ORIGINAL:
        url, params = original_url(server, track), None
    else:
        url, params = transcode_url(server, track, audio_format)

    partial = destination + ".part"
    written = 0
    with requests.get(url, params=params, stream=True, timeout=60) as response:
        response.raise_for_status()
        with open(partial, "wb") as handle:
            for chunk in response.iter_content(chunk_size):
                if should_cancel and should_cancel():
                    handle.close()
                    try:
                        os.remove(partial)
                    except OSError:
                        pass
                    return 0
                if chunk:
                    handle.write(chunk)
                    written += len(chunk)
    os.replace(partial, destination)

    if audio_format != FORMAT_ORIGINAL:
        # Originals keep the tags and artwork already in the source file; only the
        # transcoded stream arrives empty.
        write_mp3_tags(
            destination,
            track,
            fetch_cover_bytes(server, track, cover_cache),
            fetch_album_year(server, track, cover_cache),
        )
        try:
            written = os.path.getsize(destination)
        except OSError:
            pass

    return written


def write_m3u(path: str, items: Sequence, encoding="utf-8") -> str:
    """Write a playlist whose entries are relative to its own folder."""
    with open(path, "w", encoding=encoding, newline="\n") as handle:
        handle.write("#EXTM3U\n")
        for item in items:
            seconds = max(0, int(item.duration_ms or 0) // 1000)
            handle.write(f"#EXTINF:{seconds},{item.artist} - {item.title}\n")
            handle.write(item.relative_path.replace("\\", "/") + "\n")
    return path


def export_playlist(
    tracks: Sequence,
    destination: str,
    *,
    playlist_name: str,
    server=None,
    audio_format: str = FORMAT_ORIGINAL,
    structure: str = STRUCTURE_FLAT,
    max_bytes: Optional[int] = None,
    overwrite: bool = False,
    fetch: Optional[Callable] = None,
    progress: Optional[Callable] = None,
    should_cancel: Optional[Callable] = None,
) -> ExportReport:
    """Copy every track into `destination` and write a playlist beside them."""
    report = ExportReport()
    items = plan_export(tracks, audio_format=audio_format, structure=structure,
                        playlist_name=playlist_name)
    os.makedirs(destination, exist_ok=True)

    # One album's artwork is fetched once and reused for every track from it.
    cover_cache = {}
    fetcher = fetch or (
        lambda track, fmt, dest: default_fetch(
            server, track, fmt, dest, should_cancel=should_cancel,
            cover_cache=cover_cache,
        )
    )

    written_items = []
    for position, item in enumerate(items, start=1):
        if should_cancel and should_cancel():
            report.cancelled = True
            break

        if max_bytes is not None and report.bytes_written + item.estimated_bytes > max_bytes:
            # Keep going: a later, smaller track may still fit inside the budget.
            report.skipped.append((item, "would exceed the size limit"))
            continue

        target = os.path.join(destination, item.relative_path)
        if progress:
            progress(position, len(items), item)

        try:
            if os.path.exists(target) and not overwrite:
                report.skipped.append((item, "already exists"))
                written_items.append(item)
                continue

            os.makedirs(os.path.dirname(target) or destination, exist_ok=True)
            written = fetcher(item.track, audio_format, target)
            if not written and not os.path.exists(target):
                report.cancelled = report.cancelled or bool(
                    should_cancel and should_cancel()
                )
                if report.cancelled:
                    break
                raise OSError("no data written")

            report.bytes_written += written or 0
            report.exported.append(item)
            written_items.append(item)
        except Exception as error:
            logging.warning(f"Export failed for {item.title}: {error}")
            report.failed.append((item, str(error)))

    if written_items:
        playlist_path = os.path.join(
            destination, sanitize_component(playlist_name, "Playlist") + ".m3u"
        )
        try:
            report.playlist_file = write_m3u(playlist_path, written_items)
        except Exception as error:
            logging.warning(f"Could not write playlist file: {error}")

    return report
