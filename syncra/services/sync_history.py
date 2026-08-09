"""Sync run history with before/after snapshots.

'Clear on Sync' rewrites a playlist in place with no undo, which is the main reason
people do not trust automation with playlists they curated by hand. Recording the exact
track list on both sides of every run makes each sync inspectable after the fact and
reversible, and gives the Sync Manager a real diff to show before it writes anything.

Snapshots store Plex ratingKeys plus enough text to stay readable if a track is later
removed from the library.
"""

from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime
from typing import Any, Iterable, Optional

from syncra.services.library_data_db import LibraryDataDB, get_shared_db

STATUS_RUNNING = "running"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_REVERTED = "reverted"

MAX_RUNS_PER_PLAYLIST = 30


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def snapshot_tracks(tracks: Iterable[Any]) -> list[dict]:
    """Build a serializable snapshot from Plex track objects."""
    snapshot = []
    for track in tracks or []:
        rating_key = getattr(track, "ratingKey", None)
        if rating_key is None:
            continue
        snapshot.append(
            {
                "rating_key": str(rating_key),
                "title": str(getattr(track, "title", "") or ""),
                "artist": str(
                    getattr(track, "grandparentTitle", "")
                    or getattr(track, "originalTitle", "")
                    or ""
                ),
                "album": str(getattr(track, "parentTitle", "") or ""),
            }
        )
    return snapshot


def diff_snapshots(before: list[dict], after: list[dict]) -> dict:
    """Compare two snapshots by ratingKey, also reporting a pure reorder."""
    before = before or []
    after = after or []
    before_keys = {row.get("rating_key") for row in before}
    after_keys = {row.get("rating_key") for row in after}

    added = [row for row in after if row.get("rating_key") not in before_keys]
    removed = [row for row in before if row.get("rating_key") not in after_keys]
    reordered = (
        not added
        and not removed
        and [row.get("rating_key") for row in before] != [row.get("rating_key") for row in after]
    )
    return {
        "added": added,
        "removed": removed,
        "reordered": reordered,
        "before_count": len(before),
        "after_count": len(after),
    }


class SyncHistoryStore:
    def __init__(self, db: Optional[LibraryDataDB] = None):
        self._db = db or get_shared_db()

    # ------------------------------------------------------------------ writes

    def start_run(
        self,
        library_key: str,
        playlist_name: str,
        source: str = "",
        mode: str = "sync",
        before_snapshot: Optional[list[dict]] = None,
    ) -> str:
        """Open a run record and return its id."""
        run_id = secrets.token_hex(8)
        try:
            with self._db.connect() as conn:
                conn.execute(
                    """
                    INSERT INTO sync_runs (
                        run_id, library_key, playlist_name, source, mode, status,
                        started_at, before_snapshot
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        run_id,
                        str(library_key or ""),
                        str(playlist_name or ""),
                        str(source or ""),
                        str(mode or "sync"),
                        STATUS_RUNNING,
                        _now(),
                        json.dumps(before_snapshot or []),
                    ),
                )
        except Exception as error:
            logging.error(f"Could not open sync run record: {error}")
            return ""
        return run_id

    def finish_run(
        self,
        run_id: str,
        after_snapshot: Optional[list[dict]] = None,
        unmatched_count: int = 0,
        status: str = STATUS_SUCCESS,
        message: str = "",
        detail: Optional[dict] = None,
    ) -> None:
        """Close a run, computing added/removed counts from the two snapshots."""
        if not run_id:
            return
        after = after_snapshot or []
        try:
            with self._db.connect() as conn:
                row = conn.execute(
                    "SELECT before_snapshot FROM sync_runs WHERE run_id = ?", (run_id,)
                ).fetchone()
                try:
                    before = json.loads(row["before_snapshot"]) if row else []
                except (ValueError, TypeError):
                    before = []
                changes = diff_snapshots(before, after)
                conn.execute(
                    """
                    UPDATE sync_runs
                       SET status = ?, finished_at = ?, after_snapshot = ?,
                           added_count = ?, removed_count = ?, unmatched_count = ?,
                           message = ?, detail = ?
                     WHERE run_id = ?
                    """,
                    (
                        status,
                        _now(),
                        json.dumps(after),
                        len(changes["added"]),
                        len(changes["removed"]),
                        int(unmatched_count or 0),
                        str(message or ""),
                        json.dumps(detail or {}),
                        run_id,
                    ),
                )
        except Exception as error:
            logging.error(f"Could not close sync run record: {error}")
            return
        self._prune(run_id)

    def mark_reverted(self, run_id: str) -> None:
        try:
            with self._db.connect() as conn:
                conn.execute(
                    "UPDATE sync_runs SET status = ? WHERE run_id = ?", (STATUS_REVERTED, run_id)
                )
        except Exception as error:
            logging.error(f"Could not mark run as reverted: {error}")

    def _prune(self, run_id: str) -> None:
        """Keep history bounded per playlist."""
        try:
            with self._db.connect() as conn:
                row = conn.execute(
                    "SELECT library_key, playlist_name FROM sync_runs WHERE run_id = ?", (run_id,)
                ).fetchone()
                if not row:
                    return
                conn.execute(
                    """
                    DELETE FROM sync_runs
                     WHERE library_key = ? AND playlist_name = ?
                       AND run_id NOT IN (
                            SELECT run_id FROM sync_runs
                             WHERE library_key = ? AND playlist_name = ?
                             ORDER BY started_at DESC LIMIT ?
                       )
                    """,
                    (
                        row["library_key"],
                        row["playlist_name"],
                        row["library_key"],
                        row["playlist_name"],
                        MAX_RUNS_PER_PLAYLIST,
                    ),
                )
        except Exception as error:
            logging.debug(f"Could not prune sync history: {error}")

    # ------------------------------------------------------------------- reads

    def list_runs(self, library_key: str, playlist_name: str = "", limit: int = 100) -> list[dict]:
        query = "SELECT * FROM sync_runs WHERE library_key = ?"
        params: list[Any] = [str(library_key or "")]
        if playlist_name:
            query += " AND playlist_name = ?"
            params.append(playlist_name)
        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(int(limit))
        try:
            with self._db.connect() as conn:
                rows = [dict(row) for row in conn.execute(query, params).fetchall()]
        except Exception as error:
            logging.error(f"Could not list sync runs: {error}")
            return []
        return [self._decode(row) for row in rows]

    def get_run(self, run_id: str) -> Optional[dict]:
        try:
            with self._db.connect() as conn:
                row = conn.execute("SELECT * FROM sync_runs WHERE run_id = ?", (run_id,)).fetchone()
        except Exception as error:
            logging.error(f"Could not read sync run: {error}")
            return None
        return self._decode(dict(row)) if row else None

    @staticmethod
    def _decode(row: dict) -> dict:
        for field, fallback in (
            ("before_snapshot", []),
            ("after_snapshot", []),
            ("detail", {}),
        ):
            try:
                row[field] = json.loads(row.get(field) or json.dumps(fallback))
            except (ValueError, TypeError):
                row[field] = fallback
        row["changes"] = diff_snapshots(row.get("before_snapshot"), row.get("after_snapshot"))
        return row
