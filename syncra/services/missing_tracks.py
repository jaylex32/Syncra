"""The accumulated record of tracks Syncra could not find in a Plex library.

Every import and every sync already computes this list and then discards it into a
truncated message box. Kept instead, it becomes the most useful thing the matcher
produces: a precise, deduplicated answer to "what is my library missing?", with the
playlists that wanted each track and how often it has been asked for.
"""

from __future__ import annotations

import csv
import json
import logging
from datetime import datetime
from typing import Any, Iterable, Mapping, Optional

from syncra.services.library_data_db import LibraryDataDB, get_shared_db
from syncra.services.track_identity import display_name, track_fingerprint

STATUS_MISSING = "missing"
STATUS_RESOLVED = "resolved"
STATUS_IGNORED = "ignored"

_MAX_SOURCES = 25


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class MissingTracksStore:
    def __init__(self, db: Optional[LibraryDataDB] = None):
        self._db = db or get_shared_db()

    # ------------------------------------------------------------------ writes

    def record_missing(
        self,
        library_key: str,
        tracks: Iterable[Mapping[str, Any]],
        source_label: str = "",
    ) -> int:
        """Record a batch of unmatched tracks. Returns how many rows were touched.

        Re-recording a track that is already known bumps its counter and adds the new
        source rather than creating a duplicate row. A track previously marked resolved
        flips back to missing, because going missing again is real information.
        """
        rows = []
        seen_fingerprints = set()
        for track in tracks or []:
            if not isinstance(track, Mapping):
                continue
            title = str(track.get("title", "") or "").strip()
            if not title:
                continue
            artist = str(track.get("artist", "") or "").strip()
            fingerprint = track_fingerprint(title, artist)
            if not fingerprint or fingerprint in seen_fingerprints:
                continue
            seen_fingerprints.add(fingerprint)
            rows.append((fingerprint, title, artist, str(track.get("album", "") or "").strip()))

        if not rows:
            return 0

        timestamp = _now()
        label = str(source_label or "").strip() or "Unknown source"
        touched = 0
        try:
            with self._db.connect() as conn:
                for fingerprint, title, artist, album in rows:
                    existing = conn.execute(
                        "SELECT sources, times_seen, status FROM missing_tracks"
                        " WHERE library_key = ? AND fingerprint = ?",
                        (str(library_key or ""), fingerprint),
                    ).fetchone()

                    if existing is None:
                        conn.execute(
                            """
                            INSERT INTO missing_tracks (
                                library_key, fingerprint, title, artist, album,
                                status, sources, first_seen, last_seen, times_seen
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                            """,
                            (
                                str(library_key or ""),
                                fingerprint,
                                title,
                                artist,
                                album,
                                STATUS_MISSING,
                                json.dumps([label]),
                                timestamp,
                                timestamp,
                            ),
                        )
                        touched += 1
                        continue

                    try:
                        sources = json.loads(existing["sources"]) or []
                    except (ValueError, TypeError):
                        sources = []
                    if label not in sources:
                        sources.append(label)
                        sources = sources[-_MAX_SOURCES:]

                    # An ignored track stays ignored; the user already made that call.
                    new_status = existing["status"]
                    if new_status != STATUS_IGNORED:
                        new_status = STATUS_MISSING

                    conn.execute(
                        """
                        UPDATE missing_tracks
                           SET sources = ?, last_seen = ?, times_seen = times_seen + 1,
                               status = ?, album = COALESCE(NULLIF(?, ''), album),
                               resolved_rating_key = NULL
                         WHERE library_key = ? AND fingerprint = ?
                        """,
                        (
                            json.dumps(sources),
                            timestamp,
                            new_status,
                            album,
                            str(library_key or ""),
                            fingerprint,
                        ),
                    )
                    touched += 1
        except Exception as error:
            logging.error(f"Could not record missing tracks: {error}")
            return 0
        return touched

    def mark_resolved(self, library_key: str, fingerprint: str, rating_key: Any = "") -> bool:
        return self._set_status(library_key, fingerprint, STATUS_RESOLVED, rating_key)

    def mark_ignored(self, library_key: str, fingerprint: str) -> bool:
        return self._set_status(library_key, fingerprint, STATUS_IGNORED, "")

    def mark_missing(self, library_key: str, fingerprint: str) -> bool:
        return self._set_status(library_key, fingerprint, STATUS_MISSING, "")

    def _set_status(self, library_key: str, fingerprint: str, status: str, rating_key: Any) -> bool:
        try:
            with self._db.connect() as conn:
                cursor = conn.execute(
                    "UPDATE missing_tracks SET status = ?, resolved_rating_key = ?"
                    " WHERE library_key = ? AND fingerprint = ?",
                    (status, str(rating_key or "") or None, str(library_key or ""), fingerprint),
                )
            return cursor.rowcount > 0
        except Exception as error:
            logging.error(f"Could not update missing track status: {error}")
            return False

    def delete(self, library_key: str, fingerprint: str) -> bool:
        try:
            with self._db.connect() as conn:
                cursor = conn.execute(
                    "DELETE FROM missing_tracks WHERE library_key = ? AND fingerprint = ?",
                    (str(library_key or ""), fingerprint),
                )
            return cursor.rowcount > 0
        except Exception as error:
            logging.error(f"Could not delete missing track: {error}")
            return False

    def clear(self, library_key: str, status: Optional[str] = None) -> int:
        query = "DELETE FROM missing_tracks WHERE library_key = ?"
        params: list[Any] = [str(library_key or "")]
        if status:
            query += " AND status = ?"
            params.append(status)
        try:
            with self._db.connect() as conn:
                cursor = conn.execute(query, params)
            return cursor.rowcount
        except Exception as error:
            logging.error(f"Could not clear missing tracks: {error}")
            return 0

    # ------------------------------------------------------------------- reads

    def list_tracks(
        self,
        library_key: str,
        status: Optional[str] = STATUS_MISSING,
        search: str = "",
    ) -> list[dict]:
        query = "SELECT * FROM missing_tracks WHERE library_key = ?"
        params: list[Any] = [str(library_key or "")]
        if status:
            query += " AND status = ?"
            params.append(status)
        search_text = str(search or "").strip()
        if search_text:
            query += " AND (title LIKE ? OR artist LIKE ? OR album LIKE ?)"
            like = f"%{search_text}%"
            params.extend([like, like, like])
        query += " ORDER BY times_seen DESC, last_seen DESC"
        try:
            with self._db.connect() as conn:
                rows = [dict(row) for row in conn.execute(query, params).fetchall()]
        except Exception as error:
            logging.error(f"Could not list missing tracks: {error}")
            return []
        for row in rows:
            try:
                row["sources"] = json.loads(row.get("sources") or "[]")
            except (ValueError, TypeError):
                row["sources"] = []
        return rows

    def counts(self, library_key: str) -> dict:
        result = {STATUS_MISSING: 0, STATUS_RESOLVED: 0, STATUS_IGNORED: 0}
        try:
            with self._db.connect() as conn:
                for row in conn.execute(
                    "SELECT status, COUNT(*) AS total FROM missing_tracks"
                    " WHERE library_key = ? GROUP BY status",
                    (str(library_key or ""),),
                ).fetchall():
                    result[row["status"]] = int(row["total"])
        except Exception as error:
            logging.error(f"Could not count missing tracks: {error}")
        return result

    # ----------------------------------------------------------------- exports

    def export_csv(self, library_key: str, path: str, status: Optional[str] = STATUS_MISSING) -> int:
        rows = self.list_tracks(library_key, status=status)
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                ["Artist", "Title", "Album", "Times Requested", "First Seen", "Last Seen", "Sources"]
            )
            for row in rows:
                writer.writerow(
                    [
                        row.get("artist", ""),
                        row.get("title", ""),
                        row.get("album", ""),
                        row.get("times_seen", 0),
                        row.get("first_seen", ""),
                        row.get("last_seen", ""),
                        "; ".join(row.get("sources", [])),
                    ]
                )
        return len(rows)

    def export_text(self, library_key: str, path: str, status: Optional[str] = STATUS_MISSING) -> int:
        rows = self.list_tracks(library_key, status=status)
        with open(path, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(display_name(row.get("title", ""), row.get("artist", "")) + "\n")
        return len(rows)
