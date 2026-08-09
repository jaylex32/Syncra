"""Shared SQLite connection and schema for Syncra's per-library data.

Match memory, the missing-track list, and sync history all key off the same
(library_key, fingerprint) pair, so they share one database file and one schema
version. The store is deliberately forgiving: a corrupt or unreadable database is
recreated rather than allowed to block app startup, which is the failure mode that
previously took the Smart Match cache down with it.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
from contextlib import contextmanager

from syncra.services.app_paths import get_library_data_db_path

SCHEMA_VERSION = 1

_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS match_overrides (
        library_key     TEXT NOT NULL,
        fingerprint     TEXT NOT NULL,
        kind            TEXT NOT NULL DEFAULT 'match',
        rating_key      TEXT,
        source_title    TEXT,
        source_artist   TEXT,
        source_album    TEXT,
        target_title    TEXT,
        target_artist   TEXT,
        target_album    TEXT,
        created_at      TEXT NOT NULL,
        updated_at      TEXT NOT NULL,
        hit_count       INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (library_key, fingerprint)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS missing_tracks (
        library_key     TEXT NOT NULL,
        fingerprint     TEXT NOT NULL,
        title           TEXT NOT NULL,
        artist          TEXT,
        album           TEXT,
        status          TEXT NOT NULL DEFAULT 'missing',
        sources         TEXT NOT NULL DEFAULT '[]',
        first_seen      TEXT NOT NULL,
        last_seen       TEXT NOT NULL,
        times_seen      INTEGER NOT NULL DEFAULT 1,
        resolved_rating_key TEXT,
        note            TEXT,
        PRIMARY KEY (library_key, fingerprint)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_missing_status
        ON missing_tracks (library_key, status)
    """,
    """
    CREATE TABLE IF NOT EXISTS sync_runs (
        run_id          TEXT PRIMARY KEY,
        library_key     TEXT NOT NULL,
        playlist_name   TEXT NOT NULL,
        source          TEXT,
        mode            TEXT NOT NULL DEFAULT 'sync',
        status          TEXT NOT NULL DEFAULT 'running',
        started_at      TEXT NOT NULL,
        finished_at     TEXT,
        added_count     INTEGER NOT NULL DEFAULT 0,
        removed_count   INTEGER NOT NULL DEFAULT 0,
        unmatched_count INTEGER NOT NULL DEFAULT 0,
        before_snapshot TEXT NOT NULL DEFAULT '[]',
        after_snapshot  TEXT NOT NULL DEFAULT '[]',
        detail          TEXT NOT NULL DEFAULT '{}',
        message         TEXT
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_sync_runs_playlist
        ON sync_runs (library_key, playlist_name, started_at DESC)
    """,
)

_CONNECTION_LOCK = threading.Lock()


class LibraryDataDB:
    """Thin serialized wrapper around the shared SQLite file."""

    def __init__(self, db_path: str | None = None):
        self.db_path = os.path.abspath(db_path or get_library_data_db_path())
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.RLock()
        self._ensure_schema()

    def _raw_connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        try:
            conn.row_factory = sqlite3.Row
            # A damaged file fails here rather than at connect() time, so the handle has
            # to be closed before the error propagates or the file stays locked and
            # cannot be replaced.
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
        except Exception:
            conn.close()
            raise
        return conn

    def _ensure_schema(self) -> None:
        try:
            self._apply_schema()
        except sqlite3.DatabaseError as error:
            logging.warning(f"Syncra library database unusable ({error}); recreating it.")
            self._recreate()
            self._apply_schema()

    def _apply_schema(self) -> None:
        # Note: `with sqlite3.connect(...)` commits but does not close, so the connection
        # is closed explicitly. On Windows a leaked handle keeps the file locked, which
        # breaks both _recreate() and any attempt to delete the data directory.
        with self._lock:
            conn = self._raw_connect()
            try:
                for statement in _SCHEMA_STATEMENTS:
                    conn.execute(statement)
                conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
                conn.commit()
            finally:
                conn.close()

    def _recreate(self) -> None:
        for suffix in ("", "-wal", "-shm"):
            candidate = f"{self.db_path}{suffix}"
            try:
                if os.path.exists(candidate):
                    os.remove(candidate)
            except OSError as error:
                logging.error(f"Could not remove damaged database file {candidate}: {error}")

    @contextmanager
    def connect(self):
        """Yield a connection under the instance lock, committing on clean exit."""
        with self._lock:
            conn = self._raw_connect()
            try:
                yield conn
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()


_SHARED_DB: LibraryDataDB | None = None


def get_shared_db() -> LibraryDataDB:
    """Return the process-wide database handle, creating it on first use."""
    global _SHARED_DB
    with _CONNECTION_LOCK:
        if _SHARED_DB is None:
            _SHARED_DB = LibraryDataDB()
        return _SHARED_DB


def reset_shared_db(db: LibraryDataDB | None = None) -> None:
    """Replace the shared handle. Used by tests and by 'change data location'."""
    global _SHARED_DB
    with _CONNECTION_LOCK:
        _SHARED_DB = db
