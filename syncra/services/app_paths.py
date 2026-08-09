"""Filesystem locations Syncra writes to."""

from __future__ import annotations

import os
from pathlib import Path


def get_app_data_dir() -> str:
    """Return the per-user directory Syncra stores databases and caches in.

    Mirrors the location used by the Smart Match cache so everything Syncra persists
    lives together, and so a frozen binary never tries to write next to the executable.
    """
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if local_app_data:
        base_dir = os.path.join(local_app_data, "Syncra")
    else:
        base_dir = os.path.join(Path.home(), ".syncra")
    os.makedirs(base_dir, exist_ok=True)
    return os.path.abspath(base_dir)


def get_library_data_db_path() -> str:
    """Path of the SQLite database holding match memory, missing tracks, sync history."""
    return os.path.join(get_app_data_dir(), "syncra_library_data.sqlite")
