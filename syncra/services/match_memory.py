"""Remembered track-matching decisions.

Every time the user resolves an ambiguous match by hand -- picking the right candidate
in the confirmation dialog, or declaring that a track simply is not in the library --
that answer is worth keeping. Without it, the next sync of the same playlist asks the
same question and the same wrong automatic match wins again.

Two kinds of decision are stored:

    match    the source track always resolves to this Plex ratingKey
    missing  the source track is known not to be in this library; stop guessing

Overrides are scoped per library, because the same source track legitimately resolves
to different ratingKeys on different servers.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Mapping, Optional

from syncra.services.library_data_db import LibraryDataDB, get_shared_db
from syncra.services.track_identity import track_fingerprint

KIND_MATCH = "match"
KIND_MISSING = "missing"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class MatchMemoryStore:
    def __init__(self, db: Optional[LibraryDataDB] = None):
        self._db = db or get_shared_db()

    # ------------------------------------------------------------------ writes

    def remember_match(
        self,
        library_key: str,
        source_track: Mapping[str, Any],
        rating_key: Any,
        target_title: str = "",
        target_artist: str = "",
        target_album: str = "",
    ) -> bool:
        """Record that this source track resolves to a specific Plex track."""
        fingerprint = track_fingerprint(
            (source_track or {}).get("title", ""), (source_track or {}).get("artist", "")
        )
        rating_key_text = str(rating_key or "").strip()
        if not fingerprint or not rating_key_text:
            return False
        return self._upsert(
            library_key,
            fingerprint,
            KIND_MATCH,
            rating_key_text,
            source_track,
            target_title,
            target_artist,
            target_album,
        )

    def remember_missing(self, library_key: str, source_track: Mapping[str, Any]) -> bool:
        """Record that this source track is known to be absent from the library."""
        fingerprint = track_fingerprint(
            (source_track or {}).get("title", ""), (source_track or {}).get("artist", "")
        )
        if not fingerprint:
            return False
        return self._upsert(
            library_key, fingerprint, KIND_MISSING, None, source_track, "", "", ""
        )

    def _upsert(
        self,
        library_key: str,
        fingerprint: str,
        kind: str,
        rating_key: Optional[str],
        source_track: Mapping[str, Any],
        target_title: str,
        target_artist: str,
        target_album: str,
    ) -> bool:
        source = source_track or {}
        timestamp = _now()
        try:
            with self._db.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO match_overrides (
                        library_key, fingerprint, kind, rating_key,
                        source_title, source_artist, source_album,
                        target_title, target_artist, target_album,
                        created_at, updated_at, hit_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    ON CONFLICT(library_key, fingerprint) DO UPDATE SET
                        kind = excluded.kind,
                        rating_key = excluded.rating_key,
                        target_title = excluded.target_title,
                        target_artist = excluded.target_artist,
                        target_album = excluded.target_album,
                        updated_at = excluded.updated_at
                    """,
                    (
                        str(library_key or ""),
                        fingerprint,
                        kind,
                        rating_key,
                        str(source.get("title", "") or ""),
                        str(source.get("artist", "") or ""),
                        str(source.get("album", "") or ""),
                        str(target_title or ""),
                        str(target_artist or ""),
                        str(target_album or ""),
                        timestamp,
                        timestamp,
                    ),
                )
            return True
        except Exception as error:
            logging.error(f"Could not save match override: {error}")
            return False

    # ------------------------------------------------------------------- reads

    def lookup(self, library_key: str, source_track: Mapping[str, Any]) -> Optional[dict]:
        """Return the stored decision for this source track, if any."""
        fingerprint = track_fingerprint(
            (source_track or {}).get("title", ""), (source_track or {}).get("artist", "")
        )
        if not fingerprint:
            return None
        try:
            with self._db.connect() as conn:
                row = conn.execute(
                    "SELECT * FROM match_overrides WHERE library_key = ? AND fingerprint = ?",
                    (str(library_key or ""), fingerprint),
                ).fetchone()
        except Exception as error:
            logging.error(f"Could not read match override: {error}")
            return None
        return dict(row) if row else None

    def record_hit(self, library_key: str, fingerprint: str) -> None:
        """Count a use of an override, so the UI can show which ones earn their keep."""
        if not fingerprint:
            return
        try:
            with self._db.connect() as conn:
                conn.execute(
                    "UPDATE match_overrides SET hit_count = hit_count + 1"
                    " WHERE library_key = ? AND fingerprint = ?",
                    (str(library_key or ""), fingerprint),
                )
        except Exception as error:
            logging.debug(f"Could not bump override hit count: {error}")

    def list_overrides(self, library_key: str, kind: Optional[str] = None) -> list[dict]:
        query = "SELECT * FROM match_overrides WHERE library_key = ?"
        params: list[Any] = [str(library_key or "")]
        if kind:
            query += " AND kind = ?"
            params.append(kind)
        query += " ORDER BY updated_at DESC"
        try:
            with self._db.connect() as conn:
                return [dict(row) for row in conn.execute(query, params).fetchall()]
        except Exception as error:
            logging.error(f"Could not list match overrides: {error}")
            return []

    def count(self, library_key: str) -> int:
        try:
            with self._db.connect() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) AS total FROM match_overrides WHERE library_key = ?",
                    (str(library_key or ""),),
                ).fetchone()
            return int(row["total"]) if row else 0
        except Exception:
            return 0

    # ---------------------------------------------------------------- deletion

    def forget(self, library_key: str, fingerprint: str) -> bool:
        try:
            with self._db.connect() as conn:
                cursor = conn.execute(
                    "DELETE FROM match_overrides WHERE library_key = ? AND fingerprint = ?",
                    (str(library_key or ""), fingerprint),
                )
            return cursor.rowcount > 0
        except Exception as error:
            logging.error(f"Could not delete match override: {error}")
            return False

    def clear(self, library_key: str) -> int:
        try:
            with self._db.connect() as conn:
                cursor = conn.execute(
                    "DELETE FROM match_overrides WHERE library_key = ?",
                    (str(library_key or ""),),
                )
            return cursor.rowcount
        except Exception as error:
            logging.error(f"Could not clear match overrides: {error}")
            return 0
