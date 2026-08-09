"""On-disk cache for playlist cover art.

Measured against the user's server, a 300px transcoded playlist poster is ~29KB and
takes ~126ms to fetch. A 60-playlist grid is therefore ~7.5s of network time on every
visit to the Playlists page, which is far too slow to do repeatedly -- so covers are
written to disk once and re-read from there afterwards.

The cache is bounded by both file count and total bytes; when either ceiling is passed
the least recently *used* entries are dropped. Read access refreshes the mtime, so a
playlist you look at often survives pruning even if its art was fetched long ago.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from typing import Optional

from .app_paths import get_app_data_dir

MAX_ENTRIES = 600
MAX_BYTES = 96 * 1024 * 1024


def get_cover_cache_dir() -> str:
    path = os.path.join(get_app_data_dir(), "cover_cache")
    os.makedirs(path, exist_ok=True)
    return path


def cache_key(url: str) -> str:
    """Stable filename for a cover URL.

    The Plex token is a query parameter on the URL, and it changes when the user signs
    in again -- hashing the whole URL would then miss every previously cached cover, so
    the token is stripped before hashing.
    """
    cleaned = str(url or "")
    if "X-Plex-Token=" in cleaned:
        head, _, tail = cleaned.partition("X-Plex-Token=")
        _, _, rest = tail.partition("&")
        cleaned = head + rest
    return hashlib.sha1(cleaned.encode("utf-8", "replace")).hexdigest()


class CoverCache:
    """A tiny LRU file cache. Every operation is best-effort and never raises."""

    def __init__(self, directory: Optional[str] = None,
                 max_entries: int = MAX_ENTRIES, max_bytes: int = MAX_BYTES):
        self.directory = directory or get_cover_cache_dir()
        self.max_entries = max_entries
        self.max_bytes = max_bytes

    def _path_for(self, key: str) -> str:
        return os.path.join(self.directory, f"{key}.img")

    def get(self, key: str) -> Optional[bytes]:
        path = self._path_for(key)
        try:
            with open(path, "rb") as handle:
                data = handle.read()
        except OSError:
            return None
        if not data:
            return None
        try:
            # Mark it as recently used so pruning keeps what the user actually looks at.
            now = time.time()
            os.utime(path, (now, now))
        except OSError:
            pass
        return data

    def put(self, key: str, data: bytes) -> bool:
        if not data:
            return False
        path = self._path_for(key)
        # Write to a temp name first so a crash mid-write cannot leave a truncated
        # image that would then be served from cache forever.
        temp_path = f"{path}.{os.getpid()}.part"
        try:
            with open(temp_path, "wb") as handle:
                handle.write(data)
            os.replace(temp_path, path)
        except OSError as error:
            logging.debug(f"Could not cache cover {key}: {error}")
            try:
                os.remove(temp_path)
            except OSError:
                pass
            return False
        self.prune()
        return True

    def prune(self) -> int:
        """Drop least recently used entries until both ceilings are satisfied."""
        try:
            names = [n for n in os.listdir(self.directory) if n.endswith(".img")]
        except OSError:
            return 0

        entries = []
        total = 0
        for name in names:
            path = os.path.join(self.directory, name)
            try:
                stat = os.stat(path)
            except OSError:
                continue
            entries.append((stat.st_atime, stat.st_size, path))
            total += stat.st_size

        if len(entries) <= self.max_entries and total <= self.max_bytes:
            return 0

        entries.sort()  # oldest access first
        removed = 0
        for _, size, path in entries:
            if len(entries) - removed <= self.max_entries and total <= self.max_bytes:
                break
            try:
                os.remove(path)
            except OSError:
                continue
            total -= size
            removed += 1
        return removed

    def clear(self) -> int:
        try:
            names = os.listdir(self.directory)
        except OSError:
            return 0
        removed = 0
        for name in names:
            try:
                os.remove(os.path.join(self.directory, name))
                removed += 1
            except OSError:
                continue
        return removed

    def stats(self) -> dict:
        try:
            names = [n for n in os.listdir(self.directory) if n.endswith(".img")]
        except OSError:
            return {"entries": 0, "bytes": 0}
        total = 0
        for name in names:
            try:
                total += os.path.getsize(os.path.join(self.directory, name))
            except OSError:
                continue
        return {"entries": len(names), "bytes": total}
