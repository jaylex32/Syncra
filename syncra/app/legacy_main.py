import sys
import json
import os
import html
import base64
import hashlib
import hmac
import struct
import logging
import plistlib
import pyotp
import tempfile
import shutil
import zipfile
import platform
import signal
import socket
import sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler

__version__ = "2.20.3"
from typing import Dict, Any, Optional, List, Tuple
from plexapi.myplex import MyPlexAccount
from plexapi.server import PlexServer
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QLineEdit, QPushButton, QFileDialog, QListWidget,
                             QCheckBox, QListWidgetItem, QProgressBar, QTextEdit,
                             QMessageBox, QComboBox, QStackedWidget, QGroupBox, QDialog,
                             QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
                             QSplitter, QTabWidget, QSpinBox, QDateTimeEdit, QSlider, QDoubleSpinBox,
                             QFormLayout, QGridLayout, QScrollArea, QFrame, QInputDialog, QMenu, QProgressDialog,
                             QButtonGroup, QRadioButton, QStyle)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, QDateTime, QSettings, QSize
from PyQt6.QtGui import QIcon, QPixmap, QFont, QColor, QPalette, QDrag
#from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtSvgWidgets import QSvgWidget
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import math
import random
import webbrowser
import urllib.parse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import deezer
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.cache_handler import CacheFileHandler
import re
from fuzzywuzzy import fuzz
from datetime import datetime, timedelta
from time import time_ns
import threading
from email.utils import parsedate_to_datetime
import secrets
import unicodedata
from pathlib import Path

from syncra.config.defaults import APP_CONFIG_DEFAULTS, CACHE_DEFAULTS, SYNC_CONFIG_DEFAULTS, deep_merge
from syncra.qt_compat import Qt, patch_qt_legacy_apis
from syncra.services.logging_utils import log_event, new_flow_id, timed
from syncra.services.listenbrainz_client import ListenBrainzClient
from syncra.services.metadata_fixer_service import MetadataFixerService
from syncra.services.musicbrainz_provider import MusicBrainzProvider
from syncra.models.metadata import TrackIdentity
from syncra.theme.styles import MAIN_STYLESHEET
from syncra.ui.dialogs.metadata_fixer_dialog import MetadataFixerDialog

CONFIG_FILE = "app_config.json"
_SYNCRA_LIBRARY_MATCH_SESSION_CACHE = {}
_SYNCRA_LIBRARY_MATCH_SESSION_CACHE_LOCK = threading.Lock()
_SYNCRA_LIBRARY_MATCH_BUILD_STATES = {}
_SYNCRA_LIBRARY_MATCH_BUILD_STATES_LOCK = threading.Lock()
_SYNCRA_SMART_MATCH_RUNTIME_SETTINGS = dict(APP_CONFIG_DEFAULTS.get("smart_match", {}))
_SYNCRA_SMART_MATCH_CACHE_STORE = None
_SYNCRA_SMART_MATCH_CACHE_STORE_LOCK = threading.Lock()

patch_qt_legacy_apis()


def get_syncra_logo_svg():
    return """
    <svg width="250" height="100" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <linearGradient id="mainGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#00E676"/>
                <stop offset="50%" style="stop-color:#00BCD4"/>
                <stop offset="100%" style="stop-color:#2196F3"/>
            </linearGradient>
            <linearGradient id="textGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                <stop offset="0%" style="stop-color:#42A5F5"/>
                <stop offset="100%" style="stop-color:#2196F3"/>
            </linearGradient>
        </defs>
        <g transform="translate(10, 20)">
            <circle cx="25" cy="30" r="25" fill="none" stroke="url(#mainGrad)" stroke-width="4"/>
            <circle cx="25" cy="30" r="15" fill="none" stroke="url(#mainGrad)" stroke-width="2" opacity="0.7"/>
            <circle cx="25" cy="30" r="5" fill="url(#mainGrad)"/>
            <circle cx="45" cy="30" r="25" fill="none" stroke="url(#mainGrad)" stroke-width="4" opacity="0.8"/>
            <circle cx="45" cy="30" r="15" fill="none" stroke="url(#mainGrad)" stroke-width="2" opacity="0.6"/>
            <circle cx="45" cy="30" r="5" fill="url(#mainGrad)" opacity="0.8"/>
            <text x="85" y="40" font-family="Inter, sans-serif" font-size="32" font-weight="800" fill="url(#textGrad)" letter-spacing="-1px">SYNCRA</text>
        </g>
    </svg>
    """


class StartupSplashScreen(QWidget):
    def __init__(self):
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.SplashScreen)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setObjectName("startupSplash")
        self.setFixedSize(520, 300)
        self._build_ui()
        self._center_on_primary_screen()

    def _build_ui(self):
        from PyQt6.QtCore import QByteArray

        self.setStyleSheet("""
            QWidget#startupSplash {
                background-color: #0f1726;
                border: 1px solid #243248;
                border-radius: 18px;
            }
            QLabel#startupTitle {
                color: #f4f7fb;
                font-size: 20px;
                font-weight: 700;
            }
            QLabel#startupSubtitle {
                color: #9ab0cc;
                font-size: 12px;
            }
            QLabel#startupStatus {
                color: #dce7f5;
                font-size: 13px;
                font-weight: 600;
            }
            QProgressBar {
                border: 1px solid #32455f;
                border-radius: 8px;
                background: #111a29;
                color: #f4f7fb;
                text-align: center;
                height: 18px;
            }
            QProgressBar::chunk {
                border-radius: 7px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #00c7a4, stop:0.55 #20b8d9, stop:1 #2d8cff);
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        logo_widget = QSvgWidget()
        logo_widget.load(QByteArray(get_syncra_logo_svg().encode("utf-8")))
        logo_widget.setFixedSize(258, 100)
        layout.addWidget(logo_widget, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.title_label = QLabel("Starting Syncra")
        self.title_label.setObjectName("startupTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.title_label)

        subtitle = QLabel("Preparing playlists, services, and Smart Match cache")
        subtitle.setObjectName("startupSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        layout.addStretch(1)

        self.status_label = QLabel("Loading interface...")
        self.status_label.setObjectName("startupStatus")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(5)
        layout.addWidget(self.progress_bar)

    def _center_on_primary_screen(self):
        screen = QApplication.primaryScreen()
        if not screen:
            return
        geometry = screen.availableGeometry()
        self.move(
            geometry.center().x() - self.width() // 2,
            geometry.center().y() - self.height() // 2,
        )

    def update_progress(self, message, value=None):
        self.status_label.setText(str(message or "").strip() or "Loading...")
        if value is not None:
            self.progress_bar.setValue(int(max(0, min(100, value))))
        QApplication.processEvents()

    def finish_for(self, window=None):
        self.update_progress("Ready", 100)
        QApplication.processEvents()
        self.close()


def _normalize_match_text(value):
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    text = text.lower().replace("&", " and ").replace("_", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_title_variants(value):
    raw = str(value or "").strip()
    if not raw:
        return []

    variants = []

    def add_variant(candidate):
        normalized = _normalize_match_text(candidate)
        if normalized and normalized not in variants:
            variants.append(normalized)

    add_variant(raw)

    stripped = re.sub(r"\(\([^)]*\)\)", " ", raw)
    stripped = re.sub(r"\((?:album|lp|radio|single|club|extended|remaster(?:ed)?|re recorded|re-recorded|mix|version|edit)[^)]*\)", " ", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"\[(?:album|lp|radio|single|club|extended|remaster(?:ed)?|re recorded|re-recorded|mix|version|edit)[^\]]*\]", " ", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"\s+", " ", stripped).strip(" -_()[]")
    add_variant(stripped)

    no_feat = re.sub(r"\s*(?:\(|\[)?(?:feat|ft|with)\.?[^)\]]*(?:\)|\])?\s*", " ", stripped or raw, flags=re.IGNORECASE)
    no_feat = re.sub(r"\s+", " ", no_feat).strip(" -_()[]")
    add_variant(no_feat)

    return variants


def _build_title_search_terms(value):
    raw = str(value or "").strip()
    if not raw:
        return []

    terms = []

    def add_term(candidate):
        text = str(candidate or "").strip()
        if text and text not in terms:
            terms.append(text)

    add_term(raw)
    add_term(_strip_leading_track_tokens(raw))

    stripped = re.sub(r"\(\([^)]*\)\)", " ", raw)
    stripped = re.sub(r"\((?:album|lp|radio|single|club|extended|remaster(?:ed)?|re recorded|re-recorded|mix|version|edit)[^)]*\)", " ", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"\[(?:album|lp|radio|single|club|extended|remaster(?:ed)?|re recorded|re-recorded|mix|version|edit)[^\]]*\]", " ", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"\s+", " ", stripped).strip(" -_()[]")
    add_term(stripped)

    no_feat = re.sub(r"\s*(?:\(|\[)?(?:feat|ft|with)\.?[^)\]]*(?:\)|\])?\s*", " ", stripped or raw, flags=re.IGNORECASE)
    no_feat = re.sub(r"\s+", " ", no_feat).strip(" -_()[]")
    add_term(no_feat)

    add_term(stripped.replace("'", ""))
    add_term(stripped.replace("_", " "))
    add_term(no_feat.replace("'", ""))

    return terms


def _is_generic_artist_name(value):
    normalized = _normalize_match_text(value)
    return normalized in {
        "",
        "playlist",
        "playlists",
        "various artists",
        "various artist",
        "various interprets",
        "various interpretations",
        "various interpretation",
        "va",
        "soundtrack",
        "original soundtrack",
        "ost",
        "music from the motion picture",
    }


def _is_compilation_like_album(value):
    normalized = _normalize_match_text(value)
    if not normalized:
        return False
    markers = (
        "greatest hits",
        "best of",
        "mega hits",
        "megahits",
        "soundtrack",
        "story",
        "collection",
        "anthology",
        "classic",
        "classics",
        "selected and mixed",
        "vol ",
        "volume ",
        "presents ",
        "hits",
    )
    return any(marker in normalized for marker in markers)


def _set_smart_match_runtime_settings(settings):
    global _SYNCRA_SMART_MATCH_RUNTIME_SETTINGS, _SYNCRA_SMART_MATCH_CACHE_STORE
    merged = dict(APP_CONFIG_DEFAULTS.get("smart_match", {}))
    if isinstance(settings, dict):
        merged.update(settings)
    _SYNCRA_SMART_MATCH_RUNTIME_SETTINGS = merged
    with _SYNCRA_SMART_MATCH_CACHE_STORE_LOCK:
        _SYNCRA_SMART_MATCH_CACHE_STORE = None


def _get_smart_match_cache_db_path():
    cache_name = str(_SYNCRA_SMART_MATCH_RUNTIME_SETTINGS.get("cache_db", "smart_match_cache.sqlite") or "smart_match_cache.sqlite").strip()
    return os.path.abspath(cache_name)


class SmartMatchCacheStore:
    def __init__(self, db_path):
        self.db_path = db_path
        self._ensure_schema()

    def _connect(self):
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _ensure_schema(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS smart_match_meta (
                    session_key TEXT PRIMARY KEY,
                    server_id TEXT,
                    section_id TEXT,
                    track_total INTEGER,
                    newest_added_at TEXT,
                    newest_updated_at TEXT,
                    built_at TEXT,
                    row_count INTEGER
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS smart_match_rows (
                    session_key TEXT NOT NULL,
                    rating_key TEXT NOT NULL,
                    title TEXT,
                    artist TEXT,
                    album TEXT,
                    title_variants_json TEXT,
                    exact_paths_json TEXT,
                    suffix3_json TEXT,
                    suffix2_json TEXT,
                    PRIMARY KEY (session_key, rating_key)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_smart_match_rows_session ON smart_match_rows(session_key)"
            )

    def get_meta(self, session_key):
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT session_key, server_id, section_id, track_total, newest_added_at,
                       newest_updated_at, built_at, row_count
                FROM smart_match_meta WHERE session_key = ?
                """,
                (session_key,),
            ).fetchone()
        if not row:
            return None
        return {
            "session_key": row[0],
            "server_id": row[1],
            "section_id": row[2],
            "track_total": int(row[3] or 0),
            "newest_added_at": str(row[4] or ""),
            "newest_updated_at": str(row[5] or ""),
            "built_at": str(row[6] or ""),
            "row_count": int(row[7] or 0),
        }

    def load_rows(self, session_key):
        rows = []
        with self._connect() as conn:
            cursor = conn.execute(
                """
                SELECT rating_key, title, artist, album, title_variants_json,
                       exact_paths_json, suffix3_json, suffix2_json
                FROM smart_match_rows
                WHERE session_key = ?
                """,
                (session_key,),
            )
            for row in cursor.fetchall():
                rows.append({
                    "rating_key": str(row[0] or ""),
                    "title": str(row[1] or ""),
                    "artist": str(row[2] or ""),
                    "album": str(row[3] or ""),
                    "title_variants": json.loads(row[4] or "[]"),
                    "exact_paths": json.loads(row[5] or "[]"),
                    "suffix3": json.loads(row[6] or "[]"),
                    "suffix2": json.loads(row[7] or "[]"),
                })
        return rows

    def save_rows(self, session_key, fingerprint, rows):
        built_at = datetime.now().isoformat()
        with self._connect() as conn:
            conn.execute("DELETE FROM smart_match_rows WHERE session_key = ?", (session_key,))
            conn.execute("DELETE FROM smart_match_meta WHERE session_key = ?", (session_key,))
            conn.executemany(
                """
                INSERT INTO smart_match_rows (
                    session_key, rating_key, title, artist, album, title_variants_json,
                    exact_paths_json, suffix3_json, suffix2_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        session_key,
                        str(row.get("rating_key", "") or ""),
                        str(row.get("title", "") or ""),
                        str(row.get("artist", "") or ""),
                        str(row.get("album", "") or ""),
                        json.dumps(list(row.get("title_variants", []) or [])),
                        json.dumps(list(row.get("exact_paths", []) or [])),
                        json.dumps(list(row.get("suffix3", []) or [])),
                        json.dumps(list(row.get("suffix2", []) or [])),
                    )
                    for row in rows
                ],
            )
            conn.execute(
                """
                INSERT INTO smart_match_meta (
                    session_key, server_id, section_id, track_total, newest_added_at,
                    newest_updated_at, built_at, row_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_key,
                    str(fingerprint.get("server_id", "") or ""),
                    str(fingerprint.get("section_id", "") or ""),
                    int(fingerprint.get("track_total", 0) or 0),
                    str(fingerprint.get("newest_added_at", "") or ""),
                    str(fingerprint.get("newest_updated_at", "") or ""),
                    built_at,
                    len(rows),
                ),
            )

    def clear_library(self, session_key):
        with self._connect() as conn:
            conn.execute("DELETE FROM smart_match_rows WHERE session_key = ?", (session_key,))
            conn.execute("DELETE FROM smart_match_meta WHERE session_key = ?", (session_key,))


def _get_smart_match_cache_store():
    global _SYNCRA_SMART_MATCH_CACHE_STORE
    with _SYNCRA_SMART_MATCH_CACHE_STORE_LOCK:
        db_path = _get_smart_match_cache_db_path()
        if _SYNCRA_SMART_MATCH_CACHE_STORE is None or getattr(_SYNCRA_SMART_MATCH_CACHE_STORE, "db_path", None) != db_path:
            _SYNCRA_SMART_MATCH_CACHE_STORE = SmartMatchCacheStore(db_path)
        return _SYNCRA_SMART_MATCH_CACHE_STORE


def _get_library_match_session_key(library_section):
    try:
        server = getattr(library_section, "_server", None)
        server_id = (
            str(getattr(server, "machineIdentifier", "") or "").strip()
            or str(getattr(server, "friendlyName", "") or "").strip()
            or str(getattr(server, "baseurl", "") or "").strip()
        )
        section_id = (
            str(getattr(library_section, "key", "") or "").strip()
            or str(getattr(library_section, "ratingKey", "") or "").strip()
            or str(getattr(library_section, "title", "") or "").strip()
        )
        if not server_id or not section_id:
            return None
        return f"{server_id}::{section_id}"
    except Exception:
        return None


def _query_library_tracks_page(library_section, start=0, size=200, sort=None):
    server = getattr(library_section, "_server", None)
    section_id = (
        str(getattr(library_section, "key", "") or "").strip()
        or str(getattr(library_section, "ratingKey", "") or "").strip()
    )
    if not server or not section_id:
        raise ValueError("Library section is missing server or section id")
    params = {
        "type": 10,
        "X-Plex-Container-Start": max(0, int(start or 0)),
        "X-Plex-Container-Size": max(1, int(size or 200)),
        "includeElements": "Media,Part",
        "includeFields": "ratingKey,title,originalTitle,grandparentTitle,parentTitle,duration,addedAt,updatedAt",
    }
    if sort:
        params["sort"] = sort
    query = f"/library/sections/{section_id}/all?{urllib.parse.urlencode(params)}"
    return server.query(query)


def _iter_track_elements(container):
    if container is None:
        return []
    tracks = [elem for elem in list(container) if str(getattr(elem, "tag", "")).lower() == "track"]
    if tracks:
        return tracks
    return list(container.findall(".//Track"))


def _extract_index_row_from_track_element(track_elem):
    rating_key = str(track_elem.attrib.get("ratingKey", "") or "").strip()
    if not rating_key:
        return None

    title = str(track_elem.attrib.get("title", "") or "").strip()
    artist = str(track_elem.attrib.get("originalTitle", "") or track_elem.attrib.get("grandparentTitle", "") or "").strip()
    album = str(track_elem.attrib.get("parentTitle", "") or "").strip()
    try:
        duration_ms = int(track_elem.attrib.get("duration", 0) or 0)
    except Exception:
        duration_ms = 0

    exact_paths = []
    suffix3 = []
    suffix2 = []
    seen_paths = set()
    for part in track_elem.findall(".//Part"):
        file_path = str(part.attrib.get("file", "") or "").strip()
        if not file_path:
            continue
        normalized = file_path.replace("\\", "/").lower()
        if normalized in seen_paths:
            continue
        seen_paths.add(normalized)
        exact_paths.append(normalized)
        path_parts = [segment for segment in normalized.split("/") if segment]
        if len(path_parts) >= 3:
            suffix3_value = "/".join(path_parts[-3:])
            if suffix3_value not in suffix3:
                suffix3.append(suffix3_value)
        if len(path_parts) >= 2:
            suffix2_value = "/".join(path_parts[-2:])
            if suffix2_value not in suffix2:
                suffix2.append(suffix2_value)

    return {
        "rating_key": rating_key,
        "title": title,
        "artist": artist,
        "album": album,
        "duration_ms": duration_ms,
        "title_variants": _normalize_title_variants(title),
        "exact_paths": exact_paths,
        "suffix3": suffix3,
        "suffix2": suffix2,
    }


def _build_bundle_from_rows(rows):
    title_index = {}
    artist_index = {}
    album_index = {}
    exact_map = {}
    suffix3_map = {}
    suffix2_map = {}
    rows_by_key = {}

    for row in rows or []:
        rating_key = str(row.get("rating_key", "") or "").strip()
        if not rating_key:
            continue
        rows_by_key[rating_key] = row
        for variant in row.get("title_variants", []) or []:
            if variant:
                title_index.setdefault(variant, []).append(row)
        artist = _normalize_match_text(row.get("artist", ""))
        if artist:
            artist_index.setdefault(artist, []).append(row)
        album = _normalize_match_text(row.get("album", ""))
        if album:
            album_index.setdefault(album, []).append(row)
        for value in row.get("exact_paths", []) or []:
            exact_map.setdefault(value, []).append(row)
        for value in row.get("suffix3", []) or []:
            suffix3_map.setdefault(value, []).append(row)
        for value in row.get("suffix2", []) or []:
            suffix2_map.setdefault(value, []).append(row)

    return {
        "rows": list(rows_by_key.values()),
        "rows_by_key": rows_by_key,
        "titles": title_index,
        "artists": artist_index,
        "albums": album_index,
        "paths": {
            "exact": exact_map,
            "suffix3": suffix3_map,
            "suffix2": suffix2_map,
        },
    }


def _store_library_match_bundle(library_section, bundle, fingerprint=None):
    cache_attr = "_syncra_match_index_bundle"
    session_key = _get_library_match_session_key(library_section)
    try:
        setattr(library_section, cache_attr, bundle)
        setattr(library_section, "_syncra_match_rows_cache", bundle["rows"])
        setattr(library_section, "_syncra_match_rows_by_key_cache", bundle["rows_by_key"])
        setattr(library_section, "_syncra_title_index_cache", bundle["titles"])
        setattr(library_section, "_syncra_artist_index_cache", bundle["artists"])
        setattr(library_section, "_syncra_album_index_cache", bundle["albums"])
        setattr(library_section, "_syncra_path_index_cache", bundle["paths"])
    except Exception:
        pass
    if session_key is not None:
        with _SYNCRA_LIBRARY_MATCH_SESSION_CACHE_LOCK:
            payload = _SYNCRA_LIBRARY_MATCH_SESSION_CACHE.setdefault(session_key, {})
            payload["bundle"] = bundle
            if fingerprint is not None:
                payload["fingerprint"] = dict(fingerprint)
    return bundle


def _restore_library_match_bundle(library_section):
    cache_attr = "_syncra_match_index_bundle"
    if hasattr(library_section, cache_attr):
        return getattr(library_section, cache_attr)
    session_key = _get_library_match_session_key(library_section)
    if not session_key:
        return None
    with _SYNCRA_LIBRARY_MATCH_SESSION_CACHE_LOCK:
        payload = _SYNCRA_LIBRARY_MATCH_SESSION_CACHE.get(session_key, {})
        bundle = payload.get("bundle")
        fingerprint = payload.get("fingerprint")
    if bundle:
        return _store_library_match_bundle(library_section, bundle, fingerprint=fingerprint)
    return None


def _get_cached_library_fingerprint(library_section):
    session_key = _get_library_match_session_key(library_section)
    if not session_key:
        return None
    with _SYNCRA_LIBRARY_MATCH_SESSION_CACHE_LOCK:
        payload = _SYNCRA_LIBRARY_MATCH_SESSION_CACHE.get(session_key, {})
        fingerprint = payload.get("fingerprint")
        if fingerprint:
            return dict(fingerprint)
    return None


def _probe_library_match_fingerprint(library_section):
    session_key = _get_library_match_session_key(library_section)
    server = getattr(library_section, "_server", None)
    server_id = str(getattr(server, "machineIdentifier", "") or "").strip()
    section_id = str(getattr(library_section, "key", "") or "").strip()
    total_tracks = 0
    newest_added_at = ""
    newest_updated_at = ""

    try:
        latest_updated = _query_library_tracks_page(library_section, start=0, size=1, sort="updatedAt:desc")
        total_tracks = int(latest_updated.attrib.get("totalSize") or latest_updated.attrib.get("size") or 0)
        updated_items = _iter_track_elements(latest_updated)
        if updated_items:
            newest_updated_at = str(updated_items[0].attrib.get("updatedAt", "") or "").strip()
            newest_added_at = str(updated_items[0].attrib.get("addedAt", "") or "").strip()
    except Exception:
        pass

    if total_tracks > 0 and not newest_added_at:
        try:
            latest_added = _query_library_tracks_page(library_section, start=0, size=1, sort="addedAt:desc")
            added_items = _iter_track_elements(latest_added)
            if added_items:
                newest_added_at = str(added_items[0].attrib.get("addedAt", "") or "").strip()
        except Exception:
            pass

    fingerprint = {
        "session_key": session_key,
        "server_id": server_id,
        "section_id": section_id,
        "track_total": int(total_tracks or 0),
        "newest_added_at": newest_added_at,
        "newest_updated_at": newest_updated_at,
    }
    if not total_tracks and not newest_added_at and not newest_updated_at:
        cached = _get_cached_library_fingerprint(library_section)
        if cached:
            return cached
    if session_key:
        with _SYNCRA_LIBRARY_MATCH_SESSION_CACHE_LOCK:
            payload = _SYNCRA_LIBRARY_MATCH_SESSION_CACHE.setdefault(session_key, {})
            payload["fingerprint"] = dict(fingerprint)
    return fingerprint


def _library_fingerprint_matches(meta, fingerprint):
    if not meta or not fingerprint:
        return False
    return (
        str(meta.get("session_key", "") or "") == str(fingerprint.get("session_key", "") or "")
        and int(meta.get("track_total", 0) or 0) == int(fingerprint.get("track_total", 0) or 0)
        and str(meta.get("newest_added_at", "") or "") == str(fingerprint.get("newest_added_at", "") or "")
        and str(meta.get("newest_updated_at", "") or "") == str(fingerprint.get("newest_updated_at", "") or "")
    )


def _build_library_match_indexes(library_section, progress_cb=None, force_rebuild=False, stop_check=None, progress_range=(0, 100)):
    session_key = _get_library_match_session_key(library_section)
    if not session_key:
        raise ValueError("Smart Match cache requires a valid server and library section")

    def report(message, percentage):
        clamped = max(progress_range[0], min(progress_range[1], int(percentage)))
        if progress_cb:
            progress_cb(message, clamped)

    if stop_check and stop_check():
        raise RuntimeError("Smart matching canceled.")

    existing_bundle = _restore_library_match_bundle(library_section)
    previous_fingerprint = _get_cached_library_fingerprint(library_section)

    report("Checking Smart Match Cache...", progress_range[0])
    fingerprint = _probe_library_match_fingerprint(library_section)
    if existing_bundle and not force_rebuild and previous_fingerprint and _library_fingerprint_matches(previous_fingerprint, fingerprint):
        return existing_bundle
    if existing_bundle and not force_rebuild:
        _clear_library_match_caches(library_section=library_section, session_key=session_key, clear_disk=False)

    persist_cache = bool(_SYNCRA_SMART_MATCH_RUNTIME_SETTINGS.get("persist_cache", True))
    if persist_cache and not force_rebuild:
        try:
            store = _get_smart_match_cache_store()
            meta = store.get_meta(session_key)
            if _library_fingerprint_matches(meta, fingerprint):
                report("Loading Smart Match Cache...", progress_range[0] + 2)
                rows = store.load_rows(session_key)
                if rows:
                    bundle = _build_bundle_from_rows(rows)
                    return _store_library_match_bundle(library_section, bundle, fingerprint=fingerprint)
        except Exception as cache_error:
            logging.warning(f"Could not load Smart Match cache: {cache_error}")

    with _SYNCRA_LIBRARY_MATCH_BUILD_STATES_LOCK:
        active_state = _SYNCRA_LIBRARY_MATCH_BUILD_STATES.get(session_key)
        if active_state:
            wait_event = active_state["event"]
        else:
            wait_event = None
            active_state = {
                "event": threading.Event(),
                "message": "Checking Smart Match Cache...",
                "progress": progress_range[0],
                "error": None,
            }
            _SYNCRA_LIBRARY_MATCH_BUILD_STATES[session_key] = active_state

    if wait_event is not None:
        while not wait_event.wait(0.2):
            if stop_check and stop_check():
                raise RuntimeError("Smart matching canceled.")
            report(active_state.get("message", "Waiting for Smart Match cache..."), active_state.get("progress", progress_range[0]))
        if active_state.get("error"):
            raise RuntimeError(active_state["error"])
        bundle = _restore_library_match_bundle(library_section)
        if bundle:
            return bundle
        raise RuntimeError("Smart Match cache build completed without a usable result.")

    try:
        page_size = 250
        total_tracks = int(fingerprint.get("track_total", 0) or 0)
        processed = 0
        rows = []

        while True:
            if stop_check and stop_check():
                raise RuntimeError("Smart matching canceled.")
            container = _query_library_tracks_page(library_section, start=processed, size=page_size)
            track_elements = _iter_track_elements(container)
            if not track_elements:
                break
            for track_elem in track_elements:
                row = _extract_index_row_from_track_element(track_elem)
                if row:
                    rows.append(row)
            processed += len(track_elements)
            pct = progress_range[0] + int((processed / max(total_tracks or processed, 1)) * max(progress_range[1] - progress_range[0], 1))
            message = f"Building Smart Match Index ({processed:,} / {max(total_tracks, processed):,})"
            active_state["message"] = message
            active_state["progress"] = pct
            report(message, pct)
            if len(track_elements) < page_size:
                break

        bundle = _build_bundle_from_rows(rows)
        _store_library_match_bundle(library_section, bundle, fingerprint=fingerprint)
        if persist_cache:
            try:
                _get_smart_match_cache_store().save_rows(session_key, fingerprint, rows)
            except Exception as cache_error:
                logging.warning(f"Could not persist Smart Match cache: {cache_error}")
        active_state["message"] = f"Smart Match index ready ({len(rows):,} tracks)"
        active_state["progress"] = progress_range[1]
        return bundle
    except Exception as exc:
        active_state["error"] = str(exc)
        raise
    finally:
        active_state["event"].set()
        with _SYNCRA_LIBRARY_MATCH_BUILD_STATES_LOCK:
            _SYNCRA_LIBRARY_MATCH_BUILD_STATES.pop(session_key, None)


def _get_library_title_index_cached(library_section):
    cache_attr = "_syncra_title_index_cache"
    if hasattr(library_section, cache_attr):
        return getattr(library_section, cache_attr)
    return _build_library_match_indexes(library_section)["titles"]


def _get_library_artist_index_cached(library_section):
    cache_attr = "_syncra_artist_index_cache"
    if hasattr(library_section, cache_attr):
        return getattr(library_section, cache_attr)
    return _build_library_match_indexes(library_section)["artists"]


def _get_library_album_index_cached(library_section):
    cache_attr = "_syncra_album_index_cache"
    if hasattr(library_section, cache_attr):
        return getattr(library_section, cache_attr)
    return _build_library_match_indexes(library_section)["albums"]


def _get_library_path_index_cached(library_section):
    cache_attr = "_syncra_path_index_cache"
    if hasattr(library_section, cache_attr):
        return getattr(library_section, cache_attr)
    return _build_library_match_indexes(library_section)["paths"]


def _get_library_match_rows_cached(library_section):
    cache_attr = "_syncra_match_rows_cache"
    if hasattr(library_section, cache_attr):
        return getattr(library_section, cache_attr)
    return _build_library_match_indexes(library_section)["rows"]


def _get_library_match_rows_by_key_cached(library_section):
    cache_attr = "_syncra_match_rows_by_key_cache"
    if hasattr(library_section, cache_attr):
        return getattr(library_section, cache_attr)
    return _build_library_match_indexes(library_section)["rows_by_key"]


def _prime_library_match_caches(library_section, progress_cb=None, force_rebuild=False, stop_check=None, progress_range=(0, 100)):
    """Warm all match caches once so the first lookup does not stall the worker."""
    return _build_library_match_indexes(
        library_section,
        progress_cb=progress_cb,
        force_rebuild=force_rebuild,
        stop_check=stop_check,
        progress_range=progress_range,
    )


def _clear_library_match_caches(library_section=None, session_key=None, clear_disk=False):
    target_session_key = session_key or _get_library_match_session_key(library_section) if library_section is not None else session_key
    if target_session_key:
        with _SYNCRA_LIBRARY_MATCH_SESSION_CACHE_LOCK:
            _SYNCRA_LIBRARY_MATCH_SESSION_CACHE.pop(target_session_key, None)
    if library_section is not None:
        for attr in (
            "_syncra_match_index_bundle",
            "_syncra_match_rows_cache",
            "_syncra_match_rows_by_key_cache",
            "_syncra_title_index_cache",
            "_syncra_artist_index_cache",
            "_syncra_album_index_cache",
            "_syncra_path_index_cache",
        ):
            if hasattr(library_section, attr):
                try:
                    delattr(library_section, attr)
                except Exception:
                    pass
    if clear_disk and target_session_key:
        try:
            _get_smart_match_cache_store().clear_library(target_session_key)
        except Exception as cache_error:
            logging.warning(f"Could not clear Smart Match cache on disk: {cache_error}")


def _format_track_duration_ms(duration_ms):
    try:
        value = int(duration_ms or 0)
    except Exception:
        value = 0
    if value <= 0:
        return "Unknown"
    return f"{value // 60000}:{(value % 60000) // 1000:02d}"


def _build_playlist_editor_row(track):
    return {
        "track": track,
        "title": str(getattr(track, "title", "") or "").strip() or "Unknown",
        "artist": _extract_plex_track_artist_name(track) or "Unknown",
        "album": _extract_plex_track_album_name(track) or "Unknown",
        "duration": _format_track_duration_ms(getattr(track, "duration", None)),
    }


def _strip_leading_track_tokens(value):
    text = str(value or "").strip()
    patterns = (
        r"^\s*(?:cd|disc)\s*\d+\s*[-._)\]]+\s*",
        r"^\s*[a-z]?\d{2,3}\s*[-._)\]]+\s*",
        r"^\s*\d{1,2}\s*[-._)\]]+\s*",
        r"^\s*\d{2,3}\s+",
    )
    cleaned = text
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned or text


def _extract_plex_track_artist_name(track):
    artist = str(getattr(track, "originalTitle", "") or "").strip()
    if artist:
        return artist
    grandparent = str(getattr(track, "grandparentTitle", "") or "").strip()
    if grandparent:
        return grandparent
    try:
        artist_obj = track.artist() if hasattr(track, "artist") else None
        if artist_obj:
            return str(getattr(artist_obj, "title", "") or "").strip()
    except Exception:
        pass
    return ""


def _extract_plex_track_album_name(track):
    try:
        album_obj = track.album() if hasattr(track, "album") else None
        if album_obj:
            return str(getattr(album_obj, "title", "") or "").strip()
    except Exception:
        pass
    return str(getattr(track, "parentTitle", "") or "").strip()


def _extract_recording_mbid_from_plex_track_for_matching(plex_track):
    guid_candidates = []
    guid_value = getattr(plex_track, "guid", None)
    if guid_value:
        guid_candidates.append(str(guid_value))
    for guid_obj in getattr(plex_track, "guids", []) or []:
        guid_id = getattr(guid_obj, "id", None)
        if guid_id:
            guid_candidates.append(str(guid_id))

    mbid_pattern = re.compile(
        r"(?:musicbrainz\.org/recording/|musicbrainz://recording/|recording/)([0-9a-fA-F-]{36})",
        re.IGNORECASE,
    )
    for candidate in guid_candidates:
        match = mbid_pattern.search(candidate)
        if match:
            return match.group(1).lower()
    return ""


def _apply_smart_filter_penalty(score, album_title, parent_widget):
    if not parent_widget or not hasattr(parent_widget, "enable_filters_checkbox"):
        return score
    try:
        if not parent_widget.enable_filters_checkbox.isChecked():
            return score
        lowered_album = str(album_title or "").lower()
        penalty = 0
        if hasattr(parent_widget, "filter_live_checkbox") and parent_widget.filter_live_checkbox.isChecked():
            if any(keyword in lowered_album for keyword in ["live", "concert", "tour"]):
                penalty += 15
        if hasattr(parent_widget, "filter_compilation_checkbox") and parent_widget.filter_compilation_checkbox.isChecked():
            if any(keyword in lowered_album for keyword in ["best of", "greatest hits", "collection", "anthology"]):
                penalty += 12
        if hasattr(parent_widget, "filter_remaster_checkbox") and parent_widget.filter_remaster_checkbox.isChecked():
            if any(keyword in lowered_album for keyword in ["remaster", "remastered"]):
                penalty += 8
        if hasattr(parent_widget, "filter_deluxe_checkbox") and parent_widget.filter_deluxe_checkbox.isChecked():
            if any(keyword in lowered_album for keyword in ["deluxe", "special", "extended", "expanded", "anniversary"]):
                penalty += 6
        return max(0.0, score - penalty)
    except Exception as exc:
        logging.warning(f"Could not apply smart filtering penalty: {exc}")
        return score


def _score_candidate_values(source_track, target_title, target_artist, target_album, target_mbid="", parent_widget=None):
    src_title = str(source_track.get("title", "") or "").strip()
    src_artist = str(source_track.get("artist", "") or "").strip()
    src_artists = [str(value or "").strip() for value in (source_track.get("artists") or []) if str(value or "").strip()]
    src_album = str(source_track.get("album", "") or "").strip()
    src_mbid = str(source_track.get("recording_mbid", "") or "").strip().lower()
    src_isrc = str(source_track.get("isrc", "") or "").strip().upper()
    try:
        src_duration_ms = int(source_track.get("duration_ms", 0) or 0)
    except Exception:
        src_duration_ms = 0

    target_title = str(target_title or "").strip()
    if not src_title or not target_title:
        return None

    src_title_variants = _normalize_title_variants(src_title)
    target_title_variants = _normalize_title_variants(target_title)
    if not src_title_variants or not target_title_variants:
        return None

    norm_src_title = src_title_variants[0]
    norm_target_title = target_title_variants[0]
    title_score = 0.0
    for src_variant in src_title_variants:
        for target_variant in target_title_variants:
            title_score = max(
                title_score,
                float(fuzz.token_set_ratio(src_variant, target_variant)),
                float(fuzz.token_sort_ratio(src_variant, target_variant)),
                float(fuzz.partial_ratio(src_variant, target_variant)),
            )
    if title_score < 45:
        return None

    target_artist = str(target_artist or "").strip()
    target_album = str(target_album or "").strip()
    try:
        target_duration_ms = int(source_track.get("_target_duration_ms", 0) or 0)
    except Exception:
        target_duration_ms = 0
    target_isrc = str(source_track.get("_target_isrc", "") or "").strip().upper()

    norm_src_artist = "" if _is_generic_artist_name(src_artist) else _normalize_match_text(src_artist)
    norm_target_artist = _normalize_match_text(target_artist)
    artist_candidates = []
    if norm_src_artist:
        artist_candidates.append(norm_src_artist)
    for candidate in src_artists:
        norm_candidate = _normalize_match_text(candidate)
        if norm_candidate and norm_candidate not in artist_candidates and not _is_generic_artist_name(candidate):
            artist_candidates.append(norm_candidate)
    if len(src_artists) > 1:
        joined_artists = _normalize_match_text(", ".join(src_artists))
        if joined_artists and joined_artists not in artist_candidates:
            artist_candidates.append(joined_artists)

    artist_score = 0.0
    if norm_target_artist and artist_candidates:
        for candidate in artist_candidates:
            artist_score = max(
                artist_score,
                float(fuzz.token_set_ratio(candidate, norm_target_artist)),
                float(fuzz.token_sort_ratio(candidate, norm_target_artist)),
            )

    norm_src_album = _normalize_match_text(src_album)
    norm_src_album_core = norm_src_album
    artist_prefixed_album = False
    if src_artist and src_album:
        album_prefix_pattern = re.compile(
            r"^\s*" + re.escape(str(src_artist).strip()) + r"\s*-\s*",
            re.IGNORECASE,
        )
        stripped_album = re.sub(album_prefix_pattern, "", str(src_album).strip(), count=1).strip()
        stripped_norm_album = _normalize_match_text(stripped_album)
        if stripped_norm_album and stripped_norm_album != norm_src_album:
            norm_src_album_core = stripped_norm_album
            artist_prefixed_album = True
    norm_target_album = _normalize_match_text(target_album)
    album_score = 0.0
    if norm_target_album:
        if norm_src_album:
            album_score = max(album_score, float(fuzz.token_set_ratio(norm_src_album, norm_target_album)))
        if norm_src_album_core:
            album_score = max(album_score, float(fuzz.token_set_ratio(norm_src_album_core, norm_target_album)))

    if norm_src_artist and norm_src_album:
        combined_score = (title_score * 0.58) + (artist_score * 0.30) + (album_score * 0.12)
    elif norm_src_artist:
        combined_score = (title_score * 0.68) + (artist_score * 0.32)
    else:
        combined_score = title_score

    duration_score = 0.0
    duration_delta_ms = 0
    if src_duration_ms > 0 and target_duration_ms > 0:
        duration_delta_ms = abs(src_duration_ms - target_duration_ms)
        duration_delta_sec = duration_delta_ms / 1000.0
        if duration_delta_sec <= 1.5:
            duration_score = 100.0
            combined_score += 8
        elif duration_delta_sec <= 3.0:
            duration_score = 96.0
            combined_score += 6
        elif duration_delta_sec <= 6.0:
            duration_score = 90.0
            combined_score += 4
        elif duration_delta_sec <= 10.0:
            duration_score = 82.0
            combined_score += 2
        elif duration_delta_sec >= 45.0:
            duration_score = 0.0
            combined_score -= 18
        elif duration_delta_sec >= 20.0:
            duration_score = max(0.0, 100.0 - duration_delta_sec)
            combined_score -= 8
        else:
            duration_score = max(0.0, 100.0 - duration_delta_sec)

    if norm_src_artist and artist_score < 35:
        # Some path-only M3Us synthesize "Artist - Compilation Album" folder names where
        # the folder artist is album context rather than the real track artist. Do not
        # over-penalize those if title+album strongly agree.
        low_confidence_source_artist = (
            artist_prefixed_album
            and album_score >= 82
            and title_score >= 78
        )
        combined_score -= 8 if low_confidence_source_artist else 22
    if norm_src_album and norm_target_album and album_score < 35:
        combined_score -= 10

    strong_title_match = title_score >= 78
    exactish_artist_match = bool(norm_src_artist and artist_score >= 92)
    strong_artist_match = bool(norm_src_artist and artist_score >= 80)

    if any(src_variant == target_variant for src_variant in src_title_variants for target_variant in target_title_variants):
        combined_score += 4
    if norm_src_artist and norm_src_artist == norm_target_artist:
        combined_score += 4
    if norm_src_album and norm_target_album:
        if norm_src_album == norm_target_album or norm_src_album_core == norm_target_album:
            combined_score += 6
        elif strong_title_match and exactish_artist_match and album_score < 60:
            combined_score -= 8

    # Album text is often noisier than title/artist because of remaster/deluxe/compilation
    # suffixes. If we have a strong title+artist pairing, do not let the album drag the
    # candidate below the correct result.
    if strong_title_match and exactish_artist_match:
        combined_score = max(combined_score, 88.0)
    elif strong_title_match and strong_artist_match:
        combined_score = max(combined_score, 82.0)
    elif strong_title_match and album_score >= 90 and artist_prefixed_album:
        combined_score = max(combined_score, 80.0)

    combined_score = _apply_smart_filter_penalty(combined_score, target_album, parent_widget)

    if src_mbid:
        target_mbid = str(target_mbid or "").strip().lower()
        if target_mbid and target_mbid == src_mbid:
            combined_score = 100.0

    if src_isrc and target_isrc and src_isrc == target_isrc:
        combined_score = 100.0

    return {
        "score": combined_score,
        "title_score": title_score,
        "artist_score": artist_score,
        "album_score": album_score,
        "duration_score": duration_score,
        "duration_delta_ms": duration_delta_ms,
        "artist": target_artist,
        "album": target_album,
        "title": target_title,
    }


def _score_plex_track_candidate(source_track, plex_track, parent_widget=None):
    track_source = dict(source_track or {})
    track_source["_target_duration_ms"] = int(getattr(plex_track, "duration", 0) or 0)
    scored = _score_candidate_values(
        track_source,
        getattr(plex_track, "title", ""),
        _extract_plex_track_artist_name(plex_track),
        _extract_plex_track_album_name(plex_track),
        _extract_recording_mbid_from_plex_track_for_matching(plex_track),
        parent_widget=parent_widget,
    )
    if scored:
        scored["track"] = plex_track
        scored["rating_key"] = str(getattr(plex_track, "ratingKey", "") or "")
    return scored


def _score_indexed_track_candidate(source_track, candidate_row, parent_widget=None):
    track_source = dict(source_track or {})
    track_source["_target_duration_ms"] = int(candidate_row.get("duration_ms", 0) or 0)
    scored = _score_candidate_values(
        track_source,
        candidate_row.get("title", ""),
        candidate_row.get("artist", ""),
        candidate_row.get("album", ""),
        "",
        parent_widget=parent_widget,
    )
    if scored:
        scored["rating_key"] = str(candidate_row.get("rating_key", "") or "")
    return scored


def _collect_plex_track_candidates(library_section, title, artist="", album=""):
    candidates = []
    seen = set()

    def add_results(results):
        for row in results or []:
            rating_key = str(row.get("rating_key", "") or "")
            if rating_key and rating_key in seen:
                continue
            if rating_key:
                seen.add(rating_key)
            candidates.append(row)

    title_index = _get_library_title_index_cached(library_section)
    for variant in _normalize_title_variants(title):
        add_results(title_index.get(variant, []))

    if artist and not _is_generic_artist_name(artist):
        artist_index = _get_library_artist_index_cached(library_section)
        add_results(artist_index.get(_normalize_match_text(artist), []))

    if album:
        album_index = _get_library_album_index_cached(library_section)
        add_results(album_index.get(_normalize_match_text(album), []))

    return candidates


def _rank_plex_track_matches(library_section, source_track, parent_widget=None):
    title = str(source_track.get("title", "") or "").strip()
    artist = str(source_track.get("artist", "") or "").strip()
    album = str(source_track.get("album", "") or "").strip()
    if not title:
        return []

    ranked = []
    seen = set()
    initial_candidates = _collect_plex_track_candidates(library_section, title, artist, album)
    for candidate in initial_candidates:
        scored = _score_indexed_track_candidate(source_track, candidate, parent_widget)
        if not scored:
            continue
        rating_key = str(candidate.get("rating_key", "") or "")
        if rating_key:
            seen.add(rating_key)
        ranked.append(scored)

    # Plex title search can miss valid tracks when the source path contains noisy
    # suffixes or exported compilation metadata. In that case, fall back to a
    # cached full-library pass and let the scorer decide.
    needs_full_scan = not ranked and not initial_candidates
    if needs_full_scan:
        for candidate in _get_library_match_rows_cached(library_section):
            rating_key = str(candidate.get("rating_key", "") or "")
            if rating_key and rating_key in seen:
                continue
            scored = _score_indexed_track_candidate(source_track, candidate, parent_widget)
            if not scored:
                continue
            if rating_key:
                seen.add(rating_key)
            ranked.append(scored)

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked


def _get_plex_track_by_rating_key(library_section, rating_key):
    cache = getattr(library_section, "_syncra_plex_track_object_cache", None)
    if cache is None:
        cache = {}
        try:
            setattr(library_section, "_syncra_plex_track_object_cache", cache)
        except Exception:
            pass
    key = str(rating_key or "").strip()
    if not key:
        return None
    if key in cache:
        return cache[key]
    try:
        track = library_section._server.fetchItem(int(key))
    except Exception:
        try:
            track = library_section._server.fetchItem(key)
        except Exception:
            track = None
    if track is not None:
        cache[key] = track
    return track


def _hydrate_ranked_match_track(library_section, scored_match):
    if not scored_match:
        return None
    track = scored_match.get("track")
    if track is not None:
        return track
    rating_key = str(scored_match.get("rating_key", "") or "")
    return _get_plex_track_by_rating_key(library_section, rating_key)


def _hydrate_plex_tracks_by_rating_keys(library_section, rating_keys):
    hydrated = []
    seen = set()
    for rating_key in rating_keys or []:
        key = str(rating_key or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        track = _get_plex_track_by_rating_key(library_section, key)
        if track is not None:
            hydrated.append(track)
    return hydrated


def _parse_display_track_text(display_text, folder_artist="", prefer_artist_first=False):
    text = str(display_text or "").strip()
    if not text:
        return "", ""
    if " - " not in text:
        return text, folder_artist.strip()

    left, right = text.split(" - ", 1)
    left = left.strip()
    right = right.strip()
    folder_norm = _normalize_match_text(folder_artist)
    left_norm = _normalize_match_text(left)
    right_norm = _normalize_match_text(right)

    if folder_norm:
        left_match = fuzz.token_set_ratio(left_norm, folder_norm) if left_norm else 0
        right_match = fuzz.token_set_ratio(right_norm, folder_norm) if right_norm else 0
        if left_match >= 85 and left_match >= right_match + 10:
            return right, folder_artist.strip()
        if right_match >= 85 and right_match >= left_match + 10:
            return left, folder_artist.strip()

    if prefer_artist_first:
        return right, left
    return left, right


def _parse_m3u_track_from_path(path_line, extinf_text=""):
    raw_path = str(path_line or "").strip()
    if not raw_path:
        return None

    normalized_path = urllib.parse.unquote(raw_path)
    for prefix in ("file-relative://", "file://"):
        if normalized_path.lower().startswith(prefix):
            normalized_path = normalized_path[len(prefix):]
            break
    normalized_path = normalized_path.strip()

    path_parts = [part for part in normalized_path.replace("\\", "/").split("/") if part]
    filename = os.path.splitext(path_parts[-1])[0] if path_parts else normalized_path
    folder_album = path_parts[-2] if len(path_parts) >= 2 else ""
    folder_artist = path_parts[-3] if len(path_parts) >= 3 else ""

    if extinf_text:
        title, artist = _parse_display_track_text(extinf_text, folder_artist=folder_artist, prefer_artist_first=True)
    else:
        cleaned_filename = _strip_leading_track_tokens(filename)
        title = cleaned_filename
        artist = folder_artist
        if " - " in cleaned_filename:
            parts = [part.strip() for part in cleaned_filename.split(" - ") if part.strip()]
            if len(parts) >= 2:
                first_part = parts[0]
                remaining = " - ".join(parts[1:])
                folder_artist_is_generic = _is_generic_artist_name(folder_artist)
                if folder_artist:
                    first_matches_folder = fuzz.token_set_ratio(_normalize_match_text(first_part), _normalize_match_text(folder_artist)) >= 85
                    if first_matches_folder:
                        artist = "" if folder_artist_is_generic else folder_artist
                        title = remaining
                    elif len(parts) == 2 and not folder_artist_is_generic and fuzz.token_set_ratio(_normalize_match_text(parts[1]), _normalize_match_text(folder_artist)) >= 85:
                        artist = folder_artist
                        title = first_part
                    else:
                        if folder_artist_is_generic:
                            artist = first_part
                            title = remaining
                        elif _is_compilation_like_album(folder_album) and not _is_generic_artist_name(first_part):
                            artist = first_part
                            title = remaining
                        else:
                            title = cleaned_filename
                else:
                    artist = first_part
                    title = remaining

    title = str(title or "").strip() or _strip_leading_track_tokens(filename)
    artist = str(artist or "").strip()
    folder_artist_is_generic = _is_generic_artist_name(folder_artist)
    folder_album_is_playlistish = (
        not folder_album
        or _is_compilation_like_album(folder_album)
        or _normalize_match_text(folder_album) in {"rock hits", "playlist", "playlists"}
        or _normalize_match_text(folder_album).startswith("playlist ")
        or _normalize_match_text(folder_album).startswith("playlists ")
    )
    if not artist and not _is_compilation_like_album(folder_album) and not folder_artist_is_generic:
        artist = folder_artist
    if _is_generic_artist_name(artist):
        artist = ""
    album = str(folder_album or "").strip()
    if folder_artist_is_generic and folder_album_is_playlistish and not extinf_text:
        album = ""
    parsed = f"{title} - {artist}" if artist else title
    return {
        "path": raw_path,
        "title": title,
        "artist": artist,
        "album": album,
        "recording_mbid": "",
        "parsed": parsed,
        "source": "m3u",
    }


def _parse_m3u_entries(file_path):
    encodings = ("utf-8-sig", "utf-8", "cp1252", "latin1")
    content = None
    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding) as handle:
                content = handle.readlines()
            break
        except UnicodeDecodeError:
            continue

    if content is None:
        raise ValueError("Could not read M3U file with any supported encoding")

    tracks = []
    pending_extinf = ""
    for raw_line in content:
        line = str(raw_line or "").strip()
        if not line:
            continue
        if line.upper().startswith("#EXTINF"):
            pending_extinf = line.split(",", 1)[1].strip() if "," in line else ""
            continue
        if line.startswith("#"):
            continue

        is_path_like = (
            "\\" in line
            or "/" in line
            or line.lower().startswith(("file://", "file-relative://", "./", ".\\"))
            or bool(re.match(r"^[a-zA-Z]:[\\/]", line))
        )
        if is_path_like:
            track = _parse_m3u_track_from_path(line, extinf_text=pending_extinf)
        else:
            text = pending_extinf or line
            title, artist = _parse_display_track_text(text, prefer_artist_first=bool(pending_extinf))
            title = str(title or "").strip()
            artist = str(artist or "").strip()
            track = {
                "path": None,
                "title": title,
                "artist": artist,
                "album": "",
                "recording_mbid": "",
                "parsed": f"{title} - {artist}" if artist else title,
                "source": "m3u",
            }
        pending_extinf = ""
        if track and track.get("title"):
            tracks.append(track)

    return tracks


# ============================================================================
# SECURE CREDENTIAL MANAGER - Multi-OS Production-Ready
# ============================================================================

class SecureCredentialManager:
    """
    Production-ready credential manager with multi-OS support.

    Backends (in order of preference):
    1. Windows: Windows Credential Manager (native, secure)
    2. macOS: Keychain (native, secure)
    3. Linux: Secret Service API (GNOME Keyring, KWallet)
    4. Fallback: AES-256 encrypted file (all platforms)

    Works with PyInstaller binaries on all platforms.
    """

    def __init__(self, app_name="Syncra"):
        self.app_name = app_name
        self.service_name = f"{app_name}_credentials"
        self.platform = platform.system()

        # Determine which backend to use
        self.backend = self._initialize_backend()
        logging.info(f"Credential storage backend: {self.backend}")

    def _initialize_backend(self):
        """Detect and initialize the best available backend"""

        # Try keyring library first (supports all platforms)
        try:
            import keyring
            # Test if keyring works
            keyring.get_keyring()
            return "keyring"
        except Exception as e:
            logging.warning(f"Keyring not available: {e}")

        # Fallback to encrypted file storage
        return "encrypted_file"

    def save_password(self, username, password):
        """Save password securely using the best available method"""
        if not password:
            return

        try:
            if self.backend == "keyring":
                import keyring
                keyring.set_password(self.service_name, username, password)
                logging.info(f"Password saved to system keyring for {username}")
            else:
                # Use encrypted file storage
                self._save_encrypted(username, password)
                logging.info(f"Password saved to encrypted storage for {username}")
        except Exception as e:
            logging.error(f"Failed to save password: {e}")
            # Emergency fallback to encrypted file
            try:
                self._save_encrypted(username, password)
            except Exception as fallback_error:
                logging.error(f"Fallback save also failed: {fallback_error}")

    def get_password(self, username):
        """Retrieve password securely"""
        if not username:
            return None

        try:
            if self.backend == "keyring":
                import keyring
                password = keyring.get_password(self.service_name, username)
                if password:
                    logging.info(f"Password retrieved from system keyring for {username}")
                return password
            else:
                # Use encrypted file storage
                password = self._load_encrypted(username)
                if password:
                    logging.info(f"Password retrieved from encrypted storage for {username}")
                return password
        except Exception as e:
            logging.error(f"Failed to retrieve password: {e}")
            # Try fallback
            try:
                return self._load_encrypted(username)
            except:
                return None

    def delete_password(self, username):
        """Delete stored password"""
        if not username:
            return

        try:
            if self.backend == "keyring":
                import keyring
                keyring.delete_password(self.service_name, username)
            else:
                self._delete_encrypted(username)
            logging.info(f"Password deleted for {username}")
        except Exception as e:
            logging.warning(f"Error deleting password: {e}")

    # ========================================================================
    # ENCRYPTED FILE STORAGE (Fallback for all platforms)
    # ========================================================================

    def _get_machine_key(self):
        """Generate a machine-specific encryption key"""
        # Use multiple machine-specific attributes for the key
        machine_id = f"{platform.node()}_{platform.machine()}_{platform.system()}"

        # Derive a key from machine ID using PBKDF2
        salt = b'Syncra_v2_machine_salt_2025'  # Static salt for this app version
        key = hashlib.pbkdf2_hmac('sha256', machine_id.encode(), salt, 100000)
        return key[:32]  # 256-bit key for AES-256

    def _get_credentials_file(self):
        """Get path to encrypted credentials file"""
        config_dir = os.path.dirname(os.path.abspath(CONFIG_FILE))
        return os.path.join(config_dir, ".credentials.enc")

    def _save_encrypted(self, username, password):
        """Save password to encrypted file using AES-256"""
        try:
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2

            # Generate encryption key from machine ID
            machine_key = self._get_machine_key()
            fernet = Fernet(base64.urlsafe_b64encode(machine_key))

            # Encrypt password
            encrypted_password = fernet.encrypt(password.encode()).decode()

            # Load existing credentials
            credentials_file = self._get_credentials_file()
            credentials = {}
            if os.path.exists(credentials_file):
                try:
                    with open(credentials_file, 'r') as f:
                        credentials = json.load(f)
                except:
                    pass

            # Store encrypted password
            credentials[username] = encrypted_password

            # Save to file with restricted permissions
            with open(credentials_file, 'w') as f:
                json.dump(credentials, f)

            # Set file permissions (read/write for owner only)
            if self.platform != "Windows":
                os.chmod(credentials_file, 0o600)

        except ImportError:
            # Cryptography not available, use base64 as last resort
            logging.warning("Cryptography library not available, using base64 encoding")
            credentials_file = self._get_credentials_file()
            credentials = {}
            if os.path.exists(credentials_file):
                try:
                    with open(credentials_file, 'r') as f:
                        credentials = json.load(f)
                except:
                    pass

            credentials[username] = base64.b64encode(password.encode()).decode()

            with open(credentials_file, 'w') as f:
                json.dump(credentials, f)

    def _load_encrypted(self, username):
        """Load password from encrypted file"""
        credentials_file = self._get_credentials_file()

        if not os.path.exists(credentials_file):
            return None

        try:
            with open(credentials_file, 'r') as f:
                credentials = json.load(f)

            encrypted_password = credentials.get(username)
            if not encrypted_password:
                return None

            try:
                from cryptography.fernet import Fernet

                # Generate decryption key from machine ID
                machine_key = self._get_machine_key()
                fernet = Fernet(base64.urlsafe_b64encode(machine_key))

                # Decrypt password
                password = fernet.decrypt(encrypted_password.encode()).decode()
                return password

            except ImportError:
                # Cryptography not available, assume base64
                logging.warning("Cryptography library not available, using base64 decoding")
                return base64.b64decode(encrypted_password.encode()).decode()

        except Exception as e:
            logging.error(f"Error loading encrypted password: {e}")
            return None

    def _delete_encrypted(self, username):
        """Delete password from encrypted file"""
        credentials_file = self._get_credentials_file()

        if not os.path.exists(credentials_file):
            return

        try:
            with open(credentials_file, 'r') as f:
                credentials = json.load(f)

            if username in credentials:
                del credentials[username]

                with open(credentials_file, 'w') as f:
                    json.dump(credentials, f)
        except Exception as e:
            logging.error(f"Error deleting encrypted password: {e}")


# Initialize global credential manager
credential_manager = SecureCredentialManager()
SYNC_CONFIG_FILE = "sync_config.json"
CACHE_FILE = "playlist_cache.json"
SPOTIFY_LOGGED_IN = False
SPOTIFY_USER_INFO = {}
SP_DC_COOKIE = ""
OAUTH_SERVER = None
OAUTH_RESULT = {}

# OAuth App Configuration (required for Spotify API restrictions introduced Dec 22, 2025)
# Default credentials for seamless user experience in binary distribution
SP_APP_CLIENT_ID = os.getenv("SP_APP_CLIENT_ID", "880ca2262b0447bd82e4ea0b17febc16")
SP_APP_CLIENT_SECRET = os.getenv("SP_APP_CLIENT_SECRET", "c91c4b70b6e0482ebec5b91bf869c420")
SP_APP_TOKENS_FILE = os.getenv("SP_APP_TOKENS_FILE", ".spotify_oauth_cache")

# OAuth app token cache
SP_CACHED_OAUTH_APP_TOKEN = None
SP_OAUTH_APP_TOKEN_EXPIRES_AT = 0

# Rate limiting for Spotify API calls
SPOTIFY_LAST_REQUEST_TIME = 0
SPOTIFY_REQUEST_MIN_INTERVAL = 0.5  # Minimum 500ms between requests

# PLAYLIST CACHE CLASS - DEFINED FIRST!
class PlaylistCache:
    def __init__(self):
        self.cache_data = {"playlists": {}, "last_updated": {}, "version": "1.0"}
        self.load_cache()
    
    def load_cache(self):
        try:
            if os.path.exists(CACHE_FILE):
                with open(CACHE_FILE, 'r') as f:
                    self.cache_data = json.load(f)
                logging.info("Playlist cache loaded successfully")
        except Exception as e:
            logging.error(f"Error loading cache: {str(e)}")
            self.cache_data = {"playlists": {}, "last_updated": {}, "version": "1.0"}
    
    def save_cache(self):
        try:
            with open(CACHE_FILE, 'w') as f:
                json.dump(self.cache_data, f, indent=2)
            logging.info("Playlist cache saved successfully")
        except Exception as e:
            logging.error(f"Error saving cache: {str(e)}")
    
    def get_playlist_data(self, playlist_id):
        return self.cache_data["playlists"].get(playlist_id, None)
    
    def set_playlist_data(self, playlist_id, track_count, tracks_data=None):
        self.cache_data["playlists"][playlist_id] = {
            "track_count": track_count,
            "tracks_data": tracks_data,
            "cached_at": datetime.now().isoformat()
        }
        self.cache_data["last_updated"][playlist_id] = datetime.now().isoformat()
        self.save_cache()
    
    def is_cached(self, playlist_id):
        return playlist_id in self.cache_data["playlists"]
    
    def get_track_count(self, playlist_id):
        data = self.get_playlist_data(playlist_id)
        return data.get("track_count", None) if data else None
    
    def clear_cache(self):
        self.cache_data = {"playlists": {}, "last_updated": {}, "version": "1.0"}
        self.save_cache()
    
    def remove_playlist(self, playlist_id):
        if playlist_id in self.cache_data["playlists"]:
            del self.cache_data["playlists"][playlist_id]
        if playlist_id in self.cache_data["last_updated"]:
            del self.cache_data["last_updated"][playlist_id]
        self.save_cache()

def resource_path(relative_path):
    """ Get the absolute path to a resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores the path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # If not running in a PyInstaller bundle, use the directory of the script
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def initialize_config():
    def _ensure_file(file_path, defaults, label):
        try:
            existing = {}
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as fh:
                    existing = json.load(fh)
            merged = deep_merge(defaults, existing)
            if merged != existing:
                with open(file_path, "w", encoding="utf-8") as fh:
                    json.dump(merged, fh, indent=4)
                logging.info(f"Initialized {label} with defaults and merged settings.")
            else:
                logging.info(f"{label} already exists.")
        except Exception as e:
            logging.error(f"Failed to initialize {label}: {str(e)}")

    _ensure_file(CONFIG_FILE, APP_CONFIG_DEFAULTS, CONFIG_FILE)
    _ensure_file(SYNC_CONFIG_FILE, SYNC_CONFIG_DEFAULTS, SYNC_CONFIG_FILE)
    _ensure_file(CACHE_FILE, CACHE_DEFAULTS, CACHE_FILE)

def setup_logging():
    # Use a directory where we're sure to have write permissions
    log_dir = tempfile.gettempdir()
    LOG_FILE = os.path.join(log_dir, "plex_playlist_manager.log")

    try:
        # Attempt to remove the existing log file
        if os.path.exists(LOG_FILE):
            os.remove(LOG_FILE)
    except PermissionError:
        # If we can't remove it, we'll append to it instead
        print(f"Unable to remove existing log file. Will append to {LOG_FILE}")
    except Exception as e:
        print(f"Unexpected error when trying to remove log file: {e}")

    try:
        # Configure logging
        logging.basicConfig(
            filename=LOG_FILE,
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Optionally, add a stream handler for console output
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(console_handler)

        logging.info(f"Logging started. Log file: {LOG_FILE}")
    except Exception as e:
        print(f"Failed to set up logging: {e}")
        # If we can't set up file logging, we'll log to console only
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        logging.warning("Logging to console only due to file access issues")

class FetchPlaylistsThread(QThread):
    progress_update = pyqtSignal(str, int)  # message, percentage
    playlists_fetched = pyqtSignal(list)  # playlists list
    error = pyqtSignal(str)

    def __init__(self, plex_server, playlist_cache, parent=None):
        super().__init__(parent)
        self.plex_server = plex_server
        self.playlist_cache = playlist_cache
        self.parent_window = parent

    def should_exclude_playlist(self, playlist):
        """Check if playlist should be excluded from operations (large system playlists)"""
        try:
            # Get cached track count if available
            playlist_id = str(playlist.ratingKey)
            cached_count = self.playlist_cache.get_track_count(playlist_id)
            
            # Exclude by name patterns (case insensitive)
            exclude_names = [
                'all music', 'allmusic', 'all songs', 'library', 'entire library',
                'complete library', 'full library', 'music library',
                'recently added', 'recently played'  # Added these
            ]
            
            playlist_title_lower = playlist.title.lower()
            for exclude_name in exclude_names:
                if exclude_name in playlist_title_lower:
                    logging.info(f"Excluding playlist '{playlist.title}' during fetch - matches exclude pattern '{exclude_name}'")
                    return True
            
            # Exclude by size if cached (over 10,000 tracks is likely a system playlist)
            if cached_count and cached_count > 10000:
                logging.info(f"Excluding playlist '{playlist.title}' during fetch - too large ({cached_count} tracks)")
                return True
            
            return False
            
        except Exception as e:
            logging.error(f"Error checking playlist exclusion during fetch: {str(e)}")
            return False

    def run(self):
        try:
            self.progress_update.emit("Connecting to Plex server...", 10)
            
            # Fetch playlists (just basic info, no track counts)
            self.progress_update.emit("Fetching playlist list...", 30)
            all_playlists = self.plex_server.playlists()
            
            self.progress_update.emit("Filtering playlists...", 50)
            
            # Filter out massive/system playlists
            filtered_playlists = []
            excluded_count = 0
            
            for playlist in all_playlists:
                if self.should_exclude_playlist(playlist):
                    excluded_count += 1
                    continue
                filtered_playlists.append(playlist)
            
            # Prepare playlist data with cached track counts for filtered playlists only
            playlist_data = []
            
            self.progress_update.emit("Preparing playlist data...", 70)
            
            for playlist in filtered_playlists:
                # Check if we have cached track count - convert ratingKey to string
                playlist_id = str(playlist.ratingKey)
                cached_count = self.playlist_cache.get_track_count(playlist_id)
                playlist_data.append((playlist, cached_count))
            
            self.progress_update.emit("Finalizing...", 95)
            
            if excluded_count > 0:
                logging.info(f"Excluded {excluded_count} large/system playlists during fetch")
            
            self.playlists_fetched.emit(playlist_data)
            
        except Exception as e:
            logging.error(f"Error fetching playlists: {str(e)}")
            self.error.emit(str(e))

class LoadTrackCountThread(QThread):
    track_count_loaded = pyqtSignal(str, int)  # playlist_id, track_count
    error = pyqtSignal(str, str)  # playlist_id, error_message
    progress_update = pyqtSignal(str, int)  # message, percentage

    def __init__(self, playlist, playlist_cache, parent=None):
        super().__init__(parent)
        self.playlist = playlist
        self.playlist_cache = playlist_cache

    def run(self):
        try:
            playlist_id = str(self.playlist.ratingKey)
            
            # Emit progress updates
            self.progress_update.emit(f"Loading tracks for '{self.playlist.title}'...", 25)
            
            # Get track count for this specific playlist
            self.progress_update.emit("Counting tracks...", 50)
            tracks = list(self.playlist.items())
            track_count = len(tracks)
            
            self.progress_update.emit("Caching results...", 75)
            # Cache the result - convert ratingKey to string
            self.playlist_cache.set_playlist_data(playlist_id, track_count)
            
            self.progress_update.emit("Complete!", 100)
            # Emit the result - make sure playlist_id is string
            self.track_count_loaded.emit(playlist_id, track_count)
            
        except Exception as e:
            logging.error(f"Error loading track count for {self.playlist.title}: {str(e)}")
            # Convert ratingKey to string for error signal too
            playlist_id = str(self.playlist.ratingKey)
            self.error.emit(playlist_id, str(e))

class LoadPlaylistTracksThread(QThread):
    progress_update = pyqtSignal(int, int)  # current, total
    tracks_loaded = pyqtSignal(list)  # tracks list
    error = pyqtSignal(str)

    def __init__(self, playlist, parent=None):
        super().__init__(parent)
        self.playlist = playlist
        self.stop_requested = False

    def run(self):
        try:
            # Emit initial progress
            self.progress_update.emit(0, 0)

            # Fetch playlist items off the UI thread. We cannot get true incremental
            # progress from Plex here, so do not add a fake per-track loop that slows
            # the dialog down.
            tracks = list(self.playlist.items())
            if self.stop_requested:
                return
            total_tracks = len(tracks)
            row_payloads = []
            for index, track in enumerate(tracks, start=1):
                if self.stop_requested:
                    return
                row_payloads.append(_build_playlist_editor_row(track))
                if index == 1 or index % 25 == 0 or index == total_tracks:
                    self.progress_update.emit(index, total_tracks)

            self.tracks_loaded.emit(row_payloads)

        except Exception as e:
            logging.error(f"Error loading tracks: {str(e)}")
            self.error.emit(str(e))

    def stop(self):
        self.stop_requested = True

class BackupThread(QThread):
    progress_update = pyqtSignal(str, int)  # message, percentage
    backup_complete = pyqtSignal(int, str)  # backed_up_count, backup_folder
    error = pyqtSignal(str)

    def __init__(self, plex_server, backup_dir, parent=None):
        super().__init__(parent)
        self.plex_server = plex_server
        self.backup_dir = backup_dir

    def run(self):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_folder = os.path.join(self.backup_dir, f"plex_playlists_backup_{timestamp}")
            os.makedirs(backup_folder, exist_ok=True)
            
            playlists = self.plex_server.playlists()
            backed_up = 0
            total_playlists = len(playlists)
            
            for i, playlist in enumerate(playlists):
                try:
                    # Update progress
                    self.progress_update.emit(f"Backing up: {playlist.title}...", 
                                            int((i / total_playlists) * 100))
                    
                    # Sanitize the playlist name for filename
                    safe_name = playlist.title
                    # Basic sanitization for backup thread
                    invalid_chars = ['/', '\\', ':', '*', '?', '"', '<', '>', '|']
                    for char in invalid_chars:
                        safe_name = safe_name.replace(char, '_')
                    safe_name = safe_name.strip().rstrip('.')
                    if not safe_name:
                        safe_name = "Unnamed_Playlist"
                    filename = f"{safe_name}.m3u"
                    filepath = os.path.join(backup_folder, filename)
                    
                    with open(filepath, "w", encoding="utf-8") as file:
                        file.write("#EXTM3U\n")
                        file.write(f"# Playlist: {playlist.title}\n")
                        file.write(f"# Backup Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        for item in playlist.items():
                            try:
                                artist = item.originalTitle or (item.artist().title if hasattr(item, 'artist') and item.artist() else "Unknown Artist")
                                file.write(f"#EXTINF:-1,{item.title} - {artist}\n")
                                file.write(f"{item.title} - {artist}\n")
                            except Exception as track_error:
                                logging.warning(f"Error backing up track: {str(track_error)}")
                                continue
                    
                    backed_up += 1
                    
                except Exception as playlist_error:
                    logging.error(f"Error backing up playlist {playlist.title}: {str(playlist_error)}")
                    continue
            
            self.backup_complete.emit(backed_up, backup_folder)
            
        except Exception as e:
            logging.error(f"Error during backup: {str(e)}")
            self.error.emit(str(e))


class PortableBackupThread(QThread):
    progress_update = pyqtSignal(str, int)  # message, percentage
    log_update = pyqtSignal(str)
    backup_complete = pyqtSignal(dict)  # backup summary
    error = pyqtSignal(str)

    def __init__(
        self,
        plex_server,
        destination_dir,
        playlist_ids=None,
        include_m3u=True,
        m3u_beside_media=True,
        write_manifest=True,
        dedupe_tracks=True,
        organize_by_playlist=True,
        preserve_server_hierarchy=False,
        create_zip=False,
        parent=None,
    ):
        super().__init__(parent)
        self.plex_server = plex_server
        self.destination_dir = destination_dir
        self.playlist_ids = set(str(pid) for pid in (playlist_ids or []))
        self.include_m3u = bool(include_m3u)
        self.m3u_beside_media = bool(m3u_beside_media)
        self.write_manifest = bool(write_manifest)
        self.dedupe_tracks = bool(dedupe_tracks)
        self.organize_by_playlist = bool(organize_by_playlist)
        self.preserve_server_hierarchy = bool(preserve_server_hierarchy)
        self.create_zip = bool(create_zip)
        self._stop_requested = False
        self._section_locations_cache = {}

    def stop(self):
        self._stop_requested = True

    def _sanitize_name(self, value, max_length=120):
        cleaned = str(value or "").strip()
        if not cleaned:
            return "Untitled"
        replacements = {
            "/": "_",
            "\\": "_",
            ":": " -",
            "*": "",
            "?": "",
            '"': "'",
            "<": "(",
            ">": ")",
            "|": "-",
            "\n": " ",
            "\r": " ",
            "\t": " ",
        }
        for bad, repl in replacements.items():
            cleaned = cleaned.replace(bad, repl)
        cleaned = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip().rstrip(".")
        if not cleaned:
            cleaned = "Untitled"
        return cleaned[:max_length]

    def _ensure_unique_relpath(self, rel_path, used_paths):
        base, ext = os.path.splitext(rel_path)
        candidate = rel_path
        idx = 2
        while os.path.normcase(candidate) in used_paths:
            candidate = f"{base}_{idx}{ext}"
            idx += 1
        return candidate

    def _extract_track_file_path(self, track):
        try:
            media_items = getattr(track, "media", None) or []
            for media in media_items:
                parts = getattr(media, "parts", None) or []
                for part in parts:
                    file_path = str(getattr(part, "file", "") or "").strip()
                    if file_path:
                        return file_path
        except Exception:
            return ""
        return ""

    def _track_artist(self, track):
        artist = str(getattr(track, "originalTitle", "") or "").strip()
        if artist:
            return artist
        try:
            artist_obj = track.artist() if hasattr(track, "artist") else None
            if artist_obj:
                return str(getattr(artist_obj, "title", "") or "").strip() or "Unknown Artist"
        except Exception:
            pass
        return "Unknown Artist"

    def _download_track_from_plex(self, track, temp_dir):
        os.makedirs(temp_dir, exist_ok=True)
        # Use Plex-generated filename/container to avoid odd source filenames on remote servers.
        downloaded = track.download(savepath=temp_dir, keep_original_name=False)
        if not downloaded:
            return ""
        for path in downloaded:
            if path and os.path.exists(path):
                return path
        return ""

    def _emit_log(self, message):
        self.log_update.emit(message)

    def _normalize_path_for_compare(self, value):
        return str(value or "").strip().replace("\\", "/").rstrip("/").lower()

    def _get_track_section_locations(self, track):
        section_id = getattr(track, "librarySectionID", None)
        if section_id is None:
            return []
        cache_key = str(section_id)
        if cache_key in self._section_locations_cache:
            return self._section_locations_cache[cache_key]
        locations = []
        try:
            section = self.plex_server.library.sectionByID(section_id)
            raw_locations = list(getattr(section, "locations", []) or [])
            locations = [str(loc or "").strip() for loc in raw_locations if str(loc or "").strip()]
        except Exception:
            locations = []
        self._section_locations_cache[cache_key] = locations
        return locations

    def _build_preserved_relative_path(self, track, source_path):
        source_path = str(source_path or "").strip()
        if not source_path:
            return ""

        source_cmp = self._normalize_path_for_compare(source_path)
        matched_prefix = ""
        matched_prefix_cmp = ""
        for location in self._get_track_section_locations(track):
            location_cmp = self._normalize_path_for_compare(location)
            if not location_cmp:
                continue
            exact_match = source_cmp == location_cmp
            child_match = source_cmp.startswith(location_cmp + "/")
            if exact_match or child_match:
                if len(location_cmp) > len(matched_prefix_cmp):
                    matched_prefix = location
                    matched_prefix_cmp = location_cmp

        rel_raw = source_path
        if matched_prefix:
            rel_raw = source_path[len(matched_prefix):].lstrip("\\/")
        else:
            rel_raw = re.sub(r"^[a-zA-Z]:[\\/]*", "", rel_raw)
            rel_raw = rel_raw.lstrip("\\/")

        if not rel_raw:
            rel_raw = os.path.basename(source_path)
        parts = [self._sanitize_name(part, max_length=170) for part in re.split(r"[\\/]+", rel_raw) if part]
        parts = [part for part in parts if part]
        if not parts:
            return ""
        return os.path.join("media", *parts)

    def _build_backup_rel_candidate(self, track, source_path, playlist_folder_rel, fallback_filename):
        if self.preserve_server_hierarchy and source_path:
            preserved = self._build_preserved_relative_path(track, source_path)
            if preserved:
                return preserved
        safe_name = self._sanitize_name(fallback_filename, max_length=170)
        return os.path.join(playlist_folder_rel, safe_name)

    def run(self):
        try:
            if not self.destination_dir:
                raise ValueError("Select a destination folder first.")

            os.makedirs(self.destination_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_folder = os.path.join(self.destination_dir, f"syncra_portable_backup_{timestamp}")
            media_root = os.path.join(backup_folder, "media")
            playlists_root = os.path.join(backup_folder, "playlists")
            os.makedirs(media_root, exist_ok=True)
            if self.include_m3u:
                os.makedirs(playlists_root, exist_ok=True)

            self.progress_update.emit("Loading playlists from Plex...", 2)
            all_playlists = list(self.plex_server.playlists())
            if self.playlist_ids:
                selected = [p for p in all_playlists if str(getattr(p, "ratingKey", "") or "") in self.playlist_ids]
            else:
                selected = all_playlists
            if not selected:
                raise ValueError("No playlists selected for portable backup.")

            selected_payload = []
            total_tracks = 0
            total_playlists = len(selected)
            for idx, playlist in enumerate(selected, start=1):
                if self._stop_requested:
                    raise RuntimeError("Portable backup cancelled.")
                self.progress_update.emit(
                    f"Reading playlist {idx}/{total_playlists}: {playlist.title}",
                    min(8, 2 + int((idx / max(total_playlists, 1)) * 6)),
                )
                items = list(playlist.items())
                selected_payload.append((playlist, items))
                total_tracks += len(items)

            copied_files = 0
            copied_bytes = 0
            deduped_refs = 0
            remote_downloaded = 0
            missing_tracks = 0
            failed_tracks = 0
            processed_tracks = 0
            source_map = {}
            used_rel_paths = set()
            backup_playlists = []

            manifest = {
                "version": "1.0",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "backup_folder": backup_folder,
                "settings": {
                    "include_m3u": self.include_m3u,
                    "m3u_beside_media": self.m3u_beside_media,
                    "write_manifest": self.write_manifest,
                    "dedupe_tracks": self.dedupe_tracks,
                    "organize_by_playlist": self.organize_by_playlist,
                    "preserve_server_hierarchy": self.preserve_server_hierarchy,
                    "create_zip": self.create_zip,
                },
                "summary": {},
                "playlists": backup_playlists,
            }

            for playlist_idx, (playlist, items) in enumerate(selected_payload, start=1):
                if self._stop_requested:
                    raise RuntimeError("Portable backup cancelled.")
                playlist_title = str(getattr(playlist, "title", "Unnamed Playlist") or "Unnamed Playlist")
                safe_playlist_name = self._sanitize_name(playlist_title)
                playlist_folder_rel = os.path.join("media", safe_playlist_name) if self.organize_by_playlist else "media"

                self._emit_log(f"Processing playlist {playlist_idx}/{total_playlists}: {playlist_title} ({len(items)} tracks)")
                playlist_manifest = {
                    "title": playlist_title,
                    "track_count": len(items),
                    "copied_tracks": 0,
                    "deduped_tracks": 0,
                    "missing_tracks": 0,
                    "failed_tracks": 0,
                    "m3u_file": "",
                    "tracks": [],
                }
                m3u_lines = [
                    "#EXTM3U",
                    f"# Playlist: {playlist_title}",
                    f"# Backup Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                ]
                if self.include_m3u and self.m3u_beside_media and self.organize_by_playlist and not self.preserve_server_hierarchy:
                    m3u_dir_abs = os.path.join(backup_folder, playlist_folder_rel)
                    m3u_dir_rel = playlist_folder_rel
                else:
                    m3u_dir_abs = playlists_root
                    m3u_dir_rel = "playlists"
                if self.include_m3u:
                    os.makedirs(m3u_dir_abs, exist_ok=True)

                for track in items:
                    processed_tracks += 1
                    title = str(getattr(track, "title", "") or "Unknown Title")
                    artist = self._track_artist(track)
                    album = str(getattr(track, "parentTitle", "") or "")
                    duration_ms = int(getattr(track, "duration", 0) or 0)
                    rating_key = str(getattr(track, "ratingKey", "") or "").strip()

                    source_path = self._extract_track_file_path(track)
                    track_entry = {
                        "title": title,
                        "artist": artist,
                        "album": album,
                        "duration_ms": duration_ms,
                        "source_path": source_path,
                        "backup_path": "",
                        "status": "pending",
                    }

                    backup_rel_path = ""
                    dedupe_key = ""
                    if source_path:
                        dedupe_key = f"path:{os.path.normcase(os.path.normpath(source_path))}"
                    elif rating_key:
                        dedupe_key = f"rk:{rating_key}"

                    if self.dedupe_tracks and dedupe_key and dedupe_key in source_map:
                        backup_rel_path = source_map[dedupe_key]
                        deduped_refs += 1
                        playlist_manifest["deduped_tracks"] += 1
                        track_entry["status"] = "deduped"
                    else:
                        file_copied = False
                        if source_path and os.path.exists(source_path):
                            base_name = os.path.basename(source_path) or f"{artist} - {title}.audio"
                            rel_candidate = self._build_backup_rel_candidate(track, source_path, playlist_folder_rel, base_name)
                            rel_candidate = self._ensure_unique_relpath(rel_candidate, used_rel_paths)
                            backup_rel_path = rel_candidate
                            backup_abs_path = os.path.join(backup_folder, backup_rel_path)
                            os.makedirs(os.path.dirname(backup_abs_path), exist_ok=True)
                            try:
                                shutil.copy2(source_path, backup_abs_path)
                                file_copied = True
                                copied_files += 1
                                copied_bytes += int(os.path.getsize(backup_abs_path))
                                used_rel_paths.add(os.path.normcase(backup_rel_path))
                                playlist_manifest["copied_tracks"] += 1
                                track_entry["status"] = "copied_local"
                            except Exception as copy_error:
                                self._emit_log(f"Local copy failed, trying remote: {title} - {artist} | {copy_error}")

                        if not file_copied:
                            temp_download_dir = os.path.join(backup_folder, "_tmp_downloads")
                            try:
                                downloaded_file = self._download_track_from_plex(track, temp_download_dir)
                                if downloaded_file:
                                    base_name = os.path.basename(downloaded_file)
                                    rel_candidate = self._build_backup_rel_candidate(track, source_path, playlist_folder_rel, base_name)
                                    rel_candidate = self._ensure_unique_relpath(rel_candidate, used_rel_paths)
                                    backup_rel_path = rel_candidate
                                    backup_abs_path = os.path.join(backup_folder, backup_rel_path)
                                    os.makedirs(os.path.dirname(backup_abs_path), exist_ok=True)
                                    shutil.move(downloaded_file, backup_abs_path)
                                    file_copied = True
                                    copied_files += 1
                                    remote_downloaded += 1
                                    copied_bytes += int(os.path.getsize(backup_abs_path))
                                    used_rel_paths.add(os.path.normcase(backup_rel_path))
                                    playlist_manifest["copied_tracks"] += 1
                                    track_entry["status"] = "copied_remote"
                                else:
                                    if source_path:
                                        missing_tracks += 1
                                        playlist_manifest["missing_tracks"] += 1
                                        track_entry["status"] = "missing_file"
                                    else:
                                        missing_tracks += 1
                                        playlist_manifest["missing_tracks"] += 1
                                        track_entry["status"] = "missing_source_path"
                            except Exception as remote_error:
                                failed_tracks += 1
                                playlist_manifest["failed_tracks"] += 1
                                track_entry["status"] = f"remote_download_failed: {remote_error}"
                                backup_rel_path = ""
                                self._emit_log(f"Remote download failed: {title} - {artist} | {remote_error}")

                        if file_copied and self.dedupe_tracks and dedupe_key:
                            source_map[dedupe_key] = backup_rel_path
                        elif file_copied and self.dedupe_tracks and not dedupe_key and rating_key:
                            source_map[f"rk:{rating_key}"] = backup_rel_path

                        if not file_copied and not track_entry["status"].startswith(("missing_", "remote_download_failed")):
                            failed_tracks += 1
                            playlist_manifest["failed_tracks"] += 1
                            track_entry["status"] = "copy_failed"
                            backup_rel_path = ""
                            self._emit_log(f"Failed to back up track: {title} - {artist}")

                    if backup_rel_path:
                        backup_rel_path = backup_rel_path.replace("\\", "/")
                        track_entry["backup_path"] = backup_rel_path
                        if self.include_m3u:
                            m3u_track_path = os.path.relpath(
                                os.path.join(backup_folder, backup_rel_path.replace("/", os.sep)),
                                m3u_dir_abs,
                            ).replace("\\", "/")
                            m3u_lines.append(f"#EXTINF:-1,{artist} - {title}")
                            m3u_lines.append(m3u_track_path)
                    playlist_manifest["tracks"].append(track_entry)

                    if total_tracks > 0:
                        progress = 10 + int((processed_tracks / total_tracks) * 85)
                    else:
                        progress = 95
                    self.progress_update.emit(
                        f"Copying media files ({processed_tracks}/{max(total_tracks, 1)})...",
                        min(progress, 95),
                    )

                if self.include_m3u:
                    m3u_name = f"{safe_playlist_name}.m3u"
                    m3u_counter = 2
                    while os.path.exists(os.path.join(m3u_dir_abs, m3u_name)):
                        m3u_name = f"{safe_playlist_name}_{m3u_counter}.m3u"
                        m3u_counter += 1
                    m3u_abs = os.path.join(m3u_dir_abs, m3u_name)
                    with open(m3u_abs, "w", encoding="utf-8") as m3u_file:
                        m3u_file.write("\n".join(m3u_lines) + "\n")
                    playlist_manifest["m3u_file"] = os.path.join(m3u_dir_rel, m3u_name).replace("\\", "/")
                backup_playlists.append(playlist_manifest)

            temp_download_dir = os.path.join(backup_folder, "_tmp_downloads")
            if os.path.isdir(temp_download_dir):
                try:
                    shutil.rmtree(temp_download_dir, ignore_errors=True)
                except Exception:
                    pass

            manifest["summary"] = {
                "playlists": total_playlists,
                "tracks_total": total_tracks,
                "files_copied": copied_files,
                "remote_downloaded": remote_downloaded,
                "deduped_references": deduped_refs,
                "missing_tracks": missing_tracks,
                "failed_tracks": failed_tracks,
                "bytes_copied": copied_bytes,
            }

            manifest_path = ""
            if self.write_manifest:
                manifest_path = os.path.join(backup_folder, "backup_manifest.json")
                with open(manifest_path, "w", encoding="utf-8") as manifest_file:
                    json.dump(manifest, manifest_file, indent=2)

            zip_path = ""
            if self.create_zip:
                self.progress_update.emit("Creating ZIP archive...", 97)
                zip_path = f"{backup_folder}.zip"
                with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                    for root, _, files in os.walk(backup_folder):
                        for filename in files:
                            abs_file = os.path.join(root, filename)
                            arc_name = os.path.relpath(abs_file, backup_folder)
                            zf.write(abs_file, arc_name)

            self.progress_update.emit("Portable backup complete.", 100)
            self.backup_complete.emit(
                {
                    "backup_folder": backup_folder,
                    "manifest_path": manifest_path,
                    "zip_path": zip_path,
                    "playlists": total_playlists,
                    "tracks_total": total_tracks,
                    "files_copied": copied_files,
                    "remote_downloaded": remote_downloaded,
                    "deduped_references": deduped_refs,
                    "missing_tracks": missing_tracks,
                    "failed_tracks": failed_tracks,
                    "bytes_copied": copied_bytes,
                }
            )
        except Exception as e:
            logging.error(f"Portable backup failed: {e}")
            self.error.emit(str(e))


class PortableBackupPlaylistLoadThread(QThread):
    progress_update = pyqtSignal(str, int)
    playlists_loaded = pyqtSignal(list)  # [{"id": str, "title": str, "count": int}]
    error = pyqtSignal(str)

    def __init__(self, plex_server, parent=None):
        super().__init__(parent)
        self.plex_server = plex_server

    def run(self):
        try:
            self.progress_update.emit("Loading playlists...", 5)
            playlists = list(self.plex_server.playlists())
            total = len(playlists)
            payload = []
            for idx, playlist in enumerate(playlists, start=1):
                title = str(getattr(playlist, "title", "Untitled") or "Untitled")
                playlist_id = str(getattr(playlist, "ratingKey", "") or "")
                leaf_count = getattr(playlist, "leafCount", None)
                try:
                    count = int(leaf_count) if leaf_count is not None else 0
                except Exception:
                    count = 0
                payload.append({"id": playlist_id, "title": title, "count": count})
                progress = 5 + int((idx / max(total, 1)) * 95)
                self.progress_update.emit(f"Loading playlists... ({idx}/{total})", min(progress, 100))
            self.playlists_loaded.emit(payload)
        except Exception as e:
            self.error.emit(str(e))


class PortableBackupDialog(QDialog):
    def __init__(self, plex_server, parent=None):
        super().__init__(parent)
        self.plex_server = plex_server
        self.backup_thread = None
        self.playlist_load_thread = None
        self.last_backup_folder = ""
        self.last_zip_path = ""
        self._build_ui()
        self._load_playlists()

    def _build_ui(self):
        self.setWindowTitle("Portable Backup - Playlists + Audio")
        self.resize(940, 680)
        self.setModal(True)

        layout = QVBoxLayout(self)

        header = QLabel("Portable Backup")
        header.setStyleSheet("font-size: 20px; font-weight: 700; color: #f5f7fb;")
        layout.addWidget(header)

        subtitle = QLabel("Back up playlist files and copy the actual audio files to a portable folder.")
        subtitle.setStyleSheet("color: #a8b9cf;")
        layout.addWidget(subtitle)

        scope_group = QGroupBox("Scope")
        scope_layout = QVBoxLayout(scope_group)

        scope_row = QHBoxLayout()
        self.scope_all_radio = QRadioButton("All playlists")
        self.scope_selected_radio = QRadioButton("Selected playlists only")
        self.scope_all_radio.setChecked(True)
        self.scope_all_radio.toggled.connect(self._update_scope_state)
        self.scope_selected_radio.toggled.connect(self._update_scope_state)
        scope_row.addWidget(self.scope_all_radio)
        scope_row.addWidget(self.scope_selected_radio)
        scope_row.addStretch()
        self.refresh_playlists_btn = ModernButton("Refresh")
        self.refresh_playlists_btn.clicked.connect(self._load_playlists)
        scope_row.addWidget(self.refresh_playlists_btn)
        scope_layout.addLayout(scope_row)

        picker_row = QHBoxLayout()
        self.playlist_list = QListWidget()
        self.playlist_list.setMinimumHeight(180)
        picker_row.addWidget(self.playlist_list, 1)
        picker_actions = QVBoxLayout()
        self.select_all_btn = ModernButton("Select All")
        self.select_all_btn.clicked.connect(self._select_all_playlists)
        self.select_none_btn = ModernButton("Select None")
        self.select_none_btn.clicked.connect(self._select_no_playlists)
        picker_actions.addWidget(self.select_all_btn)
        picker_actions.addWidget(self.select_none_btn)
        picker_actions.addStretch()
        picker_row.addLayout(picker_actions)
        scope_layout.addLayout(picker_row)
        layout.addWidget(scope_group)

        destination_group = QGroupBox("Destination")
        destination_layout = QHBoxLayout(destination_group)
        self.destination_input = QLineEdit()
        self.destination_input.setPlaceholderText("Select backup destination folder...")
        destination_layout.addWidget(self.destination_input, 1)
        self.browse_btn = ModernButton("Browse")
        self.browse_btn.clicked.connect(self._browse_destination)
        destination_layout.addWidget(self.browse_btn)
        layout.addWidget(destination_group)

        options_group = QGroupBox("Options")
        options_layout = QGridLayout(options_group)
        self.include_m3u_cb = QCheckBox("Include M3U playlist files")
        self.include_m3u_cb.setChecked(True)
        self.m3u_beside_media_cb = QCheckBox("Write M3U beside playlist media (portable)")
        self.m3u_beside_media_cb.setChecked(True)
        self.write_manifest_cb = QCheckBox("Create backup_manifest.json")
        self.write_manifest_cb.setChecked(True)
        self.dedupe_cb = QCheckBox("Deduplicate shared tracks across playlists")
        self.dedupe_cb.setChecked(True)
        self.organize_playlist_cb = QCheckBox("Organize copied files by playlist folder")
        self.organize_playlist_cb.setChecked(True)
        self.preserve_hierarchy_cb = QCheckBox("Preserve server folder hierarchy (relative to library root)")
        self.preserve_hierarchy_cb.setChecked(False)
        self.include_m3u_cb.toggled.connect(self._sync_option_states)
        self.organize_playlist_cb.toggled.connect(self._sync_option_states)
        self.preserve_hierarchy_cb.toggled.connect(self._sync_option_states)
        self.create_zip_cb = QCheckBox("Create ZIP archive after backup")
        self.create_zip_cb.setChecked(False)
        options_layout.addWidget(self.include_m3u_cb, 0, 0)
        options_layout.addWidget(self.m3u_beside_media_cb, 0, 1)
        options_layout.addWidget(self.write_manifest_cb, 1, 0)
        options_layout.addWidget(self.dedupe_cb, 1, 1)
        options_layout.addWidget(self.preserve_hierarchy_cb, 2, 0)
        options_layout.addWidget(self.organize_playlist_cb, 2, 1)
        options_layout.addWidget(self.create_zip_cb, 3, 1)
        layout.addWidget(options_group)

        progress_group = QGroupBox("Progress")
        progress_layout = QVBoxLayout(progress_group)
        self.progress_label = QLabel("Ready.")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(160)
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addWidget(self.log_text)
        layout.addWidget(progress_group)

        button_row = QHBoxLayout()
        self.open_folder_btn = ModernButton("Open Backup Folder")
        self.open_folder_btn.clicked.connect(self._open_last_backup_folder)
        self.open_folder_btn.setEnabled(False)
        button_row.addWidget(self.open_folder_btn)
        self.open_zip_btn = ModernButton("Open ZIP")
        self.open_zip_btn.clicked.connect(self._open_last_zip)
        self.open_zip_btn.setEnabled(False)
        button_row.addWidget(self.open_zip_btn)
        button_row.addStretch()
        self.start_btn = ModernButton("Start Portable Backup")
        self.start_btn.clicked.connect(self._start_backup)
        button_row.addWidget(self.start_btn)
        self.close_btn = ModernButton("Close")
        self.close_btn.clicked.connect(self.reject)
        button_row.addWidget(self.close_btn)
        layout.addLayout(button_row)

        self._update_scope_state()
        self._sync_option_states()

    def _load_playlists(self):
        if self.playlist_load_thread and self.playlist_load_thread.isRunning():
            return
        self.playlist_list.clear()
        self._set_playlist_loading_state(True, "Loading playlists...")
        self._append_log("Loading playlists...")
        self.playlist_load_thread = PortableBackupPlaylistLoadThread(self.plex_server, self)
        self.playlist_load_thread.progress_update.connect(self._on_playlist_load_progress)
        self.playlist_load_thread.playlists_loaded.connect(self._on_playlists_loaded)
        self.playlist_load_thread.error.connect(self._on_playlists_error)
        self.playlist_load_thread.finished.connect(self._on_playlists_load_finished)
        self.playlist_load_thread.start()

    def _update_scope_state(self):
        selected_mode = self.scope_selected_radio.isChecked()
        self.playlist_list.setEnabled(selected_mode)
        self.select_all_btn.setEnabled(selected_mode)
        self.select_none_btn.setEnabled(selected_mode)

    def _select_all_playlists(self):
        for idx in range(self.playlist_list.count()):
            self.playlist_list.item(idx).setCheckState(Qt.CheckState.Checked)

    def _select_no_playlists(self):
        for idx in range(self.playlist_list.count()):
            self.playlist_list.item(idx).setCheckState(Qt.CheckState.Unchecked)

    def _browse_destination(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Backup Destination")
        if folder:
            self.destination_input.setText(folder)

    def _append_log(self, message):
        stamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.append(f"[{stamp}] {message}")

    def _sync_option_states(self):
        include_m3u = self.include_m3u_cb.isChecked()
        organize = self.organize_playlist_cb.isChecked()
        preserve = self.preserve_hierarchy_cb.isChecked()
        if preserve and self.m3u_beside_media_cb.isChecked():
            self.m3u_beside_media_cb.setChecked(False)
        self.m3u_beside_media_cb.setEnabled(
            include_m3u
            and organize
            and not preserve
            and not (self.backup_thread and self.backup_thread.isRunning())
        )

    def _set_playlist_loading_state(self, loading, message=None):
        self.refresh_playlists_btn.setEnabled(not loading and not (self.backup_thread and self.backup_thread.isRunning()))
        self.scope_all_radio.setEnabled(not loading and not (self.backup_thread and self.backup_thread.isRunning()))
        self.scope_selected_radio.setEnabled(not loading and not (self.backup_thread and self.backup_thread.isRunning()))
        self.playlist_list.setEnabled(not loading and self.scope_selected_radio.isChecked() and not (self.backup_thread and self.backup_thread.isRunning()))
        self.select_all_btn.setEnabled(not loading and self.scope_selected_radio.isChecked() and not (self.backup_thread and self.backup_thread.isRunning()))
        self.select_none_btn.setEnabled(not loading and self.scope_selected_radio.isChecked() and not (self.backup_thread and self.backup_thread.isRunning()))
        self.start_btn.setEnabled(not loading and not (self.backup_thread and self.backup_thread.isRunning()))
        if message:
            self.progress_label.setText(message)

    def _on_playlist_load_progress(self, message, percentage):
        self.progress_label.setText(message)
        self.progress_bar.setValue(max(0, min(100, int(percentage))))

    def _on_playlists_loaded(self, playlists):
        self.playlist_list.clear()
        for playlist in playlists:
            title = str(playlist.get("title", "Untitled") or "Untitled")
            playlist_id = str(playlist.get("id", "") or "")
            count = int(playlist.get("count", 0) or 0)
            item = QListWidgetItem(f"{title} ({count} tracks)")
            item.setData(Qt.ItemDataRole.UserRole, playlist_id)
            item.setCheckState(Qt.CheckState.Checked)
            self.playlist_list.addItem(item)
        self._append_log(f"Loaded {len(playlists)} playlists.")
        self.progress_label.setText("Ready.")
        self.progress_bar.setValue(0)

    def _on_playlists_error(self, message):
        self._append_log(f"Failed to load playlists: {message}")
        self.progress_label.setText("Failed to load playlists.")

    def _on_playlists_load_finished(self):
        self.playlist_load_thread = None
        self._set_playlist_loading_state(False, "Ready.")
        self._update_scope_state()

    def _selected_playlist_ids(self):
        ids = []
        for idx in range(self.playlist_list.count()):
            item = self.playlist_list.item(idx)
            if item.checkState() == Qt.CheckState.Checked:
                playlist_id = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
                if playlist_id:
                    ids.append(playlist_id)
        return ids

    def _set_running_state(self, running):
        self.scope_all_radio.setEnabled(not running)
        self.scope_selected_radio.setEnabled(not running)
        self.refresh_playlists_btn.setEnabled(not running and not (self.playlist_load_thread and self.playlist_load_thread.isRunning()))
        self.select_all_btn.setEnabled(not running and self.scope_selected_radio.isChecked())
        self.select_none_btn.setEnabled(not running and self.scope_selected_radio.isChecked())
        self.playlist_list.setEnabled(not running and self.scope_selected_radio.isChecked() and not (self.playlist_load_thread and self.playlist_load_thread.isRunning()))
        self.destination_input.setEnabled(not running)
        self.browse_btn.setEnabled(not running)
        self.include_m3u_cb.setEnabled(not running)
        self.m3u_beside_media_cb.setEnabled(not running and self.include_m3u_cb.isChecked() and self.organize_playlist_cb.isChecked())
        self.write_manifest_cb.setEnabled(not running)
        self.dedupe_cb.setEnabled(not running)
        self.preserve_hierarchy_cb.setEnabled(not running)
        self.organize_playlist_cb.setEnabled(not running)
        self.create_zip_cb.setEnabled(not running)
        self.start_btn.setEnabled(not running)
        self.close_btn.setEnabled(not running)
        self._sync_option_states()

    def _start_backup(self):
        if self.playlist_load_thread and self.playlist_load_thread.isRunning():
            QMessageBox.information(self, "Loading Playlists", "Please wait for playlists to finish loading.")
            return
        destination = self.destination_input.text().strip()
        if not destination:
            QMessageBox.warning(self, "Missing Destination", "Select a destination folder first.")
            return
        playlist_ids = []
        if self.scope_selected_radio.isChecked():
            playlist_ids = self._selected_playlist_ids()
            if not playlist_ids:
                QMessageBox.warning(self, "No Playlists Selected", "Select at least one playlist to back up.")
                return

        self.progress_label.setText("Starting portable backup...")
        self.progress_bar.setValue(0)
        self._append_log("Starting portable backup job...")
        self.last_backup_folder = ""
        self.last_zip_path = ""
        self.open_folder_btn.setEnabled(False)
        self.open_zip_btn.setEnabled(False)

        self.backup_thread = PortableBackupThread(
            plex_server=self.plex_server,
            destination_dir=destination,
            playlist_ids=playlist_ids,
            include_m3u=self.include_m3u_cb.isChecked(),
            m3u_beside_media=self.m3u_beside_media_cb.isChecked(),
            write_manifest=self.write_manifest_cb.isChecked(),
            dedupe_tracks=self.dedupe_cb.isChecked(),
            organize_by_playlist=self.organize_playlist_cb.isChecked(),
            preserve_server_hierarchy=self.preserve_hierarchy_cb.isChecked(),
            create_zip=self.create_zip_cb.isChecked(),
            parent=self,
        )
        self.backup_thread.progress_update.connect(self._on_progress_update)
        self.backup_thread.log_update.connect(self._append_log)
        self.backup_thread.backup_complete.connect(self._on_backup_complete)
        self.backup_thread.error.connect(self._on_backup_error)
        self.backup_thread.finished.connect(self._on_backup_finished)

        self._set_running_state(True)
        self.backup_thread.start()

    def _on_progress_update(self, message, percentage):
        self.progress_label.setText(message)
        self.progress_bar.setValue(max(0, min(100, int(percentage))))

    def _on_backup_complete(self, result):
        self.last_backup_folder = str(result.get("backup_folder", "") or "")
        self.last_zip_path = str(result.get("zip_path", "") or "")
        self.open_folder_btn.setEnabled(bool(self.last_backup_folder and os.path.exists(self.last_backup_folder)))
        self.open_zip_btn.setEnabled(bool(self.last_zip_path and os.path.exists(self.last_zip_path)))

        self._append_log(
            f"Complete: {result.get('files_copied', 0)} files copied "
            f"({result.get('remote_downloaded', 0)} remote), "
            f"{result.get('missing_tracks', 0)} missing, {result.get('failed_tracks', 0)} failed."
        )
        summary = (
            f"Portable backup complete.\n\n"
            f"Playlists: {result.get('playlists', 0)}\n"
            f"Tracks scanned: {result.get('tracks_total', 0)}\n"
            f"Audio files copied: {result.get('files_copied', 0)}\n"
            f"Downloaded from server: {result.get('remote_downloaded', 0)}\n"
            f"Deduped references: {result.get('deduped_references', 0)}\n"
            f"Missing files: {result.get('missing_tracks', 0)}\n"
            f"Failed copies: {result.get('failed_tracks', 0)}\n\n"
            f"Folder:\n{self.last_backup_folder}"
        )
        if self.last_zip_path:
            summary += f"\n\nZIP:\n{self.last_zip_path}"
        QMessageBox.information(self, "Portable Backup Complete", summary)

    def _on_backup_error(self, message):
        self._append_log(f"Error: {message}")
        QMessageBox.critical(self, "Portable Backup Error", message)

    def _on_backup_finished(self):
        self._set_running_state(False)
        self.backup_thread = None

    def _open_last_backup_folder(self):
        if self.last_backup_folder and os.path.exists(self.last_backup_folder):
            webbrowser.open(Path(self.last_backup_folder).resolve().as_uri())

    def _open_last_zip(self):
        if self.last_zip_path and os.path.exists(self.last_zip_path):
            webbrowser.open(Path(self.last_zip_path).resolve().as_uri())

    def closeEvent(self, event):
        if self.playlist_load_thread and self.playlist_load_thread.isRunning():
            QMessageBox.information(self, "Loading Playlists", "Please wait for playlist loading to finish.")
            event.ignore()
            return
        if self.backup_thread and self.backup_thread.isRunning():
            QMessageBox.information(self, "Backup Running", "Wait for the portable backup to finish before closing this window.")
            event.ignore()
            return
        super().closeEvent(event)

class BatchTrackCountThread(QThread):
    progress_update = pyqtSignal(str, int)  # message, percentage
    all_complete = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, playlists, playlist_cache, max_concurrent=3, parent=None):
        super().__init__(parent)
        self.playlists = playlists
        self.playlist_cache = playlist_cache
        self.max_concurrent = max_concurrent
        self.stop_requested = False


    def run(self):
        try:
            total_playlists = len(self.playlists)
            completed = 0

            for playlist, cached_count in self.playlists:
                if self.stop_requested:
                    break

                playlist_id = str(playlist.ratingKey)
                try:
                    if cached_count is None and not self.playlist_cache.is_cached(playlist_id):
                        track_count = len(list(playlist.items()))
                        self.playlist_cache.set_playlist_data(playlist_id, track_count)
                except Exception as playlist_error:
                    logging.warning(f"Failed to load track count for {playlist.title}: {playlist_error}")

                completed += 1
                progress = int((completed / max(total_playlists, 1)) * 100)
                self.progress_update.emit(
                    f"Loading track counts... ({completed}/{total_playlists})",
                    progress,
                )
            
            self.all_complete.emit()
            
        except Exception as e:
            logging.error(f"Error in batch track count loading: {str(e)}")
            self.error.emit(str(e))

    def stop(self):
        self.stop_requested = True

class ExportThread(QThread):
    progress_update = pyqtSignal(str, int)  # message, percentage
    export_complete = pyqtSignal(int)  # number of exported playlists
    error = pyqtSignal(str)

    def __init__(self, playlists_to_export, export_dir, parent=None):
        super().__init__(parent)
        self.playlists_to_export = playlists_to_export
        self.export_dir = export_dir

    def run(self):
        try:
            exported_count = 0
            total_playlists = len(self.playlists_to_export)
            
            for i, playlist in enumerate(self.playlists_to_export):
                try:
                    # Update progress
                    self.progress_update.emit(f"Exporting playlist: {playlist.title}...", 
                                            int((i / total_playlists) * 100))
                    
                    # Export the playlist
                    safe_name = self.parent_window.sanitize_filename(playlist.title) if hasattr(self, 'parent_window') else playlist.title.replace('/', '_').replace('\\', '_')
                    filename = f"{safe_name}.m3u"
                    filepath = os.path.join(self.export_dir, filename)
                    
                    with open(filepath, "w", encoding="utf-8") as file:
                        file.write("#EXTM3U\n")
                        file.write(f"# Exported from Plex on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        for item in playlist.items():
                            try:
                                # Use the actual file path from Plex, not just track info
                                for part in item.iterParts():
                                    if hasattr(part, 'file') and part.file:
                                        # Write the full file path as it was before
                                        file.write(f"{part.file}\n")
                                        break
                                else:
                                    # Fallback: if no file path available, use track info
                                    artist = item.originalTitle or (item.artist().title if hasattr(item, 'artist') and item.artist() else "Unknown Artist")
                                    file.write(f"#EXTINF:-1,{item.title} - {artist}\n")
                                    file.write(f"{item.title} - {artist}\n")
                            except Exception as e:
                                logging.warning(f"Error exporting track: {str(e)}")
                                continue
                    
                    exported_count += 1
                    
                except Exception as playlist_error:
                    logging.error(f"Error exporting playlist {playlist.title}: {str(playlist_error)}")
                    continue
            
            self.export_complete.emit(exported_count)
            
        except Exception as e:
            logging.error(f"Error during export: {str(e)}")
            self.error.emit(str(e))

class ListenBrainzPlaylistLoadThread(QThread):
    progress_update = pyqtSignal(str, int)  # message, percentage
    playlists_loaded = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, username, token, parent=None):
        super().__init__(parent)
        self.username = (username or "").strip()
        self.token = (token or "").strip()

    def run(self):
        try:
            self.progress_update.emit("Connecting to ListenBrainz...", 10)
            client = ListenBrainzClient(token=self.token or None)
            self.progress_update.emit("Fetching playlists...", 45)
            playlists = client.list_user_playlists(self.username)

            needs_count = [
                p for p in playlists
                if p.get("playlist_id") and (
                    not isinstance(p.get("track_count"), int) or int(p.get("track_count", 0)) <= 0
                )
            ]
            total_needs = len(needs_count)
            for idx, playlist in enumerate(needs_count, start=1):
                title = playlist.get("title") or "Untitled"
                pct = 45 + int((idx / max(total_needs, 1)) * 45)
                self.progress_update.emit(
                    f"Fetching track counts ({idx}/{total_needs}): {title}",
                    min(pct, 92),
                )
                try:
                    playlist_id = playlist.get("playlist_id")
                    track_count = client.get_playlist_track_count(playlist_id)
                    if isinstance(track_count, int):
                        playlist["track_count"] = track_count
                except Exception as count_error:
                    logging.debug(f"Could not fetch track count for playlist '{title}': {count_error}")

            self.progress_update.emit("Preparing playlist list...", 96)
            self.playlists_loaded.emit(playlists)
        except Exception as e:
            logging.error(f"Error loading ListenBrainz playlists (thread): {str(e)}")
            self.error.emit(str(e))

class ListenBrainzExportThread(QThread):
    progress_update = pyqtSignal(str, int)  # message, percentage
    export_complete = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, playlist, token, username, track_builder, parent=None):
        super().__init__(parent)
        self.playlist = playlist
        self.token = (token or "").strip()
        self.username = (username or "").strip()
        self.track_builder = track_builder

    def run(self):
        try:
            if not self.playlist:
                raise ValueError("No playlist selected for ListenBrainz export.")
            if not self.token:
                raise ValueError("ListenBrainz token is required for export.")

            self.progress_update.emit("Loading playlist tracks...", 5)
            playlist_items = list(self.playlist.items())
            total_items = len(playlist_items)
            if total_items == 0:
                raise ValueError("Selected playlist has no tracks.")

            tracks = []
            skipped_missing_mbid = 0
            skipped_missing_title = 0
            guid_resolved_count = 0
            search_resolved_count = 0
            mbid_cache = {}

            for idx, item in enumerate(playlist_items, start=1):
                title = (getattr(item, "title", None) or "Unknown Track").strip()
                pct = 5 + int((idx / total_items) * 80)
                self.progress_update.emit(f"Resolving MBIDs ({idx}/{total_items}): {title}", pct)
                track_entry, mbid_source = self.track_builder(item, mbid_cache)
                if track_entry:
                    tracks.append(track_entry)
                    if mbid_source == "plex_guid":
                        guid_resolved_count += 1
                    elif mbid_source == "musicbrainz_search":
                        search_resolved_count += 1
                else:
                    if mbid_source == "missing_title":
                        skipped_missing_title += 1
                    else:
                        skipped_missing_mbid += 1

            if not tracks:
                raise ValueError(
                    "This playlist has no tracks with MusicBrainz recording MBIDs. "
                    "ListenBrainz export requires MBID-based identifiers."
                )

            self.progress_update.emit("Creating ListenBrainz playlist...", 92)
            playlist_jspf = {
                "title": self.playlist.title,
                "creator": self.username or "Syncra",
                "annotation": f"Exported from Syncra at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "track": tracks,
                "extension": {"https://musicbrainz.org/doc/jspf#playlist": {"public": True}},
            }

            client = ListenBrainzClient(token=self.token)
            created = client.create_playlist(playlist_jspf)
            playlist_id = created.get("playlist_id")
            playlist_url = f"https://listenbrainz.org/playlist/{playlist_id}" if playlist_id else "Unknown URL"

            self.progress_update.emit("Finalizing export...", 100)
            self.export_complete.emit(
                {
                    "playlist_title": self.playlist.title,
                    "exported_count": len(tracks),
                    "playlist_url": playlist_url,
                    "skipped_missing_mbid": skipped_missing_mbid,
                    "skipped_missing_title": skipped_missing_title,
                    "guid_resolved_count": guid_resolved_count,
                    "search_resolved_count": search_resolved_count,
                }
            )
        except Exception as e:
            logging.error(f"ListenBrainz export thread error: {str(e)}")
            self.error.emit(str(e))

class LibraryDuplicateFinderThread(QThread):
    progress_update = pyqtSignal(str, int)  # message, percentage
    duplicates_found = pyqtSignal(list)  # duplicate groups list
    error = pyqtSignal(str)

    def __init__(self, plex_server, parent=None):
        super().__init__(parent)
        self.plex_server = plex_server
        self.include_playlist_check = True  # Default to checking playlists

    def normalize_track_signature(self, track):
        """Create a normalized signature for duplicate detection"""
        try:
            title = track.title.lower().strip() if track.title else ""
            artist = ""

            if track.artist():
                artist = track.artist().title.lower().strip()
            elif hasattr(track, 'originalTitle') and track.originalTitle:
                artist = track.originalTitle.lower().strip()

            # Clean up common variations
            title = title.replace("(", "").replace(")", "").replace("[", "").replace("]", "")
            title = title.replace("feat.", "").replace("ft.", "").replace("featuring", "")
            artist = artist.replace("(", "").replace(")", "").replace("[", "").replace("]", "")

            # Remove extra whitespace
            title = " ".join(title.split())
            artist = " ".join(artist.split())

            return f"{artist}|||{title}".lower()

        except Exception as e:
            logging.debug(f"Error normalizing track signature: {e}")
            return f"unknown|||{track.title or 'unknown'}".lower()

    def get_track_playlists(self, track):
        """Find which playlists contain this track"""
        playlists_containing_track = []
        try:
            # This is expensive but necessary for comprehensive playlist checking
            for playlist in self.plex_server.playlists():
                try:
                    if playlist.playlistType != 'audio':
                        continue
                    playlist_items = playlist.items()
                    for item in playlist_items:
                        if item.ratingKey == track.ratingKey:
                            playlists_containing_track.append(playlist.title)
                            break
                except:
                    continue
        except Exception as e:
            logging.debug(f"Error checking playlists for track: {e}")

        return playlists_containing_track

    def run(self):
        try:
            self.progress_update.emit("Scanning music library for duplicates...", 5)

            # Get music library sections
            music_sections = []
            for section in self.plex_server.library.sections():
                if section.type == 'artist':  # Music library
                    music_sections.append(section)

            if not music_sections:
                self.error.emit("No music libraries found on Plex server")
                return

            self.progress_update.emit("Loading all tracks from music library...", 10)

            # Collect all tracks from all music sections
            all_tracks = []
            for section in music_sections:
                try:
                    section_tracks = section.searchTracks()
                    all_tracks.extend(section_tracks)
                    self.progress_update.emit(f"Loaded {len(all_tracks)} tracks so far...", 15)
                except Exception as e:
                    logging.warning(f"Error loading tracks from section {section.title}: {e}")

            if not all_tracks:
                self.error.emit("No tracks found in music library")
                return

            self.progress_update.emit(f"Analyzing {len(all_tracks)} tracks for duplicates...", 20)

            # Group tracks by signature for duplicate detection
            track_groups = {}
            processed = 0

            for track in all_tracks:
                try:
                    signature = self.normalize_track_signature(track)
                    if signature not in track_groups:
                        track_groups[signature] = []

                    # Store detailed track info
                    track_info = {
                        'track': track,
                        'title': track.title or "Unknown Title",
                        'artist': track.artist().title if track.artist() else "Unknown Artist",
                        'album': track.album().title if track.album() else "Unknown Album",
                        'duration': getattr(track, 'duration', 0),
                        'bitrate': getattr(track, 'bitrate', 0),
                        'file_path': track.media[0].parts[0].file if track.media and track.media[0].parts else "Unknown Path",
                        'file_size': track.media[0].parts[0].size if track.media and track.media[0].parts else 0,
                        'rating_key': track.ratingKey,
                        'playlists': []  # Will be populated later for duplicates
                    }

                    track_groups[signature].append(track_info)

                    processed += 1
                    if processed % 100 == 0:
                        progress = 20 + (processed / len(all_tracks)) * 50
                        self.progress_update.emit(f"Processed {processed}/{len(all_tracks)} tracks...", int(progress))

                except Exception as e:
                    logging.debug(f"Error processing track: {e}")
                    continue

            self.progress_update.emit("Identifying duplicate groups...", 70)

            # Filter to only duplicate groups (groups with more than 1 track)
            duplicate_groups = []
            for signature, tracks in track_groups.items():
                if len(tracks) > 1:
                    duplicate_groups.append(tracks)

            if not duplicate_groups:
                self.duplicates_found.emit([])
                return

            # Conditionally check playlist usage
            if self.include_playlist_check:
                self.progress_update.emit("Checking playlist usage for duplicates...", 80)

                # For duplicate tracks, check which playlists they're in
                total_duplicates = sum(len(group) for group in duplicate_groups)
                checked = 0

                for group in duplicate_groups:
                    for track_info in group:
                        try:
                            track_info['playlists'] = self.get_track_playlists(track_info['track'])
                            checked += 1
                            if checked % 10 == 0:
                                progress = 80 + (checked / total_duplicates) * 15
                                self.progress_update.emit(f"Checked playlists for {checked}/{total_duplicates} duplicate tracks...", int(progress))
                        except Exception as e:
                            logging.debug(f"Error checking playlists for duplicate: {e}")
                            track_info['playlists'] = []

                self.progress_update.emit("Duplicate scan completed!", 100)
            else:
                # Skip playlist checking for faster scan
                for group in duplicate_groups:
                    for track_info in group:
                        track_info['playlists'] = []  # Empty playlist list

                self.progress_update.emit("Duplicate scan completed! (Playlists not checked for faster scanning)", 100)

            self.duplicates_found.emit(duplicate_groups)

        except Exception as e:
            logging.error(f"Error in library duplicate finding thread: {str(e)}")
            self.error.emit(str(e))

class PlaylistTrackTable(QTableWidget):
    """Table widget that supports safe drag-and-drop row reordering."""

    rows_reordered = pyqtSignal(int, int)  # from_row, to_row

    def __init__(self, parent=None):
        super().__init__(parent)
        self._drag_row = -1
        self._drag_track_id = None
        self._drag_row_items = []
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDrop)

    def startDrag(self, supportedActions):
        self._drag_row = self.currentRow()
        if self._drag_row < 0:
            return

        self._drag_row_items = []
        for col in range(self.columnCount()):
            item = self.item(self._drag_row, col)
            self._drag_row_items.append(item.clone() if item else None)

        title_item = self.item(self._drag_row, 0)
        self._drag_track_id = title_item.data(Qt.UserRole) if title_item else None

        drag = QDrag(self)
        mime_data = self.mimeData(self.selectedItems())
        drag.setMimeData(mime_data)
        drag.exec(Qt.MoveAction)

    def dropEvent(self, event):
        if self._drag_row < 0 or not self._drag_row_items:
            event.ignore()
            return

        drop_point = event.position().toPoint() if hasattr(event, "position") else event.pos()
        drop_row = self.rowAt(drop_point.y())
        if drop_row == -1:
            drop_row = self.rowCount() - 1
        drop_row = max(0, min(drop_row, self.rowCount() - 1))

        row_data = self._drag_row_items
        from_row = self._drag_row

        if drop_row == from_row:
            event.accept()
            self.selectRow(drop_row)
            self._drag_row = -1
            self._drag_track_id = None
            self._drag_row_items = []
            return

        self.removeRow(from_row)
        if drop_row > from_row:
            drop_row -= 1
        drop_row = max(0, min(drop_row, self.rowCount()))

        self.insertRow(drop_row)
        for col, item in enumerate(row_data):
            if item is not None:
                new_item = item.clone()
                if col == 0 and self._drag_track_id is not None:
                    new_item.setData(Qt.UserRole, self._drag_track_id)
                self.setItem(drop_row, col, new_item)
            else:
                self.setItem(drop_row, col, QTableWidgetItem(''))

        event.accept()

        if from_row != drop_row:
            self.rows_reordered.emit(from_row, drop_row)

        self.selectRow(drop_row)

        self._drag_row = -1
        self._drag_track_id = None
        self._drag_row_items = []


class LoadingDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Loading...")
        self.setModal(True)
        self.setFixedSize(350, 155)
        self.setWindowFlags(Qt.Dialog | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self._cancel_callback = None
        
        layout = QVBoxLayout(self)
        
        self.message_label = QLabel("Please wait...")
        self.message_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.message_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        
        self.detail_label = QLabel("")
        self.detail_label.setAlignment(Qt.AlignCenter)
        self.detail_label.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(self.detail_label)

        button_row = QHBoxLayout()
        button_row.addStretch()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self._handle_cancel_clicked)
        button_row.addWidget(self.cancel_button)
        button_row.addStretch()
        layout.addLayout(button_row)
    
    def update_progress(self, message, percentage):
        self.message_label.setText(message)
        self.progress_bar.setValue(percentage)
        if percentage < 100:
            self.detail_label.setText(f"{percentage}% complete")
        else:
            self.detail_label.setText("Almost done...")

    def configure_cancel(self, callback=None, visible=False, button_text="Cancel"):
        self._cancel_callback = callback
        self.cancel_button.setText(button_text)
        self.cancel_button.setVisible(bool(visible))

    def _handle_cancel_clicked(self):
        if callable(self._cancel_callback):
            self._cancel_callback()


class PlexServerPlaylistLoadThread(QThread):
    progress_update = pyqtSignal(str, int)
    playlists_loaded = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, profile, parent=None):
        super().__init__(parent)
        self.profile = profile or {}

    def run(self):
        try:
            profile_name = str(self.profile.get("name", "Source server") or "Source server").strip()
            base_url = str(self.profile.get("base_url", "") or "").strip()
            token = str(self.profile.get("token", "") or "").strip()
            if not base_url or not token:
                raise ValueError("Selected server profile is missing base URL or token.")

            self.progress_update.emit(f"Connecting to {profile_name}...", 10)
            source_server = PlexServer(base_url, token)

            self.progress_update.emit("Loading source playlists...", 45)
            raw_playlists = list(source_server.playlists())

            payload = []
            total = max(len(raw_playlists), 1)
            for idx, playlist in enumerate(raw_playlists, start=1):
                title = str(getattr(playlist, "title", "") or "").strip()
                if not title:
                    continue
                payload.append(
                    {
                        "title": title,
                        "rating_key": str(getattr(playlist, "ratingKey", "") or ""),
                        "leaf_count": getattr(playlist, "leafCount", None),
                    }
                )
                pct = 45 + int((idx / total) * 45)
                self.progress_update.emit(f"Reading playlists ({idx}/{total})...", min(90, pct))

            payload.sort(key=lambda item: item.get("title", "").lower())
            self.progress_update.emit("Source playlists ready.", 100)
            self.playlists_loaded.emit(payload)
        except Exception as e:
            logging.error(f"Error loading source Plex playlists: {e}", exc_info=True)
            self.error.emit(str(e))


class PlexServerPlaylistTransferThread(QThread):
    progress_update = pyqtSignal(str, int)
    transfer_complete = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(
        self,
        source_profile,
        source_playlist_title,
        target_server,
        target_section_id,
        target_profile=None,
        target_section_title="",
        target_mode="overwrite",
        sync_policy="keep_extras",
        target_name_override=None,
        filter_settings=None,
        dry_run=False,
        parent=None,
    ):
        super().__init__(parent)
        self.source_profile = source_profile or {}
        self.source_playlist_title = str(source_playlist_title or "").strip()
        self.target_server = target_server
        self.target_section_id = target_section_id
        self.target_profile = target_profile or {}
        self.target_section_title = str(target_section_title or "").strip()
        self.target_mode = str(target_mode or "overwrite").strip().lower()
        self.sync_policy = str(sync_policy or "keep_extras").strip().lower()
        self.target_name_override = str(target_name_override or "").strip()
        self.filter_settings = filter_settings or {}
        self.dry_run = bool(dry_run)

    def _track_artist_name(self, track):
        artist_name = ""
        try:
            artist_name = (getattr(track, "originalTitle", "") or "").strip()
            if not artist_name and hasattr(track, "artist") and track.artist():
                artist_name = (track.artist().title or "").strip()
        except Exception:
            artist_name = ""
        if not artist_name:
            artist_name = (getattr(track, "grandparentTitle", "") or "").strip()
        return artist_name

    def _extract_recording_mbid_from_plex_track(self, plex_track):
        candidates = []
        guid_value = getattr(plex_track, "guid", None)
        if guid_value:
            candidates.append(str(guid_value))
        for guid_obj in getattr(plex_track, "guids", []) or []:
            guid_id = getattr(guid_obj, "id", None)
            if guid_id:
                candidates.append(str(guid_id))

        mbid_pattern = re.compile(
            r"(?:musicbrainz\.org/recording/|musicbrainz://recording/|recording/)([0-9a-fA-F-]{36})",
            re.IGNORECASE,
        )
        for value in candidates:
            match = mbid_pattern.search(value)
            if match:
                return match.group(1).lower()
        return ""

    def _build_source_track_identity(self, source_track):
        title = str(getattr(source_track, "title", "") or "").strip()
        artist = self._track_artist_name(source_track)
        album = ""
        try:
            if hasattr(source_track, "album") and source_track.album():
                album = str(source_track.album().title or "").strip()
        except Exception:
            album = ""

        return {
            "title": title,
            "artist": artist,
            "album": album,
            "recording_mbid": self._extract_recording_mbid_from_plex_track(source_track),
        }

    def _score_candidate(self, source_track, target_track):
        src_title = source_track.get("title", "")
        src_artist = source_track.get("artist", "")
        src_album = source_track.get("album", "")
        src_mbid = source_track.get("recording_mbid", "")

        target_title = str(getattr(target_track, "title", "") or "").strip()
        if not src_title or not target_title:
            return -1.0

        title_score = float(fuzz.token_set_ratio(src_title.lower(), target_title.lower()))
        if title_score < 50:
            return -1.0

        target_artist = self._track_artist_name(target_track)
        artist_score = float(fuzz.token_set_ratio(src_artist.lower(), target_artist.lower())) if (src_artist and target_artist) else 0.0

        target_album = ""
        try:
            if hasattr(target_track, "album") and target_track.album():
                target_album = str(target_track.album().title or "").strip()
        except Exception:
            target_album = ""
        album_score = float(fuzz.token_set_ratio(src_album.lower(), target_album.lower())) if (src_album and target_album) else 0.0

        if src_artist and src_album:
            combined_score = (title_score * 0.58) + (artist_score * 0.30) + (album_score * 0.12)
        elif src_artist:
            combined_score = (title_score * 0.68) + (artist_score * 0.32)
        else:
            combined_score = title_score

        if src_artist and artist_score < 40:
            combined_score -= 18
        if src_album and target_album and album_score < 35:
            combined_score -= 8

        if self.filter_settings.get("enabled", False):
            album_title = target_album.lower()
            penalty = 0
            if self.filter_settings.get("avoid_live", False) and any(k in album_title for k in ["live", "concert", "tour"]):
                penalty += 15
            if self.filter_settings.get("avoid_compilation", False) and any(k in album_title for k in ["best of", "greatest hits", "collection", "anthology"]):
                penalty += 12
            if self.filter_settings.get("deprioritize_remaster", False) and any(k in album_title for k in ["remaster", "remastered"]):
                penalty += 8
            if self.filter_settings.get("deprioritize_deluxe", False) and any(k in album_title for k in ["deluxe", "special", "extended", "expanded", "anniversary"]):
                penalty += 6
            combined_score = max(0.0, combined_score - penalty)

        if src_mbid:
            target_mbid = self._extract_recording_mbid_from_plex_track(target_track)
            if target_mbid and target_mbid == src_mbid:
                return 100.0

        return combined_score

    def _find_best_match(self, library_section, source_track):
        title = source_track.get("title", "")
        artist = source_track.get("artist", "")
        if not title:
            return None

        try:
            candidates = list(library_section.searchTracks(title=title) or [])
        except Exception:
            candidates = []
        if not candidates:
            return None

        best_track = None
        best_score = -1.0
        best_artist_score = 0.0
        for candidate in candidates:
            score = self._score_candidate(source_track, candidate)
            if score < 0:
                continue

            candidate_artist = self._track_artist_name(candidate)
            artist_score = float(fuzz.token_set_ratio(artist.lower(), candidate_artist.lower())) if (artist and candidate_artist) else 0.0
            if score > best_score:
                best_score = score
                best_track = candidate
                best_artist_score = artist_score

        if not best_track:
            return None

        min_score = 78.0 if artist else 90.0
        if best_score < min_score:
            return None
        if artist and best_artist_score < 40.0 and best_score < 100.0:
            return None
        return best_track

    def _find_playlist_by_title(self, server, title):
        for playlist in server.playlists():
            if str(getattr(playlist, "title", "") or "").strip().lower() == title.lower():
                return playlist
        return None

    def _resolve_target_name(self, target_server, requested_name):
        if self.target_mode == "overwrite":
            return requested_name

        # create_copy mode - find an available copy name
        existing = {str(getattr(p, "title", "") or "").strip().lower() for p in target_server.playlists()}
        if requested_name.lower() not in existing:
            return requested_name
        index = 1
        while True:
            candidate = f"{requested_name} (Copy {index})"
            if candidate.lower() not in existing:
                return candidate
            index += 1

    def _track_display(self, track):
        artist = self._track_artist_name(track)
        title = str(getattr(track, "title", "") or "Unknown Title").strip()
        if artist:
            return f"{artist} - {title}"
        return title

    def _dedupe_tracks(self, tracks):
        unique = []
        seen = set()
        for track in tracks:
            rating_key = str(getattr(track, "ratingKey", "") or "")
            if not rating_key:
                continue
            if rating_key in seen:
                continue
            seen.add(rating_key)
            unique.append(track)
        return unique

    def _build_final_tracks(self, existing_playlist, matched_tracks):
        existing_items = list(existing_playlist.items()) if existing_playlist else []
        matched_tracks = self._dedupe_tracks(matched_tracks)
        matched_key_set = {str(getattr(track, "ratingKey", "") or "") for track in matched_tracks}

        # Policy is only meaningful when overwriting an existing playlist.
        if not existing_playlist:
            return matched_tracks
        if self.sync_policy == "add_only":
            result = list(existing_items)
            existing_key_set = {str(getattr(track, "ratingKey", "") or "") for track in existing_items}
            for track in matched_tracks:
                key = str(getattr(track, "ratingKey", "") or "")
                if key and key not in existing_key_set:
                    result.append(track)
                    existing_key_set.add(key)
            return self._dedupe_tracks(result)
        if self.sync_policy == "mirror":
            return matched_tracks

        # keep_extras (default): source order first, then keep target extras.
        extras = [track for track in existing_items if str(getattr(track, "ratingKey", "") or "") not in matched_key_set]
        return self._dedupe_tracks(matched_tracks + extras)

    def _compute_diff(self, existing_playlist, final_tracks):
        existing_items = list(existing_playlist.items()) if existing_playlist else []
        final_tracks = self._dedupe_tracks(final_tracks)
        existing_keys = [str(getattr(track, "ratingKey", "") or "") for track in existing_items]
        final_keys = [str(getattr(track, "ratingKey", "") or "") for track in final_tracks]
        existing_set = set(existing_keys)
        final_set = set(final_keys)

        to_add = [track for track in final_tracks if str(getattr(track, "ratingKey", "") or "") not in existing_set]
        to_remove = [track for track in existing_items if str(getattr(track, "ratingKey", "") or "") not in final_set]
        will_reorder = bool(existing_items) and existing_keys != final_keys

        return {
            "will_add": len(to_add),
            "will_remove": len(to_remove),
            "will_reorder": will_reorder,
            "add_samples": [self._track_display(track) for track in to_add[:8]],
            "remove_samples": [self._track_display(track) for track in to_remove[:8]],
            "existing_count": len(existing_items),
        }

    def run(self):
        try:
            base_url = str(self.source_profile.get("base_url", "") or "").strip()
            token = str(self.source_profile.get("token", "") or "").strip()
            profile_name = str(self.source_profile.get("name", "Source server") or "Source server").strip()
            if not base_url or not token:
                raise ValueError("Source profile is missing base URL or token.")
            if not self.source_playlist_title:
                raise ValueError("No source playlist selected.")

            self.progress_update.emit(f"Connecting to source server '{profile_name}'...", 5)
            source_server = PlexServer(base_url, token)

            target_server = self.target_server
            if not target_server:
                target_base_url = str(self.target_profile.get("base_url", "") or "").strip()
                target_token = str(self.target_profile.get("token", "") or "").strip()
                target_name = str(self.target_profile.get("name", "Target server") or "Target server").strip()
                if not target_base_url or not target_token:
                    raise ValueError("Target profile is missing base URL or token.")
                self.progress_update.emit(f"Connecting to target server '{target_name}'...", 9)
                target_server = PlexServer(target_base_url, target_token)

            self.progress_update.emit("Resolving source playlist...", 12)
            source_playlist = self._find_playlist_by_title(source_server, self.source_playlist_title)
            if not source_playlist:
                raise ValueError(f"Source playlist '{self.source_playlist_title}' was not found.")

            source_tracks = list(source_playlist.items())
            total = len(source_tracks)
            if total == 0:
                raise ValueError("Selected source playlist has no tracks.")

            self.progress_update.emit("Preparing target library...", 18)
            try:
                target_section = target_server.library.sectionByID(self.target_section_id)
            except Exception:
                target_section = None
                if self.target_section_title:
                    for section in target_server.library.sections():
                        if str(getattr(section, "title", "") or "").strip().lower() == self.target_section_title.lower():
                            target_section = section
                            break
                if not target_section:
                    raise ValueError("Target library section was not found on target server.")

            matched_tracks = []
            seen_target_keys = set()
            missing_tracks = []
            for idx, source_track in enumerate(source_tracks, start=1):
                identity = self._build_source_track_identity(source_track)
                matched = self._find_best_match(target_section, identity)
                if matched:
                    rating_key = str(getattr(matched, "ratingKey", "") or "")
                    if rating_key and rating_key in seen_target_keys:
                        continue
                    if rating_key:
                        seen_target_keys.add(rating_key)
                    matched_tracks.append(matched)
                else:
                    display = f"{identity.get('artist', 'Unknown Artist')} - {identity.get('title', 'Unknown Title')}"
                    missing_tracks.append(display)

                progress = 18 + int((idx / max(total, 1)) * 72)
                self.progress_update.emit(f"Matching tracks ({idx}/{total})...", min(progress, 90))

            if not matched_tracks:
                raise ValueError("No matching tracks were found on the target server.")

            target_name = self.target_name_override or str(getattr(source_playlist, "title", "Imported Playlist") or "Imported Playlist")
            target_name = self._resolve_target_name(target_server, target_name)

            existing_target = self._find_playlist_by_title(target_server, target_name)
            final_tracks = matched_tracks
            if self.target_mode == "overwrite":
                final_tracks = self._build_final_tracks(existing_target, matched_tracks)
            diff = self._compute_diff(existing_target, final_tracks)

            if self.dry_run:
                self.progress_update.emit("Dry run complete.", 100)
                self.transfer_complete.emit(
                    {
                        "dry_run": True,
                        "source_playlist": self.source_playlist_title,
                        "target_playlist": target_name,
                        "target_exists": bool(existing_target),
                        "total_tracks": total,
                        "matched_tracks": len(matched_tracks),
                        "final_tracks": len(final_tracks),
                        "missing_tracks": len(missing_tracks),
                        "missing_samples": missing_tracks[:15],
                        "mode": self.target_mode,
                        "sync_policy": self.sync_policy,
                        **diff,
                    }
                )
                return

            if existing_target and self.target_mode == "overwrite":
                existing_items = list(existing_target.items())
                existing_keys = [str(getattr(track, "ratingKey", "") or "") for track in existing_items]
                final_keys = [str(getattr(track, "ratingKey", "") or "") for track in final_tracks]
                if existing_keys != final_keys:
                    self.progress_update.emit("Applying policy changes to target playlist...", 94)
                if existing_items:
                    existing_target.removeItems(existing_items)
                if final_tracks:
                    existing_target.addItems(final_tracks)
                created_playlist = existing_target
            else:
                self.progress_update.emit("Creating target playlist...", 97)
                created_playlist = target_server.createPlaylist(target_name, items=final_tracks)

            self.progress_update.emit("Transfer complete.", 100)
            self.transfer_complete.emit(
                {
                    "source_playlist": self.source_playlist_title,
                    "target_playlist": str(getattr(created_playlist, "title", target_name) or target_name),
                    "total_tracks": total,
                    "matched_tracks": len(matched_tracks),
                    "final_tracks": len(final_tracks),
                    "missing_tracks": len(missing_tracks),
                    "missing_samples": missing_tracks[:15],
                    "mode": self.target_mode,
                    "sync_policy": self.sync_policy,
                    **diff,
                }
            )
        except Exception as e:
            logging.error(f"Error transferring playlist between Plex servers: {e}", exc_info=True)
            self.error.emit(str(e))


class PlaylistCoverLoadThread(QThread):
    cover_loaded = pyqtSignal(bytes)
    error = pyqtSignal(str)

    def __init__(self, image_url, parent=None):
        super().__init__(parent)
        self.image_url = str(image_url or "").strip()

    def run(self):
        try:
            if not self.image_url:
                raise ValueError("No playlist cover URL available.")
            response = requests.get(
                self.image_url,
                headers={"User-Agent": f"Syncra/{__version__}"},
                timeout=25,
            )
            response.raise_for_status()
            self.cover_loaded.emit(response.content)
        except Exception as e:
            self.error.emit(str(e))


class PlaylistEditorDialog(QDialog):
    def __init__(self, playlist, plex_server, parent=None):
        super().__init__(parent)
        self.playlist = playlist
        self.plex_server = plex_server
        self.tracks_loaded = False
        self.tracks = []
        self.track_rows = []
        self.track_lookup = {}  # Maps identifiers to Plex track objects
        self.original_track_order = {}
        self.original_track_ids = []
        self.load_tracks_thread = None
        self.cover_load_thread = None
        self.pending_cover_path = ""
        self.current_cover_url = ""
        self.current_cover_is_custom = False
        self.highlight_duplicates_enabled = False
        self._allow_close_without_prompt = False
        self._pending_render_tracks = []
        self._render_cursor = 0
        self._render_batch_size = 60
        self._loading_started = False
        self.setWindowTitle(f"Edit Playlist: {playlist.title}")
        self.setObjectName("playlistEditorDialog")
        self.setModal(True)
        self.resize(980, 680)
        self.setMinimumSize(900, 620)
        self.setStyleSheet(self._dialog_stylesheet())
        
        # Setup UI immediately (non-blocking)
        self.setup_ui()
        self.load_cover_preview()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._loading_started:
            self._loading_started = True
            QTimer.singleShot(0, self.start_background_loading)

    def _dialog_stylesheet(self):
        return """
            QDialog#playlistEditorDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #121b2b, stop:1 #0f1828);
                border: 1px solid #344d70;
                border-radius: 10px;
            }
            QDialog#playlistEditorDialog QLabel#editorTitleLabel {
                font-weight: 750;
                font-size: 15px;
                color: #eaf2ff;
            }
            QDialog#playlistEditorDialog QLabel#editorTrackCount {
                color: #9db4d7;
                font-size: 13px;
            }
            QDialog#playlistEditorDialog QFrame#editorCoverCard {
                background-color: #152236;
                border: 1px solid #35527a;
                border-radius: 10px;
            }
            QDialog#playlistEditorDialog QLabel#editorCoverPreview {
                background-color: #0f1a2b;
                border: 1px solid #3a5a86;
                border-radius: 8px;
                color: #a8c0e1;
                font-size: 12px;
            }
            QDialog#playlistEditorDialog QLabel#editorCoverTitle {
                color: #dce9fb;
                font-size: 12px;
                font-weight: 700;
            }
            QDialog#playlistEditorDialog QLabel#editorCoverStatus {
                color: #a8c0e1;
                font-size: 11px;
            }
            QDialog#playlistEditorDialog QLabel#editorSearchLabel {
                color: #dbe7fb;
                font-weight: 650;
                font-size: 13px;
            }
            QDialog#playlistEditorDialog QLabel#editorLoadingLabel {
                color: #b6c9e6;
                font-size: 15px;
                font-weight: 700;
                padding: 6px 4px;
            }
            QDialog#playlistEditorDialog QLabel#editorLoadingSub {
                color: #8ca3c6;
                font-size: 12px;
                padding: 0 4px 8px 4px;
            }
            QDialog#playlistEditorDialog QLabel#editorLoadingDetail {
                color: #8ca3c6;
                font-size: 12px;
                padding: 8px;
            }
            QDialog#playlistEditorDialog QFrame#editorLoadingCard {
                background-color: #132136;
                border: 1px solid #355078;
                border-radius: 12px;
            }
            QDialog#playlistEditorDialog QProgressBar#editorLoadingProgress {
                background-color: #16243a;
                border: 1px solid #355078;
                border-radius: 8px;
                text-align: center;
                font-weight: 700;
                color: #d7e8ff;
                min-height: 24px;
            }
            QDialog#playlistEditorDialog QProgressBar#editorLoadingProgress::chunk {
                background-color: #2ed27a;
                border-radius: 7px;
            }
            QDialog#playlistEditorDialog QLineEdit#editorSearchInput {
                background-color: #18273c;
                border: 1px solid #3e577b;
                border-radius: 7px;
                padding: 8px 10px;
                color: #f2f7ff;
                font-size: 14px;
            }
            QDialog#playlistEditorDialog QLineEdit#editorSearchInput:focus {
                border: 1px solid #46a3ff;
            }
            QDialog#playlistEditorDialog QTableWidget#editorTracksTable {
                background-color: #16253a;
                color: #f3f8ff;
                gridline-color: #2f476a;
                border: 1px solid #36527a;
                border-radius: 8px;
                selection-background-color: #2d4f7a;
                selection-color: #ffffff;
            }
            QDialog#playlistEditorDialog QTableWidget#editorTracksTable::item {
                padding: 7px 10px;
                border-bottom: 1px solid #223754;
            }
            QDialog#playlistEditorDialog QTableWidget#editorTracksTable::item:selected {
                background-color: #2d5a8f;
                color: #ffffff;
            }
            QDialog#playlistEditorDialog QHeaderView::section {
                background: #213651;
                color: #e8f1ff;
                border: 1px solid #3a577f;
                padding: 8px;
                font-weight: 800;
            }
            QDialog#playlistEditorDialog QTableWidget#editorTracksTable QTableCornerButton::section {
                background: #213651;
                border: 1px solid #3a577f;
            }
            QDialog#playlistEditorDialog QPushButton#editorBtnNeutral {
                background-color: #22344f;
                border: 1px solid #476287;
                border-radius: 8px;
                color: #e0edff;
                font-weight: 700;
                padding: 8px 14px;
                min-height: 22px;
            }
            QDialog#playlistEditorDialog QPushButton#editorBtnNeutral:hover {
                background-color: #2a4468;
            }
            QDialog#playlistEditorDialog QPushButton#editorBtnNeutral:disabled {
                background-color: #1b2a42;
                border: 1px solid #334d71;
                color: #7890b0;
            }
            QDialog#playlistEditorDialog QPushButton#editorBtnPrimary {
                background-color: #2ed27a;
                border: 1px solid #2bc970;
                border-radius: 8px;
                color: #ffffff;
                font-weight: 800;
                padding: 8px 18px;
                min-height: 22px;
            }
            QDialog#playlistEditorDialog QPushButton#editorBtnPrimary:hover {
                background-color: #26bf6a;
            }
            QDialog#playlistEditorDialog QPushButton#editorBtnPrimary:disabled {
                background-color: #2b4f3d;
                border: 1px solid #3a7055;
                color: #9ec5ae;
            }
            QDialog#playlistEditorDialog QPushButton#editorBtnDanger {
                background-color: #ff4b47;
                border: 1px solid #f44c4a;
                border-radius: 8px;
                color: #ffffff;
                font-weight: 800;
                padding: 8px 18px;
                min-height: 22px;
            }
            QDialog#playlistEditorDialog QPushButton#editorBtnDanger:hover {
                background-color: #ef3f3c;
            }
        """
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Playlist info header
        info_layout = QHBoxLayout()
        self.editor_title_label = QLabel(f"Editing Playlist: {self.playlist.title}")
        self.editor_title_label.setObjectName("editorTitleLabel")
        info_layout.addWidget(self.editor_title_label)

        self.track_count_label = QLabel("Tracks: Loading...")
        self.track_count_label.setObjectName("editorTrackCount")
        info_layout.addWidget(self.track_count_label)
        info_layout.addStretch()
        layout.addLayout(info_layout)

        # Loading section (visible initially)
        self.loading_section = QWidget()
        loading_layout = QVBoxLayout(self.loading_section)
        loading_layout.setContentsMargins(0, 0, 0, 0)
        loading_layout.setSpacing(0)
        loading_layout.addStretch()

        loading_card = QFrame()
        loading_card.setObjectName("editorLoadingCard")
        loading_card_layout = QVBoxLayout(loading_card)
        loading_card_layout.setContentsMargins(18, 16, 18, 14)
        loading_card_layout.setSpacing(6)

        self.loading_label = QLabel("Preparing playlist editor...")
        self.loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_label.setObjectName("editorLoadingLabel")
        loading_card_layout.addWidget(self.loading_label)

        self.loading_sub = QLabel(f"Playlist: {self.playlist.title}")
        self.loading_sub.setObjectName("editorLoadingSub")
        self.loading_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_card_layout.addWidget(self.loading_sub)

        self.loading_progress = QProgressBar()
        self.loading_progress.setObjectName("editorLoadingProgress")
        self.loading_progress.setRange(0, 100)
        self.loading_progress.setValue(0)
        self.loading_progress.setFormat("%p%")
        loading_card_layout.addWidget(self.loading_progress)

        self.loading_detail = QLabel("Initializing...")
        self.loading_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_detail.setObjectName("editorLoadingDetail")
        loading_card_layout.addWidget(self.loading_detail)

        loading_actions_layout = QHBoxLayout()
        loading_actions_layout.addStretch()
        self.retry_loading_btn = QPushButton("Retry Loading")
        self.retry_loading_btn.setObjectName("editorBtnNeutral")
        self.retry_loading_btn.clicked.connect(self.retry_loading)
        self.retry_loading_btn.setVisible(False)
        loading_actions_layout.addWidget(self.retry_loading_btn)
        loading_actions_layout.addStretch()
        loading_card_layout.addLayout(loading_actions_layout)

        loading_layout.addWidget(loading_card, alignment=Qt.AlignmentFlag.AlignCenter)
        loading_layout.addStretch()

        layout.addWidget(self.loading_section)

        # Editor section (hidden initially)
        self.editor_section = QWidget()
        self.editor_section.setVisible(False)
        editor_layout = QVBoxLayout(self.editor_section)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(10)

        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(12)

        # Left cover/actions panel
        cover_card = QFrame()
        cover_card.setObjectName("editorCoverCard")
        cover_card.setFixedWidth(230)
        cover_layout = QVBoxLayout(cover_card)
        cover_layout.setContentsMargins(10, 10, 10, 10)
        cover_layout.setSpacing(8)

        cover_title = QLabel("Playlist Cover")
        cover_title.setObjectName("editorCoverTitle")
        cover_layout.addWidget(cover_title)

        self.cover_preview_label = QLabel("No cover")
        self.cover_preview_label.setObjectName("editorCoverPreview")
        self.cover_preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_preview_label.setMinimumSize(200, 200)
        self.cover_preview_label.setMaximumSize(200, 200)
        cover_layout.addWidget(self.cover_preview_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.cover_status_label = QLabel("Using current Plex cover.")
        self.cover_status_label.setObjectName("editorCoverStatus")
        self.cover_status_label.setWordWrap(True)
        cover_layout.addWidget(self.cover_status_label)

        self.change_cover_btn = QPushButton("Change Cover...")
        self.change_cover_btn.setObjectName("editorBtnNeutral")
        self.change_cover_btn.clicked.connect(self.choose_cover_image)
        self.change_cover_btn.setEnabled(False)
        cover_layout.addWidget(self.change_cover_btn)

        self.clear_cover_btn = QPushButton("Clear Pending Cover")
        self.clear_cover_btn.setObjectName("editorBtnNeutral")
        self.clear_cover_btn.clicked.connect(self.clear_pending_cover)
        self.clear_cover_btn.setEnabled(False)
        cover_layout.addWidget(self.clear_cover_btn)
        cover_layout.addStretch()

        body_layout.addWidget(cover_card)

        # Right tracks area
        tracks_panel = QWidget()
        tracks_layout = QVBoxLayout(tracks_panel)
        tracks_layout.setContentsMargins(0, 0, 0, 0)
        tracks_layout.setSpacing(8)

        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(8)
        search_label = QLabel("Search:")
        search_label.setObjectName("editorSearchLabel")
        search_layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("editorSearchInput")
        self.search_input.setPlaceholderText("Search tracks by title, artist, or album...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.filter_tracks)
        search_layout.addWidget(self.search_input)
        tracks_layout.addLayout(search_layout)

        self.tracks_table = PlaylistTrackTable()
        self.tracks_table.setObjectName("editorTracksTable")
        self.tracks_table.setColumnCount(4)
        self.tracks_table.rows_reordered.connect(self.handle_row_reorder)
        self.tracks_table.setHorizontalHeaderLabels(["Title", "Artist", "Album", "Duration"])
        self.tracks_table.horizontalHeader().setStretchLastSection(False)
        self.tracks_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tracks_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.tracks_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tracks_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tracks_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tracks_table.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.tracks_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tracks_table.customContextMenuRequested.connect(self.show_context_menu)
        self.tracks_table.setAlternatingRowColors(False)
        self.tracks_table.setColumnWidth(0, 280)
        self.tracks_table.setColumnWidth(1, 220)
        self.tracks_table.setColumnWidth(2, 220)
        self.tracks_table.verticalHeader().setDefaultSectionSize(30)
        tracks_layout.addWidget(self.tracks_table)

        body_layout.addWidget(tracks_panel, 1)
        editor_layout.addLayout(body_layout)
        layout.addWidget(self.editor_section, 1)

        # Button section
        self.action_bar = QWidget()
        button_layout = QHBoxLayout(self.action_bar)
        button_layout.setContentsMargins(0, 4, 0, 0)
        button_layout.setSpacing(8)

        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.setObjectName("editorBtnNeutral")
        self.delete_button.clicked.connect(self.delete_selected)
        self.delete_button.setEnabled(False)
        button_layout.addWidget(self.delete_button)

        self.move_up_button = QPushButton("Move Up")
        self.move_up_button.setObjectName("editorBtnNeutral")
        self.move_up_button.clicked.connect(self.move_up)
        self.move_up_button.setEnabled(False)
        button_layout.addWidget(self.move_up_button)

        self.move_down_button = QPushButton("Move Down")
        self.move_down_button.setObjectName("editorBtnNeutral")
        self.move_down_button.clicked.connect(self.move_down)
        self.move_down_button.setEnabled(False)
        button_layout.addWidget(self.move_down_button)

        self.sort_button = QPushButton("Sort...")
        self.sort_button.setObjectName("editorBtnNeutral")
        self.sort_button.clicked.connect(self.show_sort_menu)
        self.sort_button.setEnabled(False)
        button_layout.addWidget(self.sort_button)

        self.highlight_duplicates_button = QPushButton("Highlight Duplicates")
        self.highlight_duplicates_button.setObjectName("editorBtnNeutral")
        self.highlight_duplicates_button.setCheckable(True)
        self.highlight_duplicates_button.toggled.connect(self.toggle_duplicate_highlighting)
        self.highlight_duplicates_button.setEnabled(False)
        button_layout.addWidget(self.highlight_duplicates_button)

        button_layout.addStretch()

        self.save_button = QPushButton("Save Changes")
        self.save_button.setObjectName("editorBtnPrimary")
        self.save_button.clicked.connect(self.save_changes)
        self.save_button.setEnabled(False)
        button_layout.addWidget(self.save_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("editorBtnDanger")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        self.action_bar.setVisible(False)
        layout.addWidget(self.action_bar)
    
    def _register_track(self, track):
        """Store the track reference and return a safe identifier for UI usage."""
        identifier = getattr(track, 'ratingKey', None)
        if identifier is None:
            identifier = getattr(track, 'key', None)
        if identifier is None:
            identifier = getattr(track, 'guid', None)
        if identifier is None:
            identifier = f'track-{id(track)}'
        identifier = str(identifier)
        self.track_lookup[identifier] = track
        return identifier

    def _set_cover_placeholder(self, text):
        self.cover_preview_label.setPixmap(QPixmap())
        self.cover_preview_label.setText(text)

    def _set_cover_from_bytes(self, image_bytes):
        pixmap = QPixmap()
        if not image_bytes or not pixmap.loadFromData(image_bytes):
            self._set_cover_placeholder("Cover unavailable")
            return False
        pixmap = pixmap.scaled(
            200,
            200,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.cover_preview_label.setPixmap(pixmap)
        self.cover_preview_label.setText("")
        return True

    def _set_cover_from_file(self, path):
        pixmap = QPixmap(path)
        if pixmap.isNull():
            self._set_cover_placeholder("Invalid image")
            return False
        pixmap = pixmap.scaled(
            200,
            200,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.cover_preview_label.setPixmap(pixmap)
        self.cover_preview_label.setText("")
        return True

    def _playlist_cover_url(self):
        self.current_cover_is_custom = False
        try:
            posters = self.plex_server.query(f"/library/metadata/{self.playlist.ratingKey}/posters")
            selected_default = ""
            fallback_custom = ""
            for poster in posters:
                try:
                    poster_key = str(poster.attrib.get("key", "") or "").strip()
                    poster_thumb = str(poster.attrib.get("thumb", "") or "").strip()
                    poster_rating_key = str(poster.attrib.get("ratingKey", "") or "").strip()
                    is_selected = str(poster.attrib.get("selected", "0") or "0") == "1"
                    is_default = poster_rating_key == "default://"
                    candidate = poster_thumb or poster_key
                    if not candidate:
                        continue
                    if is_selected and not is_default:
                        self.current_cover_is_custom = True
                        if candidate.startswith("http://") or candidate.startswith("https://"):
                            return candidate
                        if candidate.startswith("/"):
                            return self.plex_server.url(candidate, includeToken=True)
                    if not is_default and not fallback_custom:
                        fallback_custom = candidate
                    elif is_default and is_selected and not selected_default:
                        selected_default = candidate
                except Exception:
                    continue

            for candidate in (fallback_custom, selected_default):
                clean = str(candidate or "").strip()
                if not clean:
                    continue
                if clean.startswith("http://") or clean.startswith("https://"):
                    self.current_cover_is_custom = clean == fallback_custom and bool(fallback_custom)
                    return clean
                if clean.startswith("/"):
                    self.current_cover_is_custom = clean == fallback_custom and bool(fallback_custom)
                    return self.plex_server.url(clean, includeToken=True)
        except Exception:
            pass

        candidates = []
        for attr in ("composite", "art", "thumb"):
            try:
                value = getattr(self.playlist, attr, None)
                if value:
                    candidates.append(str(value))
            except Exception:
                continue
        try:
            thumb_url = getattr(self.playlist, "thumbUrl", None)
            if callable(thumb_url):
                thumb_url = thumb_url()
            if thumb_url:
                candidates.append(str(thumb_url))
        except Exception:
            pass

        for value in candidates:
            clean = str(value or "").strip()
            if not clean:
                continue
            if clean.startswith("http://") or clean.startswith("https://"):
                return clean
            if clean.startswith("/"):
                try:
                    return self.plex_server.url(clean, includeToken=True)
                except Exception:
                    continue
        return ""

    def load_cover_preview(self):
        self._set_cover_placeholder("Loading cover...")
        self.cover_status_label.setText("Loading current Plex cover...")
        self.current_cover_url = self._playlist_cover_url()
        if not self.current_cover_url:
            self._set_cover_placeholder("No cover")
            self.cover_status_label.setText("No current cover found.")
            return

        self.cover_load_thread = PlaylistCoverLoadThread(self.current_cover_url, self)
        self.cover_load_thread.cover_loaded.connect(self._on_cover_loaded)
        self.cover_load_thread.error.connect(self._on_cover_error)
        self.cover_load_thread.finished.connect(lambda: setattr(self, "cover_load_thread", None))
        self.cover_load_thread.start()

    def _on_cover_loaded(self, image_bytes):
        if self.pending_cover_path:
            return
        if self._set_cover_from_bytes(image_bytes):
            self.cover_status_label.setText("Using custom Plex cover." if self.current_cover_is_custom else "Using current Plex cover.")
        else:
            self.cover_status_label.setText("Unable to render current cover.")

    def _on_cover_error(self, error_message):
        if self.pending_cover_path:
            return
        self._set_cover_placeholder("Cover unavailable")
        self.cover_status_label.setText("Could not load current cover.")
        logging.warning(f"Playlist cover preview load failed: {error_message}")

    def choose_cover_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Playlist Cover",
            "",
            "Image Files (*.jpg *.jpeg *.png *.webp *.bmp)",
        )
        if not path:
            return
        if self._set_cover_from_file(path):
            self.pending_cover_path = path
            self.cover_status_label.setText(f"Pending cover change: {os.path.basename(path)}")
            self.clear_cover_btn.setEnabled(True)
            self._update_dirty_state()
        else:
            QMessageBox.warning(self, "Invalid Image", "The selected file could not be loaded as an image.")

    def clear_pending_cover(self):
        self.pending_cover_path = ""
        self.clear_cover_btn.setEnabled(False)
        if self.current_cover_url:
            self.load_cover_preview()
        else:
            self._set_cover_placeholder("No cover")
            self.cover_status_label.setText("Using current Plex cover.")
        self._update_dirty_state()

    def _resolve_track(self, track_id):
        """Return the registered track object for a given identifier."""
        return self.track_lookup.get(track_id)

    def _current_track_ids(self):
        track_ids = []
        for row in range(self.tracks_table.rowCount()):
            item = self.tracks_table.item(row, 0)
            if not item:
                continue
            track_id = item.data(Qt.UserRole)
            if track_id is not None:
                track_ids.append(track_id)
        return track_ids

    def _has_unsaved_changes(self):
        if not self.tracks_loaded:
            return bool(self.pending_cover_path)
        if self.pending_cover_path:
            return True
        return self._current_track_ids() != self.original_track_ids

    def _update_dirty_state(self):
        is_dirty = self._has_unsaved_changes()
        title_suffix = " • Modified" if is_dirty else ""
        self.editor_title_label.setText(f"Editing Playlist: {self.playlist.title}{title_suffix}")
        if self.tracks_loaded:
            self.setWindowTitle(
                f"Editing: {self.playlist.title} ({len(self.tracks)} tracks){title_suffix}"
            )
            self.save_button.setEnabled(is_dirty)
        return is_dirty

    def _mark_saved_state(self):
        self.original_track_ids = self._current_track_ids()
        self.original_track_order = {
            track_id: index for index, track_id in enumerate(self.original_track_ids)
        }
        self.pending_cover_path = ""
        self.clear_cover_btn.setEnabled(False)
        self._update_dirty_state()

    def _row_duplicate_signature(self, row_data):
        return (
            _normalize_match_text(row_data.get("title", "")),
            _normalize_match_text(row_data.get("artist", "")),
            _normalize_match_text(row_data.get("album", "")),
        )

    def _snapshot_row_signature(self, row):
        title_item = self.tracks_table.item(row, 0)
        artist_item = self.tracks_table.item(row, 1)
        album_item = self.tracks_table.item(row, 2)
        return (
            _normalize_match_text(title_item.text() if title_item else ""),
            _normalize_match_text(artist_item.text() if artist_item else ""),
            _normalize_match_text(album_item.text() if album_item else ""),
        )

    def _apply_duplicate_highlighting(self):
        duplicate_counts = {}
        for row in self._snapshot_table_rows():
            signature = self._row_duplicate_signature(row)
            if any(signature):
                duplicate_counts[signature] = duplicate_counts.get(signature, 0) + 1

        duplicate_color = QColor("#4b355f")
        normal_color = QColor()
        for row in range(self.tracks_table.rowCount()):
            signature = self._snapshot_row_signature(row)
            is_duplicate = self.highlight_duplicates_enabled and duplicate_counts.get(signature, 0) > 1
            tooltip = "Possible duplicate track" if is_duplicate else ""
            for col in range(self.tracks_table.columnCount()):
                item = self.tracks_table.item(row, col)
                if not item:
                    continue
                item.setBackground(duplicate_color if is_duplicate else normal_color)
                item.setToolTip(tooltip)

    def toggle_duplicate_highlighting(self, enabled):
        self.highlight_duplicates_enabled = bool(enabled)
        self.highlight_duplicates_button.setText("Hide Duplicates" if enabled else "Highlight Duplicates")
        self._apply_duplicate_highlighting()

    def _select_duplicate_group_for_row(self, row):
        target_signature = self._snapshot_row_signature(row)
        if not any(target_signature):
            return
        self.tracks_table.clearSelection()
        for current_row in range(self.tracks_table.rowCount()):
            if self._snapshot_row_signature(current_row) == target_signature:
                self.tracks_table.selectRow(current_row)

    def _confirm_discard_changes(self):
        if not self._has_unsaved_changes():
            return True
        reply = QMessageBox.question(
            self,
            "Discard Changes?",
            "You have unsaved playlist changes. Close the editor and discard them?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _render_tracks(self, track_rows, start_row=0, end_row=None):
        """Render the provided track list into the table."""
        if end_row is None:
            end_row = len(track_rows)
        for row in range(start_row, min(end_row, len(track_rows))):
            row_data = track_rows[row]
            track = row_data["track"]
            title_item = QTableWidgetItem(row_data["title"])
            artist_item = QTableWidgetItem(row_data["artist"])
            album_item = QTableWidgetItem(row_data["album"])
            duration_item = QTableWidgetItem(row_data["duration"])

            for item in (title_item, artist_item, album_item, duration_item):
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)

            self.tracks_table.setItem(row, 0, title_item)
            self.tracks_table.setItem(row, 1, artist_item)
            self.tracks_table.setItem(row, 2, album_item)
            self.tracks_table.setItem(row, 3, duration_item)

            track_id = self._register_track(track)
            self.tracks_table.item(row, 0).setData(Qt.UserRole, track_id)

    def start_background_loading(self):
        """Start loading tracks in background thread immediately"""
        self.loading_progress.setValue(10)
        self.loading_detail.setText("Connecting to Plex server...")
        self.retry_loading_btn.setVisible(False)
        
        # Start background thread immediately
        self.load_tracks_thread = LoadPlaylistTracksThread(self.playlist, self)
        self.load_tracks_thread.progress_update.connect(self.update_loading_progress)
        self.load_tracks_thread.tracks_loaded.connect(self.on_tracks_loaded)
        self.load_tracks_thread.error.connect(self.on_tracks_error)
        self.load_tracks_thread.start()
    
    def update_loading_progress(self, current, total):
        """Update loading progress with smooth animations"""
        if total > 0:
            percentage = int((current / total) * 90) + 10  # 10-100 range
            self.loading_progress.setValue(percentage)
            self.loading_detail.setText(f"Loading track {current} of {total}...")
        else:
            # Indeterminate progress
            self.loading_progress.setValue(50)
            self.loading_detail.setText("Loading playlist data...")
    
    def on_tracks_loaded(self, track_rows):
        """Handle tracks loaded from background thread without blocking the dialog."""
        try:
            self.track_rows = list(track_rows)
            self.tracks = [row["track"] for row in self.track_rows]
            self.original_track_order = {}
            for original_index, row in enumerate(self.track_rows):
                track = row.get("track")
                track_id = self._register_track(track)
                self.original_track_order[track_id] = original_index
            self.original_track_ids = [
                track_id
                for track_id in (self._register_track(row.get("track")) for row in self.track_rows)
                if track_id is not None
            ]
            self.track_lookup.clear()
            for row in self.track_rows:
                track = row.get("track")
                self._register_track(track)
            self.tracks_table.clearContents()
            self.tracks_table.setRowCount(len(self.tracks))
            self.track_count_label.setText(f"🎵 Tracks: {len(self.tracks)}")
            self._pending_render_tracks = self.track_rows
            self._render_cursor = 0

            self.loading_progress.setValue(90)
            self.loading_detail.setText("Rendering tracks...")
            QTimer.singleShot(0, self._render_next_chunk)

        except Exception as e:
            logging.error(f"Error processing loaded tracks: {str(e)}")
            self.on_tracks_error(str(e))

    def _render_next_chunk(self):
        """Render the loaded tracks in UI-sized chunks to keep the dialog responsive."""
        try:
            total_tracks = len(self._pending_render_tracks)
            if total_tracks == 0:
                self.loading_progress.setValue(100)
                self.loading_detail.setText("Ready!")
                QTimer.singleShot(0, self.show_editor)
                return

            end_index = min(self._render_cursor + self._render_batch_size, total_tracks)
            self._render_tracks(self._pending_render_tracks, start_row=self._render_cursor, end_row=end_index)
            self._render_cursor = end_index

            if self._render_cursor < total_tracks:
                render_fraction = self._render_cursor / total_tracks
                percentage = 90 + int(render_fraction * 9)
                self.loading_progress.setValue(min(99, percentage))
                self.loading_detail.setText(f"Rendering tracks... ({self._render_cursor}/{total_tracks})")
                QTimer.singleShot(0, self._render_next_chunk)
                return

            self._refresh_internal_track_list()
            self.loading_progress.setValue(100)
            self.loading_detail.setText("Ready!")
            self._pending_render_tracks = []
            self._apply_duplicate_highlighting()
            QTimer.singleShot(0, self.show_editor)

        except Exception as e:
            logging.error(f"Error rendering playlist tracks: {str(e)}")
            self.on_tracks_error(str(e))
    
    def populate_tracks_table(self, tracks):
        """Populate tracks table efficiently with row numbers"""
        self.tracks_table.setRowCount(len(tracks))
        self.track_count_label.setText(f"🎵 Tracks: {len(tracks)}")

        # Reset lookup so identifiers reflect current dataset
        self.track_lookup.clear()

        # Render the tracks into the table
        self._render_tracks(tracks)
        self._refresh_internal_track_list()
        self._apply_duplicate_highlighting()

    def show_editor(self):
        """Show the editor interface with smooth transition"""
        # Hide loading section
        self.loading_section.setVisible(False)
        
        # Show editor section
        self.editor_section.setVisible(True)
        self.action_bar.setVisible(True)
        
        # Enable all buttons
        self.delete_button.setEnabled(True)
        self.move_up_button.setEnabled(True)
        self.move_down_button.setEnabled(True)
        self.sort_button.setEnabled(True)
        self.highlight_duplicates_button.setEnabled(True)
        self.save_button.setEnabled(False)
        self.change_cover_btn.setEnabled(True)
        self.clear_cover_btn.setEnabled(bool(self.pending_cover_path))
        
        self.tracks_loaded = True
        
        # Update window title
        self.setWindowTitle(f"Editing: {self.playlist.title} ({len(self.tracks)} tracks)")
        self._update_dirty_state()
    
    def filter_tracks(self, search_text):
        """Filter tracks based on search text"""
        search_text = search_text.lower().strip()
        
        for row in range(self.tracks_table.rowCount()):
            # Get track data from the row
            title_item = self.tracks_table.item(row, 0)  # Title
            artist_item = self.tracks_table.item(row, 1)  # Artist  
            album_item = self.tracks_table.item(row, 2)   # Album
            
            # Check if search text matches any field
            show_row = False
            if not search_text:  # Empty search shows all
                show_row = True
            else:
                # Search in title, artist, and album
                if title_item and search_text in title_item.text().lower():
                    show_row = True
                elif artist_item and search_text in artist_item.text().lower():
                    show_row = True
                elif album_item and search_text in album_item.text().lower():
                    show_row = True
            
            # Show or hide the row
            self.tracks_table.setRowHidden(row, not show_row)
    
    def show_context_menu(self, position):
        """Show right-click context menu"""
        if not self.tracks_loaded:
            return
        
        # Get the row that was right-clicked
        item = self.tracks_table.itemAt(position)
        if not item:
            return
        
        row = item.row()
        
        # Create context menu
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #142238;
                color: #e4f0ff;
                border: 1px solid #38567f;
                border-radius: 6px;
            }
            QMenu::item {
                padding: 8px 20px;
            }
            QMenu::item:selected {
                background-color: #2d5a8f;
                color: #ffffff;
            }
        """)
        
        # Add actions
        set_position_action = menu.addAction("📍 Set Position...")
        move_to_top_action = menu.addAction("⬆️ Move to Top")
        move_to_bottom_action = menu.addAction("⬇️ Move to Bottom")
        menu.addSeparator()
        select_duplicates_action = menu.addAction("🧩 Select Duplicate Group")
        copy_track_action = menu.addAction("📋 Copy Title / Artist")
        menu.addSeparator()
        delete_action = menu.addAction("🗑️ Delete Track")
        
        # Show menu and handle selection
        action = menu.exec(self.tracks_table.mapToGlobal(position))
        
        if action == set_position_action:
            self.set_track_position(row)
        elif action == move_to_top_action:
            self.move_track_to_position(row, 0)
        elif action == move_to_bottom_action:
            self.move_track_to_position(row, self.tracks_table.rowCount() - 1)
        elif action == select_duplicates_action:
            self._select_duplicate_group_for_row(row)
        elif action == copy_track_action:
            title_item = self.tracks_table.item(row, 0)
            artist_item = self.tracks_table.item(row, 1)
            title = title_item.text() if title_item else ""
            artist = artist_item.text() if artist_item else ""
            QApplication.clipboard().setText(f"{title} - {artist}".strip(" -"))
        elif action == delete_action:
            self.delete_track_at_row(row)

    def _duration_sort_value(self, value):
        text = str(value or "").strip()
        if not text or text.lower() == "unknown":
            return 0
        parts = text.split(":")
        try:
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            if len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        except Exception:
            return 0
        return 0

    def _snapshot_table_rows(self):
        rows = []
        for row in range(self.tracks_table.rowCount()):
            title_item = self.tracks_table.item(row, 0)
            artist_item = self.tracks_table.item(row, 1)
            album_item = self.tracks_table.item(row, 2)
            duration_item = self.tracks_table.item(row, 3)
            rows.append(
                {
                    "title": title_item.text() if title_item else "",
                    "artist": artist_item.text() if artist_item else "",
                    "album": album_item.text() if album_item else "",
                    "duration": duration_item.text() if duration_item else "",
                    "track_id": title_item.data(Qt.UserRole) if title_item else None,
                }
            )
        return rows

    def _rebuild_table_from_rows(self, rows, selected_track_ids=None):
        self.tracks_table.setRowCount(len(rows))
        self.tracks_table.clearSelection()

        for row_index, row_data in enumerate(rows):
            items = [
                QTableWidgetItem(row_data.get("title", "")),
                QTableWidgetItem(row_data.get("artist", "")),
                QTableWidgetItem(row_data.get("album", "")),
                QTableWidgetItem(row_data.get("duration", "")),
            ]
            for item in items:
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
            items[0].setData(Qt.UserRole, row_data.get("track_id"))

            for col, item in enumerate(items):
                self.tracks_table.setItem(row_index, col, item)

            if selected_track_ids and row_data.get("track_id") in selected_track_ids:
                self.tracks_table.selectRow(row_index)

        self.track_count_label.setText(f"🎵 Tracks: {len(rows)}")
        self._refresh_internal_track_list()
        self.filter_tracks(self.search_input.text())
        self._apply_duplicate_highlighting()

    def sort_tracks(self, mode):
        if not self.tracks_loaded:
            QMessageBox.warning(self, "Loading", "Please wait for tracks to finish loading.")
            return

        rows = self._snapshot_table_rows()
        if not rows:
            return

        selected_track_ids = set()
        for item in self.tracks_table.selectedItems():
            track_id = self.tracks_table.item(item.row(), 0).data(Qt.UserRole)
            if track_id is not None:
                selected_track_ids.add(track_id)

        reverse = False
        if mode == "title_asc":
            key_fn = lambda row: (_normalize_match_text(row["title"]), _normalize_match_text(row["artist"]), _normalize_match_text(row["album"]))
        elif mode == "title_desc":
            key_fn = lambda row: (_normalize_match_text(row["title"]), _normalize_match_text(row["artist"]), _normalize_match_text(row["album"]))
            reverse = True
        elif mode == "artist_asc":
            key_fn = lambda row: (_normalize_match_text(row["artist"]), _normalize_match_text(row["title"]), _normalize_match_text(row["album"]))
        elif mode == "artist_desc":
            key_fn = lambda row: (_normalize_match_text(row["artist"]), _normalize_match_text(row["title"]), _normalize_match_text(row["album"]))
            reverse = True
        elif mode == "album_asc":
            key_fn = lambda row: (_normalize_match_text(row["album"]), _normalize_match_text(row["artist"]), _normalize_match_text(row["title"]))
        elif mode == "album_desc":
            key_fn = lambda row: (_normalize_match_text(row["album"]), _normalize_match_text(row["artist"]), _normalize_match_text(row["title"]))
            reverse = True
        elif mode == "duration_short":
            key_fn = lambda row: (self._duration_sort_value(row["duration"]), _normalize_match_text(row["artist"]), _normalize_match_text(row["title"]))
        elif mode == "duration_long":
            key_fn = lambda row: (self._duration_sort_value(row["duration"]), _normalize_match_text(row["artist"]), _normalize_match_text(row["title"]))
            reverse = True
        elif mode == "duplicates":
            key_fn = lambda row: (
                _normalize_match_text(row["title"]),
                _normalize_match_text(row["artist"]),
                _normalize_match_text(row["album"]),
                self._duration_sort_value(row["duration"]),
            )
        elif mode == "artist_album_title":
            key_fn = lambda row: (
                _normalize_match_text(row["artist"]),
                _normalize_match_text(row["album"]),
                _normalize_match_text(row["title"]),
            )
        elif mode == "original_order":
            key_fn = lambda row: (
                self.original_track_order.get(
                    row.get("track_id"),
                    10**9,
                ),
                _normalize_match_text(row["artist"]),
                _normalize_match_text(row["album"]),
                _normalize_match_text(row["title"]),
            )
        else:
            return

        rows.sort(key=key_fn, reverse=reverse)
        self._rebuild_table_from_rows(rows, selected_track_ids=selected_track_ids)
        self._update_dirty_state()

    def show_sort_menu(self):
        if not self.tracks_loaded:
            QMessageBox.warning(self, "Loading", "Please wait for tracks to finish loading.")
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #142238;
                color: #e4f0ff;
                border: 1px solid #38567f;
                border-radius: 6px;
            }
            QMenu::item {
                padding: 8px 20px;
            }
            QMenu::item:selected {
                background-color: #2d5a8f;
                color: #ffffff;
            }
        """)

        actions = {
            menu.addAction("Original Playlist Order"): "original_order",
            menu.addSeparator(): None,
            menu.addAction("Title A–Z"): "title_asc",
            menu.addAction("Title Z–A"): "title_desc",
            menu.addAction("Artist A–Z"): "artist_asc",
            menu.addAction("Artist Z–A"): "artist_desc",
            menu.addAction("Album A–Z"): "album_asc",
            menu.addAction("Album Z–A"): "album_desc",
            menu.addAction("Duration: Shortest First"): "duration_short",
            menu.addAction("Duration: Longest First"): "duration_long",
            menu.addAction("Duplicate Finder (Title / Artist / Album)"): "duplicates",
            menu.addAction("Artist / Album / Title"): "artist_album_title",
        }

        chosen = menu.exec(self.sort_button.mapToGlobal(self.sort_button.rect().bottomLeft()))
        if chosen in actions and actions[chosen]:
            self.sort_tracks(actions[chosen])
    
    def handle_row_reorder(self, from_row, to_row):
        """Handle internal drag-and-drop row reordering."""
        if from_row == to_row:
            return

        row_count = self.tracks_table.rowCount()
        if not self.tracks or len(self.tracks) != row_count:
            self._refresh_internal_track_list()

        if self.tracks and len(self.tracks) == row_count:
            track_obj = self.tracks.pop(from_row)
            insert_index = max(0, min(to_row, len(self.tracks)))
            self.tracks.insert(insert_index, track_obj)
        else:
            self._refresh_internal_track_list()

        self._refresh_internal_track_list()

        self.tracks_table.selectRow(to_row)
        target_item = self.tracks_table.item(to_row, 0)
        if target_item:
            self.tracks_table.scrollToItem(target_item, QAbstractItemView.PositionAtCenter)
        self._apply_duplicate_highlighting()
        self._update_dirty_state()

    def set_track_position(self, current_row):
        """Allow user to set specific position for a track"""
        track_title = self.tracks_table.item(current_row, 0).text()
        current_position = current_row + 1
        total_tracks = self.tracks_table.rowCount()
        
        # Show input dialog
        new_position, ok = QInputDialog.getInt(
            self, 
            "Set Track Position",
            f"Move '{track_title}' to position:\n(Current: {current_position}, Total: {total_tracks})",
            current_position,  # default value
            1,                 # minimum
            total_tracks       # maximum
        )
        
        if ok and new_position != current_position:
            target_row = new_position - 1  # Convert to 0-based index
            self.move_track_to_position(current_row, target_row)
    
    def move_track_to_position(self, from_row, to_row, show_feedback=True):
        """Move track from one position to another using the same logic as arrow buttons."""
        try:
            final_row = self._move_row(from_row, to_row)
            if final_row is not None and show_feedback:
                QMessageBox.information(self, "Success", f"Track moved to position {final_row + 1}")
        except Exception as e:
            logging.error(f"Error moving track: {str(e)}")
            if show_feedback:
                QMessageBox.warning(self, "Move Error", f"Failed to move track: {str(e)}")


    def _move_row(self, from_row, to_row):
        """Core row-move helper shared by drag, arrows, and context actions."""
        row_count = self.tracks_table.rowCount()
        if row_count == 0:
            return None

        from_row = max(0, min(from_row, row_count - 1))
        to_row = max(0, min(to_row, row_count - 1))

        if from_row == to_row:
            return None

        if not self.tracks or len(self.tracks) != row_count:
            self._refresh_internal_track_list()

        if from_row < to_row:
            for row in range(from_row, to_row):
                self.swap_rows(row, row + 1)
                if len(self.tracks) > row + 1:
                    self.tracks[row], self.tracks[row + 1] = self.tracks[row + 1], self.tracks[row]
        else:
            for row in range(from_row, to_row, -1):
                self.swap_rows(row, row - 1)
                if len(self.tracks) > row:
                    self.tracks[row], self.tracks[row - 1] = self.tracks[row - 1], self.tracks[row]

        self.tracks_table.selectRow(to_row)
        target_item = self.tracks_table.item(to_row, 0)
        if target_item:
            self.tracks_table.scrollToItem(target_item, QAbstractItemView.PositionAtCenter)
        self._apply_duplicate_highlighting()
        self._update_dirty_state()

        return to_row

    def _refresh_internal_track_list(self):
        """Synchronize internal track list with current table order."""
        ordered_tracks = []
        for row in range(self.tracks_table.rowCount()):
            item = self.tracks_table.item(row, 0)
            if not item:
                continue
            track_id = item.data(Qt.UserRole)
            if track_id is None:
                continue
            track_obj = self._resolve_track(track_id)
            if track_obj:
                ordered_tracks.append(track_obj)
                # ensure the track_id stays on the row after operations
                item.setData(Qt.UserRole, track_id)
        self.tracks = ordered_tracks

    def delete_track_at_row(self, row):
        """Delete a specific track"""
        track_title = self.tracks_table.item(row, 0).text()
        
        reply = QMessageBox.question(self, "Confirm Deletion", 
                                   f"Delete '{track_title}'?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.tracks_table.removeRow(row)
            self.track_count_label.setText(f"🎵 Tracks: {self.tracks_table.rowCount()}")
            self._refresh_internal_track_list()
            self._apply_duplicate_highlighting()
            self._update_dirty_state()
            # Show success message instead of statusBar
            QMessageBox.information(self, "Deleted", f"Deleted '{track_title}'")

    def on_tracks_error(self, error_message):
        """Handle error loading tracks with user-friendly display"""
        self.loading_progress.setValue(0)
        self.loading_progress.setStyleSheet("""
            QProgressBar::chunk {
                background-color: #f44336;
            }
        """)
        self.loading_label.setText("❌ Error Loading Tracks")
        self.loading_detail.setText(f"Error: {error_message}")
        self.retry_loading_btn.setVisible(True)
        
        QMessageBox.warning(self, "Loading Error", f"Failed to load tracks: {error_message}")
    
    def retry_loading(self):
        """Retry loading tracks"""
        self.loading_label.setText("Retrying...")
        self.loading_detail.setText("Attempting to reload tracks...")
        self.loading_progress.setValue(0)
        self.retry_loading_btn.setVisible(False)
        self.loading_progress.setStyleSheet("""
            QProgressBar::chunk {
                background-color: #2ed27a;
            }
        """)
        
        # Restart loading
        self.start_background_loading()
            
    def delete_selected(self):
        if not self.tracks_loaded:
            QMessageBox.warning(self, "Loading", "Please wait for tracks to finish loading.")
            return
            
        selected_rows = set()
        for item in self.tracks_table.selectedItems():
            selected_rows.add(item.row())
            
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select tracks to delete.")
            return
            
        reply = QMessageBox.question(self, "Confirm Deletion", 
                                   f"Delete {len(selected_rows)} selected track(s)?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            for row in sorted(selected_rows, reverse=True):
                self.tracks_table.removeRow(row)
                       
            # Update track count
            self.track_count_label.setText(f"🎵 Tracks: {self.tracks_table.rowCount()}")
            self._refresh_internal_track_list()
            self._apply_duplicate_highlighting()
            self._update_dirty_state()
                
    def move_up(self):
        current_row = self.tracks_table.currentRow()
        final_row = self._move_row(current_row, current_row - 1)
        if final_row is not None:
            self.tracks_table.setCurrentCell(final_row, 0)
            
    def move_down(self):
        current_row = self.tracks_table.currentRow()
        final_row = self._move_row(current_row, current_row + 1)
        if final_row is not None:
            self.tracks_table.setCurrentCell(final_row, 0)
            
    def swap_rows(self, row1, row2):
        # Handle all 4 columns
        for col in range(self.tracks_table.columnCount()):
            item1 = self.tracks_table.takeItem(row1, col)
            item2 = self.tracks_table.takeItem(row2, col)
            self.tracks_table.setItem(row1, col, item2)
            self.tracks_table.setItem(row2, col, item1)
            
    def save_changes(self):
        if not self.tracks_loaded:
            QMessageBox.warning(self, "Loading", "Please wait for tracks to finish loading.")
            return
            
        try:
            # Show saving progress
            self.save_button.setText("Saving...")
            self.save_button.setEnabled(False)
            
            # Get current track order - Look at column 0 (title)
            tracks = []
            for row in range(self.tracks_table.rowCount()):
                item = self.tracks_table.item(row, 0)  # Title column now
                if not item:
                    continue

                track_id = item.data(Qt.UserRole)
                if track_id is None:
                    continue

                track_obj = self._resolve_track(track_id)
                if track_obj:
                    tracks.append(track_obj)
                else:
                    logging.warning(f"Unresolved track identifier during save: {track_id}")

            existing_items = list(self.playlist.items())
            if existing_items:
                self.playlist.removeItems(existing_items)
            if tracks:
                self.playlist.addItems(tracks)

            cover_updated = False
            cover_error = ""
            if self.pending_cover_path:
                try:
                    self.playlist.uploadPoster(filepath=self.pending_cover_path)
                    cover_updated = True
                    self.pending_cover_path = ""
                except Exception as cover_exc:
                    cover_error = str(cover_exc)

            if cover_error:
                QMessageBox.warning(
                    self,
                    "Saved With Cover Warning",
                    "Track order was saved, but cover upload failed.\n\n"
                    f"Error: {cover_error}",
                )
            else:
                success_msg = "Playlist updated successfully."
                if cover_updated:
                    success_msg += "\nCover image updated."
                QMessageBox.information(self, "Success", success_msg)
            self._mark_saved_state()
            self._allow_close_without_prompt = True
            self.accept()
            
        except Exception as e:
            logging.error(f"Error saving playlist changes: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to save changes: {str(e)}")
        finally:
            self.save_button.setText("Save Changes")
            self.save_button.setEnabled(True)
    
    def closeEvent(self, event):
        """Handle dialog close event"""
        if not self._allow_close_without_prompt and not self._confirm_discard_changes():
            event.ignore()
            return
        if self.load_tracks_thread and self.load_tracks_thread.isRunning():
            self.load_tracks_thread.stop()
            self.load_tracks_thread.wait(150)
        if self.cover_load_thread and self.cover_load_thread.isRunning():
            self.cover_load_thread.terminate()
            self.cover_load_thread.wait(500)
        event.accept()

    def reject(self):
        if not self._allow_close_without_prompt and not self._confirm_discard_changes():
            return
        self._allow_close_without_prompt = True
        super().reject()

class PlaylistMergerDialog(QDialog):
    def __init__(self, playlists, plex_server, parent=None):
        super().__init__(parent)
        self.playlists = playlists
        self.plex_server = plex_server
        self.setWindowTitle("Merge Playlists")
        self.setModal(True)
        self.resize(600, 400)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Instructions
        layout.addWidget(QLabel("Select playlists to merge and specify the target:"))
        
        # Playlist selection
        self.playlist_list = QListWidget()
        for playlist in self.playlists:
            item = QListWidgetItem(f"{playlist.title} ({len(list(playlist.items()))} tracks)")
            item.setData(Qt.UserRole, playlist)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.playlist_list.addItem(item)
        layout.addWidget(self.playlist_list)
        
        # Merge options
        options_group = QGroupBox("Merge Options")
        options_layout = QVBoxLayout(options_group)
        
        # Target playlist option
        self.target_new = QCheckBox("Create new playlist")
        self.target_new.setChecked(True)
        self.target_new.toggled.connect(self.on_target_changed)
        options_layout.addWidget(self.target_new)
        
        self.target_existing = QCheckBox("Merge into existing playlist")
        self.target_existing.toggled.connect(self.on_target_changed)
        options_layout.addWidget(self.target_existing)
        
        # New playlist name
        self.new_name_layout = QHBoxLayout()
        self.new_name_layout.addWidget(QLabel("New playlist name:"))
        self.new_name_input = QLineEdit("Merged Playlist")
        self.new_name_layout.addWidget(self.new_name_input)
        options_layout.addLayout(self.new_name_layout)
        
        # Existing playlist combo
        self.existing_combo_layout = QHBoxLayout()
        self.existing_combo_layout.addWidget(QLabel("Target playlist:"))
        self.existing_combo = QComboBox()
        self.existing_combo.setEnabled(False)
        self.populate_existing_playlists()
        self.existing_combo_layout.addWidget(self.existing_combo)
        options_layout.addLayout(self.existing_combo_layout)
        
        # Additional options
        self.remove_duplicates = QCheckBox("Remove duplicate tracks")
        self.remove_duplicates.setChecked(True)
        options_layout.addWidget(self.remove_duplicates)
        
        self.delete_source = QCheckBox("Delete source playlists after merge")
        options_layout.addWidget(self.delete_source)
        
        layout.addWidget(options_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.merge_button = QPushButton("Merge Playlists")
        self.merge_button.clicked.connect(self.merge_playlists)
        button_layout.addWidget(self.merge_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
    def on_target_changed(self):
        if self.target_new.isChecked():
            self.target_existing.setChecked(False)
            self.new_name_input.setEnabled(True)
            self.existing_combo.setEnabled(False)
        elif self.target_existing.isChecked():
            self.target_new.setChecked(False)
            self.new_name_input.setEnabled(False)
            self.existing_combo.setEnabled(True)
            
    def populate_existing_playlists(self):
        try:
            for playlist in self.plex_server.playlists():
                self.existing_combo.addItem(playlist.title, playlist)
        except Exception as e:
            logging.error(f"Error populating playlists: {str(e)}")
            
    def get_selected_playlists(self):
        selected = []
        for i in range(self.playlist_list.count()):
            item = self.playlist_list.item(i)
            if item.checkState() == Qt.Checked:
                selected.append(item.data(Qt.UserRole))
        return selected
        
    def merge_playlists(self):
        selected_playlists = self.get_selected_playlists()
        
        if len(selected_playlists) < 2:
            QMessageBox.warning(self, "Invalid Selection", "Please select at least 2 playlists to merge.")
            return
            
        try:
            # Collect all tracks
            all_tracks = []
            track_signatures = set()  # For duplicate detection
            
            for playlist in selected_playlists:
                for track in playlist.items():
                    if self.remove_duplicates.isChecked():
                        # Create signature for duplicate detection
                        signature = f"{track.title}_{track.originalTitle or (track.artist().title if hasattr(track, 'artist') and track.artist() else '')}"
                        if signature not in track_signatures:
                            all_tracks.append(track)
                            track_signatures.add(signature)
                    else:
                        all_tracks.append(track)
            
            if not all_tracks:
                QMessageBox.warning(self, "No Tracks", "No tracks found in selected playlists.")
                return
                
            # Create or update target playlist
            if self.target_new.isChecked():
                playlist_name = self.new_name_input.text() or "Merged Playlist"
                target_playlist = self.plex_server.createPlaylist(playlist_name, items=all_tracks)
            else:
                target_playlist = self.existing_combo.currentData()
                if target_playlist:
                    target_playlist.addItems(all_tracks)
                    
            # Delete source playlists if requested
            if self.delete_source.isChecked():
                for playlist in selected_playlists:
                    if playlist != target_playlist:  # Don't delete target if it's in the selection
                        playlist.delete()
                        
            QMessageBox.information(self, "Success", 
                                  f"Successfully merged {len(selected_playlists)} playlists into '{target_playlist.title}' with {len(all_tracks)} tracks.")
            self.accept()
            
        except Exception as e:
            logging.error(f"Error merging playlists: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to merge playlists: {str(e)}")

class SmartMatchIndexBuildThread(QThread):
    progress_update = pyqtSignal(str, int)
    build_complete = pyqtSignal(dict)
    build_error = pyqtSignal(str)

    def __init__(self, library_section, force_rebuild=False, parent=None):
        super().__init__(parent)
        self.library_section = library_section
        self.force_rebuild = bool(force_rebuild)
        self.stop_requested = False

    def stop(self):
        self.stop_requested = True

    def run(self):
        try:
            bundle = _prime_library_match_caches(
                self.library_section,
                progress_cb=self.progress_update.emit,
                force_rebuild=self.force_rebuild,
                stop_check=lambda: self.stop_requested,
                progress_range=(0, 100),
            )
            session_key = _get_library_match_session_key(self.library_section)
            fingerprint = _get_cached_library_fingerprint(self.library_section) or {}
            self.build_complete.emit({
                "session_key": session_key,
                "track_total": int(fingerprint.get("track_total", 0) or 0),
                "row_count": len(bundle.get("rows", []) or []),
                "built_at": datetime.now().isoformat(),
            })
        except Exception as e:
            if str(e).strip().lower() == "smart matching canceled.":
                self.build_error.emit("Smart matching canceled.")
            else:
                self.build_error.emit(str(e))


class SmartM3UUploadThread(QThread):
    """Thread for smart M3U upload to prevent UI freezing"""
    progress_update = pyqtSignal(str, int)  # message, percentage
    track_found = pyqtSignal(object)  # matched track
    track_prompt_needed = pyqtSignal(str, str, list, int, int, object)  # title, artist, candidates, index, total, result_holder
    upload_complete = pyqtSignal(int, int, list, object)  # matched_count, total_count, not_found_list, matched_tracks
    upload_error = pyqtSignal(str)

    def __init__(self, m3u_path, track_infos, library_section, parent=None):
        super().__init__(parent)
        self.m3u_path = m3u_path
        self.track_infos = track_infos
        self.library_section = library_section
        self.matched_rating_keys = []
        self.not_found = []
        self.parent_widget = parent
        self.stop_requested = False

    def stop(self):
        self.stop_requested = True

    def run(self):
        """Run the smart matching process in background thread"""
        try:
            total_tracks = len(self.track_infos)
            self.progress_update.emit("Checking Smart Match Cache...", 1)
            _prime_library_match_caches(
                self.library_section,
                progress_cb=self.progress_update.emit,
                stop_check=lambda: self.stop_requested,
                progress_range=(1, 45),
            )
            if self.stop_requested:
                self.upload_error.emit("Smart matching canceled.")
                return
            self.progress_update.emit("Matching playlist tracks... (0/{})".format(total_tracks), 46)

            for i, track_info in enumerate(self.track_infos):
                if self.stop_requested:
                    self.upload_error.emit("Smart matching canceled.")
                    return
                try:
                    title = str(track_info.get('title', '') or '').strip()
                    artist = str(track_info.get('artist', '') or '').strip()
                    album = str(track_info.get('album', '') or '').strip()

                    match_progress = 46 + int(((i + 1) / max(total_tracks, 1)) * 54)
                    self.progress_update.emit(f"Matching playlist tracks ({i+1}/{total_tracks})", match_progress)

                    scored_matches = _rank_plex_track_matches(
                        self.library_section,
                        track_info,
                        self.parent_widget,
                    )

                    if scored_matches:
                        best_score = scored_matches[0]["score"]
                        best_artist_score = scored_matches[0]["artist_score"]

                        if best_score >= 82 and (not artist or best_artist_score >= 40 or best_score >= 100):
                            best_rating_key = str(scored_matches[0].get("rating_key", "") or "")
                            if best_rating_key:
                                self.matched_rating_keys.append(best_rating_key)
                        elif best_score >= 68:
                            prompt_candidates = [
                                (_hydrate_ranked_match_track(self.library_section, match), match["score"], match["artist"])
                                for match in scored_matches[:5]
                            ]
                            prompt_candidates = [candidate for candidate in prompt_candidates if candidate[0] is not None]
                            result_holder = {'track': None}
                            self.track_prompt_needed.emit(
                                title, artist, prompt_candidates, i + 1, total_tracks, result_holder
                            )
                            import time
                            timeout = 0
                            while result_holder.get('track') is None and result_holder.get('skipped') is None and timeout < 300:
                                if self.stop_requested:
                                    self.upload_error.emit("Smart matching canceled.")
                                    return
                                time.sleep(0.1)
                                timeout += 1

                            if result_holder.get('track'):
                                selected_key = str(getattr(result_holder['track'], 'ratingKey', '') or '')
                                if selected_key:
                                    self.matched_rating_keys.append(selected_key)
                            else:
                                self.not_found.append(f"{title} - {artist}" if artist else title)
                        else:
                            not_found_label = f"{title} - {artist}" if artist else title
                            if album:
                                not_found_label = f"{not_found_label} ({album})"
                            self.not_found.append(not_found_label)
                    else:
                        self.not_found.append(f"{title} - {artist}" if artist else title)

                except Exception as track_error:
                    logging.error(f"Error processing track {track_info}: {track_error}")
                    self.not_found.append(f"{track_info.get('title', 'Unknown')} - {track_info.get('artist', '')}")

            # Upload complete
            self.upload_complete.emit(len(self.matched_rating_keys), total_tracks, self.not_found, list(self.matched_rating_keys))

        except Exception as e:
            logging.error(f"Smart M3U upload thread error: {str(e)}")
            self.upload_error.emit(str(e))

class SyncThread(QThread):
    progress_update = pyqtSignal(str, int)  # message, percentage
    sync_complete = pyqtSignal(str, int, int)  # playlist_name, added_tracks, total_tracks
    error = pyqtSignal(str)

    def __init__(self, sync_configs, plex_server, parent=None):
        super().__init__(parent)
        self.sync_configs = sync_configs
        self.plex_server = plex_server
        self.spotify_auth = SpotifyAnonymousAuth()
        self.deezer_client = deezer.Client()
        self.tidal_client = TidalClient()
        self.stop_requested = False

    def _ensure_not_cancelled(self):
        if self.stop_requested:
            raise SyncCancelled()

    def run(self):
        try:
            for playlist_name, config in self.sync_configs.items():
                self._ensure_not_cancelled()

                self.progress_update.emit(f"Syncing {playlist_name}...", 0)
                added_tracks = self.sync_playlist(playlist_name, config)
                self.sync_complete.emit(playlist_name, added_tracks, len(config.get('tracks', [])))

        except SyncCancelled:
            logging.info('Sync cancelled by user request.')
        except Exception as e:
            logging.error(f"Error in sync thread: {str(e)}")
            self.error.emit(str(e))

    def sync_playlist(self, playlist_name, config):
        try:
            # Locate the Plex playlist by name
            plex_playlist = None
            for playlist in self.plex_server.playlists():
                if playlist.title == playlist_name:
                    plex_playlist = playlist
                    break

            if not plex_playlist:
                self.error.emit(f"Plex playlist '{playlist_name}' not found")
                return 0

            self._ensure_not_cancelled()
            clear_before_sync = bool(config.get('clear_before_sync', False))

            # Capture current playlist state for duplicate detection/rebuild
            current_items = list(plex_playlist.items())
            current_keys = [track.ratingKey for track in current_items]
            current_key_set = set(current_keys)

            # Resolve source tracks from the configured URL
            source_tracks = []
            source_url = config.get('source_url', '')

            if "spotify.com" in source_url:
                source_tracks = self.get_spotify_tracks(source_url)
            elif "deezer.com" in source_url:
                source_tracks = self.get_deezer_tracks(source_url)
            elif "tidal.com" in source_url:
                source_tracks = self.get_tidal_tracks(source_url)
            elif "listenbrainz.org" in source_url:
                source_tracks = self.get_listenbrainz_tracks(source_url)
            elif source_url.endswith('.m3u') or source_url.endswith('.m3u8'):
                source_tracks = self.get_m3u_tracks(source_url)

            # Store for downstream reporting
            config['tracks'] = source_tracks

            matched_source_tracks = []
            matched_source_keys = []
            seen_m3u_signatures = set()
            added_count = 0
            library_section = self.plex_server.library.sectionByID(config.get('library_section'))
            total_tracks = max(len(source_tracks), 1)
            use_smart_matching = False
            if hasattr(self.parent(), 'm3u_smart_matching_radio'):
                use_smart_matching = self.parent().m3u_smart_matching_radio.isChecked()
            if use_smart_matching and source_tracks:
                self.progress_update.emit(f"Indexing library for {playlist_name}...", 1)
                _prime_library_match_caches(library_section)

            for i, track_info in enumerate(source_tracks):
                self._ensure_not_cancelled()
                source_track = self.normalize_source_track(track_info)
                track_path = source_track.get('path')
                parsed_info = source_track.get('parsed', '')
                track_title = source_track.get('title', '')
                artist_name = source_track.get('artist', '')
                track_signature = parsed_info.lower()

                # Skip duplicate entries only for file-based M3U rows.
                if track_path and track_signature in seen_m3u_signatures:
                    continue
                if track_path:
                    seen_m3u_signatures.add(track_signature)

                plex_track = None

                # Determine matching strategy for M3U files
                # Try path-based or smart matching for M3U files
                if track_path:
                    if use_smart_matching:
                        # Smart matching still benefits from a strict cached path-suffix
                        # check when a path exists. This is fast and safer than metadata
                        # scoring when artist/album/file suffixes line up.
                        plex_track = self.find_track_by_path(library_section, track_path)
                        if not plex_track:
                            plex_track = self.find_best_match(library_section, source_track)
                    else:
                        # Path matching mode: Use exact file paths (original behavior)
                        plex_track = self.find_track_by_path(library_section, track_path)

                        # Log if path matching failed (will fall back to fuzzy matching)
                        if not plex_track:
                            logging.warning(f"Path match failed for: {track_path}, falling back to fuzzy matching")

                # Fall back to fuzzy matching if other methods failed
                if not plex_track:
                    plex_track = self.find_best_match(library_section, source_track)

                if plex_track:
                    matched_source_tracks.append(plex_track)
                    matched_source_keys.append(plex_track.ratingKey)
                    if plex_track.ratingKey not in current_key_set:
                        added_count += 1

                progress = int((i + 1) / total_tracks * 100)
                self.progress_update.emit(f"Checking {playlist_name}... ({i+1}/{len(source_tracks)})", progress)

            if clear_before_sync:
                final_tracks = matched_source_tracks
            else:
                source_key_set = set(matched_source_keys)
                # Keep non-source extras, but always place source tracks first in source order.
                extras = [track for track in current_items if track.ratingKey not in source_key_set]
                final_tracks = matched_source_tracks + extras

            final_keys = [track.ratingKey for track in final_tracks]
            should_rebuild = clear_before_sync or (final_keys != current_keys)

            if should_rebuild:
                self._ensure_not_cancelled()
                if current_items:
                    try:
                        plex_playlist.removeItems(current_items)
                    except Exception as removal_error:
                        logging.warning(f"Failed to clear playlist '{playlist_name}': {removal_error}")
                if final_tracks:
                    self._ensure_not_cancelled()
                    plex_playlist.addItems(final_tracks)

            return added_count

        except SyncCancelled:
            raise
        except Exception as e:
            logging.error(f"Error syncing playlist {playlist_name}: {str(e)}")
            self.error.emit(f"Error syncing {playlist_name}: {str(e)}")
            return 0

    def get_spotify_tracks(self, url):
        try:
            playlist_id = url.split('/')[-1].split('?')[0]
            tracks, _, _ = fetch_spotify_playlist_tracks_enriched(
                playlist_id,
                self.spotify_auth,
                stop_check=lambda: self.stop_requested,
            )
            return tracks
        except SyncCancelled:
            return []
        except Exception as e:
            logging.error(f"Error getting Spotify tracks: {str(e)}")
            return []

    def get_deezer_tracks(self, url):
        try:
            playlist_id = url.split('/')[-1]
            playlist = self.deezer_client.get_playlist(playlist_id)
            tracks = []
            for track in playlist.tracks:
                title = (getattr(track, "title", "") or "").strip()
                if not title:
                    continue
                artist_name = (getattr(getattr(track, "artist", None), "name", "") or "").strip()
                album_name = (getattr(getattr(track, "album", None), "title", "") or "").strip()
                parsed = f"{title} - {artist_name}" if artist_name else title
                tracks.append({
                    "title": title,
                    "artist": artist_name,
                    "album": album_name,
                    "parsed": parsed,
                    "path": None,
                    "source": "deezer",
                })
            return tracks
        except Exception as e:
            logging.error(f"Error getting Deezer tracks: {str(e)}")
            return []

    def get_tidal_tracks(self, url):
        try:
            playlist_uuid = url.split('/')[-1]
            tracks_data = self.tidal_client.get_playlist_tracks(playlist_uuid)
            tracks = []
            for item in tracks_data['items']:
                title = (item.get("title") or "").strip()
                if not title:
                    continue
                artist_name = ((item.get("artist") or {}).get("name") or "").strip()
                album_name = ((item.get("album") or {}).get("title") or "").strip()
                parsed = f"{title} - {artist_name}" if artist_name else title
                tracks.append({
                    "title": title,
                    "artist": artist_name,
                    "album": album_name,
                    "parsed": parsed,
                    "path": None,
                    "source": "tidal",
                })
            return tracks
        except Exception as e:
            logging.error(f"Error getting Tidal tracks: {str(e)}")
            return []

    def get_listenbrainz_tracks(self, url):
        try:
            token = ""
            parent = self.parent()
            if parent and hasattr(parent, "listenbrainz_token_input"):
                token = parent.listenbrainz_token_input.text().strip()

            client = ListenBrainzClient(token=token or None)
            playlist = client.get_playlist(url)
            entries = playlist.get("track") or []

            tracks = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                title = (entry.get("title") or "").strip()
                artist = (entry.get("creator") or "").strip()
                album = (entry.get("album") or "").strip()
                recording_mbid = self._extract_recording_mbid(entry)
                if not title:
                    continue
                parsed = f"{title} - {artist}" if artist else title
                tracks.append({
                    "title": title,
                    "artist": artist,
                    "album": album,
                    "recording_mbid": recording_mbid,
                    "parsed": parsed,
                    "path": None,
                    "source": "listenbrainz",
                })
            return tracks
        except Exception as e:
            logging.error(f"Error getting ListenBrainz tracks: {str(e)}")
            return []

    def get_m3u_tracks(self, file_path):
        try:
            tracks = _parse_m3u_entries(file_path)
            logging.info(f"Parsed {len(tracks)} tracks from M3U file: {file_path}")
            return tracks

        except Exception as e:
            logging.error(f"Error getting M3U tracks: {str(e)}")
            return []

    def stop(self):
        self.stop_requested = True

    def parse_track_info_smart(self, track_line):
        """Smart parser that handles multiple M3U formats"""
        try:
            # Format 1: File path (like F:\Music\Artist\Album\Track.flac)
            if '\\' in track_line or '/' in track_line:
                parsed = _parse_m3u_track_from_path(track_line)
                return parsed.get("parsed", "").strip() if parsed else str(track_line or "").strip()
            
            # Format 2: "Track Title - Artist Name"
            elif ' - ' in track_line:
                parts = track_line.split(' - ', 1)
                return f"{parts[0].strip()} - {parts[1].strip()}"
            
            # Format 3: Just track title
            else:
                return track_line.strip()
                
        except Exception as e:
            logging.warning(f"Error parsing track info: {str(e)}")
            return track_line.strip()

    def parse_file_path(self, file_path):
        """Extract artist and track from file path"""
        try:
            parsed = _parse_m3u_track_from_path(file_path)
            if parsed:
                return parsed.get("parsed", "").strip()
            return os.path.splitext(os.path.basename(file_path))[0]
            
        except Exception as e:
            logging.warning(f"Error parsing file path {file_path}: {str(e)}")
            return os.path.splitext(os.path.basename(file_path))[0]

    def find_best_match(self, library_section, track):
        try:
            self._ensure_not_cancelled()
            normalized_track = self.normalize_source_track(track)
            title, artist, album, recording_mbid = self.parse_track_info(normalized_track)
            if not title:
                return None
            scored_tracks = _rank_plex_track_matches(library_section, normalized_track, self.parent())
            if not scored_tracks:
                return None

            best = scored_tracks[0]
            min_score = 70 if artist else 84
            if best["score"] >= min_score:
                if artist and best["artist_score"] < 40 and best["score"] < 100:
                    return None
                best_track = _hydrate_ranked_match_track(library_section, best)
                if not best_track:
                    return None
                logging.debug(
                    f"Best match for '{title}': {best_track.title} from '{best['album']}' "
                    f"(score: {best['score']:.1f}, artist: {best['artist']})"
                )
                return best_track
            return None

        except SyncCancelled:
            raise
        except Exception as e:
            logging.error(f'Error finding match for track: {str(e)}')
            return None

    def find_track_by_path(self, library_section, file_path):
        """Find track by exact file path to avoid duplicate matches

        This method tries multiple matching strategies in order of specificity:
        1. Exact full path match
        2. Suffix match (for different mount points)
        3. Partial match of last 3+ path components (artist/album/track)

        Returns the first matching track found, or None if no match.
        """
        try:
            self._ensure_not_cancelled()

            # Normalize path separators for comparison
            search_path = file_path.replace('\\', '/').lower()
            path_parts = [segment for segment in search_path.split('/') if segment]
            path_index = _get_library_path_index_cached(library_section)

            exact_matches = path_index["exact"].get(search_path, [])
            if len(exact_matches) == 1:
                logging.info(f"Found exact path match for: {file_path}")
                return _get_plex_track_by_rating_key(library_section, exact_matches[0].get("rating_key"))

            if len(path_parts) >= 3:
                suffix3 = "/".join(path_parts[-3:])
                suffix3_matches = path_index["suffix3"].get(suffix3, [])
                if len(suffix3_matches) == 1:
                    logging.info(f"Found suffix-3 path match for: {file_path}")
                    return _get_plex_track_by_rating_key(library_section, suffix3_matches[0].get("rating_key"))

            if len(path_parts) >= 2:
                suffix2 = "/".join(path_parts[-2:])
                suffix2_matches = path_index["suffix2"].get(suffix2, [])
                if len(suffix2_matches) == 1:
                    logging.info(f"Found suffix-2 path match for: {file_path}")
                    return _get_plex_track_by_rating_key(library_section, suffix2_matches[0].get("rating_key"))

            logging.debug(f"No path match found for: {file_path}")
            return None

        except SyncCancelled:
            raise
        except Exception as e:
            logging.error(f'Error finding track by path: {str(e)}')
            return None

    def find_track_by_plex_search(self, library_section, track_title, artist_name=""):
        """Find track using Plex's native search API (improved method for NAS/remote servers)

        This method uses Plex's built-in search functionality which is much more reliable
        for cross-platform scenarios (Windows -> NAS, different mount points, etc.)

        Uses the Plex Media Server API endpoint: /library/sections/{id}/all?type=10
        where type=10 specifies audio tracks.

        Args:
            library_section: Plex library section object
            track_title: Title of the track to find
            artist_name: Artist name (optional, improves accuracy)

        Returns:
            First matching Plex track object, or None if no match found
        """
        try:
            self._ensure_not_cancelled()

            # Use Plex's native search API with type=10 for tracks
            # This is much more reliable than manual iteration
            search_results = library_section.searchTracks(title=track_title, limit=50)

            if not search_results:
                logging.debug(f"No tracks found for title: {track_title}")
                return None

            # If we have an artist name, filter results by artist
            if artist_name:
                for track in search_results:
                    try:
                        # Get track's artist
                        track_artist = track.originalTitle or (track.grandparentTitle if hasattr(track, 'grandparentTitle') else '')

                        if not track_artist and hasattr(track, 'artist'):
                            track_artist_obj = track.artist()
                            if track_artist_obj:
                                track_artist = track_artist_obj.title

                        # Fuzzy match artist names (case insensitive, partial match)
                        if track_artist and artist_name.lower() in track_artist.lower():
                            logging.info(f"Found track via Plex search: {track.title} by {track_artist}")
                            return track

                    except Exception as track_error:
                        logging.debug(f"Error checking track artist: {track_error}")
                        continue

            # If no artist match or no artist provided, return first result
            # (Plex search already ranks by relevance)
            logging.info(f"Found track via Plex search (no artist filter): {search_results[0].title}")
            return search_results[0]

        except SyncCancelled:
            raise
        except Exception as e:
            logging.error(f'Error finding track by Plex search: {str(e)}')
            return None

    def _extract_recording_mbid(self, source_track):
        candidates = []
        if isinstance(source_track, dict):
            if source_track.get("recording_mbid"):
                candidates.append(str(source_track.get("recording_mbid")))
            identifier = source_track.get("identifier")
            if isinstance(identifier, str):
                candidates.append(identifier)
            elif isinstance(identifier, list):
                candidates.extend(str(value) for value in identifier if value)

        mbid_pattern = re.compile(
            r"(?:musicbrainz\.org/recording/|musicbrainz://recording/|recording/)([0-9a-fA-F-]{36})",
            re.IGNORECASE,
        )
        uuid_pattern = re.compile(
            r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
            re.IGNORECASE,
        )
        for candidate in candidates:
            match = mbid_pattern.search(candidate)
            if match:
                return match.group(1).lower()
            uuid_match = uuid_pattern.search(candidate)
            if uuid_match:
                return uuid_match.group(1).lower()
        return ""

    def _extract_recording_mbid_from_plex_track(self, plex_track):
        guid_candidates = []
        for attr in ("guid",):
            value = getattr(plex_track, attr, None)
            if value:
                guid_candidates.append(str(value))
        for guid_obj in getattr(plex_track, "guids", []) or []:
            guid_id = getattr(guid_obj, "id", None)
            if guid_id:
                guid_candidates.append(str(guid_id))

        mbid_pattern = re.compile(
            r"(?:musicbrainz\.org/recording/|musicbrainz://recording/|recording/)([0-9a-fA-F-]{36})",
            re.IGNORECASE,
        )
        for candidate in guid_candidates:
            match = mbid_pattern.search(candidate)
            if match:
                return match.group(1).lower()
        return ""

    def normalize_source_track(self, track_info):
        if isinstance(track_info, dict):
            track = dict(track_info)
            title = str(track.get("title", "") or "").strip()
            artist = str(track.get("artist", "") or "").strip()
            album = str(track.get("album", "") or "").strip()
            parsed = str(track.get("parsed", "") or "").strip()
            if not parsed and title:
                parsed = f"{title} - {artist}" if artist else title
            if not title and parsed:
                if " - " in parsed:
                    parts = parsed.split(" - ", 1)
                    title = parts[0].strip()
                    if not artist:
                        artist = parts[1].strip()
                else:
                    title = parsed

            track["title"] = title
            track["artist"] = artist
            track["album"] = album
            track["parsed"] = parsed
            track["path"] = track.get("path")
            artists = track.get("artists") or []
            if isinstance(artists, (list, tuple)):
                track["artists"] = [str(value or "").strip() for value in artists if str(value or "").strip()]
            elif artists:
                track["artists"] = [str(artists).strip()]
            else:
                track["artists"] = []
            track["isrc"] = str(track.get("isrc", "") or "").strip().upper()
            try:
                track["duration_ms"] = int(track.get("duration_ms", 0) or 0)
            except Exception:
                track["duration_ms"] = 0
            if not track.get("recording_mbid"):
                track["recording_mbid"] = self._extract_recording_mbid(track)
            return track

        parsed = self.parse_track_info_smart(str(track_info or ""))
        title = parsed
        artist = ""
        if " - " in parsed:
            parts = parsed.split(" - ", 1)
            title = parts[0].strip()
            artist = parts[1].strip()
        return {
            "title": title.strip(),
            "artist": artist.strip(),
            "album": "",
            "recording_mbid": "",
            "parsed": parsed.strip(),
            "path": None,
        }

    def parse_track_info(self, track):
        normalized = self.normalize_source_track(track)
        return (
            normalized.get("title", ""),
            normalized.get("artist", ""),
            normalized.get("album", ""),
            normalized.get("recording_mbid", ""),
        )

    def stop(self):
        self.stop_requested = True

class PlaylistSortingThread(QThread):
    progress_update = pyqtSignal(str, int)
    sorting_complete = pyqtSignal(str, int, int)  # playlist_name, matched_count, total_count
    error = pyqtSignal(str)

    def __init__(self, playlist, streaming_url, plex_server, parent=None):
        super().__init__(parent)
        self.playlist = playlist
        self.streaming_url = streaming_url
        self.plex_server = plex_server

    def run(self):
        try:
            self.progress_update.emit("Fetching streaming service playlist...", 10)
            
            # Get tracks from streaming service (reuse existing logic)
            streaming_tracks = self.get_streaming_tracks()
            
            if not streaming_tracks:
                self.error.emit("No tracks found in streaming service playlist.")
                return
            
            self.progress_update.emit("Loading current Plex playlist...", 30)
            
            # Get current Plex playlist tracks
            plex_tracks = list(self.playlist.items())
            
            self.progress_update.emit("Matching tracks...", 50)
            
            # Match and reorder tracks
            ordered_tracks = self.match_and_order_tracks(streaming_tracks, plex_tracks)
            
            if not ordered_tracks:
                self.error.emit("No matching tracks found between streaming service and Plex playlist.")
                return
            
            self.progress_update.emit("Reordering playlist...", 80)
            
            # Clear and rebuild playlist in new order
            self.playlist.removeItems(self.playlist.items())
            self.playlist.addItems(ordered_tracks)
            
            self.progress_update.emit("Complete!", 100)
            self.sorting_complete.emit(self.playlist.title, len(ordered_tracks), len(streaming_tracks))
            
        except Exception as e:
            logging.error(f"Error in playlist sorting: {str(e)}")
            self.error.emit(str(e))

    def get_streaming_tracks(self):
        """Get tracks from streaming service URL"""
        try:
            # Reuse existing PlaylistConverterThread logic
            if "spotify.com" in self.streaming_url:
                return self.get_spotify_tracks()
            elif "deezer.com" in self.streaming_url:
                return self.get_deezer_tracks()
            elif "tidal.com" in self.streaming_url:
                return self.get_tidal_tracks()
            else:
                raise ValueError("Unsupported streaming service")
                
        except Exception as e:
            logging.error(f"Error getting streaming tracks: {str(e)}")
            return []

    def get_spotify_tracks(self):
        """Get Spotify tracks using the shared enriched playlist fetch."""
        try:
            auth = SpotifyAnonymousAuth()
            playlist_id = self.streaming_url.split('/')[-1].split('?')[0]
            tracks, _, _ = fetch_spotify_playlist_tracks_enriched(playlist_id, auth)
            return [str(track.get("parsed") or f"{track.get('title', '')} - {track.get('artist', '')}".strip(" -")) for track in tracks]
        except Exception as e:
            logging.error(f"Error getting Spotify tracks: {str(e)}")
            return []

    def match_and_order_tracks(self, streaming_tracks, plex_tracks):
        """Match streaming tracks to Plex tracks and return in streaming order"""
        try:
            ordered_tracks = []
            
            for streaming_track in streaming_tracks:
                # Parse and clean streaming track info
                if ' - ' in streaming_track:
                    title, artist = streaming_track.split(' - ', 1)
                else:
                    title, artist = streaming_track, ''
                
                # ENHANCED: Clean the title to improve matching
                clean_title = self.clean_track_title(title)
                
                # Find best match in Plex tracks
                best_match = None
                best_score = 0
                
                for plex_track in plex_tracks:
                    try:
                        # Clean Plex track title too
                        clean_plex_title = self.clean_track_title(plex_track.title) if plex_track.title else ""
                        
                        # Calculate similarity with cleaned titles
                        from fuzzywuzzy import fuzz
                        
                        # Try multiple matching approaches
                        title_score = max(
                            fuzz.ratio(clean_title.lower(), clean_plex_title.lower()),
                            fuzz.partial_ratio(clean_title.lower(), clean_plex_title.lower()),
                            fuzz.token_set_ratio(clean_title.lower(), clean_plex_title.lower())
                        )
                        
                        artist_score = 0
                        if artist:
                            clean_artist = self.clean_artist_name(artist)
                            if plex_track.originalTitle:
                                plex_artist = self.clean_artist_name(plex_track.originalTitle)
                                artist_score = fuzz.token_set_ratio(clean_artist.lower(), plex_artist.lower())
                            elif hasattr(plex_track, 'artist') and plex_track.artist():
                                plex_artist = self.clean_artist_name(plex_track.artist().title)
                                artist_score = fuzz.token_set_ratio(clean_artist.lower(), plex_artist.lower())
                        
                        # Adjust weights - if no artist info, rely more on title
                        if artist:
                            combined_score = (title_score * 0.7) + (artist_score * 0.3)
                        else:
                            combined_score = title_score  # Pure title matching
                        
                        # LOWERED threshold and added logging for debugging
                        if combined_score > best_score and combined_score > 60:  # Was 70, now 60
                            best_score = combined_score
                            best_match = plex_track
                            
                    except Exception as e:
                        logging.warning(f"Error matching track: {str(e)}")
                        continue
                
                if best_match and best_match not in ordered_tracks:
                    ordered_tracks.append(best_match)
                    logging.info(f"✅ Matched '{streaming_track}' to '{best_match.title}' (score: {best_score:.1f})")
                elif best_match:
                    logging.warning(f"❌ Track already in playlist: '{streaming_track}' (score: {best_score:.1f})")
                else:
                    logging.warning(f"❌ No match for '{streaming_track}' (best score: {best_score:.1f})")
            
            return ordered_tracks
            
        except Exception as e:
            logging.error(f"Error matching tracks: {str(e)}")
            return []
    
    def clean_track_title(self, title):
        """Clean track title for better matching"""
        if not title:
            return ""
        
        import re
        
        # Remove common additions that cause matching issues
        cleaned = title
        
        # Remove feat/featuring variations (case insensitive)
        feat_patterns = [
            r'\(feat\.?\s+[^)]+\)',     # (feat. Artist)
            r'\(ft\.?\s+[^)]+\)',      # (ft. Artist)
            r'\(featuring\s+[^)]+\)',  # (featuring Artist)
            r'\(with\s+[^)]+\)',       # (with Artist)
            r'feat\.?\s+.+$',          # feat. Artist (at end)
            r'ft\.?\s+.+$',            # ft. Artist (at end)
            r'featuring\s+.+$',        # featuring Artist (at end)
        ]
        
        for pattern in feat_patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        
        # Remove extra whitespace and common suffixes
        cleaned = re.sub(r'\s+', ' ', cleaned)  # Multiple spaces to single
        cleaned = cleaned.strip(' -()[]')       # Trim common chars
        
        return cleaned
    
    def clean_artist_name(self, artist):
        """Clean artist name for better matching"""
        if not artist:
            return ""
        
        import re
        
        # Remove "feat" mentions from artist field too
        cleaned = re.sub(r'\s*feat\.?\s+.+$', '', artist, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*ft\.?\s+.+$', '', artist, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*featuring\s+.+$', '', artist, flags=re.IGNORECASE)
        
        return cleaned.strip()

class TimeoutException(Exception):
    pass

def timeout_handler(sig, frame):
    raise TimeoutException

class TrackMatchConfirmationDialog(QDialog):
    def __init__(self, source_track, plex_track, match_score, parent=None):
        super().__init__(parent)
        self.source_track = source_track
        self.plex_track = plex_track
        self.match_score = match_score
        self.user_choice = None
        self.setup_ui()

    def _source_track_display(self):
        if isinstance(self.source_track, dict):
            title = str(self.source_track.get("title", "") or "").strip()
            artist = str(self.source_track.get("artist", "") or "").strip()
            album = str(self.source_track.get("album", "") or "").strip()
            if title and artist and album:
                return f"{title} - {artist}\nAlbum: {album}"
            if title and artist:
                return f"{title} - {artist}"
            return title or str(self.source_track)
        return str(self.source_track)
        
    def setup_ui(self):
        self.setWindowTitle("Confirm Track Match")
        self.setModal(True)
        
        # Set minimum size but allow resizing
        self.setMinimumSize(750, 650)
        self.resize(800, 700)
        
        # Remove maximize button but keep resize ability
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        
        # Main dark theme matching the app
        self.setStyleSheet("""
            QDialog { 
                background-color: #2b2b2b; 
                color: #ffffff; 
            }
            QLabel { 
                color: #ffffff; 
                background-color: transparent;
            }
            QFrame {
                background-color: #2b2b2b;
            }
        """)
        
        # Create main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)
        
        # Create scrollable area for content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #2b2b2b;
            }
            QScrollBar:vertical {
                background-color: #3a3a3a;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #555555;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #666666;
            }
        """)
        
        # Content widget inside scroll area
        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: #2b2b2b;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(25)
        content_layout.setContentsMargins(10, 10, 10, 10)
        
        # Header section
        header_frame = self.create_header_section()
        content_layout.addWidget(header_frame)
        
        # Source track section
        source_frame = self.create_source_section()
        content_layout.addWidget(source_frame)
        
        # Plex track section
        plex_frame = self.create_plex_section()
        content_layout.addWidget(plex_frame)
        
        # Instructions
        instructions_frame = self.create_instructions_section()
        content_layout.addWidget(instructions_frame)
        
        # Add stretch to push content to top
        content_layout.addStretch()
        
        # Set up scroll area
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
        
        # Button section (fixed at bottom)
        button_frame = self.create_button_section()
        main_layout.addWidget(button_frame)
        
        # Set focus
        self.use_btn.setFocus()
        
    def create_header_section(self):
        """Create the header with title and score"""
        frame = QFrame()
        frame.setStyleSheet("background-color: #2b2b2b;")
        layout = QVBoxLayout(frame)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("🎵 Track Match Confirmation")
        title.setFont(QFont("Arial", 24, QFont.Bold))
        title.setStyleSheet("color: #00bcd4;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Score with dynamic color
        score_color = self.get_score_color()
        score = QLabel(f"Match Confidence: {self.match_score:.1f}%")
        score.setFont(QFont("Arial", 20, QFont.Bold))
        score.setStyleSheet(f"color: {score_color};")
        score.setAlignment(Qt.AlignCenter)
        layout.addWidget(score)
        
        # Warning
        warning = QLabel("⚠️ Please review this track match carefully")
        warning.setFont(QFont("Arial", 16, QFont.Bold))
        warning.setStyleSheet("color: #ffa726;")
        warning.setAlignment(Qt.AlignCenter)
        layout.addWidget(warning)
        
        return frame
        
    def create_source_section(self):
        """Create the source track section"""
        frame = QFrame()
        frame.setStyleSheet("background-color: #2b2b2b;")
        layout = QVBoxLayout(frame)
        layout.setSpacing(10)
        
        # Header
        header = QLabel("📱 SOURCE TRACK (From Streaming Service)")
        header.setFont(QFont("Arial", 16, QFont.Bold))
        header.setStyleSheet("color: #00bcd4; padding: 5px;")
        layout.addWidget(header)
        
        # Content box
        content_box = QLabel(self._source_track_display())
        content_box.setWordWrap(True)
        content_box.setAlignment(Qt.AlignTop)
        content_box.setMinimumHeight(80)
        content_box.setStyleSheet("""
            QLabel {
                background-color: #3a3a3a;
                border: 2px solid #00bcd4;
                border-radius: 8px;
                padding: 20px;
                font-size: 14px;
                font-weight: bold;
                color: #ffffff;
                line-height: 1.4;
            }
        """)
        layout.addWidget(content_box)
        
        return frame
        
    def create_plex_section(self):
        """Create the Plex track section"""
        frame = QFrame()
        frame.setStyleSheet("background-color: #2b2b2b;")
        layout = QVBoxLayout(frame)
        layout.setSpacing(10)
        
        # Header
        header = QLabel("🎬 PLEX LIBRARY MATCH")
        header.setFont(QFont("Arial", 16, QFont.Bold))
        header.setStyleSheet("color: #888888; padding: 5px;")
        layout.addWidget(header)
        
        # Content box
        plex_info = self.get_plex_info()
        content_box = QLabel(plex_info)
        content_box.setWordWrap(True)
        content_box.setAlignment(Qt.AlignTop)
        content_box.setMinimumHeight(80)
        content_box.setStyleSheet("""
            QLabel {
                background-color: #404040;
                border: 2px solid #666666;
                border-radius: 8px;
                padding: 20px;
                font-size: 14px;
                font-weight: bold;
                color: #ffffff;
                line-height: 1.4;
            }
        """)
        layout.addWidget(content_box)
        
        return frame
        
    def create_instructions_section(self):
        """Create the instructions section"""
        frame = QFrame()
        frame.setStyleSheet("background-color: #2b2b2b;")
        layout = QVBoxLayout(frame)
        layout.setSpacing(10)
        
        instructions = QLabel("Choose what to do with this track match:")
        instructions.setFont(QFont("Arial", 16, QFont.Bold))
        instructions.setStyleSheet("color: #ffffff; padding: 10px;")
        instructions.setAlignment(Qt.AlignCenter)
        layout.addWidget(instructions)
        
        return frame
        
    def create_button_section(self):
        """Create the button section"""
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background-color: #353535;
                border-top: 2px solid #555555;
                border-radius: 0px;
            }
        """)
        
        layout = QHBoxLayout(frame)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Create buttons
        self.use_btn = self.create_button(
            "✅ Use This Match", 
            "#00bcd4", 
            "#00acc1",
            self.use_match
        )
        
        self.skip_btn = self.create_button(
            "❌ Skip This Track", 
            "#666666", 
            "#777777",
            self.skip_track
        )
        
        self.skip_all_btn = self.create_button(
            "⏭️ Skip All Low Matches", 
            "#888888", 
            "#999999",
            self.skip_all_low_matches
        )
        
        # Add buttons to layout
        layout.addWidget(self.use_btn)
        layout.addWidget(self.skip_btn)
        layout.addWidget(self.skip_all_btn)
        
        return frame
        
    def create_button(self, text, bg_color, hover_color, click_handler):
        """Create a styled button"""
        button = QPushButton(text)
        button.clicked.connect(click_handler)
        button.setFont(QFont("Arial", 12, QFont.Bold))
        button.setMinimumHeight(50)
        button.setMinimumWidth(180)
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg_color};
                color: white;
                font-weight: bold;
                padding: 15px 20px;
                border-radius: 6px;
                border: none;
                font-size: 13px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: {hover_color};
            }}
        """)
        return button
        
    def get_score_color(self):
        """Get color based on match score"""
        if self.match_score < 70:
            return "#ff6b6b"  # Soft red
        elif self.match_score < 80:
            return "#ffa726"  # Soft orange
        else:
            return "#00bcd4"  # App's teal color
            
    def get_plex_info(self):
        """Get Plex track info with better formatting"""
        try:
            if not self.plex_track:
                return "❌ No Plex track found"
            
            title = getattr(self.plex_track, 'title', 'Unknown Title')
            
            # Get artist info
            artist = 'Unknown Artist'
            if hasattr(self.plex_track, 'originalTitle') and self.plex_track.originalTitle:
                artist = self.plex_track.originalTitle
            elif hasattr(self.plex_track, 'artist'):
                try:
                    artist_obj = self.plex_track.artist()
                    if artist_obj and hasattr(artist_obj, 'title'):
                        artist = artist_obj.title
                except:
                    pass
            
            # Get album info
            album_info = ''
            if hasattr(self.plex_track, 'album'):
                try:
                    album_obj = self.plex_track.album()
                    if album_obj and hasattr(album_obj, 'title'):
                        album_info = f"\n🎵 Album: {album_obj.title}"
                except:
                    pass
            
            # Get track number if available
            track_info = ''
            if hasattr(self.plex_track, 'index') and self.plex_track.index:
                track_info = f"\n🔢 Track: #{self.plex_track.index}"
            
            # Get duration if available
            duration_info = ''
            if hasattr(self.plex_track, 'duration') and self.plex_track.duration:
                duration_ms = self.plex_track.duration
                duration_sec = duration_ms // 1000
                minutes = duration_sec // 60
                seconds = duration_sec % 60
                duration_info = f"\n⏱️ Duration: {minutes}:{seconds:02d}"
            
            return f"🎵 {title}\n👤 Artist: {artist}{album_info}{track_info}{duration_info}"
            
        except Exception as e:
            return f"❌ Error loading track info: {str(e)}"
    
    def use_match(self):
        """User accepts the match"""
        self.user_choice = "use"
        self.accept()
    
    def skip_track(self):
        """User skips this track"""
        self.user_choice = "skip"
        self.accept()
    
    def skip_all_low_matches(self):
        """User skips all low confidence matches"""
        self.user_choice = "skip_all"
        self.accept()
        
    def keyPressEvent(self, event):
        """Handle keyboard shortcuts"""
        if event.key() == Qt.Key_Enter or event.key() == Qt.Key_Return:
            self.use_match()
        elif event.key() == Qt.Key_Escape:
            self.skip_track()
        else:
            super().keyPressEvent(event)

class SpotifyLoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Login to Spotify")
        self.setModal(True)
        self.setFixedSize(450, 400)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("<h2>🎵 Connect to Spotify</h2>")
        header.setAlignment(Qt.AlignCenter)
        layout.addWidget(header)
        
        # Instructions
        instructions = QLabel("""
        <div style='text-align: left; padding: 20px; line-height: 1.5;'>
        <p><b>Simple Cookie-Based Login:</b></p>
        
        <p><b>Step 1:</b> Open <a href="https://open.spotify.com">https://open.spotify.com</a> and login</p>
        <p><b>Step 2:</b> Press <b>F12</b> → <b>Application</b> tab → <b>Cookies</b></p>
        <p><b>Step 3:</b> Find <b>sp_dc</b> cookie and copy its value</p>
        <p><b>Step 4:</b> Paste the value below</p>
        </div>
        """)
        instructions.setWordWrap(True)
        instructions.setOpenExternalLinks(True)
        layout.addWidget(instructions)
        
        # Cookie input
        cookie_group = QGroupBox("Cookie Value")
        cookie_layout = QVBoxLayout(cookie_group)
        
        self.cookie_input = QTextEdit()
        self.cookie_input.setPlaceholderText("Paste your sp_dc cookie value here...")
        self.cookie_input.setMaximumHeight(80)
        self.cookie_input.textChanged.connect(self.validate_cookie)
        cookie_layout.addWidget(self.cookie_input)
        
        layout.addWidget(cookie_group)
        
        # Status
        self.status_label = QLabel("Paste your cookie and it will be validated automatically")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #888888; padding: 10px;")
        layout.addWidget(self.status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.ok_button = QPushButton("✅ Save & Login")
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setEnabled(False)
        self.ok_button.setStyleSheet("""
            QPushButton {
                background-color: #1DB954;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1ed760;
            }
            QPushButton:disabled {
                background-color: #666666;
            }
        """)
        button_layout.addWidget(self.ok_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        # Initialize result
        self.login_successful = False
        self.sp_dc_cookie = ""
    
    def validate_cookie(self):
        """Validate cookie as user types"""
        cookie_text = self.cookie_input.toPlainText().strip()
        
        if len(cookie_text) < 10:
            self.status_label.setText("Paste your sp_dc cookie value above")
            self.status_label.setStyleSheet("color: #888;")
            self.ok_button.setEnabled(False)
        elif len(cookie_text) < 50:
            self.status_label.setText("❌ Value seems too short - make sure you copied the full value")
            self.status_label.setStyleSheet("color: #f44336;")
            self.ok_button.setEnabled(False)
        else:
            self.status_label.setText("✅ Cookie looks valid! Click 'Save & Login' to continue")
            self.status_label.setStyleSheet("color: #1DB954; font-weight: bold;")
            self.sp_dc_cookie = cookie_text
            self.login_successful = True
            self.ok_button.setEnabled(True)

class SpotifyUserPlaylistsDialog(QDialog):
    def __init__(self, spotify_auth, parent=None):
        super().__init__(parent)
        self.spotify_auth = spotify_auth
        self.setWindowTitle("Import Your Spotify Playlists")
        self.setModal(True)
        self.resize(600, 500)
        self.selected_playlists = []
        self.setup_ui()
        self.load_user_playlists()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header = QLabel("<h3>Select Playlists to Import</h3>")
        layout.addWidget(header)
        
        # Loading label
        self.loading_label = QLabel("Loading your playlists...")
        self.loading_label.setAlignment(Qt.AlignCenter)
        self.loading_label.setStyleSheet("color: #888888; padding: 20px;")
        layout.addWidget(self.loading_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Playlists list
        self.playlists_widget = QListWidget()
        self.playlists_widget.setVisible(False)
        layout.addWidget(self.playlists_widget)
        
        # Selection controls
        selection_layout = QHBoxLayout()
        
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all_playlists)
        self.select_all_btn.setVisible(False)
        selection_layout.addWidget(self.select_all_btn)
        
        self.select_none_btn = QPushButton("Select None")
        self.select_none_btn.clicked.connect(self.select_no_playlists)
        self.select_none_btn.setVisible(False)
        selection_layout.addWidget(self.select_none_btn)
        
        selection_layout.addStretch()
        layout.addLayout(selection_layout)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.import_button = QPushButton("Import Selected Playlists")
        self.import_button.clicked.connect(self.accept)
        self.import_button.setEnabled(False)
        self.import_button.setStyleSheet("""
            QPushButton {
                background-color: #1DB954;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1ed760;
            }
            QPushButton:disabled {
                background-color: #666666;
            }
        """)
        button_layout.addWidget(self.import_button)
        
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
    
    def load_user_playlists(self):
        """Load user's playlists in background thread"""
        self.load_thread = LoadUserPlaylistsThread(self.spotify_auth, self)
        self.load_thread.playlists_loaded.connect(self.on_playlists_loaded)
        self.load_thread.error.connect(self.on_load_error)
        self.load_thread.start()
    
    def on_playlists_loaded(self, playlists):
        """Handle playlists loaded"""
        self.loading_label.setVisible(False)
        self.playlists_widget.setVisible(True)
        self.select_all_btn.setVisible(True)
        self.select_none_btn.setVisible(True)
        
        for playlist in playlists:
            item = QListWidgetItem()
            item.setText(f"{playlist['name']} ({playlist['tracks']['total']} tracks)")
            item.setData(Qt.UserRole, playlist)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.playlists_widget.addItem(item)
        
        self.import_button.setEnabled(True)
        self.loading_label.setText(f"✅ Found {len(playlists)} playlists in your account")
        self.loading_label.setVisible(True)
    
    def on_load_error(self, error_message):
        """Handle loading error"""
        self.loading_label.setText(f"❌ Error loading playlists: {error_message}")
        QMessageBox.warning(self, "Error", f"Failed to load playlists: {error_message}")
    
    def select_all_playlists(self):
        """Select all playlists"""
        for i in range(self.playlists_widget.count()):
            item = self.playlists_widget.item(i)
            item.setCheckState(Qt.Checked)
    
    def select_no_playlists(self):
        """Deselect all playlists"""
        for i in range(self.playlists_widget.count()):
            item = self.playlists_widget.item(i)
            item.setCheckState(Qt.Unchecked)
    
    def get_selected_playlists(self):
        """Get list of selected playlists"""
        selected = []
        for i in range(self.playlists_widget.count()):
            item = self.playlists_widget.item(i)
            if item.checkState() == Qt.Checked:
                selected.append(item.data(Qt.UserRole))
        return selected

class ManualCookieDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manual Cookie Entry")
        self.setModal(True)
        self.setFixedSize(500, 400)
        self.cookie_value = ""
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Instructions
        instructions = QLabel("""
        <h3>📋 Manual Cookie Entry</h3>
        <p><b>Step 1:</b> Open <a href="https://open.spotify.com">https://open.spotify.com</a> in your browser</p>
        <p><b>Step 2:</b> Login to your Spotify account</p>
        <p><b>Step 3:</b> Press <b>F12</b> → <b>Application</b> tab → <b>Cookies</b> → <b>https://open.spotify.com</b></p>
        <p><b>Step 4:</b> Find cookie named <b>sp_dc</b> and copy its value</p>
        <p><b>Step 5:</b> Paste the value below</p>
        """)
        instructions.setWordWrap(True)
        instructions.setOpenExternalLinks(True)
        layout.addWidget(instructions)
        
        # Cookie input
        cookie_group = QGroupBox("Cookie Value")
        cookie_layout = QVBoxLayout(cookie_group)
        
        self.cookie_input = QTextEdit()
        self.cookie_input.setPlaceholderText("Paste your sp_dc cookie value here...")
        self.cookie_input.setMaximumHeight(80)
        cookie_layout.addWidget(self.cookie_input)
        
        # Validation button
        validate_button = QPushButton("🔍 Validate Cookie")
        validate_button.clicked.connect(self.validate_cookie)
        cookie_layout.addWidget(validate_button)
        
        layout.addWidget(cookie_group)
        
        # Status
        self.status_label = QLabel("Paste your cookie and click validate")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #888888; padding: 10px;")
        layout.addWidget(self.status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.ok_button = QPushButton("✅ Use Cookie")
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setEnabled(False)
        self.ok_button.setStyleSheet("""
            QPushButton {
                background-color: #1DB954;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1ed760;
            }
            QPushButton:disabled {
                background-color: #666666;
            }
        """)
        button_layout.addWidget(self.ok_button)
        
        cancel_button = QPushButton("❌ Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
    
    def validate_cookie(self):
        """Validate the entered cookie"""
        cookie_text = self.cookie_input.toPlainText().strip()
        
        if not cookie_text:
            self.status_label.setText("❌ Please enter a cookie value")
            return
        
        if len(cookie_text) < 50:
            self.status_label.setText("❌ Cookie value seems too short")
            return
        
        # Test the cookie
        try:
            self.status_label.setText("🔄 Testing cookie...")
            QApplication.processEvents()
            
            # Create a test auth instance
            global SP_DC_COOKIE
            original_cookie = SP_DC_COOKIE
            SP_DC_COOKIE = cookie_text
            
            auth = SpotifyAnonymousAuth()
            token = auth.get_token()
            
            if token:
                self.status_label.setText("✅ Cookie is valid!")
                self.cookie_value = cookie_text
                self.ok_button.setEnabled(True)
            else:
                self.status_label.setText("❌ Cookie validation failed")
                SP_DC_COOKIE = original_cookie
                
        except Exception as e:
            self.status_label.setText(f"❌ Cookie test failed: {str(e)}")
            SP_DC_COOKIE = original_cookie

class OAuthCallbackServer:
    def __init__(self, dialog):
        self.dialog = dialog
        self.port = self.get_free_port()
        self.running = False
        self.httpd = None
    
    def get_free_port(self):
        """Get a fixed port for the callback server"""
        # Use a fixed port instead of random
        FIXED_PORT = 8888  # This should be registered with your Spotify app
        
        # Check if port is available
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', FIXED_PORT))
                return FIXED_PORT
        except OSError:
            # If 8888 is busy, try a few alternatives (all should be registered)
            for port in [8889, 8890, 8891, 8892]:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.bind(('127.0.0.1', port))
                        return port
                except OSError:
                    continue
            
            # Fallback to original method if all fixed ports are busy
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', 0))
                s.listen(1)
                port = s.getsockname()[1]
            return port

    
    def run(self):
        """Run the OAuth callback server"""
        try:
            class CallbackHandler(BaseHTTPRequestHandler):
                def __init__(self, server_instance, *args, **kwargs):
                    self.server_instance = server_instance
                    super().__init__(*args, **kwargs)
                
                def do_GET(self):
                    """Handle GET request (OAuth callback)"""
                    try:
                        # Parse the callback URL
                        parsed_url = urllib.parse.urlparse(self.path)
                        query_params = urllib.parse.parse_qs(parsed_url.query)
                        
                        if 'code' in query_params:
                            # Success - we got the authorization code
                            self.send_response(200)
                            self.send_header('Content-type', 'text/html')
                            self.end_headers()
                            
                            success_html = """
                            <html>
                            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                                <h1>✅ Login Successful!</h1>
                                <p>You can now close this browser tab and return to the application.</p>
                                <script>
                                    setTimeout(function() {
                                        window.close();
                                    }, 3000);
                                </script>
                            </body>
                            </html>
                            """
                            self.wfile.write(success_html.encode())
                            
                            # Try to extract cookie (this is a simplified approach)
                            # In a real implementation, you'd exchange the code for tokens
                            self.server_instance.handle_success()
                            
                        elif 'error' in query_params:
                            # Error in OAuth flow
                            error = query_params['error'][0]
                            self.send_response(400)
                            self.send_header('Content-type', 'text/html')
                            self.end_headers()
                            
                            error_html = f"""
                            <html>
                            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                                <h1>❌ Login Failed</h1>
                                <p>Error: {error}</p>
                                <p>You can close this tab and try again.</p>
                            </body>
                            </html>
                            """
                            self.wfile.write(error_html.encode())
                            
                            self.server_instance.handle_error(error)
                        
                        else:
                            # Unknown callback
                            self.send_response(400)
                            self.send_header('Content-type', 'text/html')
                            self.end_headers()
                            self.wfile.write(b"Invalid callback")
                    
                    except Exception as e:
                        logging.error(f"OAuth callback error: {e}")
                        self.server_instance.handle_error(str(e))
                
                def log_message(self, format, *args):
                    # Suppress server logs
                    pass
            
            # Create server with custom handler
            handler = lambda *args, **kwargs: CallbackHandler(self, *args, **kwargs)
            self.httpd = HTTPServer(('localhost', self.port), handler)
            self.running = True
            
            logging.info(f"OAuth callback server started on port {self.port}")
            self.httpd.serve_forever()
            
        except Exception as e:
            logging.error(f"OAuth server error: {e}")
            self.handle_error(str(e))
    
    def handle_success(self):
        """Handle successful OAuth callback"""
        # Since we can't easily extract cookies from the OAuth flow,
        # we'll prompt the user to get the cookie manually after login
        QTimer.singleShot(100, self.prompt_for_cookie)
    
    def prompt_for_cookie(self):
        """Prompt user to extract cookie after successful OAuth"""
        # Show a dialog asking user to get the cookie
        cookie_dialog = PostOAuthCookieDialog(self.dialog)
        if cookie_dialog.exec() == QDialog.Accepted:
            self.dialog.oauth_success(cookie_dialog.cookie_value)
        else:
            self.dialog.oauth_error("Cookie extraction cancelled")
    
    def handle_error(self, error):
        """Handle OAuth error"""
        QTimer.singleShot(100, lambda: self.dialog.oauth_error(error))
    
    def stop(self):
        """Stop the OAuth server"""
        self.running = False
        if self.httpd:
            self.httpd.shutdown()

class PostOAuthCookieDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Extract Cookie")
        self.setModal(True)
        self.setFixedSize(450, 300)
        self.cookie_value = ""
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Instructions
        instructions = QLabel("""
        <h3>🔄 One More Step!</h3>
        <p>Your browser should now be logged into Spotify.</p>
        <p><b>To complete the setup:</b></p>
        <ol>
        <li>In your browser, press <b>F12</b></li>
        <li>Go to <b>Application</b> tab → <b>Cookies</b> → <b>https://open.spotify.com</b></li>
        <li>Find cookie named <b>sp_dc</b></li>
        <li>Copy its value and paste below</li>
        </ol>
        """)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Cookie input
        self.cookie_input = QLineEdit()
        self.cookie_input.setPlaceholderText("Paste sp_dc cookie value here...")
        layout.addWidget(self.cookie_input)
        
        # Auto-validate as user types
        self.cookie_input.textChanged.connect(self.validate_cookie)
        
        # Status
        self.status_label = QLabel("Paste the sp_dc cookie value")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #888888; padding: 10px;")
        layout.addWidget(self.status_label)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.ok_button = QPushButton("✅ Complete Setup")
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setEnabled(False)
        self.ok_button.setStyleSheet("""
            QPushButton {
                background-color: #1DB954;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1ed760;
            }
            QPushButton:disabled {
                background-color: #666666;
            }
        """)
        button_layout.addWidget(self.ok_button)
        
        manual_button = QPushButton("📋 Manual Method")
        manual_button.clicked.connect(self.show_manual_method)
        button_layout.addWidget(manual_button)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
    
    def validate_cookie(self):
        """Validate cookie as user types"""
        cookie_text = self.cookie_input.text().strip()
        
        if len(cookie_text) < 10:
            self.status_label.setText("Enter the sp_dc cookie value...")
            self.ok_button.setEnabled(False)
        elif len(cookie_text) < 50:
            self.status_label.setText("Cookie value seems too short...")
            self.ok_button.setEnabled(False)
        else:
            self.status_label.setText("✅ Cookie looks valid!")
            self.cookie_value = cookie_text
            self.ok_button.setEnabled(True)
    
    def show_manual_method(self):
        """Show detailed manual instructions"""
        QMessageBox.information(self, "Manual Cookie Extraction", 
            "1. Go to https://open.spotify.com in your browser\n"
            "2. Make sure you're logged in\n"
            "3. Press F12 to open Developer Tools\n"
            "4. Click 'Application' tab (Chrome) or 'Storage' tab (Firefox)\n"
            "5. Expand 'Cookies' → click 'https://open.spotify.com'\n"
            "6. Find cookie named 'sp_dc'\n"
            "7. Copy the 'Value' (it's a long string)\n"
            "8. Paste it in the input field above")
        
class LoadUserPlaylistsThread(QThread):
    playlists_loaded = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def __init__(self, spotify_auth, parent=None):
        super().__init__(parent)
        self.spotify_auth = spotify_auth
    
    def run(self):
        try:
            # Get TOTP token and client ID
            token = self.spotify_auth.refresh_token_if_needed()
            client_id = self.spotify_auth.cached_client_id

            # Headers with proper authentication
            headers = {
                'Authorization': f'Bearer {token}',
                'Client-Id': client_id,
                'User-Agent': self.spotify_auth.user_agent,
                'Accept': 'application/json',
            }

            # Get playlists using Spotify Web API with TOTP token
            playlists = []
            url = 'https://api.spotify.com/v1/me/playlists?limit=50'

            while url:
                response = requests.get(url, headers=headers, timeout=30)

                print(f"Playlist request: {response.status_code} - {url}")
                print(f"Response headers: {dict(response.headers)}")

                if response.status_code == 401:
                    raise Exception("Token expired or invalid. Please login again.")
                elif response.status_code == 404:
                    raise Exception("Playlists not accessible. Your account may have restricted privacy settings.")
                elif response.status_code != 200:
                    raise Exception(f"Failed to get playlists: {response.status_code} - {response.text}")

                data = response.json()
                playlists.extend(data['items'])
                url = data.get('next')

            # Filter for playlists with tracks
            user_playlists = []
            for playlist in playlists:
                if playlist['tracks']['total'] > 0:
                    user_playlists.append(playlist)

            self.playlists_loaded.emit(user_playlists)

        except Exception as e:
            logging.error(f"Error loading user playlists: {str(e)}")
            self.error.emit(str(e))

class SpotifyAnonymousAuth:
    def __init__(self):
        self.access_token = None
        self.token_expiration = 0
        self.client_id = None
        self.user_agent = None
        self.session = self._setup_session()
        
        # TOTP Configuration from friend's working code
        self.secret_cipher_dict = {
            "61": [123, 105, 79, 70, 110, 59, 52, 125, 60, 49, 80, 70, 89, 75, 80, 86, 63, 53, 123, 37, 117, 49, 52, 93, 77, 62, 47, 86, 48, 104, 68, 72],
            "60": [79, 109, 69, 123, 90, 65, 46, 74, 94, 34, 58, 48, 70, 71, 92, 85, 122, 63, 91, 64, 87, 87],
            "59": [44, 55, 47, 42, 70, 40, 34, 114, 76, 74, 50, 111, 120, 97, 75, 76, 94, 102, 43, 69, 49, 120, 118, 80, 64, 78],
        }
        self.secret_dict_source = (os.getenv("SPOTIFY_SECRET_DICT_URL") or "https://github.com/xyloflake/spot-secrets-go/blob/main/secrets/secretDict.json?raw=true").strip()
        self.token_max_retries = 3
        self.token_retry_delay = 0.5
        self.secret_fetch_timeout = 15
        self.totp_ver = 0  # Auto-select highest
        self.token_url = "https://open.spotify.com/api/token"
        self.server_time_url = "https://open.spotify.com/"
        
        # Cache variables
        self.cached_access_token = None
        self.cached_client_id = ""
        self.access_token_expires_at = 0
        
    def _setup_session(self):
        """Setup session with proper retry strategy"""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=5,
            connect=3,
            read=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD", "OPTIONS"],
            raise_on_status=False,
            respect_retry_after_header=True
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=100, pool_maxsize=100)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        
        return session

    def get_random_user_agent(self) -> str:
        """Generate a random realistic browser user agent"""
        browser = random.choice(['chrome', 'firefox', 'edge', 'safari'])

        if browser == 'chrome':
            os_choice = random.choice(['mac', 'windows'])
            if os_choice == 'mac':
                return (
                    f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_{random.randrange(11, 15)}_{random.randrange(4, 9)}) "
                    f"AppleWebKit/{random.randrange(530, 537)}.{random.randrange(30, 37)} (KHTML, like Gecko) "
                    f"Chrome/{random.randrange(80, 105)}.0.{random.randrange(3000, 4500)}.{random.randrange(60, 125)} "
                    f"Safari/{random.randrange(530, 537)}.{random.randrange(30, 36)}"
                )
            else:
                chrome_version = random.randint(80, 105)
                build = random.randint(3000, 4500)
                patch = random.randint(60, 125)
                return (
                    f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    f"AppleWebKit/537.36 (KHTML, like Gecko) "
                    f"Chrome/{chrome_version}.0.{build}.{patch} Safari/537.36"
                )

        elif browser == 'firefox':
            os_choice = random.choice(['windows', 'mac', 'linux'])
            version = random.randint(90, 110)
            if os_choice == 'windows':
                return (
                    f"Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:{version}.0) "
                    f"Gecko/20100101 Firefox/{version}.0"
                )
            elif os_choice == 'mac':
                return (
                    f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_{random.randrange(11, 15)}_{random.randrange(0, 10)}; rv:{version}.0) "
                    f"Gecko/20100101 Firefox/{version}.0"
                )
            else:
                return (
                    f"Mozilla/5.0 (X11; Linux x86_64; rv:{version}.0) "
                    f"Gecko/20100101 Firefox/{version}.0"
                )

        elif browser == 'edge':
            chrome_version = random.randint(80, 105)
            build = random.randint(3000, 4500)
            patch = random.randint(60, 125)
            version_str = f"{chrome_version}.0.{build}.{patch}"
            return (
                f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                f"AppleWebKit/537.36 (KHTML, like Gecko) "
                f"Chrome/{version_str} Safari/537.36 Edg/{version_str}"
            )

        elif browser == 'safari':
            mac_major = random.randrange(11, 16)
            mac_minor = random.randrange(0, 10)
            webkit_major = random.randint(600, 610)
            webkit_minor = random.randint(1, 20)
            webkit_patch = random.randint(1, 20)
            safari_version = random.randint(13, 16)
            return (
                f"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_{mac_major}_{mac_minor}) "
                f"AppleWebKit/{webkit_major}.{webkit_minor}.{webkit_patch} (KHTML, like Gecko) "
                f"Version/{safari_version}.0 Safari/{webkit_major}.{webkit_minor}.{webkit_patch}"
            )
        
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def fetch_server_time(self, user_agent: str) -> int:
        """Fetch server time from Spotify using Date header"""
        headers = {
            "User-Agent": user_agent,
            "Accept": "*/*",
        }

        try:
            if platform.system() != 'Windows':
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(17)
            response = self.session.head(self.server_time_url, headers=headers, timeout=15, verify=True)
            response.raise_for_status()
        except TimeoutException as e:
            raise Exception(f"fetch_server_time() timeout after 17s: {e}")
        except Exception as e:
            raise Exception(f"fetch_server_time() error: {e}")
        finally:
            if platform.system() != 'Windows':
                signal.alarm(0)

        date_hdr = response.headers.get("Date")
        if not date_hdr:
            raise Exception("fetch_server_time() missing 'Date' header")

        return int(parsedate_to_datetime(date_hdr).timestamp())

    def generate_totp(self, secret_dict: Optional[Dict[str, List[int]]] = None, server_time: Optional[int] = None) -> str:
        """Generate a TOTP value for the provided server time"""
        if secret_dict is None:
            secret_dict = self.secret_cipher_dict
        if server_time is None:
            raise ValueError("server_time is required to generate TOTP")

        ver = self.totp_ver or max(map(int, secret_dict))
        key = str(ver)
        if key not in secret_dict:
            raise Exception(f"generate_totp(): Defined TOTP_VER ({ver}) is missing in SECRET_CIPHER_DICT")

        secret_cipher_bytes = secret_dict[key]
        transformed = [e ^ ((t % 33) + 9) for t, e in enumerate(secret_cipher_bytes)]
        joined = ''.join(str(num) for num in transformed)
        hex_str = joined.encode().hex()
        secret = base64.b32encode(bytes.fromhex(hex_str)).decode().rstrip("=")

        totp = pyotp.TOTP(secret, digits=6, interval=30)
        return totp.at(server_time)

    def fetch_and_update_secrets(self):
        """Fetch updated secrets from remote or local source"""
        source = (self.secret_dict_source or '').strip()
        if not source:
            return False

        try:
            payload = None
            if source.lower().startswith(('http://', 'https://')):
                headers = {
                    "User-Agent": self.get_random_user_agent(),
                    "Accept": "application/json",
                }
                response = self.session.get(source, headers=headers, timeout=self.secret_fetch_timeout, verify=True)
                response.raise_for_status()
                payload = response.json()
            else:
                resolved_source = source
                if source.startswith('file:'):
                    parsed = urllib.parse.urlparse(source)
                    raw_path = parsed.path
                    if parsed.netloc:
                        raw_path = f"/{parsed.netloc}{parsed.path}"
                    resolved_source = urllib.parse.unquote(raw_path or parsed.path)
                    if os.name == 'nt' and resolved_source.startswith('/') and len(resolved_source) > 3 and resolved_source[2] == ':':
                        resolved_source = resolved_source.lstrip('/')
                path = Path(resolved_source).expanduser()
                payload = json.loads(path.read_text(encoding='utf-8'))

            if not isinstance(payload, dict) or not payload:
                raise ValueError('Fetched payload not a non-empty dict')

            for key, value in payload.items():
                if not isinstance(key, str) or not key.isdigit():
                    raise ValueError(f"Invalid key format: {key}")
                if not isinstance(value, list) or not all(isinstance(x, int) for x in value):
                    raise ValueError(f"Invalid value format for key {key}")

            self.secret_cipher_dict = {str(k): list(v) for k, v in payload.items()}
            logging.info('✅ Updated Spotify TOTP secrets from source')
            return True

        except Exception as e:
            logging.warning(f"Failed to get new secrets: {e}")
            return False

    def try_get_temporary_cookie(self):
        """Try to get a temporary cookie by simulating a browser visit"""
        user_agent = self.get_random_user_agent()
        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        }

        self.user_agent = user_agent

        try:
            response = self.session.get("https://open.spotify.com/", headers=headers, timeout=10)
            cookies = self.session.cookies
            for cookie in cookies:
                if cookie.name == 'sp_dc' and cookie.value:
                    logging.info("✅ Found temporary sp_dc cookie")
                    return cookie.value

            response = self.session.get("https://open.spotify.com/search", headers=headers, timeout=10)
            cookies = self.session.cookies
            for cookie in cookies:
                if cookie.name == 'sp_dc' and cookie.value:
                    logging.info("✅ Found temporary sp_dc cookie from web player")
                    return cookie.value

        except Exception as e:
            logging.debug(f"Could not get temporary cookie: {e}")

        return None

    def refresh_access_token_with_totp(self, sp_dc: str = None, secret_dict: Optional[Dict[str, List[int]]] = None, user_agent: Optional[str] = None) -> dict:
        """Refresh access token using TOTP method from friend's working code"""
        secret_dict = secret_dict or self.secret_cipher_dict
        user_agent = user_agent or self.get_random_user_agent()
        self.user_agent = user_agent

        transport = True
        init = True
        session = self.session
        data: dict = {}
        token = ''

        server_time = self.fetch_server_time(user_agent)
        client_time = int(time_ns() / 1000 / 1000)
        otp_value = self.generate_totp(secret_dict, server_time)
        totp_ver = self.totp_ver or max(map(int, secret_dict))

        params = {
            "reason": "transport",
            "productType": "web-player",
            "totp": otp_value,
            "totpServer": otp_value,
            "totpVer": totp_ver,
        }

        if totp_ver < 10:
            params.update({
                "sTime": server_time,
                "cTime": client_time,
                "buildDate": time.strftime('%Y-%m-%d', time.gmtime(server_time)),
                "buildVer": f"web-player_{time.strftime('%Y-%m-%d', time.gmtime(server_time))}_{server_time * 1000}_{secrets.token_hex(4)}",
            })

        headers = {
            "User-Agent": user_agent,
            "Accept": "application/json",
            "Referer": "https://open.spotify.com/",
            "App-Platform": "WebPlayer",
            "Origin": "https://open.spotify.com",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

        if sp_dc:
            headers['Cookie'] = f'sp_dc={sp_dc}'

        last_err = ''

        try:
            if platform.system() != "Windows":
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(17)

            response = session.get(self.token_url, params=params, headers=headers, timeout=15, verify=True)
            response.raise_for_status()
            data = response.json()
            token = data.get('accessToken', '')

        except (requests.RequestException, TimeoutException, requests.HTTPError, ValueError) as e:
            transport = False
            last_err = str(e)
        finally:
            if platform.system() != "Windows":
                signal.alarm(0)

        if not transport or (transport and not self.validate_token(token, data.get('clientId', ''), user_agent)):
            params['reason'] = 'init'

            try:
                if platform.system() != "Windows":
                    signal.signal(signal.SIGALRM, timeout_handler)
                    signal.alarm(17)

                response = session.get(self.token_url, params=params, headers=headers, timeout=15, verify=True)
                response.raise_for_status()
                data = response.json()
                token = data.get('accessToken', '')

            except (requests.RequestException, TimeoutException, requests.HTTPError, ValueError) as e:
                init = False
                last_err = str(e)
            finally:
                if platform.system() != "Windows":
                    signal.alarm(0)

        if not init or not data or 'accessToken' not in data:
            raise Exception(f"refresh_access_token_with_totp(): Unsuccessful token request{': ' + last_err if last_err else ''}")

        return {
            'access_token': token,
            'expires_at': data['accessTokenExpirationTimestampMs'] // 1000,
            'client_id': data.get('clientId', ''),
            'length': len(token),
            'user_agent': user_agent,
        }

    def validate_token(self, access_token: str, client_id: str = None, user_agent: Optional[str] = None) -> bool:
        """
        Validate token by checking its format and length.
        Note: /v1/me endpoint no longer works with cookie-based tokens due to
        Spotify restrictions introduced Dec 22, 2025.
        """
        # Basic validation - check if token exists and has reasonable length
        if not access_token or len(access_token) < 50:
            return False

        # Token should be a valid base64-like string
        # Spotify tokens are typically JWT-like format or long base64 strings
        return True

    def get_token_with_working_method(self):
        """Get Spotify access token using the working TOTP method"""
        now = time.time()

        if self.cached_access_token and now < self.access_token_expires_at and self.validate_token(self.cached_access_token, self.cached_client_id, self.user_agent):
            logging.debug('✅ Using cached valid token')
            return self.cached_access_token

        max_retries = self.token_max_retries
        retry = 0
        last_error = ''

        sp_dc_to_use = SP_DC_COOKIE if SP_DC_COOKIE and SP_DC_COOKIE != 'your_sp_dc_cookie_value_here' else None

        env_cookie = os.getenv('SP_DC_COOKIE', '')
        if env_cookie and env_cookie != 'your_sp_dc_cookie_value_here':
            sp_dc_to_use = env_cookie

        if not sp_dc_to_use:
            sp_dc_to_use = self.try_get_temporary_cookie()

        while retry < max_retries:
            try:
                token_data = self.refresh_access_token_with_totp(sp_dc_to_use)
                token = token_data['access_token']
                client_id = token_data.get('client_id', '')
                token_user_agent = token_data.get('user_agent', self.user_agent)

                self.cached_access_token = token
                self.access_token_expires_at = token_data['expires_at']
                self.cached_client_id = client_id
                self.user_agent = token_user_agent

                if not self.cached_access_token or not self.validate_token(self.cached_access_token, self.cached_client_id, token_user_agent):
                    retry += 1
                    time.sleep(self.token_retry_delay * retry)
                else:
                    logging.info(f'✅ Successfully obtained Spotify token (attempt {retry + 1})')
                    break
            except Exception as e:
                last_error = str(e)
                retry += 1
                if retry < max_retries:
                    logging.warning(f'Token attempt {retry} failed: {e}, retrying...')
                    time.sleep(self.token_retry_delay * retry)

        if retry == max_retries:
            if self.fetch_and_update_secrets():
                try:
                    token_data = self.refresh_access_token_with_totp(sp_dc_to_use, self.secret_cipher_dict)
                    token = token_data['access_token']
                    client_id = token_data.get('client_id', '')
                    token_user_agent = token_data.get('user_agent', self.user_agent)

                    self.cached_access_token = token
                    self.access_token_expires_at = token_data['expires_at']
                    self.cached_client_id = client_id
                    self.user_agent = token_user_agent

                    if self.cached_access_token and self.validate_token(self.cached_access_token, self.cached_client_id, token_user_agent):
                        logging.info('✅ Successfully obtained Spotify token with updated secrets')
                        return self.cached_access_token
                except Exception as e:
                    last_error = str(e)

            error_msg = (
                f"Failed to obtain valid Spotify access token after {max_retries} attempts. "
                f"Last error: {last_error}\n\n"
                f"🔑 Please set your sp_dc cookie value in the SP_DC_COOKIE variable at the top of main.py"
            )
            raise RuntimeError(error_msg)

        return self.cached_access_token

    def get_token(self):
        """Main method to get Spotify token"""
        return self.get_token_with_working_method()

    def is_token_valid(self):
        """Check if current token is still valid"""
        return self.cached_access_token and time.time() < self.access_token_expires_at and self.validate_token(self.cached_access_token, self.cached_client_id)

    def refresh_token_if_needed(self):
        """Refresh token if it's about to expire"""
        if not self.is_token_valid():
            self.cached_access_token = None
            self.access_token_expires_at = 0
            return self.get_token()
        return self.cached_access_token


# Global fallback token fetcher
def get_public_spotify_token():
    """
    Fetch a public Spotify access token from the spotify-key repository.
    This is a fallback when our own authentication gets rate limited.

    Returns:
        str: A valid Spotify access token, or None if unavailable
    """
    try:
        response = requests.get(
            'https://raw.githubusercontent.com/itzzzme/spotify-key/refs/heads/main/token.json',
            timeout=10
        )
        if response.status_code == 200:
            tokens_data = response.json()
            tokens = tokens_data.get('tokens', [])
            if tokens and len(tokens) > 0:
                # Get the first token
                token = tokens[0].get('access_token', '')
                if token and len(token) > 50:
                    logging.info('✅ Retrieved public fallback token from spotify-key repo')
                    return token
    except Exception as e:
        logging.debug(f'Could not fetch public token: {e}')

    return None


class SpotifyOAuthApp:
    """
    OAuth App authentication for Spotify API calls.
    Currently used only for OAuth-backed endpoints that still accept
    application credentials, such as some playlist artwork lookups.
    """
    def __init__(self):
        self.client_id = SP_APP_CLIENT_ID
        self.client_secret = SP_APP_CLIENT_SECRET
        self.tokens_file = SP_APP_TOKENS_FILE
        self.spotify_client = None
        self.session = self._setup_session()

    def _setup_session(self):
        """Setup session with proper retry strategy"""
        session = requests.Session()
        retry_strategy = Retry(
            total=5,
            connect=3,
            read=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD", "OPTIONS"],
            raise_on_status=False,
            respect_retry_after_header=True
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=100, pool_maxsize=100)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def initialize_client(self):
        """Initialize Spotipy client with Client Credentials flow"""
        if not self.client_id or not self.client_secret:
            raise ValueError(
                "Spotify OAuth app credentials are required. "
                "Please set SP_APP_CLIENT_ID and SP_APP_CLIENT_SECRET environment variables "
                "or configure them in the application settings."
            )

        try:
            # Set up cache handler if tokens file is specified
            cache_handler = None
            if self.tokens_file:
                cache_handler = CacheFileHandler(cache_path=self.tokens_file)

            # Create auth manager with Client Credentials flow
            auth_manager = SpotifyClientCredentials(
                client_id=self.client_id,
                client_secret=self.client_secret,
                cache_handler=cache_handler,
                requests_session=self.session
            )

            # Initialize Spotipy client
            self.spotify_client = spotipy.Spotify(
                auth_manager=auth_manager,
                requests_session=self.session
            )

            logging.info("✅ Spotify OAuth app client initialized successfully")
            return True

        except Exception as e:
            logging.error(f"Failed to initialize Spotify OAuth app client: {e}")
            raise

    def get_token(self):
        """Get valid OAuth app access token"""
        global SP_CACHED_OAUTH_APP_TOKEN, SP_OAUTH_APP_TOKEN_EXPIRES_AT

        now = time.time()

        # Return cached token if still valid
        if SP_CACHED_OAUTH_APP_TOKEN and now < SP_OAUTH_APP_TOKEN_EXPIRES_AT:
            return SP_CACHED_OAUTH_APP_TOKEN

        # Initialize client if needed
        if not self.spotify_client:
            self.initialize_client()

        # Get fresh token from auth manager
        try:
            token_info = self.spotify_client.auth_manager.get_access_token(as_dict=True)
            SP_CACHED_OAUTH_APP_TOKEN = token_info['access_token']
            SP_OAUTH_APP_TOKEN_EXPIRES_AT = token_info['expires_at']
            logging.info("✅ OAuth app token refreshed successfully")
            return SP_CACHED_OAUTH_APP_TOKEN
        except Exception as e:
            logging.error(f"Failed to get OAuth app token: {e}")
            raise

def _spotify_respect_global_rate_limit():
    global SPOTIFY_LAST_REQUEST_TIME
    now = time.time()
    time_since_last = now - SPOTIFY_LAST_REQUEST_TIME
    if time_since_last < SPOTIFY_REQUEST_MIN_INTERVAL:
        time.sleep(SPOTIFY_REQUEST_MIN_INTERVAL - time_since_last)
    SPOTIFY_LAST_REQUEST_TIME = time.time()


def _extract_spotify_track_id_from_playlist_item(item):
    if not isinstance(item, dict):
        return ""
    uri = str(item.get("uri", "") or "").strip()
    if uri.startswith("spotify:track:"):
        return uri.split(":")[-1].strip()

    track_node = item.get("itemV2") or item.get("track") or {}
    data_node = track_node.get("data") if isinstance(track_node, dict) else {}
    uri = str(data_node.get("uri", "") or "").strip()
    if uri.startswith("spotify:track:"):
        return uri.split(":")[-1].strip()
    return ""


def _fetch_spotify_track_page_payload(track_id, spotify_auth):
    track_id = str(track_id or "").strip()
    if not track_id:
        return None

    headers = {
        "User-Agent": spotify_auth.user_agent or "Mozilla/5.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://open.spotify.com/",
    }
    track_url = f"https://open.spotify.com/track/{track_id}"

    for attempt in range(3):
        _spotify_respect_global_rate_limit()
        response = requests.get(track_url, headers=headers, timeout=30)
        if response.status_code == 429 and attempt < 2:
            retry_after = int(response.headers.get("Retry-After", 2) or 2)
            time.sleep(max(1, min(retry_after, 5)))
            continue
        if response.status_code == 404:
            return None
        response.raise_for_status()
        text = response.text or ""

        def meta_value(key):
            patterns = [
                rf'<meta[^>]+property=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']+)["\']',
                rf'<meta[^>]+name=["\']{re.escape(key)}["\'][^>]+content=["\']([^"\']+)["\']',
            ]
            for pattern in patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    return html.unescape(match.group(1).strip())
            return ""

        title = meta_value("og:title")
        description = meta_value("og:description")
        image_url = meta_value("og:image")
        release_date = meta_value("music:release_date")
        duration_raw = meta_value("music:duration")
        musician_values = re.findall(
            r'<meta[^>]+(?:property|name)=["\']music:musician_description["\'][^>]+content=["\']([^"\']+)["\']',
            text,
            re.IGNORECASE,
        )
        musician_values = [html.unescape(value.strip()) for value in musician_values if value and value.strip()]

        parts = [part.strip() for part in description.split("·")] if description else []
        artist_block = musician_values[0] if musician_values else (parts[0] if len(parts) >= 1 else "")
        album_name = parts[1] if len(parts) >= 2 else ""
        artist_list = [segment.strip() for segment in artist_block.split(",") if segment.strip()]
        primary_artist = artist_list[0] if artist_list else artist_block.strip()

        try:
            duration_ms = int(float(duration_raw) * 1000) if duration_raw else 0
        except Exception:
            duration_ms = 0

        release_year = None
        if release_date:
            try:
                release_year = int(str(release_date).split("-", 1)[0])
            except Exception:
                release_year = None

        if not title:
            return None

        return {
            "title": title,
            "artist": primary_artist,
            "artists": artist_list or ([primary_artist] if primary_artist else []),
            "album": album_name,
            "release_date": release_date,
            "release_year": release_year,
            "release_art_url": image_url,
            "duration_ms": duration_ms,
            "isrc": "",
            "spotify_track_id": track_id,
            "platform_id": track_id,
            "platform_url": track_url,
            "explicit": False,
            "popularity": None,
            "parsed": f"{title} - {primary_artist}" if primary_artist else title,
            "path": None,
            "source": "spotify",
        }

    return None


def fetch_spotify_playlist_tracks_enriched(playlist_id, spotify_auth, progress_cb=None, stop_check=None):
    playlist_id = str(playlist_id or "").strip()
    if not playlist_id:
        raise ValueError("Missing Spotify playlist id.")

    token = spotify_auth.refresh_token_if_needed()
    client_id = spotify_auth.cached_client_id
    headers = {
        "Authorization": f"Bearer {token}",
        "Client-Id": client_id,
        "Content-Type": "application/json",
        "User-Agent": spotify_auth.user_agent,
        "Accept": "application/json",
        "Referer": "https://open.spotify.com/",
    }

    def emit(message, value):
        if progress_cb:
            progress_cb(message, int(max(0, min(100, value))))

    _spotify_respect_global_rate_limit()
    response = requests.get(
        f"https://spclient.wg.spotify.com/playlist/v2/playlist/{playlist_id}",
        headers=headers,
        timeout=30,
    )
    if response.status_code == 401:
        spotify_auth.cached_access_token = None
        token = spotify_auth.refresh_token_if_needed()
        headers["Authorization"] = f"Bearer {token}"
        _spotify_respect_global_rate_limit()
        response = requests.get(
            f"https://spclient.wg.spotify.com/playlist/v2/playlist/{playlist_id}",
            headers=headers,
            timeout=30,
        )
    if response.status_code == 403:
        raise ValueError("Access denied. Playlist may be private or unavailable.")
    if response.status_code == 404:
        raise ValueError("Playlist not found. Please check the URL.")
    response.raise_for_status()

    playlist_data = response.json()
    playlist_name = playlist_data.get("attributes", {}).get("name", "Unknown Playlist")
    playlist_image_url = None
    try:
        extractor_owner = PlaylistConverterThread.__new__(PlaylistConverterThread)
        extractor_owner.spotify_auth = spotify_auth
        playlist_image_url = extractor_owner._extract_spotify_playlist_image_candidate(playlist_data)
        if not playlist_image_url:
            playlist_image_url = extractor_owner._resolve_spotify_playlist_image_url(playlist_id, playlist_image_url)
    except Exception as image_error:
        logging.warning(f"Could not resolve Spotify playlist artwork: {image_error}")

    total_tracks = int(playlist_data.get("length", 0) or 0)
    track_page_limit = 100
    offset = 0
    max_pages = max(1, int(math.ceil(max(total_tracks, 1) / max(track_page_limit, 1))) + 2) if total_tracks > 0 else 25
    track_ids = []
    seen_track_ids = set()
    previous_page_signature = None

    emit("Scanning Spotify playlist...", 5)
    for page_number in range(max_pages):
        if stop_check and stop_check():
            raise SyncCancelled()

        page_start = offset + 1
        page_end = min(offset + track_page_limit, total_tracks) if total_tracks > 0 else (offset + track_page_limit)
        emit(
            f"Scanning Spotify playlist... ({page_start}-{page_end})",
            5 + int((min(offset, total_tracks) / max(total_tracks, 1)) * 20) if total_tracks > 0 else 10,
        )
        logging.info(f"Spotify playlist scan request: playlist={playlist_id} offset={offset} limit={track_page_limit}")
        _spotify_respect_global_rate_limit()
        page_response = requests.get(
            f"https://spclient.wg.spotify.com/playlist/v2/playlist/{playlist_id}",
            headers=headers,
            params={"offset": offset, "limit": track_page_limit},
            timeout=30,
        )
        if page_response.status_code == 401:
            spotify_auth.cached_access_token = None
            token = spotify_auth.refresh_token_if_needed()
            headers["Authorization"] = f"Bearer {token}"
            headers["Client-Id"] = spotify_auth.cached_client_id
            _spotify_respect_global_rate_limit()
            page_response = requests.get(
                f"https://spclient.wg.spotify.com/playlist/v2/playlist/{playlist_id}",
                headers=headers,
                params={"offset": offset, "limit": track_page_limit},
                timeout=30,
            )
        if page_response.status_code == 429:
            retry_after = int(page_response.headers.get("Retry-After", 2) or 2)
            capped_retry = max(1, min(retry_after, 15))
            logging.warning(f"Spotify playlist scan rate limited, waiting {capped_retry}s")
            time.sleep(capped_retry)
            continue
        page_response.raise_for_status()
        page_payload = page_response.json() or {}
        items = ((page_payload.get("contents") or {}).get("items") or [])
        if not items:
            break

        page_track_ids = []
        for item in items:
            track_id = _extract_spotify_track_id_from_playlist_item(item)
            if track_id:
                page_track_ids.append(track_id)

        page_signature = tuple(page_track_ids[:10])
        if previous_page_signature is not None and page_signature == previous_page_signature:
            logging.warning(f"Spotify playlist scan repeated page at offset {offset}; stopping early.")
            break
        previous_page_signature = page_signature

        new_track_count = 0
        for track_id in page_track_ids:
            if track_id in seen_track_ids:
                continue
            seen_track_ids.add(track_id)
            track_ids.append(track_id)
            new_track_count += 1

        if new_track_count == 0:
            logging.warning(f"Spotify playlist scan returned no new track ids at offset {offset}; stopping early.")
            break

        offset += len(items)
        if total_tracks > 0:
            emit(
                f"Scanning Spotify playlist... ({min(len(track_ids), total_tracks)}/{total_tracks})",
                5 + int((min(len(track_ids), total_tracks) / max(total_tracks, 1)) * 20),
            )
        else:
            emit(f"Scanning Spotify playlist... ({len(track_ids)} found)", 25)

        if total_tracks > 0 and len(track_ids) >= total_tracks:
            break
        if len(items) < track_page_limit:
            break

    effective_total = total_tracks if total_tracks > 0 else len(track_ids)
    tracks = []
    if track_ids:
        ordered_tracks = [None] * len(track_ids)
        total_to_fetch = len(track_ids)
        max_workers = min(8, max(2, (os.cpu_count() or 4)))
        emit("Loading Spotify track metadata...", 30)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {
                executor.submit(_fetch_spotify_track_page_payload, track_id, spotify_auth): index
                for index, track_id in enumerate(track_ids)
            }
            completed = 0
            for future in as_completed(future_to_index):
                if stop_check and stop_check():
                    raise SyncCancelled()
                index = future_to_index[future]
                track_id = track_ids[index]
                try:
                    ordered_tracks[index] = future.result()
                except Exception as e:
                    logging.warning(f"Failed to load Spotify track page for {track_id}: {e}")
                completed += 1
                emit(
                    f"Loading Spotify track metadata... ({completed}/{total_to_fetch})",
                    30 + int((completed / max(total_to_fetch, 1)) * 65),
                )
        tracks = [track for track in ordered_tracks if track]

    emit(f"Loaded Spotify playlist '{playlist_name}' ({len(tracks)} tracks)", 95)
    return tracks, playlist_name, playlist_image_url


class TidalClient:
    BASE_URL = 'https://api.tidal.com/v1/'
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'user-agent': 'TIDAL/3704 CFNetwork/1220.1 Darwin/20.3.0',
            'x-tidal-token': 'i4ZDjcyhed7Mu47q'
        })
    
    def get_playlist(self, uuid):
        response = self.session.get(f"{self.BASE_URL}playlists/{uuid}", params={'countryCode': 'US'})
        response.raise_for_status()
        return response.json()
    
    def get_playlist_tracks(self, uuid):
        response = self.session.get(f"{self.BASE_URL}playlists/{uuid}/tracks", params={'limit': 500, 'countryCode': 'US'})
        response.raise_for_status()
        return response.json()

class PlaylistConversionCancelled(Exception):
    """Raised when the user cancels streaming playlist conversion."""

class SyncCancelled(Exception):
    """Raised when a sync operation is cancelled mid-run."""
    pass

class PlaylistConverterThread(QThread):
    progress_update = pyqtSignal(int)
    progress_message = pyqtSignal(str)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    cancelled = pyqtSignal()
    # NEW: Signal for track match confirmation
    track_match_confirmation_needed = pyqtSignal(object, object, float)  # source_track, plex_track, score

    def __init__(self, playlist_source, plex_server, library_section, listenbrainz_token=None, parent=None):
        super().__init__(parent)
        self.playlist_source = playlist_source
        self.plex_server = plex_server
        self.library_section = library_section
        self.listenbrainz_token = listenbrainz_token.strip() if listenbrainz_token else None
        self.spotify_auth = SpotifyAnonymousAuth()
        self.deezer_client = deezer.Client()
        self.tidal_client = TidalClient()
        
        # NEW: Track confirmation state
        self.skip_all_low_matches = False
        self.user_response = None
        self.response_received = threading.Event()

        # Cancellation support
        self._cancel_requested = False

    def run(self):
        try:
            self._ensure_not_cancelled()
            self.progress_message.emit('Fetching playlist details...')

            if "open.spotify.com" in self.playlist_source:
                tracks, playlist_name, playlist_image_url = self.get_spotify_playlist_info()
            elif "deezer.com" in self.playlist_source:
                tracks, playlist_name, playlist_image_url = self.get_deezer_playlist_info()
            elif "tidal.com" in self.playlist_source:
                tracks, playlist_name, playlist_image_url = self.get_tidal_playlist_info()
            elif "listenbrainz.org" in self.playlist_source:
                tracks, playlist_name, playlist_image_url = self.get_listenbrainz_playlist_info()
            else:
                raise ValueError("Unsupported playlist source")

            self._ensure_not_cancelled()
            self.progress_message.emit(f"Matching tracks for '{playlist_name}' ({len(tracks)} items)...")

            self.create_plex_playlist(tracks, playlist_name, playlist_image_url)

            if self._cancel_requested:
                self.cancelled.emit()
                return

            self.finished.emit()
        except PlaylistConversionCancelled:
            logging.info('Playlist conversion cancelled by user')
            self.cancelled.emit()
        except Exception as e:
            logging.error(f"Error in PlaylistConverterThread: {str(e)}", exc_info=True)
            self.error.emit(str(e))

    def wait_for_user_response(self):
        """Wait for user response from main thread"""
        self.response_received.wait()
        self.response_received.clear()
        return self.user_response

    def set_user_response(self, response):
        """Set user response and signal that response was received"""
        self.user_response = response
        self.response_received.set()

    def request_cancel(self):
        self._cancel_requested = True
        self.progress_message.emit('Cancelling...')

    def _ensure_not_cancelled(self):
        if self._cancel_requested:
            raise PlaylistConversionCancelled()

    def get_tidal_playlist_info(self):
        self._ensure_not_cancelled()
        playlist_uuid = self.playlist_source.split('/')[-1]
        self.progress_message.emit('Fetching Tidal playlist metadata...')
        playlist_data = self.tidal_client.get_playlist(playlist_uuid)
        tracks_data = self.tidal_client.get_playlist_tracks(playlist_uuid)

        playlist_name = playlist_data['title']
        playlist_image_url = playlist_data['image']

        tracks = []
        total = tracks_data.get('totalNumberOfItems', len(tracks_data.get('items', [])) or 1)
        with ThreadPoolExecutor(max_workers=25) as executor:
            future_to_track = {executor.submit(self.process_tidal_track, item): item for item in tracks_data['items']}
            for future in as_completed(future_to_track):
                self._ensure_not_cancelled()
                track = future.result()
                if track:
                    tracks.append(track)
                self.progress_update.emit(int(len(tracks) / total * 50))
                self.progress_message.emit(f"Processing Tidal track {len(tracks)}/{total}")

        logging.info(f"Fetched {len(tracks)} tracks from Tidal playlist '{playlist_name}'")
        return tracks, playlist_name, playlist_image_url

    def get_listenbrainz_playlist_info(self):
        self._ensure_not_cancelled()
        self.progress_message.emit("Fetching ListenBrainz playlist metadata...")
        client = ListenBrainzClient(token=self.listenbrainz_token)
        playlist = client.get_playlist(self.playlist_source)
        playlist_name = playlist.get("title") or "ListenBrainz Playlist"
        playlist_image_url = self._extract_image_url_from_listenbrainz_playlist(playlist)

        track_entries = playlist.get("track") or []
        if not isinstance(track_entries, list):
            track_entries = []

        tracks = []
        total = len(track_entries) if track_entries else 1
        for idx, entry in enumerate(track_entries):
            self._ensure_not_cancelled()
            if not isinstance(entry, dict):
                continue
            title = (entry.get("title") or "").strip()
            artist = (entry.get("creator") or "").strip()
            album = (entry.get("album") or "").strip()
            recording_mbid = self._extract_recording_mbid(entry)
            if not title:
                continue
            parsed = f"{title} - {artist}" if artist else title
            tracks.append({
                "title": title,
                "artist": artist,
                "album": album,
                "recording_mbid": recording_mbid,
                "identifier": entry.get("identifier"),
                "parsed": parsed,
                "path": None,
                "source": "listenbrainz",
            })
            self.progress_update.emit(int(((idx + 1) / total) * 50))
            self.progress_message.emit(f"Processing ListenBrainz track {idx + 1}/{total}")

        if not tracks:
            raise ValueError("No tracks found in ListenBrainz playlist")

        logging.info(f"Fetched {len(tracks)} tracks from ListenBrainz playlist '{playlist_name}'")
        return tracks, playlist_name, playlist_image_url

    def _normalize_image_url(self, value):
        if value is None:
            return ""
        if isinstance(value, list):
            for entry in value:
                normalized = self._normalize_image_url(entry)
                if normalized:
                    return normalized
            return ""
        if isinstance(value, dict):
            for key in ("url", "src", "picture", "image"):
                normalized = self._normalize_image_url(value.get(key))
                if normalized:
                    return normalized
            return ""

        raw = str(value).strip()
        if not raw:
            return ""
        if raw.startswith("spotify:image:"):
            image_id = raw.split("spotify:image:", 1)[1].strip()
            return f"https://i.scdn.co/image/{image_id}" if image_id else ""
        if raw.startswith("spotify:mosaic:"):
            parts = [p.strip() for p in raw.split(":") if p.strip()]
            # spotify:mosaic:<image_id>[:<image_id>...]
            if len(parts) >= 3:
                return f"https://i.scdn.co/image/{parts[2]}"
            return ""
        if raw.startswith("image:"):
            image_id = raw.split("image:", 1)[1].strip()
            return f"https://i.scdn.co/image/{image_id}" if image_id else ""
        if raw.startswith("//"):
            return f"https:{raw}"
        if raw.startswith("http://") or raw.startswith("https://"):
            return raw
        if re.fullmatch(r"[A-Za-z0-9]{20,}", raw):
            return f"https://i.scdn.co/image/{raw}"
        return ""

    def _extract_spotify_playlist_image_candidate(self, payload):
        if not isinstance(payload, dict):
            return ""
        candidates = [
            (payload.get("attributes") or {}).get("picture"),
            (payload.get("attributes") or {}).get("image"),
            (payload.get("metadata") or {}).get("image_url"),
            (payload.get("metadata") or {}).get("picture"),
            payload.get("images"),
            payload.get("image"),
            payload.get("picture"),
        ]
        for candidate in candidates:
            normalized = self._normalize_image_url(candidate)
            if normalized:
                return normalized
        return ""

    def _resolve_spotify_playlist_image_url(self, playlist_id, current_image_value):
        normalized = self._normalize_image_url(current_image_value)
        if normalized:
            return normalized
        try:
            oauth_app = SpotifyOAuthApp()
            oauth_token = oauth_app.get_token()
            headers = {
                "Authorization": f"Bearer {oauth_token}",
                "User-Agent": self.spotify_auth.user_agent,
            }
            response = requests.get(
                f"https://api.spotify.com/v1/playlists/{playlist_id}",
                headers=headers,
                params={"fields": "images"},
                timeout=20,
            )
            if response.status_code == 200:
                payload = response.json() or {}
                normalized = self._normalize_image_url(payload.get("images"))
                if normalized:
                    return normalized
            else:
                logging.info(f"Spotify cover lookup returned HTTP {response.status_code}; falling back to public artwork sources.")
        except Exception as e:
            logging.warning(f"Spotify cover lookup failed: {e}")

        # Fallback: read public OpenGraph image directly from Spotify page.
        try:
            page_response = requests.get(
                f"https://open.spotify.com/playlist/{playlist_id}",
                headers={"User-Agent": self.spotify_auth.user_agent},
                timeout=20,
            )
            if page_response.status_code == 200:
                match = re.search(
                    r'<meta\s+property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
                    page_response.text,
                    re.IGNORECASE,
                )
                if match:
                    normalized = self._normalize_image_url(match.group(1))
                    if normalized:
                        return normalized
            else:
                logging.warning(f"Spotify og:image lookup returned HTTP {page_response.status_code}")
        except Exception as e:
            logging.warning(f"Spotify og:image lookup failed: {e}")
        return ""

    def process_tidal_track(self, item):
        try:
            title = (item.get("title") or "").strip()
            if not title:
                return None
            artist_name = ((item.get("artist") or {}).get("name") or "").strip()
            album_name = ((item.get("album") or {}).get("title") or "").strip()
            parsed = f"{title} - {artist_name}" if artist_name else title
            return {
                "title": title,
                "artist": artist_name,
                "album": album_name,
                "parsed": parsed,
                "path": None,
                "source": "tidal",
            }
        except Exception as e:
            logging.error(f"Error processing Tidal track: {str(e)}")
            return None

    def get_spotify_playlist_info(self):
        """
        Get Spotify playlist info using cookie-based authentication with proper rate limiting.
        """
        max_retries = 5
        retry_count = 0
        base_wait_time = 2

        while retry_count < max_retries:
            self._ensure_not_cancelled()
            self.progress_message.emit(f'Fetching Spotify playlist (attempt {retry_count + 1}/{max_retries})...')
            try:
                playlist_id = self.playlist_source.split('/')[-1].split('?')[0]
                logging.info(f"Processing Spotify playlist ID: {playlist_id} (attempt {retry_count + 1})")
                tracks, playlist_name, playlist_image_url = fetch_spotify_playlist_tracks_enriched(
                    playlist_id,
                    self.spotify_auth,
                    progress_cb=lambda message, value: (
                        self.progress_message.emit(message),
                        self.progress_update.emit(int(value)),
                    ),
                    stop_check=lambda: getattr(self, "_cancel_requested", False),
                )
                logging.info(f"Successfully fetched {len(tracks)} tracks from Spotify playlist '{playlist_name}'")
                return tracks, playlist_name, playlist_image_url
                
            except ValueError as e:
                # Don't retry on these errors
                logging.error(f"Spotify playlist error: {str(e)}")
                raise
                
            except Exception as e:
                logging.error(f"Unexpected error on attempt {retry_count + 1}: {str(e)}")
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = 2 ** retry_count  # Exponential backoff
                    logging.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise ValueError(f"Failed to fetch Spotify playlist after {max_retries} attempts: {str(e)}")
        
        raise ValueError("Failed to fetch Spotify playlist after all retry attempts")

    def get_deezer_playlist_info(self):
        self._ensure_not_cancelled()
        playlist_id = self.playlist_source.split('/')[-1]
        self.progress_message.emit('Fetching Deezer playlist metadata...')
        playlist = self.deezer_client.get_playlist(playlist_id)

        tracks = []
        total = getattr(playlist, 'nb_tracks', None) or len(getattr(playlist, 'tracks', [])) or 1
        for track in playlist.tracks:
            self._ensure_not_cancelled()
            title = (getattr(track, "title", "") or "").strip()
            if not title:
                continue
            artist_name = (getattr(getattr(track, "artist", None), "name", "") or "").strip()
            album_name = (getattr(getattr(track, "album", None), "title", "") or "").strip()
            parsed = f"{title} - {artist_name}" if artist_name else title
            tracks.append({
                "title": title,
                "artist": artist_name,
                "album": album_name,
                "parsed": parsed,
                "path": None,
                "source": "deezer",
            })
            self.progress_update.emit(int(len(tracks) / total * 50))
            self.progress_message.emit(f"Processing Deezer track {len(tracks)}/{total}")

        playlist_name = playlist.title
        playlist_image_url = playlist.picture_xl

        logging.info(f"Fetched {len(tracks)} tracks from Deezer playlist '{playlist_name}'")
        return tracks, playlist_name, playlist_image_url

    def create_plex_playlist(self, tracks, playlist_name, playlist_image_url):
        try:
            # Use the target name and action decided on the main thread
            final_name = getattr(self, 'target_playlist_name', playlist_name)
            action = getattr(self, 'conflict_action', 'create')
            existing_playlist = getattr(self, 'existing_playlist', None)
            
            self._ensure_not_cancelled()

            # Handle the pre-decided action
            if action == "overwrite" and existing_playlist:
                existing_playlist.delete()
                logging.info(f"Deleted existing playlist: {playlist_name}")
            
            library_section = self.plex_server.library.sectionByID(self.library_section)
            
            plex_tracks = []
            not_found_tracks = []
            total_tracks = len(tracks)
            for i, track in enumerate(tracks):
                self._ensure_not_cancelled()
                title, artist, _, _ = self.parse_track_info(track)
                track_label = f"{title} - {artist}" if artist else title
                self.progress_message.emit(f"Matching track {i + 1}/{total_tracks}: {track_label}")
                plex_track = self.find_best_match(library_section, track)
                if plex_track:
                    plex_tracks.append(plex_track)
                else:
                    not_found_tracks.append(track_label)
                self.progress_update.emit(50 + int((i + 1) / total_tracks * 50))
            
            self._ensure_not_cancelled()
            self.progress_message.emit(f"Creating Plex playlist '{final_name}'...")

            if plex_tracks:
                # Use the final_name (which might be renamed) instead of original playlist_name
                plex_playlist = self.plex_server.createPlaylist(final_name, items=plex_tracks)
                
                # Set the playlist image if available
                if playlist_image_url:
                    normalized_image_url = self._normalize_image_url(playlist_image_url) or str(playlist_image_url).strip()
                    temp_file = ""
                    try:
                        img_response = requests.get(
                            normalized_image_url,
                            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'},
                            timeout=30,
                        )
                        img_response.raise_for_status()

                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                            tmp.write(img_response.content)
                            temp_file = tmp.name

                        plex_playlist.uploadPoster(filepath=temp_file)
                        logging.info(f"Successfully set thumbnail for playlist '{final_name}' using local file")
                    except Exception as thumb_error:
                        logging.error(f"Failed to upload thumbnail file: {str(thumb_error)}")
                        try:
                            plex_playlist.uploadPoster(url=normalized_image_url)
                            logging.info(f"Successfully set thumbnail for playlist '{final_name}'")
                        except Exception as url_thumb_error:
                            logging.error(f"Failed to set thumbnail: {str(url_thumb_error)}")
                    finally:
                        if temp_file:
                            try:
                                os.remove(temp_file)
                            except Exception:
                                pass
                
                logging.info(f"Successfully created playlist '{final_name}' with {len(plex_tracks)} tracks")
                if not_found_tracks:
                    logging.warning(f"Could not find matches for {len(not_found_tracks)} tracks in your Plex library")
                    for track in not_found_tracks:
                        logging.warning(f"Not found: {track}")

                self.final_playlist_name = final_name
            else:
                raise ValueError("No matching tracks found in your Plex library")
        except PlaylistConversionCancelled:
            raise
        except Exception as e:
            logging.error(f"Error creating Plex playlist: {str(e)}", exc_info=True)
            raise ValueError(f"Error creating Plex playlist: {e}")

    def find_best_match(self, library_section, track):
        """Enhanced find_best_match with user confirmation for low scores"""
        self._ensure_not_cancelled()
        normalized_track = self.normalize_source_track(track)
        title, artist, album, recording_mbid = self.parse_track_info(normalized_track)
        if not title:
            return None
        scored_tracks = _rank_plex_track_matches(library_section, normalized_track, self.parent())

        # Find the best match
        best_match = None
        best_score = 0
        best_artist_score = 0

        if scored_tracks:
            best_match = _hydrate_ranked_match_track(library_section, scored_tracks[0])
            best_score = scored_tracks[0]["score"]
            best_artist_score = scored_tracks[0]["artist_score"]

        # NEW: Handle different score ranges
        high_score_threshold = 78 if artist else 86
        medium_score_threshold = 64 if artist else 76

        if best_score >= high_score_threshold and (not artist or best_artist_score >= 40 or best_score >= 100):
            # High confidence - auto accept
            logging.info(f"High confidence match for '{track}' to '{best_match.title}' (score: {best_score})")
            return best_match
        elif best_score >= medium_score_threshold and not self.skip_all_low_matches:
            # Medium confidence - ask user
            logging.info(f"Medium confidence match for '{track}' to '{best_match.title}' (score: {best_score}) - asking user")
            
            # Emit signal to main thread for user confirmation
            self.track_match_confirmation_needed.emit(track, best_match, best_score)
            
            # Wait for user response
            user_choice = self.wait_for_user_response()
            
            if user_choice == "use":
                logging.info(f"User approved match for '{track}' to '{best_match.title}'")
                return best_match
            elif user_choice == "skip":
                logging.info(f"User skipped match for '{track}'")
                return None
            elif user_choice == "skip_all":
                logging.info(f"User chose to skip all remaining low matches")
                self.skip_all_low_matches = True
                return None
        elif best_score >= medium_score_threshold and self.skip_all_low_matches:
            # User previously chose to skip all low matches
            logging.info(f"Skipping low confidence match for '{track}' (score: {best_score}) - user chose skip all")
            return None
        else:
            # Very low confidence - auto skip
            logging.warning(f"Very low confidence match for '{track}' (best score: {best_score}) - auto skipping")
            return None

    def _extract_recording_mbid(self, source_track):
        candidates = []
        if isinstance(source_track, dict):
            if source_track.get("recording_mbid"):
                candidates.append(str(source_track.get("recording_mbid")))
            identifier = source_track.get("identifier")
            if isinstance(identifier, str):
                candidates.append(identifier)
            elif isinstance(identifier, list):
                candidates.extend(str(value) for value in identifier if value)

        mbid_pattern = re.compile(
            r"(?:musicbrainz\.org/recording/|musicbrainz://recording/|recording/)([0-9a-fA-F-]{36})",
            re.IGNORECASE,
        )
        uuid_pattern = re.compile(
            r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
            re.IGNORECASE,
        )
        for candidate in candidates:
            match = mbid_pattern.search(candidate)
            if match:
                return match.group(1).lower()
            uuid_match = uuid_pattern.search(candidate)
            if uuid_match:
                return uuid_match.group(1).lower()
        return ""

    def _extract_recording_mbid_from_plex_track(self, plex_track):
        guid_candidates = []
        for attr in ("guid",):
            value = getattr(plex_track, attr, None)
            if value:
                guid_candidates.append(str(value))
        for guid_obj in getattr(plex_track, "guids", []) or []:
            guid_id = getattr(guid_obj, "id", None)
            if guid_id:
                guid_candidates.append(str(guid_id))

        mbid_pattern = re.compile(
            r"(?:musicbrainz\.org/recording/|musicbrainz://recording/|recording/)([0-9a-fA-F-]{36})",
            re.IGNORECASE,
        )
        for candidate in guid_candidates:
            match = mbid_pattern.search(candidate)
            if match:
                return match.group(1).lower()
        return ""

    def _extract_image_url_from_text(self, text):
        if not text:
            return None
        match = re.search(r"https?://\S+", str(text), re.IGNORECASE)
        if not match:
            return None

        candidate = match.group(0).strip().rstrip(").,;")
        lowered = candidate.lower()
        image_extensions = (".jpg", ".jpeg", ".png", ".webp", ".gif")
        if any(ext in lowered for ext in image_extensions):
            return candidate
        return None

    def _extract_image_url_from_listenbrainz_playlist(self, playlist):
        if not isinstance(playlist, dict):
            return None

        direct_url = (
            playlist.get("image")
            or playlist.get("image_url")
            or playlist.get("thumbnail")
            or playlist.get("cover_art")
            or playlist.get("picture")
        )
        if isinstance(direct_url, str):
            image_url = self._extract_image_url_from_text(direct_url)
            if image_url:
                return image_url

        fields_to_scan = [
            playlist.get("annotation"),
            playlist.get("description"),
            playlist.get("notes"),
        ]

        extension = playlist.get("extension")
        if isinstance(extension, dict):
            for _, ext_payload in extension.items():
                fields_to_scan.append(ext_payload)

        while fields_to_scan:
            value = fields_to_scan.pop(0)
            if isinstance(value, str):
                image_url = self._extract_image_url_from_text(value)
                if image_url:
                    return image_url
            elif isinstance(value, dict):
                fields_to_scan.extend(value.values())
            elif isinstance(value, list):
                fields_to_scan.extend(value)
        return None

    def normalize_source_track(self, track_info):
        if isinstance(track_info, dict):
            track = dict(track_info)
            title = str(track.get("title", "") or "").strip()
            artist = str(track.get("artist", "") or "").strip()
            album = str(track.get("album", "") or "").strip()
            parsed = str(track.get("parsed", "") or "").strip()
            if not parsed and title:
                parsed = f"{title} - {artist}" if artist else title
            if not title and parsed:
                if " - " in parsed:
                    parts = parsed.split(" - ", 1)
                    title = parts[0].strip()
                    if not artist:
                        artist = parts[1].strip()
                else:
                    title = parsed

            track["title"] = title
            track["artist"] = artist
            track["album"] = album
            track["parsed"] = parsed
            track["path"] = track.get("path")
            artists = track.get("artists") or []
            if isinstance(artists, (list, tuple)):
                track["artists"] = [str(value or "").strip() for value in artists if str(value or "").strip()]
            elif artists:
                track["artists"] = [str(artists).strip()]
            else:
                track["artists"] = []
            track["isrc"] = str(track.get("isrc", "") or "").strip().upper()
            try:
                track["duration_ms"] = int(track.get("duration_ms", 0) or 0)
            except Exception:
                track["duration_ms"] = 0
            if not track.get("recording_mbid"):
                track["recording_mbid"] = self._extract_recording_mbid(track)
            return track

        text = str(track_info or "").strip()
        title = text
        artist = ""
        if " - " in text:
            parts = text.split(" - ", 1)
            title = parts[0].strip()
            artist = parts[1].strip()
        return {
            "title": title,
            "artist": artist,
            "album": "",
            "recording_mbid": "",
            "parsed": text,
            "path": None,
            "artists": [artist] if artist else [],
            "isrc": "",
            "duration_ms": 0,
        }

    def parse_track_info(self, track):
        if isinstance(track, dict):
            title = str(track.get("title", "") or "").strip()
            artist = str(track.get("artist", "") or "").strip()
            album = str(track.get("album", "") or "").strip()
            if not title:
                parsed = str(track.get("parsed", "") or "").strip()
                if " - " in parsed:
                    parts = parsed.split(" - ", 1)
                    title = parts[0].strip()
                    if not artist:
                        artist = parts[1].strip()
                else:
                    title = parsed
            return title, artist, album, self._extract_recording_mbid(track)

        text = str(track or "").strip()
        parts = text.split(' - ', 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip(), "", ""
        return text, '', "", ""

class ModernButton(QPushButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFixedHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self.setProperty("class", "modern-button")

class ModernLineEdit(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFixedHeight(40)

class LibraryDuplicateManagerDialog(QDialog):
    """Professional duplicate track management dialog with safe deletion and playlist integration"""

    def __init__(self, duplicate_groups, plex_server, parent=None):
        super().__init__(parent)
        self.duplicate_groups = duplicate_groups
        self.plex_server = plex_server
        self.selected_for_deletion = set()  # Track rating keys of tracks marked for deletion
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("🔍 Library Duplicate Manager")
        self.setModal(True)
        self.resize(1200, 800)

        layout = QVBoxLayout(self)

        # Header with statistics
        header_layout = QHBoxLayout()

        total_duplicates = sum(len(group) for group in self.duplicate_groups)
        total_space_wasted = sum(
            sum(track['file_size'] for track in group[1:])  # All but the first track in each group
            for group in self.duplicate_groups
        )
        space_mb = total_space_wasted / (1024 * 1024) if total_space_wasted else 0

        # Check if playlist info was included
        playlist_mode = "with playlist info" if any(any(t['playlists'] for t in group) for group in self.duplicate_groups) else "fast mode"

        stats_label = QLabel(f"📊 Found {len(self.duplicate_groups)} duplicate groups "
                           f"({total_duplicates} total tracks, ~{space_mb:.1f}MB potential savings)\n"
                           f"💨 Scan mode: {playlist_mode}")
        stats_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #2196F3; padding: 10px;")
        header_layout.addWidget(stats_label)
        header_layout.addStretch()

        # Action buttons in header
        select_suggested_btn = QPushButton("✨ Auto-Select (Keep Best Quality)")
        select_suggested_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        select_suggested_btn.clicked.connect(self.auto_select_best_quality)
        header_layout.addWidget(select_suggested_btn)

        layout.addLayout(header_layout)

        # Main content area with scroll
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_widget)

        # Create duplicate group widgets
        for i, group in enumerate(self.duplicate_groups):
            group_widget = self.create_duplicate_group_widget(group, i)
            self.scroll_layout.addWidget(group_widget)

        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

        # Bottom action bar
        action_layout = QHBoxLayout()

        # Info about selected tracks
        self.selection_info = QLabel("No tracks selected for deletion")
        self.selection_info.setStyleSheet("color: #666666; font-style: italic;")
        action_layout.addWidget(self.selection_info)

        action_layout.addStretch()

        # Action buttons
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        action_layout.addWidget(cancel_btn)

        self.delete_btn = QPushButton("🗑️ Delete Selected Duplicates")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.delete_btn.setEnabled(False)
        self.delete_btn.clicked.connect(self.confirm_deletion)
        action_layout.addWidget(self.delete_btn)

        layout.addLayout(action_layout)

    def create_duplicate_group_widget(self, group, group_index):
        """Create widget for a single duplicate group"""
        group_box = QGroupBox(f"🎵 Duplicate Group {group_index + 1}: {group[0]['title']} - {group[0]['artist']}")
        group_box.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 2px solid #3498db;
                border-radius: 8px;
                margin: 8px 0px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #2c3e50;
                background-color: white;
            }
        """)

        layout = QVBoxLayout(group_box)

        # Sort tracks by quality (bitrate, then file size)
        sorted_tracks = sorted(group, key=lambda t: (t['bitrate'] or 0, t['file_size'] or 0), reverse=True)

        for i, track in enumerate(sorted_tracks):
            track_widget = self.create_track_widget(track, i == 0)  # First (highest quality) suggested to keep
            layout.addWidget(track_widget)

        return group_box

    def create_track_widget(self, track, is_suggested_keep):
        """Create widget for individual track with full details"""
        track_frame = QFrame()
        track_frame.setStyleSheet(f"""
            QFrame {{
                border: 2px solid {'#4CAF50' if is_suggested_keep else '#ddd'};
                border-radius: 6px;
                padding: 8px;
                margin: 4px;
                background-color: {'#f8fff8' if is_suggested_keep else '#ffffff'};
            }}
        """)

        layout = QHBoxLayout(track_frame)

        # Checkbox for deletion selection (disabled for suggested keep)
        checkbox = QCheckBox()
        checkbox.setEnabled(not is_suggested_keep)
        if is_suggested_keep:
            checkbox.setToolTip("🌟 Recommended to keep (highest quality)")
        else:
            checkbox.setToolTip("Select to delete this duplicate")

        checkbox.toggled.connect(lambda checked: self.on_track_selection_changed(track['rating_key'], checked))
        layout.addWidget(checkbox)

        # Track details
        details_layout = QVBoxLayout()

        # Main info line
        main_info = QLabel(f"🎵 <b>{track['title']}</b> - {track['artist']} ({track['album']})")
        main_info.setStyleSheet("font-size: 14px; margin: 2px 0;")
        details_layout.addWidget(main_info)

        # Technical details
        duration_str = f"{track['duration'] // 60000}:{(track['duration'] % 60000) // 1000:02d}" if track['duration'] else "Unknown"
        bitrate_str = f"{track['bitrate']}kbps" if track['bitrate'] else "Unknown bitrate"
        size_str = f"{track['file_size'] / (1024*1024):.1f}MB" if track['file_size'] else "Unknown size"

        tech_info = QLabel(f"⚡ {duration_str} • {bitrate_str} • {size_str}")
        tech_info.setStyleSheet("color: #666666; font-size: 12px; margin: 2px 0;")
        details_layout.addWidget(tech_info)

        # File path
        path_info = QLabel(f"📁 {track['file_path']}")
        path_info.setStyleSheet("color: #888888; font-size: 11px; font-family: monospace; margin: 2px 0;")
        details_layout.addWidget(path_info)

        # Playlists containing this track
        if track['playlists']:
            playlists_str = ", ".join(track['playlists'][:3])  # Show first 3 playlists
            if len(track['playlists']) > 3:
                playlists_str += f" (+{len(track['playlists']) - 3} more)"
            playlist_info = QLabel(f"📝 In playlists: {playlists_str}")
        elif any(any(t['playlists'] for t in group) for group in self.duplicate_groups):
            # Some tracks have playlist info, so this one truly isn't in playlists
            playlist_info = QLabel("📝 Not in any playlists")
        else:
            # No tracks have playlist info, so it wasn't checked
            playlist_info = QLabel("📝 Playlist usage not checked (fast scan mode)")

        playlist_info.setStyleSheet("color: #2196F3; font-size: 12px; margin: 2px 0;")
        details_layout.addWidget(playlist_info)

        layout.addLayout(details_layout)

        # Quality indicator
        quality_layout = QVBoxLayout()
        if is_suggested_keep:
            quality_label = QLabel("🌟 KEEP\n(Best Quality)")
            quality_label.setStyleSheet("""
                QLabel {
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                    text-align: center;
                    padding: 8px;
                    border-radius: 6px;
                    font-size: 12px;
                }
            """)
        else:
            quality_label = QLabel("⚠️ DUPLICATE\n(Lower Quality)")
            quality_label.setStyleSheet("""
                QLabel {
                    background-color: #ff9800;
                    color: white;
                    font-weight: bold;
                    text-align: center;
                    padding: 8px;
                    border-radius: 6px;
                    font-size: 12px;
                }
            """)

        quality_layout.addWidget(quality_label)
        layout.addLayout(quality_layout)

        return track_frame

    def auto_select_best_quality(self):
        """Automatically select lower quality duplicates for deletion"""
        self.selected_for_deletion.clear()

        for group in self.duplicate_groups:
            # Sort by quality, keep the best one
            sorted_tracks = sorted(group, key=lambda t: (t['bitrate'] or 0, t['file_size'] or 0), reverse=True)
            # Select all but the highest quality for deletion
            for track in sorted_tracks[1:]:
                self.selected_for_deletion.add(track['rating_key'])

        self.update_ui_selections()
        self.update_selection_info()

    def on_track_selection_changed(self, rating_key, checked):
        """Handle individual track selection"""
        if checked:
            self.selected_for_deletion.add(rating_key)
        else:
            self.selected_for_deletion.discard(rating_key)

        self.update_selection_info()

    def update_ui_selections(self):
        """Update UI to reflect current selections"""
        # This would need to update checkboxes - simplified for now
        pass

    def update_selection_info(self):
        """Update selection information label"""
        count = len(self.selected_for_deletion)
        if count == 0:
            self.selection_info.setText("No tracks selected for deletion")
            self.delete_btn.setEnabled(False)
        else:
            # Calculate space savings
            total_size = 0
            for group in self.duplicate_groups:
                for track in group:
                    if track['rating_key'] in self.selected_for_deletion:
                        total_size += track['file_size'] or 0

            size_mb = total_size / (1024 * 1024)
            self.selection_info.setText(f"🗑️ {count} tracks selected for deletion (~{size_mb:.1f}MB)")
            self.delete_btn.setEnabled(True)

    def confirm_deletion(self):
        """Confirm and execute deletion with comprehensive safety checks"""
        if not self.selected_for_deletion:
            return

        # Collect detailed info about tracks being deleted
        tracks_to_delete = []
        playlists_affected = set()

        for group in self.duplicate_groups:
            for track in group:
                if track['rating_key'] in self.selected_for_deletion:
                    tracks_to_delete.append(track)
                    playlists_affected.update(track['playlists'])

        # Safety confirmation dialog
        reply = QMessageBox.question(
            self, "⚠️ Confirm Deletion",
            f"You are about to permanently delete {len(tracks_to_delete)} duplicate tracks.\n\n"
            f"📊 Space to be freed: ~{sum(t['file_size'] or 0 for t in tracks_to_delete) / (1024*1024):.1f}MB\n"
            f"📝 Playlists affected: {len(playlists_affected)}\n\n"
            "🔄 Playlists will be automatically updated to use the remaining versions.\n\n"
            "⚠️ THIS CANNOT BE UNDONE!\n\n"
            "Are you absolutely sure you want to continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.execute_deletion(tracks_to_delete)

    def create_duplicate_log(self, tracks_to_delete):
        """Create a detailed log file of the duplicate deletion operation"""
        try:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"duplicate_deletion_log_{timestamp}.txt"

            # Try to save in script directory first
            try:
                if hasattr(sys, '_MEIPASS'):
                    script_dir = os.path.dirname(sys.executable)
                else:
                    script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
                log_path = os.path.join(script_dir, log_filename)
            except:
                # Fallback to temp directory
                import tempfile
                log_path = os.path.join(tempfile.gettempdir(), log_filename)

            with open(log_path, 'w', encoding='utf-8') as log_file:
                log_file.write("🔍 PLEX LIBRARY DUPLICATE DELETION LOG\n")
                log_file.write("=" * 50 + "\n")
                log_file.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_file.write(f"Total duplicate groups: {len(self.duplicate_groups)}\n")
                log_file.write(f"Tracks selected for deletion: {len(tracks_to_delete)}\n")
                log_file.write("\n")

                # Log all duplicate groups with details
                for group_idx, group in enumerate(self.duplicate_groups, 1):
                    log_file.write(f"\n{'='*60}\n")
                    log_file.write(f"DUPLICATE GROUP {group_idx}: {group[0]['title']} - {group[0]['artist']}\n")
                    log_file.write(f"{'='*60}\n")

                    # Sort by quality for logging
                    sorted_tracks = sorted(group, key=lambda t: (t['bitrate'] or 0, t['file_size'] or 0), reverse=True)

                    for track_idx, track in enumerate(sorted_tracks, 1):
                        action = "DELETING" if track['rating_key'] in self.selected_for_deletion else "KEEPING"
                        quality_note = "(BEST QUALITY)" if track_idx == 1 else "(LOWER QUALITY)"

                        log_file.write(f"\n  Track {track_idx}: {action} {quality_note}\n")
                        log_file.write(f"    Title: {track['title']}\n")
                        log_file.write(f"    Artist: {track['artist']}\n")
                        log_file.write(f"    Album: {track['album']}\n")
                        log_file.write(f"    Duration: {track['duration'] // 60000 if track['duration'] else 0}:{(track['duration'] % 60000) // 1000:02d if track['duration'] else 0}\n")
                        log_file.write(f"    Bitrate: {track['bitrate'] or 'Unknown'}kbps\n")
                        log_file.write(f"    File Size: {track['file_size'] / (1024*1024):.1f}MB\n" if track['file_size'] else "    File Size: Unknown\n")
                        log_file.write(f"    File Path: {track['file_path']}\n")
                        log_file.write(f"    Rating Key: {track['rating_key']}\n")

                        if track['playlists']:
                            log_file.write(f"    Playlists: {', '.join(track['playlists'])}\n")
                        else:
                            log_file.write("    Playlists: None\n")

                log_file.write(f"\n{'='*60}\n")
                log_file.write("DELETION SUMMARY\n")
                log_file.write(f"{'='*60}\n")
                space_saved = sum(t['file_size'] or 0 for t in tracks_to_delete) / (1024*1024)
                log_file.write(f"Estimated space to be freed: {space_saved:.1f}MB\n")
                log_file.write(f"Operation initiated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

            return log_path

        except Exception as e:
            logging.error(f"Failed to create duplicate deletion log: {e}")
            return None

    def execute_deletion(self, tracks_to_delete):
        """Execute the actual deletion process with comprehensive logging"""
        # Create detailed log before deletion
        log_path = self.create_duplicate_log(tracks_to_delete)

        # Create progress dialog
        progress = QProgressDialog("Deleting duplicate tracks...", "Cancel", 0, len(tracks_to_delete), self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()

        deleted_count = 0
        errors = []
        deletion_log = []

        for i, track in enumerate(tracks_to_delete):
            if progress.wasCanceled():
                break

            progress.setValue(i)
            progress.setLabelText(f"Deleting: {track['title']} - {track['artist']}")

            try:
                # Delete from Plex library
                plex_track = self.plex_server.fetchItem(track['rating_key'])
                plex_track.delete()
                deleted_count += 1
                success_msg = f"✅ DELETED: {track['title']} - {track['artist']} ({track['file_path']})"
                deletion_log.append(success_msg)
                logging.info(f"Deleted duplicate track: {track['title']} - {track['artist']}")

            except Exception as e:
                error_msg = f"❌ FAILED: {track['title']} - {track['artist']}: {str(e)}"
                errors.append(f"{track['title']} - {track['artist']}: {str(e)}")
                deletion_log.append(error_msg)
                logging.error(f"Failed to delete duplicate: {error_msg}")

        progress.setValue(len(tracks_to_delete))

        # Update log with deletion results
        if log_path:
            try:
                with open(log_path, 'a', encoding='utf-8') as log_file:
                    log_file.write(f"\n{'='*60}\n")
                    log_file.write("DELETION RESULTS\n")
                    log_file.write(f"{'='*60}\n")
                    log_file.write(f"Successfully deleted: {deleted_count} tracks\n")
                    log_file.write(f"Failed to delete: {len(errors)} tracks\n")
                    log_file.write(f"Operation completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                    log_file.write("DETAILED DELETION LOG:\n")
                    log_file.write("-" * 30 + "\n")
                    for entry in deletion_log:
                        log_file.write(f"{entry}\n")

                    if errors:
                        log_file.write(f"\nERRORS ENCOUNTERED:\n")
                        log_file.write("-" * 20 + "\n")
                        for error in errors:
                            log_file.write(f"❌ {error}\n")

            except Exception as e:
                logging.error(f"Failed to update deletion log: {e}")

        # Show completion summary
        completion_msg = f"🎉 Successfully deleted {deleted_count} duplicate tracks!"
        if log_path:
            completion_msg += f"\n\n📄 Detailed log saved to:\n{log_path}"

        if errors:
            QMessageBox.warning(self, "Deletion Completed with Errors",
                              f"✅ Successfully deleted: {deleted_count} tracks\n"
                              f"❌ Failed to delete: {len(errors)} tracks\n\n"
                              f"Errors:\n" + "\n".join(errors[:5]) +
                              (f"\n... and {len(errors) - 5} more" if len(errors) > 5 else "") +
                              (f"\n\n📄 Full log saved to:\n{log_path}" if log_path else ""))
        else:
            QMessageBox.information(self, "Deletion Completed",
                                  f"{completion_msg}\n\nYour library is now cleaner and more organized.")

        self.accept()  # Close dialog


class UserSelectionDialog(QDialog):
    """Dialog for selecting a Plex user from available accounts"""

    def __init__(self, account, parent=None):
        super().__init__(parent)
        self.account = account
        self.selected_user = None
        self.selected_user_token = None
        self.selected_account = None  # Will hold the switched account for home users
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Select Plex User")
        self.setObjectName("userSelectionDialog")
        self.setMinimumSize(620, 500)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        self.setStyleSheet("""
            QDialog#userSelectionDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #121b2b, stop:1 #0f1828);
                border: 1px solid #344d70;
                border-radius: 12px;
            }
            QFrame#userSelectionHeaderCard {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1d2c43, stop:1 #1a2334);
                border: 1px solid #465876;
                border-radius: 12px;
            }
            QLabel#userSelectionTitle {
                color: #f4f8ff;
                font-size: 25px;
                font-weight: 800;
            }
            QLabel#userSelectionSubtitle {
                color: #b8c9df;
                font-size: 13px;
            }
            QLabel#userSelectionChip {
                color: #8ad8ff;
                background-color: #1f2f40;
                border: 1px solid #2fb8ff;
                border-radius: 10px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 700;
            }
            QListWidget#userSelectionList {
                background-color: #16253a;
                border: 1px solid #36527a;
                border-radius: 10px;
                color: #f3f8ff;
                padding: 8px;
                outline: none;
                font-size: 14px;
            }
            QListWidget#userSelectionList::item {
                background-color: #1d2e46;
                border: 1px solid #345173;
                border-radius: 8px;
                padding: 12px 14px;
                margin: 4px 0;
            }
            QListWidget#userSelectionList::item:hover {
                background-color: #29415f;
                border: 1px solid #4b6f9d;
            }
            QListWidget#userSelectionList::item:selected {
                background-color: #2c8fdb;
                border: 1px solid #4fa8ee;
                color: #ffffff;
            }
            QPushButton#userSelectPrimaryButton {
                background-color: #2fb8ff;
                border: 1px solid #53c6ff;
                border-radius: 9px;
                color: #ffffff;
                font-size: 14px;
                font-weight: 800;
                padding: 10px 18px;
                min-width: 140px;
            }
            QPushButton#userSelectPrimaryButton:hover {
                background-color: #239ede;
            }
            QPushButton#userSelectPrimaryButton:pressed {
                background-color: #1f88c0;
            }
            QPushButton#userSelectSecondaryButton {
                background-color: #24364f;
                border: 1px solid #4a6187;
                border-radius: 9px;
                color: #d9e7ff;
                font-size: 14px;
                font-weight: 700;
                padding: 10px 18px;
                min-width: 120px;
            }
            QPushButton#userSelectSecondaryButton:hover {
                background-color: #31496b;
            }
            QPushButton#userSelectSecondaryButton:pressed {
                background-color: #2a3f5c;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        header_card = QFrame()
        header_card.setObjectName("userSelectionHeaderCard")
        header_layout = QVBoxLayout(header_card)
        header_layout.setContentsMargins(14, 12, 14, 12)
        header_layout.setSpacing(6)

        header_title = QLabel("Select Plex User")
        header_title.setObjectName("userSelectionTitle")
        header_layout.addWidget(header_title)

        self.summary_label = QLabel("Choose which user account to manage playlists for.")
        self.summary_label.setObjectName("userSelectionSubtitle")
        header_layout.addWidget(self.summary_label)

        self.user_count_chip = QLabel("Loading users...")
        self.user_count_chip.setObjectName("userSelectionChip")
        header_layout.addWidget(self.user_count_chip, alignment=Qt.AlignmentFlag.AlignLeft)

        layout.addWidget(header_card)

        self.user_list = QListWidget()
        self.user_list.setObjectName("userSelectionList")
        self.user_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.user_list.itemDoubleClicked.connect(lambda _item: self.on_user_selected())
        layout.addWidget(self.user_list)

        self.populate_users()

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        select_btn = QPushButton("Select User")
        select_btn.setObjectName("userSelectPrimaryButton")
        select_btn.setDefault(True)
        select_btn.clicked.connect(self.on_user_selected)
        button_layout.addWidget(select_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("userSelectSecondaryButton")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def populate_users(self):
        """Populate the user list with available Plex users"""
        try:
            self.user_list.clear()

            # Get main account user
            main_user_item = QListWidgetItem(f"{self.account.username}   •   Administrator")
            main_user_item.setData(Qt.UserRole, {'user': None, 'is_admin': True, 'username': self.account.username})
            main_user_item.setToolTip("Administrator account with full access")
            self.user_list.addItem(main_user_item)

            # Get managed/home users
            try:
                users = self.account.users()
                for user in users:
                    # Determine user type label
                    if hasattr(user, 'home') and user.home:
                        user_type = "Home User"
                    elif hasattr(user, 'friend') and user.friend:
                        user_type = "Friend"
                    else:
                        user_type = "User"

                    # Get user info
                    username = user.title if hasattr(user, 'title') else str(user)

                    user_item = QListWidgetItem(f"{username}   •   {user_type}")
                    user_item.setData(Qt.UserRole, {'user': user, 'is_admin': False, 'username': username})
                    user_item.setToolTip(f"{user_type}: {username}")
                    self.user_list.addItem(user_item)

            except Exception as user_error:
                logging.warning(f"Could not load managed users: {user_error}")

            # Select first item by default
            if self.user_list.count() > 0:
                self.user_list.setCurrentRow(0)
            self.user_count_chip.setText(f"{self.user_list.count()} account(s) available")
            self.summary_label.setText("Choose which user account to manage playlists for this session.")

        except Exception as e:
            logging.error(f"Error populating users: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to load users: {str(e)}")

    def on_user_selected(self):
        """Handle user selection"""
        current_item = self.user_list.currentItem()
        if not current_item:
            QMessageBox.warning(self, "No Selection", "Please select a user account.")
            return

        user_data = current_item.data(Qt.UserRole)
        self.selected_user = user_data['user']
        self.selected_user_name = user_data['username']
        self.is_admin = user_data['is_admin']

        # Get user-specific token/account if not admin
        if not self.is_admin and self.selected_user:
            try:
                # For home users, switch to their account context
                # This returns a new MyPlexAccount instance for the home user
                self.selected_account = self.account.switchHomeUser(self.selected_user)
                self.selected_user_token = self.selected_account.authenticationToken
                logging.info(f"Switched to home user: {self.selected_user_name}")
            except Exception as e:
                logging.error(f"Could not switch to home user: {e}")
                QMessageBox.critical(self, "Switch Error",
                    f"Failed to switch to user '{self.selected_user_name}'.\n\n"
                    f"This user may require a PIN or may not have proper permissions.\n\n"
                    f"Error: {str(e)}")
                return
        else:
            # Use main account for admin
            self.selected_account = self.account
            self.selected_user_token = self.account.authenticationToken

        self.accept()


class PlexPlaylistManager(QMainWindow):
    def __init__(self, startup_splash=None):
        super().__init__()
        self._startup_splash = startup_splash
        self._startup_splash_active = startup_splash is not None
        self.playlists = []
        self.playlist_data = []  # Store playlist objects with track counts
        self.plex_server = None
        self.spotify_client = None
        self.sync_thread = None
        self.fetch_thread = None
        self.export_thread = None  # Add export thread tracking
        self.backup_thread = None  # Add backup thread tracking
        self.batch_track_count_thread = None  # Add batch track count thread
        self.loading_dialog = None
        self.playlist_cache = PlaylistCache()  # Initialize cache system
        self.track_count_threads = {}  # Keep track of background track count loading
        self.last_section_id = None  # Remember the last selected Plex library section
        self.auto_sync_timer = QTimer()
        self.auto_sync_timer.timeout.connect(self.perform_auto_sync)
        self.scheduled_sync_timer = QTimer()
        self.scheduled_sync_timer.timeout.connect(self.check_scheduled_sync)
        self.scheduled_sync_timer.start(60000)  # Check every minute
        self.path_mappings = []  # Store user-defined path mappings
        self.plex_library_paths = []  # Cache Plex library root paths
        self.feature_flags = APP_CONFIG_DEFAULTS.get("features", {}).copy()
        self.smart_match_settings = APP_CONFIG_DEFAULTS.get("smart_match", {}).copy()
        self.metadata_settings = APP_CONFIG_DEFAULTS.get("metadata", {}).copy()
        self.metadata_service = None
        self._suspend_settings_apply = True
        self._startup_auto_fetch_pending = False
        self.smart_match_preload_thread = None
        self.smart_match_preload_session_key = ""
        self.smart_match_preload_show_dialog = False
        self._pending_smart_match_import = None
        self.apple_music_library_data = None
        self.plex_server_profiles = []
        self.source_server_playlists = []
        self.source_server_playlists_profile_url = ""
        self.server_sync_policy = "keep_extras"
        self.server_sync_jobs = []
        self.server_sync_job_queue = []
        self.server_sync_job_thread = None
        self.server_sync_jobs_ui_refreshing = False
        self.source_playlist_load_thread = None
        self.server_playlist_transfer_thread = None

        # User management
        self.current_user = None  # Currently selected user
        self.current_user_name = "Administrator"  # Display name of current user
        self.is_admin = True  # Whether current user is administrator
        self.plex_account = None  # MyPlexAccount instance for user management

        self._update_startup_progress("Loading interface...", 8)
        self.initUI()
        self._update_startup_progress("Loading configuration...", 28)
        _set_smart_match_runtime_settings(self.smart_match_settings)
        self.load_config()
        self._update_startup_progress("Applying settings...", 72)
        self._suspend_settings_apply = False
        self.apply_settings_from_controls(save=False, show_message=False)
        self._update_startup_progress("Preparing metadata services...", 84)
        self.setup_metadata_service()
        self._update_startup_progress("Finalizing window...", 94)
        self.setStyleSheet(self.get_stylesheet())
        self.setWindowTitle('Syncra - Playlist Manager')
        self.setWindowIcon(QIcon('Syncra Icon.ico'))
        self.setMinimumSize(860, 540)
        self.resize(1280, 780)
        self._update_startup_progress("Ready", 100)

    def _update_startup_progress(self, message, value=None):
        splash = getattr(self, "_startup_splash", None)
        if splash and getattr(self, "_startup_splash_active", False):
            splash.update_progress(message, value)
        
    def get_logo_svg(self):
        """Return the complete SVG logo code"""
        return get_syncra_logo_svg()

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Left navigation sidebar
        sidebar = QWidget()
        sidebar.setFixedWidth(290)
        sidebar.setObjectName("leftSidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 14, 16, 14)
        sidebar_layout.setSpacing(8)

        # Logo section
        from PyQt6.QtSvgWidgets import QSvgWidget
        from PyQt6.QtCore import QByteArray

        logo_widget = QSvgWidget()
        svg_data = QByteArray(self.get_logo_svg().encode('utf-8'))
        logo_widget.load(svg_data)
        logo_widget.setFixedSize(258, 100)
        sidebar_layout.addWidget(logo_widget)

        self.home_btn = ModernButton("Home")
        self.connection_btn = ModernButton("Connection")
        self.playlists_btn = ModernButton("Playlists")
        self.streaming_btn = ModernButton("Streaming Import")
        self.local_tracks_btn = ModernButton("Local Tracks")
        self.sync_btn = ModernButton("Sync Manager")
        self.tools_btn = ModernButton("Tools && Utilities")
        self.settings_btn = ModernButton("Settings")

        nav_style = "text-align: left; padding-left: 12px; font-weight: 600;"
        for btn in [
            self.home_btn,
            self.connection_btn,
            self.playlists_btn,
            self.streaming_btn,
            self.local_tracks_btn,
            self.sync_btn,
            self.tools_btn,
            self.settings_btn,
        ]:
            btn.setStyleSheet(nav_style)

        self._set_button_icon(self.home_btn, "home", QStyle.StandardPixmap.SP_DesktopIcon)
        self._set_button_icon(self.connection_btn, "connection", QStyle.StandardPixmap.SP_DriveNetIcon)
        self._set_button_icon(self.playlists_btn, "playlists", QStyle.StandardPixmap.SP_FileDialogListView)
        self._set_button_icon(self.streaming_btn, "streaming_import", QStyle.StandardPixmap.SP_MediaPlay)
        self._set_button_icon(self.local_tracks_btn, "local_tracks", QStyle.StandardPixmap.SP_DirHomeIcon)
        self._set_button_icon(self.sync_btn, "sync_manager", QStyle.StandardPixmap.SP_BrowserReload)
        self._set_button_icon(self.tools_btn, "tools_utilities", QStyle.StandardPixmap.SP_ComputerIcon)
        self._set_button_icon(self.settings_btn, "settings", QStyle.StandardPixmap.SP_FileDialogDetailedView)

        sidebar_layout.addWidget(self._sidebar_label("Explore"))
        sidebar_layout.addWidget(self.home_btn)
        sidebar_layout.addWidget(self.connection_btn)
        sidebar_layout.addWidget(self.playlists_btn)

        sidebar_layout.addWidget(self._sidebar_label("Import & Sync"))
        sidebar_layout.addWidget(self.streaming_btn)
        sidebar_layout.addWidget(self.local_tracks_btn)
        sidebar_layout.addWidget(self.sync_btn)

        sidebar_layout.addWidget(self._sidebar_label("Utilities"))
        sidebar_layout.addWidget(self.tools_btn)
        sidebar_layout.addWidget(self.settings_btn)
        sidebar_layout.addStretch()

        main_layout.addWidget(sidebar)

        # Main content area
        content_container = QWidget()
        content_container.setObjectName("mainContentSurface")
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(18, 14, 18, 14)
        content_layout.setSpacing(10)

        header_frame = QFrame()
        header_frame.setObjectName("topHeaderCard")
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(16, 12, 16, 12)
        header_layout.setSpacing(12)

        header_text_col = QVBoxLayout()
        header_text_col.setContentsMargins(0, 0, 0, 0)
        header_text_col.setSpacing(0)
        self.page_title_label = QLabel("Home")
        self.page_title_label.setObjectName("pageTitle")
        self.page_title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
        self.page_subtitle_label = QLabel("Quick actions and system overview")
        self.page_subtitle_label.setObjectName("pageSubtitle")
        self.page_subtitle_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        header_text_col.addWidget(self.page_title_label)
        header_text_col.addWidget(self.page_subtitle_label)
        header_layout.addLayout(header_text_col, 1)

        chip_col = QVBoxLayout()
        chip_col.setSpacing(6)
        chip_col.setContentsMargins(0, 0, 0, 0)
        self.header_connection_chip = QLabel("Offline")
        self.header_connection_chip.setObjectName("headerChipWarn")
        self.header_connection_chip.setAlignment(Qt.AlignCenter)
        self.header_metadata_chip = QLabel("Metadata: Off")
        self.header_metadata_chip.setObjectName("headerChipNeutral")
        self.header_metadata_chip.setAlignment(Qt.AlignCenter)
        self.header_user_chip = QLabel("User: Guest")
        self.header_user_chip.setObjectName("headerChipNeutral")
        self.header_user_chip.setAlignment(Qt.AlignCenter)
        chip_col.addWidget(self.header_connection_chip)
        chip_col.addWidget(self.header_metadata_chip)
        chip_col.addWidget(self.header_user_chip)
        header_layout.addLayout(chip_col, 0)
        content_layout.addWidget(header_frame)

        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("mainContentStack")
        content_layout.addWidget(self.content_stack, 1)
        main_layout.addWidget(content_container, 1)

        # Create pages
        self.create_dashboard_page()
        self.create_connection_page()
        self.create_playlists_page()
        self.create_streaming_services_page()
        self.create_local_tracks_page()
        self.create_sync_manager_page()
        self.create_tools_page()
        self.create_settings_page()

        # Connect navigation
        self.home_btn.clicked.connect(lambda: self.navigate_to_page(0, "Home", "Quick actions and system overview"))
        self.connection_btn.clicked.connect(lambda: self.navigate_to_page(1, "Connection", "Connect and authenticate with Plex"))
        self.playlists_btn.clicked.connect(lambda: self.navigate_to_page(2, "Playlists", "Manage import, export, and editing"))
        self.streaming_btn.clicked.connect(lambda: self.navigate_to_page(3, "Streaming Import", "Import from Spotify, Deezer, Tidal, ListenBrainz, and Apple Music XML"))
        self.local_tracks_btn.clicked.connect(lambda: self.navigate_to_page(4, "Local Tracks", "Scan folders and build playlists"))
        self.sync_btn.clicked.connect(lambda: self.navigate_to_page(5, "Sync Manager", "Configure recurring sync jobs"))
        self.tools_btn.clicked.connect(lambda: self.navigate_to_page(6, "Tools & Utilities", "Advanced maintenance and analysis"))
        self.settings_btn.clicked.connect(lambda: self.navigate_to_page(7, "Settings", "Feature flags and application preferences"))

        self.navigate_to_page(0, "Home", "Quick actions and system overview")

        # Status bar
        self.statusBar().showMessage("Ready")

    def _sidebar_label(self, text):
        label = QLabel(text.upper())
        label.setStyleSheet("color: #8fa1ba; font-size: 11px; font-weight: 700; padding: 4px 8px;")
        return label

    def _resolve_asset_icon(self, icon_key):
        icon_dir = resource_path(os.path.join("assets", "icons"))
        icon_candidates = {
            "home": ["home.svg", "home.png"],
            "connection": ["connection.svg", "connection.png"],
            "plex_connect": ["plex-connect.svg", "plex-connect.png", "connection.svg", "connection.png"],
            "users": ["users.svg", "users.png"],
            "playlists": ["playlists.svg", "playlists.png"],
            "streaming_import": ["streaming-import.svg", "streaming-import.png"],
            "local_tracks": ["local-tracks.svg", "LocalTracks.png"],
            "sync_manager": ["sync-manager.svg", "sync-manager.png"],
            "tools_utilities": ["tool-utilities.svg", "tool-utilities.png"],
            "settings": ["settings.svg", "settings.png"],
            "metadata_fixer": ["tool-utilities.svg", "tool-utilities.png"],
        }
        for icon_name in icon_candidates.get(icon_key, []):
            icon_path = os.path.join(icon_dir, icon_name)
            if os.path.exists(icon_path):
                return QIcon(icon_path)
        return None

    def _set_button_icon(self, button, icon_key, fallback_pixmap):
        icon = self._resolve_asset_icon(icon_key)
        if icon and not icon.isNull():
            button.setIcon(icon)
        else:
            button.setIcon(self.style().standardIcon(fallback_pixmap))
        button.setIconSize(QSize(16, 16))

    def _add_page_to_stack(self, page):
        scroll = QScrollArea()
        scroll.setObjectName("pageScrollArea")
        page.setObjectName("contentPage")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(page)
        self.content_stack.addWidget(scroll)

    def add_unified_page_header(self, layout, title, subtitle, icon_key):
        header = QFrame()
        header.setObjectName("sectionHeaderCard")
        row = QVBoxLayout(header)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)
        title_row.addStretch(1)

        title_icon = QLabel()
        title_icon.setFixedSize(22, 22)
        icon = self._resolve_asset_icon(icon_key)
        if icon and not icon.isNull():
            title_icon.setPixmap(icon.pixmap(QSize(18, 18)))
        title_icon.setAlignment(Qt.AlignCenter)
        title_row.addWidget(title_icon, 0, Qt.AlignCenter)

        section_title = QLabel(title)
        section_title.setObjectName("sectionHeaderTitle")
        section_title.setAlignment(Qt.AlignCenter)
        title_row.addWidget(section_title, 0, Qt.AlignCenter)

        right_balance = QLabel()
        right_balance.setFixedSize(22, 22)
        title_row.addWidget(right_balance, 0, Qt.AlignCenter)
        title_row.addStretch(1)

        section_subtitle = QLabel(subtitle)
        section_subtitle.setObjectName("sectionHeaderSubtitle")
        section_subtitle.setAlignment(Qt.AlignCenter)

        row.addLayout(title_row)
        row.addWidget(section_subtitle, 0, Qt.AlignCenter)
        layout.addWidget(header)

    def navigate_to_page(self, index, title, subtitle):
        self.content_stack.setCurrentIndex(index)
        self.page_title_label.setText(title)
        self.page_subtitle_label.setText(subtitle)

    def create_dashboard_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(12)

        hero = QFrame()
        hero.setObjectName("dashboardHeroCard")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(18, 16, 18, 16)
        hero_layout.setSpacing(12)

        hero_top_row = QHBoxLayout()
        hero_title_wrap = QVBoxLayout()
        hero_title_wrap.setSpacing(2)
        self.dashboard_hero_title = QLabel("Welcome back")
        self.dashboard_hero_title.setObjectName("dashboardHeroTitle")
        self.dashboard_hero_subtitle = QLabel("Control your Plex music workflow from one modern workspace.")
        self.dashboard_hero_subtitle.setObjectName("dashboardHeroSubtitle")
        hero_title_wrap.addWidget(self.dashboard_hero_title)
        hero_title_wrap.addWidget(self.dashboard_hero_subtitle)
        hero_top_row.addLayout(hero_title_wrap, 1)

        self.dashboard_live_badge = QLabel("Live")
        self.dashboard_live_badge.setObjectName("headerChipAccent")
        hero_top_row.addWidget(self.dashboard_live_badge, 0, Qt.AlignTop)
        hero_layout.addLayout(hero_top_row)

        metrics_row = QHBoxLayout()
        metrics_row.setSpacing(10)
        self.metric_playlists = QLabel("Playlists\n0")
        self.metric_playlists.setObjectName("dashboardMetricCard")
        self.metric_playlists.setAlignment(Qt.AlignCenter)
        self.metric_sync_jobs = QLabel("Sync Jobs\n0")
        self.metric_sync_jobs.setObjectName("dashboardMetricCard")
        self.metric_sync_jobs.setAlignment(Qt.AlignCenter)
        self.metric_user = QLabel("Active User\nGuest")
        self.metric_user.setObjectName("dashboardMetricCard")
        self.metric_user.setAlignment(Qt.AlignCenter)
        metrics_row.addWidget(self.metric_playlists)
        metrics_row.addWidget(self.metric_sync_jobs)
        metrics_row.addWidget(self.metric_user)
        hero_layout.addLayout(metrics_row)
        layout.addWidget(hero)

        quick_group = QGroupBox("Quick Actions")
        quick_layout = QGridLayout(quick_group)

        connect_quick = ModernButton("Connect to Plex")
        connect_quick.clicked.connect(lambda: self.navigate_to_page(1, "Connection", "Connect and authenticate with Plex"))
        self._set_button_icon(connect_quick, "connection", QStyle.StandardPixmap.SP_DriveNetIcon)
        fetch_quick = ModernButton("Open Playlists")
        fetch_quick.clicked.connect(lambda: self.navigate_to_page(2, "Playlists", "Manage import, export, and editing"))
        self._set_button_icon(fetch_quick, "playlists", QStyle.StandardPixmap.SP_FileDialogListView)
        stream_quick = ModernButton("Import Streaming URL")
        stream_quick.clicked.connect(lambda: self.navigate_to_page(3, "Streaming Import", "Import from Spotify, Deezer, Tidal, ListenBrainz, and Apple Music XML"))
        self._set_button_icon(stream_quick, "streaming_import", QStyle.StandardPixmap.SP_MediaPlay)
        sync_quick = ModernButton("Open Sync Manager")
        sync_quick.clicked.connect(lambda: self.navigate_to_page(5, "Sync Manager", "Configure recurring sync jobs"))
        self._set_button_icon(sync_quick, "sync_manager", QStyle.StandardPixmap.SP_BrowserReload)
        tools_quick = ModernButton("Open Tools")
        tools_quick.clicked.connect(lambda: self.navigate_to_page(6, "Tools & Utilities", "Advanced maintenance and analysis"))
        self._set_button_icon(tools_quick, "tools_utilities", QStyle.StandardPixmap.SP_ComputerIcon)

        quick_layout.addWidget(connect_quick, 0, 0)
        quick_layout.addWidget(fetch_quick, 0, 1)
        quick_layout.addWidget(stream_quick, 1, 0)
        quick_layout.addWidget(sync_quick, 1, 1)
        quick_layout.addWidget(tools_quick, 2, 0)
        layout.addWidget(quick_group)

        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout(status_group)
        self.dashboard_status_label = QLabel("Connection: Not connected\nMetadata Fixer: Disabled")
        self.dashboard_status_label.setStyleSheet("color: #c9d1df; line-height: 1.4;")
        self.dashboard_status_label.setAlignment(Qt.AlignCenter)
        status_layout.addWidget(self.dashboard_status_label)
        layout.addWidget(status_group)
        layout.addStretch()

        self._add_page_to_stack(page)

    def create_sync_manager_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.add_unified_page_header(layout, "Sync Manager", "Configure scheduled synchronization between sources and Plex", "sync_manager")

        # Auto-sync controls
        header_layout = QHBoxLayout()
        self.auto_sync_checkbox = QCheckBox("Enable Auto-Sync")
        self.auto_sync_checkbox.stateChanged.connect(self.toggle_auto_sync)
        header_layout.addWidget(self.auto_sync_checkbox)

        self.sync_interval_spinbox = QSpinBox()
        self.sync_interval_spinbox.setMinimum(5)
        self.sync_interval_spinbox.setMaximum(1440)  # 24 hours
        self.sync_interval_spinbox.setValue(60)
        self.sync_interval_spinbox.setSuffix(" minutes")
        self.sync_interval_spinbox.valueChanged.connect(lambda: self.save_sync_config())
        header_layout.addWidget(QLabel("Interval:"))
        header_layout.addWidget(self.sync_interval_spinbox)

        layout.addLayout(header_layout)

        # Scheduled Sync Section
        scheduled_group = QGroupBox("Scheduled Sync")
        scheduled_layout = QVBoxLayout(scheduled_group)

        # First row: Enable checkbox, date/time picker
        first_row = QHBoxLayout()

        self.scheduled_sync_checkbox = QCheckBox("Enable Scheduled Sync")
        self.scheduled_sync_checkbox.stateChanged.connect(self.toggle_scheduled_sync)
        first_row.addWidget(self.scheduled_sync_checkbox)

        first_row.addWidget(QLabel("Start Date & Time:"))

        from PyQt6.QtCore import QDateTime
        self.scheduled_datetime = QDateTimeEdit()
        self.scheduled_datetime.setCalendarPopup(True)  # Show calendar popup
        self.scheduled_datetime.setDisplayFormat("yyyy-MM-dd HH:mm")
        self.scheduled_datetime.setMinimumDateTime(QDateTime.currentDateTime())
        self.scheduled_datetime.setDateTime(QDateTime.currentDateTime().addSecs(3600))  # Default 1 hour from now
        self.scheduled_datetime.dateTimeChanged.connect(self.on_scheduled_datetime_changed)
        first_row.addWidget(self.scheduled_datetime)

        first_row.addStretch()
        scheduled_layout.addLayout(first_row)

        # Second row: Repeat options
        second_row = QHBoxLayout()

        second_row.addWidget(QLabel("Repeat:"))

        self.repeat_combo = QComboBox()
        self.repeat_combo.addItem("Once (No Repeat)", "once")
        self.repeat_combo.addItem("Daily", "daily")
        self.repeat_combo.addItem("Every Weekday (Mon-Fri)", "weekdays")
        self.repeat_combo.addItem("Weekly (Every 7 days)", "weekly")
        self.repeat_combo.addItem("Bi-Weekly (Every 14 days)", "biweekly")
        self.repeat_combo.addItem("Monthly (Every 30 days)", "monthly")
        self.repeat_combo.currentIndexChanged.connect(self.on_repeat_changed)
        second_row.addWidget(self.repeat_combo)

        second_row.addWidget(QLabel("     Status:"))

        self.scheduled_status_label = QLabel("No scheduled sync")
        self.scheduled_status_label.setStyleSheet("color: #888; font-style: italic;")
        second_row.addWidget(self.scheduled_status_label)

        second_row.addStretch()
        scheduled_layout.addLayout(second_row)

        layout.addWidget(scheduled_group)
        
        # Sync configurations
        sync_group = QGroupBox("Sync Configurations")
        sync_layout = QVBoxLayout(sync_group)
        
        # Add new sync config
        add_config_layout = QHBoxLayout()
        add_config_layout.setContentsMargins(0, 0, 0, 0)
        add_config_layout.setSpacing(6)
        
        self.sync_playlist_combo = QComboBox()
        self.sync_playlist_combo.setMinimumWidth(200)
        self.sync_playlist_combo.setMinimumHeight(34)
        add_config_layout.addWidget(QLabel("Plex Playlist:"))
        add_config_layout.addWidget(self.sync_playlist_combo)
        
        self.sync_source_input = QLineEdit()
        self.sync_source_input.setMinimumHeight(34)
        self.sync_source_input.setPlaceholderText("Enter streaming URL (Spotify/Deezer/Tidal/ListenBrainz) or M3U file path")
        add_config_layout.addWidget(QLabel("Source:"))
        add_config_layout.addWidget(self.sync_source_input)
        
        self.add_sync_config_btn = ModernButton("Add Sync Config")
        self.add_sync_config_btn.setFixedHeight(34)
        self.add_sync_config_btn.clicked.connect(self.add_sync_config)
        add_config_layout.addWidget(self.add_sync_config_btn)
        add_config_layout.setAlignment(self.add_sync_config_btn, Qt.AlignmentFlag.AlignVCenter)
        
        sync_layout.addLayout(add_config_layout)
        
        # Sync configurations table
        self.sync_configs_table = QTableWidget()
        self.sync_configs_table.setColumnCount(5)
        self.sync_configs_table.setHorizontalHeaderLabels(["Playlist", "Source", "Last Sync", "Clear on Sync", "Actions"])
        self.sync_configs_table.horizontalHeader().setStretchLastSection(True)
        
        # HIDE THE VERTICAL HEADER (row numbers) - this removes the white bar
        self.sync_configs_table.verticalHeader().setVisible(False)
        
        # FIXED: Set proper column widths for buttons to be visible
        self.sync_configs_table.setColumnWidth(0, 200)  # Playlist
        self.sync_configs_table.setColumnWidth(1, 300)  # Source
        self.sync_configs_table.setColumnWidth(2, 150)  # Last Sync
        self.sync_configs_table.setColumnWidth(3, 140)  # Clear before sync
        self.sync_configs_table.setColumnWidth(4, 180)  # Actions - wider for buttons
        sync_layout.addWidget(self.sync_configs_table)
        
        layout.addWidget(sync_group)
        
        # Manual sync controls
        manual_group = QGroupBox("Manual Sync")
        manual_layout = QHBoxLayout(manual_group)
        
        self.sync_selected_btn = ModernButton("Sync Selected")
        self.sync_selected_btn.clicked.connect(self.sync_selected_playlists)
        manual_layout.addWidget(self.sync_selected_btn)
        
        self.sync_all_btn = ModernButton("Sync All")
        self.sync_all_btn.clicked.connect(self.sync_all_playlists)
        manual_layout.addWidget(self.sync_all_btn)
        
        manual_layout.addStretch()
        
        layout.addWidget(manual_group)
        
        # Sync progress
        self.sync_progress_group = QGroupBox("Sync Progress")
        self.sync_progress_group.setVisible(False)
        progress_layout = QVBoxLayout(self.sync_progress_group)
        
        self.sync_status_label = QLabel("Ready")
        progress_layout.addWidget(self.sync_status_label)
        
        self.sync_progress_bar = QProgressBar()
        progress_layout.addWidget(self.sync_progress_bar)
        
        self.stop_sync_btn = ModernButton("Stop Sync")
        self.stop_sync_btn.clicked.connect(self.stop_sync)
        progress_layout.addWidget(self.stop_sync_btn)
        
        layout.addWidget(self.sync_progress_group)
        
        # Sync log
        log_group = QGroupBox("Sync Log")
        log_layout = QVBoxLayout(log_group)
        
        self.sync_log = QTextEdit()
        self.sync_log.setMaximumHeight(150)
        self.sync_log.setReadOnly(True)
        log_layout.addWidget(self.sync_log)
        
        layout.addWidget(log_group)
        
        self._add_page_to_stack(page)
        
    def create_tools_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.add_unified_page_header(layout, "Tools & Utilities", "Advanced operations, diagnostics, and library maintenance", "tools_utilities")
        
        # Playlist operations
        playlist_ops_group = QGroupBox("Playlist Operations")
        playlist_ops_layout = QGridLayout(playlist_ops_group)
        
        # Merge playlists
        self.merge_playlists_btn = ModernButton("Merge Playlists")
        self.merge_playlists_btn.clicked.connect(self.show_playlist_merger)
        playlist_ops_layout.addWidget(self.merge_playlists_btn, 0, 0)
        
        # Duplicate detection
        self.find_duplicates_btn = ModernButton("🔍 Find Library Duplicates")
        self.find_duplicates_btn.clicked.connect(self.find_duplicate_tracks)
        self.find_duplicates_btn.setToolTip("Scan entire music library for duplicate tracks with safe deletion options")
        playlist_ops_layout.addWidget(self.find_duplicates_btn, 0, 1)
        
        # Backup playlists
        self.backup_playlists_btn = ModernButton("Backup All Playlists")
        self.backup_playlists_btn.clicked.connect(self.backup_all_playlists)
        playlist_ops_layout.addWidget(self.backup_playlists_btn, 1, 0)
        
        # Restore playlists
        self.restore_playlists_btn = ModernButton("Restore Playlists")
        self.restore_playlists_btn.clicked.connect(self.restore_playlists)
        playlist_ops_layout.addWidget(self.restore_playlists_btn, 1, 1)

        # Portable playlist+audio backup
        self.portable_backup_btn = ModernButton("Portable Backup")
        self.portable_backup_btn.clicked.connect(self.open_portable_backup_dialog)
        self.portable_backup_btn.setToolTip("Back up playlists plus actual audio files into a portable folder")
        self._set_button_icon(self.portable_backup_btn, "local_tracks", QStyle.StandardPixmap.SP_DriveHDIcon)
        playlist_ops_layout.addWidget(self.portable_backup_btn, 2, 1)

        # File metadata fixer
        self.metadata_fixer_btn = ModernButton("File Metadata Fixer")
        self.metadata_fixer_btn.clicked.connect(self.open_metadata_fixer)
        self.metadata_fixer_btn.setToolTip("Scan with MusicBrainz and write selected metadata fixes to local audio file tags")
        self._set_button_icon(self.metadata_fixer_btn, "metadata_fixer", QStyle.StandardPixmap.SP_FileDialogInfoView)
        playlist_ops_layout.addWidget(self.metadata_fixer_btn, 2, 0)

        layout.addWidget(playlist_ops_group)

        # Cross-server transfer
        server_sync_group = QGroupBox("Plex Server Sync")
        server_sync_layout = QVBoxLayout(server_sync_group)

        profile_row = QHBoxLayout()
        profile_row.setContentsMargins(0, 0, 0, 0)
        profile_row.setSpacing(6)
        profile_row.addWidget(QLabel("Source Server Profile:"))
        self.server_sync_profile_combo = QComboBox()
        self.server_sync_profile_combo.setMinimumHeight(34)
        self.server_sync_profile_combo.addItem("Select source server profile...", None)
        self.server_sync_profile_combo.currentIndexChanged.connect(self.on_server_profile_changed)
        profile_row.addWidget(self.server_sync_profile_combo, 1)

        self.server_sync_add_current_btn = ModernButton("Add Current Server")
        self.server_sync_add_current_btn.setFixedHeight(34)
        self.server_sync_add_current_btn.clicked.connect(self.add_current_server_profile)
        profile_row.addWidget(self.server_sync_add_current_btn)
        profile_row.setAlignment(self.server_sync_add_current_btn, Qt.AlignmentFlag.AlignVCenter)
        self.server_sync_remove_profile_btn = ModernButton("Remove Profile")
        self.server_sync_remove_profile_btn.setFixedHeight(34)
        self.server_sync_remove_profile_btn.clicked.connect(self.remove_selected_server_profile)
        profile_row.addWidget(self.server_sync_remove_profile_btn)
        profile_row.setAlignment(self.server_sync_remove_profile_btn, Qt.AlignmentFlag.AlignVCenter)
        server_sync_layout.addLayout(profile_row)

        playlist_row = QHBoxLayout()
        playlist_row.setContentsMargins(0, 0, 0, 0)
        playlist_row.setSpacing(6)
        playlist_row.addWidget(QLabel("Source Playlist:"))
        self.server_sync_playlist_combo = QComboBox()
        self.server_sync_playlist_combo.setMinimumHeight(34)
        self.server_sync_playlist_combo.addItem("Load source playlists first...", None)
        playlist_row.addWidget(self.server_sync_playlist_combo, 1)
        self.server_sync_load_playlists_btn = ModernButton("Load Source Playlists")
        self.server_sync_load_playlists_btn.setFixedHeight(34)
        self.server_sync_load_playlists_btn.clicked.connect(self.load_source_server_playlists)
        playlist_row.addWidget(self.server_sync_load_playlists_btn)
        playlist_row.setAlignment(self.server_sync_load_playlists_btn, Qt.AlignmentFlag.AlignVCenter)
        server_sync_layout.addLayout(playlist_row)

        policy_row = QHBoxLayout()
        policy_row.addWidget(QLabel("Sync Policy:"))
        self.server_sync_policy_combo = QComboBox()
        self.server_sync_policy_combo.addItem("Mirror source (exact)", "mirror")
        self.server_sync_policy_combo.addItem("Add missing only", "add_only")
        self.server_sync_policy_combo.addItem("Source first, keep target extras", "keep_extras")
        self.server_sync_policy_combo.setToolTip(
            "Mirror: target becomes source order exactly. "
            "Add missing only: append only missing tracks. "
            "Keep extras: source order first, preserve extra target tracks."
        )
        default_policy = getattr(self, "server_sync_policy", "keep_extras")
        policy_index = self.server_sync_policy_combo.findData(default_policy)
        self.server_sync_policy_combo.setCurrentIndex(policy_index if policy_index >= 0 else 2)
        self.server_sync_policy_combo.currentIndexChanged.connect(self.on_server_sync_policy_changed)
        policy_row.addWidget(self.server_sync_policy_combo, 1)
        server_sync_layout.addLayout(policy_row)

        action_row = QHBoxLayout()
        self.server_sync_overwrite_cb = QCheckBox("Overwrite target playlist if it exists")
        self.server_sync_overwrite_cb.setChecked(True)
        self.server_sync_overwrite_cb.stateChanged.connect(self.on_server_sync_overwrite_changed)
        action_row.addWidget(self.server_sync_overwrite_cb)
        action_row.addStretch()
        self.server_sync_preview_btn = ModernButton("Dry Run Diff")
        self.server_sync_preview_btn.clicked.connect(self.preview_playlist_transfer_from_source_server)
        self._set_button_icon(self.server_sync_preview_btn, "playlists", QStyle.StandardPixmap.SP_FileDialogDetailedView)
        action_row.addWidget(self.server_sync_preview_btn)
        self.server_sync_transfer_btn = ModernButton("Transfer to Connected Server")
        self.server_sync_transfer_btn.clicked.connect(self.transfer_playlist_from_source_server)
        self._set_button_icon(self.server_sync_transfer_btn, "sync_manager", QStyle.StandardPixmap.SP_BrowserReload)
        action_row.addWidget(self.server_sync_transfer_btn)
        server_sync_layout.addLayout(action_row)
        self.on_server_sync_overwrite_changed()

        self.server_sync_status = QLabel(
            "Save multiple source servers, load a playlist from one server, and transfer it directly into the currently connected Plex server."
        )
        self.server_sync_status.setWordWrap(True)
        self.server_sync_status.setStyleSheet("color: #b8c9df; font-size: 12px;")
        server_sync_layout.addWidget(self.server_sync_status)

        scheduler_group = QGroupBox("Scheduled Server Sync Jobs")
        scheduler_layout = QVBoxLayout(scheduler_group)

        scheduler_controls = QHBoxLayout()
        scheduler_controls.addWidget(QLabel("Interval:"))
        self.server_sync_job_interval_spin = QSpinBox()
        self.server_sync_job_interval_spin.setRange(5, 10080)
        self.server_sync_job_interval_spin.setValue(60)
        self.server_sync_job_interval_spin.setSuffix(" min")
        scheduler_controls.addWidget(self.server_sync_job_interval_spin)
        scheduler_controls.addStretch()

        self.server_sync_add_job_btn = ModernButton("Add Scheduled Job")
        self.server_sync_add_job_btn.clicked.connect(self.add_server_sync_job_from_current_selection)
        scheduler_controls.addWidget(self.server_sync_add_job_btn)

        self.server_sync_run_due_btn = ModernButton("Run Due Jobs Now")
        self.server_sync_run_due_btn.clicked.connect(lambda: self.check_server_sync_jobs(force_run_due=True))
        scheduler_controls.addWidget(self.server_sync_run_due_btn)

        self.server_sync_remove_job_btn = ModernButton("Remove Selected Job")
        self.server_sync_remove_job_btn.clicked.connect(self.remove_selected_server_sync_job)
        scheduler_controls.addWidget(self.server_sync_remove_job_btn)
        scheduler_layout.addLayout(scheduler_controls)

        self.server_sync_jobs_list = QListWidget()
        self.server_sync_jobs_list.setMinimumHeight(130)
        self.server_sync_jobs_list.itemChanged.connect(self.on_server_sync_job_item_changed)
        scheduler_layout.addWidget(self.server_sync_jobs_list)

        self.server_sync_jobs_status = QLabel("No scheduled server sync jobs configured.")
        self.server_sync_jobs_status.setStyleSheet("color: #9cb2d2; font-size: 12px;")
        scheduler_layout.addWidget(self.server_sync_jobs_status)

        server_sync_layout.addWidget(scheduler_group)

        layout.addWidget(server_sync_group)

        # Statistics
        stats_group = QGroupBox("Playlist Statistics")
        stats_layout = QVBoxLayout(stats_group)
        
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setMaximumHeight(200)
        stats_layout.addWidget(self.stats_text)
        
        self.update_stats_btn = ModernButton("Update Statistics")
        self.update_stats_btn.clicked.connect(self.update_playlist_statistics)
        stats_layout.addWidget(self.update_stats_btn)
        
        layout.addWidget(stats_group)
        
        # Library analysis
        analysis_group = QGroupBox("Library Analysis")
        analysis_layout = QVBoxLayout(analysis_group)
        
        self.analysis_text = QTextEdit()
        self.analysis_text.setReadOnly(True)
        self.analysis_text.setMaximumHeight(200)
        analysis_layout.addWidget(self.analysis_text)
        
        self.analyze_library_btn = ModernButton("Analyze Music Library")
        self.analyze_library_btn.clicked.connect(self.analyze_music_library)
        analysis_layout.addWidget(self.analyze_library_btn)
        
        layout.addWidget(analysis_group)
        
        layout.addStretch()
        self._add_page_to_stack(page)
        self.refresh_feature_dependent_ui()
        self.refresh_server_sync_profiles_ui()
        self.refresh_server_sync_jobs_ui()

    def _build_current_server_profile(self):
        if not self.plex_server:
            return None

        base_url = str(getattr(self.plex_server, "_baseurl", "") or "").strip()
        if not base_url:
            ip = self.server_ip_input.text().strip() if hasattr(self, "server_ip_input") else ""
            port = self.server_port_input.text().strip() if hasattr(self, "server_port_input") else ""
            if not ip or not port:
                return None
            base_url = f"http://{ip}:{port}"

        token = self.token_input.text().strip() if hasattr(self, "token_input") else ""
        if not token and self.plex_account:
            token = str(getattr(self.plex_account, "authenticationToken", "") or "").strip()
        if not token:
            token = str(getattr(self.plex_server, "_token", "") or "").strip()
        if not token:
            return None

        profile_name = self.current_user_name if self.current_user_name else "Current Server"
        ip_hint = self.server_ip_input.text().strip() if hasattr(self, "server_ip_input") else ""
        if ip_hint:
            profile_name = f"{profile_name} @ {ip_hint}"
        return {
            "name": profile_name,
            "base_url": base_url,
            "token": token,
        }

    def refresh_server_sync_profiles_ui(self):
        if not hasattr(self, "server_sync_profile_combo"):
            return

        selected_base = None
        current_data = self.server_sync_profile_combo.currentData()
        if isinstance(current_data, dict):
            selected_base = str(current_data.get("base_url", "") or "").strip().lower()

        self.server_sync_profile_combo.blockSignals(True)
        self.server_sync_profile_combo.clear()
        self.server_sync_profile_combo.addItem("Select source server profile...", None)

        profiles = self.plex_server_profiles if isinstance(self.plex_server_profiles, list) else []
        for profile in profiles:
            if not isinstance(profile, dict):
                continue
            name = str(profile.get("name", "Unnamed Server") or "Unnamed Server").strip()
            base_url = str(profile.get("base_url", "") or "").strip()
            label = f"{name} ({base_url})" if base_url else name
            self.server_sync_profile_combo.addItem(label, profile)

        if selected_base:
            for idx in range(self.server_sync_profile_combo.count()):
                profile = self.server_sync_profile_combo.itemData(idx)
                if isinstance(profile, dict) and str(profile.get("base_url", "") or "").strip().lower() == selected_base:
                    self.server_sync_profile_combo.setCurrentIndex(idx)
                    break

        self.server_sync_profile_combo.blockSignals(False)
        self.on_server_profile_changed()

    def add_current_server_profile(self):
        profile = self._build_current_server_profile()
        if not profile:
            QMessageBox.warning(self, "Not Connected", "Connect to a Plex server first, then add it as a profile.")
            return

        existing_profiles = self.plex_server_profiles if isinstance(self.plex_server_profiles, list) else []
        base_url_key = str(profile.get("base_url", "") or "").strip().lower()
        replaced = False
        for idx, existing in enumerate(existing_profiles):
            if not isinstance(existing, dict):
                continue
            existing_key = str(existing.get("base_url", "") or "").strip().lower()
            if existing_key and existing_key == base_url_key:
                existing_profiles[idx] = profile
                replaced = True
                break

        if not replaced:
            existing_profiles.append(profile)
        self.plex_server_profiles = existing_profiles
        self.refresh_server_sync_profiles_ui()
        self.save_config()
        self.statusBar().showMessage("Server profile saved.", 2500)

    def remove_selected_server_profile(self):
        if not hasattr(self, "server_sync_profile_combo"):
            return
        profile = self.server_sync_profile_combo.currentData()
        if not isinstance(profile, dict):
            QMessageBox.warning(self, "No Profile Selected", "Select a source server profile to remove.")
            return

        base_url = str(profile.get("base_url", "") or "").strip().lower()
        if not base_url:
            return
        self.plex_server_profiles = [
            item for item in (self.plex_server_profiles or [])
            if not (isinstance(item, dict) and str(item.get("base_url", "") or "").strip().lower() == base_url)
        ]
        self.source_server_playlists = []
        self.source_server_playlists_profile_url = ""
        if hasattr(self, "server_sync_playlist_combo"):
            self.server_sync_playlist_combo.clear()
            self.server_sync_playlist_combo.addItem("Load source playlists first...", None)
        self.refresh_server_sync_profiles_ui()
        self.save_config()
        self.statusBar().showMessage("Server profile removed.", 2500)

    def on_server_profile_changed(self):
        profile = self.server_sync_profile_combo.currentData() if hasattr(self, "server_sync_profile_combo") else None
        has_profile = isinstance(profile, dict)
        profile_url = str(profile.get("base_url", "") or "").strip().lower() if has_profile else ""
        if profile_url != self.source_server_playlists_profile_url:
            self.source_server_playlists = []
            if hasattr(self, "server_sync_playlist_combo"):
                self.server_sync_playlist_combo.clear()
                self.server_sync_playlist_combo.addItem("Load source playlists first...", None)
        if hasattr(self, "server_sync_load_playlists_btn"):
            self.server_sync_load_playlists_btn.setEnabled(has_profile)
        if hasattr(self, "server_sync_add_job_btn"):
            self.server_sync_add_job_btn.setEnabled(bool(self.plex_server) and has_profile and bool(self.source_server_playlists))
        if hasattr(self, "server_sync_preview_btn"):
            self.server_sync_preview_btn.setEnabled(bool(self.plex_server) and has_profile and bool(self.source_server_playlists))
        if hasattr(self, "server_sync_transfer_btn"):
            self.server_sync_transfer_btn.setEnabled(bool(self.plex_server) and has_profile and bool(self.source_server_playlists))

    def on_server_sync_policy_changed(self):
        selected_policy = self.server_sync_policy_combo.currentData() if hasattr(self, "server_sync_policy_combo") else self.server_sync_policy
        self.server_sync_policy = str(selected_policy or "keep_extras").strip().lower()
        if not self._suspend_settings_apply:
            self.save_config()

    def on_server_sync_overwrite_changed(self):
        overwrite_enabled = bool(self.server_sync_overwrite_cb.isChecked()) if hasattr(self, "server_sync_overwrite_cb") else True
        if hasattr(self, "server_sync_policy_combo"):
            self.server_sync_policy_combo.setEnabled(overwrite_enabled)
        if not self._suspend_settings_apply:
            self.save_config()

    def _server_sync_parse_datetime(self, value):
        if not value:
            return None
        try:
            parsed = datetime.strptime(str(value), "%Y-%m-%d %H:%M")
            return parsed
        except Exception:
            return None

    def _server_sync_format_datetime(self, value):
        if isinstance(value, datetime):
            return value.strftime("%Y-%m-%d %H:%M")
        return datetime.now().strftime("%Y-%m-%d %H:%M")

    def _server_sync_next_run(self, interval_minutes):
        try:
            minutes = max(5, int(interval_minutes))
        except Exception:
            minutes = 60
        return datetime.now() + timedelta(minutes=minutes)

    def _server_sync_job_label(self, job):
        source_profile = job.get("source_profile", {}) if isinstance(job, dict) else {}
        profile_name = str(source_profile.get("name", "Unknown Source") or "Unknown Source").strip()
        target_profile = job.get("target_profile", {}) if isinstance(job, dict) else {}
        target_name = str(target_profile.get("name", "Target server") or "Target server").strip()
        playlist_name = str(job.get("source_playlist_title", "Unknown Playlist") or "Unknown Playlist").strip()
        policy = self._server_sync_policy_label(job.get("sync_policy", "keep_extras"))
        interval = int(job.get("interval_minutes", 60) or 60)
        next_run = str(job.get("next_run", "") or "n/a")
        last_status = str(job.get("last_status", "") or "").strip()
        base = f"{profile_name} -> {target_name}:{playlist_name} | Every {interval}m | {policy} | Next: {next_run}"
        if last_status:
            base += f" | Last: {last_status}"
        return base

    def refresh_server_sync_jobs_ui(self):
        if not hasattr(self, "server_sync_jobs_list"):
            return

        self.server_sync_jobs_ui_refreshing = True
        self.server_sync_jobs_list.clear()
        jobs = self.server_sync_jobs if isinstance(self.server_sync_jobs, list) else []
        enabled_count = 0
        for job in jobs:
            if not isinstance(job, dict):
                continue
            item = QListWidgetItem(self._server_sync_job_label(job))
            item.setData(Qt.ItemDataRole.UserRole, str(job.get("id", "") or ""))
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
            is_enabled = bool(job.get("enabled", True))
            if is_enabled:
                enabled_count += 1
            item.setCheckState(Qt.CheckState.Checked if is_enabled else Qt.CheckState.Unchecked)
            self.server_sync_jobs_list.addItem(item)
        self.server_sync_jobs_ui_refreshing = False

        if hasattr(self, "server_sync_jobs_status"):
            if not jobs:
                self.server_sync_jobs_status.setText("No scheduled server sync jobs configured.")
            else:
                self.server_sync_jobs_status.setText(f"Scheduled jobs: {len(jobs)} total, {enabled_count} enabled.")
        if hasattr(self, "server_sync_run_due_btn"):
            self.server_sync_run_due_btn.setEnabled(bool(jobs))

    def on_server_sync_job_item_changed(self, item):
        if self.server_sync_jobs_ui_refreshing:
            return
        if not item:
            return
        job_id = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not job_id:
            return
        enabled = item.checkState() == Qt.CheckState.Checked
        updated = False
        for job in self.server_sync_jobs:
            if isinstance(job, dict) and str(job.get("id", "")) == job_id:
                job["enabled"] = enabled
                updated = True
                break
        if updated:
            self.save_config()
            self.refresh_server_sync_jobs_ui()

    def _find_server_sync_job_by_id(self, job_id):
        for job in self.server_sync_jobs:
            if isinstance(job, dict) and str(job.get("id", "")) == str(job_id):
                return job
        return None

    def add_server_sync_job_from_current_selection(self):
        try:
            request = self._build_server_transfer_request()
        except Exception as e:
            QMessageBox.warning(self, "Server Sync Scheduler", str(e))
            return

        target_profile = self._build_current_server_profile()
        if not target_profile:
            QMessageBox.warning(self, "Server Sync Scheduler", "Connect to the target server before creating scheduled jobs.")
            return

        interval = int(self.server_sync_job_interval_spin.value()) if hasattr(self, "server_sync_job_interval_spin") else 60
        job = {
            "id": secrets.token_hex(8),
            "enabled": True,
            "source_profile": dict(request.get("profile", {})),
            "target_profile": target_profile,
            "source_playlist_title": request.get("source_playlist_title"),
            "target_section_id": request.get("section_id"),
            "target_section_title": self.section_combo.currentText().strip() if hasattr(self, "section_combo") else "",
            "target_mode": request.get("transfer_mode", "overwrite"),
            "sync_policy": request.get("sync_policy", "keep_extras"),
            "target_playlist_name": request.get("source_playlist_title"),
            "interval_minutes": interval,
            "next_run": self._server_sync_format_datetime(self._server_sync_next_run(interval)),
            "last_run": "",
            "last_status": "Pending",
        }
        if not isinstance(self.server_sync_jobs, list):
            self.server_sync_jobs = []
        self.server_sync_jobs.append(job)
        self.save_config()
        self.refresh_server_sync_jobs_ui()
        self.statusBar().showMessage("Scheduled server sync job added.", 3000)

    def remove_selected_server_sync_job(self):
        if not hasattr(self, "server_sync_jobs_list"):
            return
        item = self.server_sync_jobs_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Server Sync Scheduler", "Select a scheduled job to remove.")
            return
        job_id = str(item.data(Qt.ItemDataRole.UserRole) or "").strip()
        if not job_id:
            return

        self.server_sync_jobs = [
            job for job in (self.server_sync_jobs or [])
            if not (isinstance(job, dict) and str(job.get("id", "")) == job_id)
        ]
        self.save_config()
        self.refresh_server_sync_jobs_ui()
        self.statusBar().showMessage("Scheduled job removed.", 2500)

    def check_server_sync_jobs(self, force_run_due=False):
        jobs = [job for job in (self.server_sync_jobs or []) if isinstance(job, dict)]
        if not jobs:
            if force_run_due:
                QMessageBox.information(self, "Server Sync Scheduler", "No scheduled jobs configured.")
            return

        if (self.server_sync_job_thread and self.server_sync_job_thread.isRunning()) or (
            self.server_playlist_transfer_thread and self.server_playlist_transfer_thread.isRunning()
        ) or (
            self.sync_thread and self.sync_thread.isRunning()
        ):
            if force_run_due:
                QMessageBox.information(self, "Server Sync Scheduler", "A server transfer is already running.")
            return

        now = datetime.now()
        due_jobs = []
        for job in jobs:
            if not bool(job.get("enabled", True)):
                continue
            next_run = self._server_sync_parse_datetime(job.get("next_run"))
            if not next_run:
                next_run = now
                job["next_run"] = self._server_sync_format_datetime(next_run)
            if now >= next_run:
                due_jobs.append(job)

        if not due_jobs:
            if force_run_due:
                QMessageBox.information(self, "Server Sync Scheduler", "No due jobs right now.")
            return

        due_jobs.sort(key=lambda j: self._server_sync_parse_datetime(j.get("next_run")) or now)
        self.server_sync_job_queue = due_jobs
        self._run_next_server_sync_job()

    def _run_next_server_sync_job(self):
        if not self.server_sync_job_queue:
            self.save_config()
            self.refresh_server_sync_jobs_ui()
            return

        job = self.server_sync_job_queue.pop(0)
        source_profile = job.get("source_profile", {}) if isinstance(job, dict) else {}
        target_profile = job.get("target_profile", {}) if isinstance(job, dict) else {}
        source_playlist = str(job.get("source_playlist_title", "") or "").strip()
        target_section_id = job.get("target_section_id")
        target_section_title = str(job.get("target_section_title", "") or "").strip()
        target_mode = str(job.get("target_mode", "overwrite") or "overwrite").strip().lower()
        sync_policy = str(job.get("sync_policy", "keep_extras") or "keep_extras").strip().lower()
        target_name = str(job.get("target_playlist_name", source_playlist) or source_playlist).strip()
        filter_settings = {
            "enabled": bool(self.enable_filters_checkbox.isChecked()) if hasattr(self, "enable_filters_checkbox") else False,
            "avoid_live": bool(self.filter_live_checkbox.isChecked()) if hasattr(self, "filter_live_checkbox") else False,
            "avoid_compilation": bool(self.filter_compilation_checkbox.isChecked()) if hasattr(self, "filter_compilation_checkbox") else False,
            "deprioritize_remaster": bool(self.filter_remaster_checkbox.isChecked()) if hasattr(self, "filter_remaster_checkbox") else False,
            "deprioritize_deluxe": bool(self.filter_deluxe_checkbox.isChecked()) if hasattr(self, "filter_deluxe_checkbox") else False,
        }

        source_base_url = str(source_profile.get("base_url", "") or "").strip() if isinstance(source_profile, dict) else ""
        source_token = str(source_profile.get("token", "") or "").strip() if isinstance(source_profile, dict) else ""
        target_base_url = str(target_profile.get("base_url", "") or "").strip() if isinstance(target_profile, dict) else ""
        target_token = str(target_profile.get("token", "") or "").strip() if isinstance(target_profile, dict) else ""

        if not source_profile or not target_profile or not source_base_url or not source_token or not target_base_url or not target_token:
            job["last_run"] = self._server_sync_format_datetime(datetime.now())
            job["last_status"] = "Error: source/target profile missing"
            interval = int(job.get("interval_minutes", 60) or 60)
            job["next_run"] = self._server_sync_format_datetime(self._server_sync_next_run(interval))
            if hasattr(self, "sync_log"):
                self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Server job skipped (profile missing): {source_playlist}")
            self._run_next_server_sync_job()
            return

        if hasattr(self, "sync_log"):
            self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Running server sync job: {source_playlist}")
        if hasattr(self, "server_sync_jobs_status"):
            self.server_sync_jobs_status.setText(f"Running scheduled job: {source_playlist}")

        self.server_sync_job_thread = PlexServerPlaylistTransferThread(
            source_profile=source_profile,
            source_playlist_title=source_playlist,
            target_server=None,
            target_section_id=target_section_id,
            target_profile=target_profile,
            target_section_title=target_section_title,
            target_mode=target_mode,
            sync_policy=sync_policy,
            target_name_override=target_name,
            filter_settings=filter_settings,
            dry_run=False,
            parent=self,
        )
        self.server_sync_job_thread.progress_update.connect(
            lambda message, _pct: self._on_server_sync_job_progress(job, message)
        )
        self.server_sync_job_thread.transfer_complete.connect(
            lambda result: self._on_server_sync_job_complete(job, result)
        )
        self.server_sync_job_thread.error.connect(
            lambda error_message: self._on_server_sync_job_error(job, error_message)
        )
        self.server_sync_job_thread.finished.connect(self._on_server_sync_job_finished)
        self.server_sync_job_thread.start()

    def _on_server_sync_job_progress(self, job, message):
        if hasattr(self, "server_sync_jobs_status"):
            self.server_sync_jobs_status.setText(message)
        self.statusBar().showMessage(message)

    def _on_server_sync_job_complete(self, job, result):
        now = datetime.now()
        matched = int(result.get("matched_tracks", 0))
        total = int(result.get("total_tracks", 0))
        final_count = int(result.get("final_tracks", matched))
        job["last_run"] = self._server_sync_format_datetime(now)
        job["last_status"] = f"OK {matched}/{total} (final {final_count})"
        interval = int(job.get("interval_minutes", 60) or 60)
        job["next_run"] = self._server_sync_format_datetime(self._server_sync_next_run(interval))
        if hasattr(self, "sync_log"):
            self.sync_log.append(
                f"[{now.strftime('%H:%M:%S')}] Server job completed: {job.get('source_playlist_title', 'Unknown')} ({matched}/{total})"
            )

    def _on_server_sync_job_error(self, job, error_message):
        now = datetime.now()
        short_error = str(error_message or "Unknown error")
        if len(short_error) > 140:
            short_error = short_error[:140] + "..."
        job["last_run"] = self._server_sync_format_datetime(now)
        job["last_status"] = f"Error: {short_error}"
        interval = int(job.get("interval_minutes", 60) or 60)
        job["next_run"] = self._server_sync_format_datetime(self._server_sync_next_run(interval))
        if hasattr(self, "sync_log"):
            self.sync_log.append(
                f"[{now.strftime('%H:%M:%S')}] Server job error: {job.get('source_playlist_title', 'Unknown')} -> {short_error}"
            )
        logging.error(f"Scheduled server sync job failed: {error_message}")

    def _on_server_sync_job_finished(self):
        self.server_sync_job_thread = None
        self.save_config()
        self.refresh_server_sync_jobs_ui()
        self._run_next_server_sync_job()

    def load_source_server_playlists(self):
        profile = self.server_sync_profile_combo.currentData() if hasattr(self, "server_sync_profile_combo") else None
        if not isinstance(profile, dict):
            QMessageBox.warning(self, "No Source Selected", "Select a source server profile first.")
            return

        self.show_loading("Plex Server Sync", "Loading source server playlists...")
        if hasattr(self, "server_sync_load_playlists_btn"):
            self.server_sync_load_playlists_btn.setEnabled(False)

        self.source_playlist_load_thread = PlexServerPlaylistLoadThread(profile, self)
        self.source_playlist_load_thread.progress_update.connect(self.on_source_server_playlists_progress)
        self.source_playlist_load_thread.playlists_loaded.connect(self.on_source_server_playlists_loaded)
        self.source_playlist_load_thread.error.connect(self.on_source_server_playlists_error)
        self.source_playlist_load_thread.finished.connect(self._on_source_playlist_load_finished)
        self.source_playlist_load_thread.start()

    def _on_source_playlist_load_finished(self):
        if hasattr(self, "server_sync_load_playlists_btn"):
            self.server_sync_load_playlists_btn.setEnabled(True)

    def on_source_server_playlists_progress(self, message, percentage):
        if self.loading_dialog:
            self.loading_dialog.update_progress(message, percentage)
        if hasattr(self, "server_sync_status"):
            self.server_sync_status.setText(message)

    def on_source_server_playlists_loaded(self, playlists):
        self.hide_loading()
        self.source_server_playlists = playlists if isinstance(playlists, list) else []
        profile = self.server_sync_profile_combo.currentData() if hasattr(self, "server_sync_profile_combo") else None
        self.source_server_playlists_profile_url = (
            str(profile.get("base_url", "") or "").strip().lower() if isinstance(profile, dict) else ""
        )

        if hasattr(self, "server_sync_playlist_combo"):
            self.server_sync_playlist_combo.blockSignals(True)
            self.server_sync_playlist_combo.clear()
            self.server_sync_playlist_combo.addItem("Select source playlist...", None)
            for playlist in self.source_server_playlists:
                title = str(playlist.get("title", "") or "").strip()
                if not title:
                    continue
                leaf_count = playlist.get("leaf_count")
                label = f"{title} ({leaf_count} tracks)" if isinstance(leaf_count, int) else title
                self.server_sync_playlist_combo.addItem(label, title)
            self.server_sync_playlist_combo.blockSignals(False)

        self.on_server_profile_changed()
        self.statusBar().showMessage(f"Loaded {len(self.source_server_playlists)} source playlists.", 3000)
        if hasattr(self, "server_sync_status"):
            self.server_sync_status.setText(
                f"Loaded {len(self.source_server_playlists)} playlists. Select one and transfer it to the connected server."
            )

    def on_source_server_playlists_error(self, error_message):
        self.hide_loading()
        self.source_server_playlists = []
        self.source_server_playlists_profile_url = ""
        logging.error(f"Error loading source server playlists: {error_message}")
        QMessageBox.warning(self, "Source Server Error", f"Failed to load source playlists:\n{error_message}")
        if hasattr(self, "server_sync_status"):
            self.server_sync_status.setText("Failed to load source playlists. Check profile URL/token and try again.")

    def _build_server_transfer_request(self):
        if not self.plex_server:
            raise ValueError("Connect to the target Plex server first.")

        section_id = self.section_combo.currentData()
        if not section_id:
            raise ValueError("Select a target music library section first.")

        profile = self.server_sync_profile_combo.currentData() if hasattr(self, "server_sync_profile_combo") else None
        if not isinstance(profile, dict):
            raise ValueError("Select a source server profile first.")

        source_playlist_title = self.server_sync_playlist_combo.currentData() if hasattr(self, "server_sync_playlist_combo") else None
        if not source_playlist_title:
            raise ValueError("Select a source playlist to transfer.")

        transfer_mode = "overwrite" if (hasattr(self, "server_sync_overwrite_cb") and self.server_sync_overwrite_cb.isChecked()) else "create_copy"
        sync_policy = self.server_sync_policy_combo.currentData() if hasattr(self, "server_sync_policy_combo") else self.server_sync_policy
        sync_policy = str(sync_policy or "keep_extras").strip().lower()
        filter_settings = {
            "enabled": bool(self.enable_filters_checkbox.isChecked()) if hasattr(self, "enable_filters_checkbox") else False,
            "avoid_live": bool(self.filter_live_checkbox.isChecked()) if hasattr(self, "filter_live_checkbox") else False,
            "avoid_compilation": bool(self.filter_compilation_checkbox.isChecked()) if hasattr(self, "filter_compilation_checkbox") else False,
            "deprioritize_remaster": bool(self.filter_remaster_checkbox.isChecked()) if hasattr(self, "filter_remaster_checkbox") else False,
            "deprioritize_deluxe": bool(self.filter_deluxe_checkbox.isChecked()) if hasattr(self, "filter_deluxe_checkbox") else False,
        }
        return {
            "profile": profile,
            "source_playlist_title": source_playlist_title,
            "section_id": section_id,
            "transfer_mode": transfer_mode,
            "sync_policy": sync_policy,
            "filter_settings": filter_settings,
        }

    def _start_server_playlist_transfer(self, dry_run=False):
        request = self._build_server_transfer_request()
        source_playlist_title = request["source_playlist_title"]
        sync_policy = request["sync_policy"]
        operation_label = "Dry run preview" if dry_run else "Transfer"
        self.show_loading("Plex Server Sync", f"{operation_label} for '{source_playlist_title}'...")

        if hasattr(self, "server_sync_transfer_btn"):
            self.server_sync_transfer_btn.setEnabled(False)
        if hasattr(self, "server_sync_preview_btn"):
            self.server_sync_preview_btn.setEnabled(False)

        self.server_playlist_transfer_thread = PlexServerPlaylistTransferThread(
            source_profile=request["profile"],
            source_playlist_title=source_playlist_title,
            target_server=self.plex_server,
            target_section_id=request["section_id"],
            target_mode=request["transfer_mode"],
            sync_policy=sync_policy,
            target_name_override=source_playlist_title,
            filter_settings=request["filter_settings"],
            dry_run=dry_run,
            parent=self,
        )
        self.server_playlist_transfer_thread.progress_update.connect(self.on_server_playlist_transfer_progress)
        self.server_playlist_transfer_thread.transfer_complete.connect(self.on_server_playlist_transfer_complete)
        self.server_playlist_transfer_thread.error.connect(self.on_server_playlist_transfer_error)
        self.server_playlist_transfer_thread.finished.connect(self._on_server_playlist_transfer_finished)
        self.server_playlist_transfer_thread.start()

    def transfer_playlist_from_source_server(self):
        try:
            self._start_server_playlist_transfer(dry_run=False)
        except Exception as e:
            QMessageBox.warning(self, "Plex Server Sync", str(e))

    def preview_playlist_transfer_from_source_server(self):
        try:
            self._start_server_playlist_transfer(dry_run=True)
        except Exception as e:
            QMessageBox.warning(self, "Plex Server Sync", str(e))

    def _on_server_playlist_transfer_finished(self):
        if hasattr(self, "server_sync_transfer_btn"):
            self.server_sync_transfer_btn.setEnabled(True)
        if hasattr(self, "server_sync_preview_btn"):
            self.server_sync_preview_btn.setEnabled(True)
        self.on_server_profile_changed()

    def on_server_playlist_transfer_progress(self, message, percentage):
        if self.loading_dialog:
            self.loading_dialog.update_progress(message, percentage)
        if hasattr(self, "server_sync_status"):
            self.server_sync_status.setText(message)
        self.statusBar().showMessage(message)

    def _server_sync_policy_label(self, policy_value):
        mapping = {
            "mirror": "Mirror source (exact)",
            "add_only": "Add missing only",
            "keep_extras": "Source first, keep target extras",
        }
        key = str(policy_value or "keep_extras").strip().lower()
        return mapping.get(key, key)

    def on_server_playlist_transfer_complete(self, result):
        self.hide_loading()
        if bool(result.get("dry_run", False)):
            source_name = result.get("source_playlist", "Source Playlist")
            target_name = result.get("target_playlist", "Target Playlist")
            matched = int(result.get("matched_tracks", 0))
            final_count = int(result.get("final_tracks", matched))
            total = int(result.get("total_tracks", 0))
            missing = int(result.get("missing_tracks", 0))
            will_add = int(result.get("will_add", 0))
            will_remove = int(result.get("will_remove", 0))
            will_reorder = bool(result.get("will_reorder", False))
            target_exists = bool(result.get("target_exists", False))
            existing_count = int(result.get("existing_count", 0))
            mode = str(result.get("mode", "overwrite"))
            sync_policy = str(result.get("sync_policy", "keep_extras"))
            sync_policy_label = self._server_sync_policy_label(sync_policy)

            summary = (
                f"Dry Run for '{source_name}' -> '{target_name}'\n\n"
                f"Target exists: {'Yes' if target_exists else 'No'}"
            )
            if target_exists:
                summary += f" ({existing_count} current tracks)"
            summary += (
                f"\nMode: {mode}\n"
                f"Policy: {sync_policy_label}\n"
                f"Matched: {matched}/{total}\n"
                f"Final target tracks: {final_count}\n"
                f"Missing: {missing}\n"
                f"Will add: {will_add}\n"
                f"Will remove: {will_remove}\n"
                f"Will reorder: {'Yes' if will_reorder else 'No'}"
            )

            add_samples = result.get("add_samples", []) or []
            remove_samples = result.get("remove_samples", []) or []
            missing_samples = result.get("missing_samples", []) or []
            detail_lines = []
            if add_samples:
                detail_lines.append("\nAdd samples:")
                detail_lines.extend([f"- {item}" for item in add_samples[:8]])
            if remove_samples:
                detail_lines.append("\nRemove samples:")
                detail_lines.extend([f"- {item}" for item in remove_samples[:8]])
            if missing_samples:
                detail_lines.append("\nMissing samples:")
                detail_lines.extend([f"- {item}" for item in missing_samples[:8]])
            if detail_lines:
                summary += "\n" + "\n".join(detail_lines)

            QMessageBox.information(self, "Plex Server Sync Dry Run", summary)
            self.statusBar().showMessage(f"Dry run complete for '{source_name}'.", 5000)
            if hasattr(self, "server_sync_status"):
                self.server_sync_status.setText(
                    f"Dry run complete: {matched}/{total} matched, {missing} missing, add {will_add}, remove {will_remove}."
                )
            return

        matched = int(result.get("matched_tracks", 0))
        final_count = int(result.get("final_tracks", matched))
        total = int(result.get("total_tracks", 0))
        missing = int(result.get("missing_tracks", 0))
        source_name = result.get("source_playlist", "Source Playlist")
        target_name = result.get("target_playlist", "Target Playlist")
        sync_policy = str(result.get("sync_policy", "keep_extras"))
        sync_policy_label = self._server_sync_policy_label(sync_policy)
        summary = (
            f"Transferred '{source_name}' to '{target_name}'.\n\n"
            f"Matched: {matched}/{total}\n"
            f"Final target tracks: {final_count}\n"
            f"Policy: {sync_policy_label}\n"
            f"Missing: {missing}"
        )
        missing_samples = result.get("missing_samples", []) or []
        if missing_samples:
            summary += "\n\nMissing samples:\n" + "\n".join(missing_samples[:8])

        QMessageBox.information(self, "Plex Server Sync Complete", summary)
        self.statusBar().showMessage(f"Transferred '{source_name}' to '{target_name}' ({matched}/{total} matched).", 5000)
        if hasattr(self, "server_sync_status"):
            self.server_sync_status.setText(
                f"Transfer complete: '{source_name}' -> '{target_name}' ({matched}/{total} matched)."
            )
        self.fetch_playlists()

    def on_server_playlist_transfer_error(self, error_message):
        self.hide_loading()
        logging.error(f"Plex server playlist transfer failed: {error_message}")
        QMessageBox.warning(self, "Plex Server Sync Error", f"Failed to transfer playlist:\n{error_message}")
        if hasattr(self, "server_sync_status"):
            self.server_sync_status.setText("Transfer failed. Check server profiles, tokens, and library selection.")

    def setup_metadata_service(self):
        """Initialize metadata service from config defaults/runtime values."""
        try:
            metadata_cfg = self.metadata_settings or APP_CONFIG_DEFAULTS.get("metadata", {})
            self.metadata_service = MetadataFixerService(
                provider=MusicBrainzProvider(
                    user_agent=metadata_cfg.get("user_agent", APP_CONFIG_DEFAULTS["metadata"]["user_agent"]),
                    rate_limit_rps=float(metadata_cfg.get("rate_limit_rps", 1.0)),
                    cache_ttl_hours=int(metadata_cfg.get("cache_ttl_hours", 168)),
                ),
                review_threshold=int(metadata_cfg.get("review_threshold", 80)),
            )
        except Exception as e:
            logging.error(f"Failed to initialize metadata service: {e}")
            self.metadata_service = None

    def get_tracks_for_metadata_scope(self, scope, selected_playlists):
        """Collect tracks for metadata fixer scope."""
        if not self.plex_server:
            return []
        if scope == "playlists":
            tracks = []
            for playlist in selected_playlists:
                try:
                    tracks.extend(list(playlist.items()))
                except Exception as e:
                    logging.warning(f"Failed to load playlist items for metadata scan: {e}")
            return tracks

        section_id = self.section_combo.currentData()
        if not section_id:
            return []
        try:
            section = self.plex_server.library.sectionByID(section_id)
            return list(section.searchTracks())
        except Exception as e:
            logging.error(f"Failed to load library tracks for metadata scan: {e}")
            return []

    def open_metadata_fixer(self):
        """Open metadata fixer dialog if feature is enabled."""
        self.apply_settings_from_controls(save=False, show_message=False)
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return
        if not self.feature_flags.get("metadata_fixer", False):
            QMessageBox.warning(
                self,
                "Feature Disabled",
                "File Metadata Fixer is currently disabled.\n\nEnable it in Settings > Runtime Features and click Apply.",
            )
            return
        if not self.metadata_service:
            self.setup_metadata_service()
        dialog = MetadataFixerDialog(
            metadata_service=self.metadata_service,
            get_tracks_for_scope=self.get_tracks_for_metadata_scope,
            playlists=self.playlists or [],
            parent=self,
        )
        dialog.exec()

    def open_portable_backup_dialog(self):
        """Open portable backup dialog for playlist + audio export."""
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return
        dialog = PortableBackupDialog(self.plex_server, self)
        dialog.exec()

    def refresh_feature_dependent_ui(self):
        metadata_enabled = bool(self.feature_flags.get("metadata_fixer", False))
        if hasattr(self, "metadata_fixer_btn"):
            self.metadata_fixer_btn.setEnabled(metadata_enabled)
            if metadata_enabled:
                self.metadata_fixer_btn.setToolTip("Scan with MusicBrainz and write selected metadata fixes to local audio file tags")
            else:
                self.metadata_fixer_btn.setToolTip("Disabled. Enable in Settings > Runtime Features.")
        if hasattr(self, "header_connection_chip"):
            if self.plex_server:
                self.header_connection_chip.setText("Connected")
                self.header_connection_chip.setObjectName("headerChipOk")
            else:
                self.header_connection_chip.setText("Offline")
                self.header_connection_chip.setObjectName("headerChipWarn")
            self.header_connection_chip.style().unpolish(self.header_connection_chip)
            self.header_connection_chip.style().polish(self.header_connection_chip)
        if hasattr(self, "header_metadata_chip"):
            self.header_metadata_chip.setText("Metadata: On" if metadata_enabled else "Metadata: Off")
            self.header_metadata_chip.setObjectName("headerChipAccent" if metadata_enabled else "headerChipNeutral")
            self.header_metadata_chip.style().unpolish(self.header_metadata_chip)
            self.header_metadata_chip.style().polish(self.header_metadata_chip)
        if hasattr(self, "header_user_chip"):
            user_label = self.current_user_name if self.current_user_name else "Guest"
            self.header_user_chip.setText(f"User: {user_label}")
        if hasattr(self, "dashboard_status_label"):
            connection_state = "Connected" if self.plex_server else "Not connected"
            fixer_state = "Enabled" if metadata_enabled else "Disabled"
            self.dashboard_status_label.setText(f"Connection: {connection_state}\nFile Metadata Fixer: {fixer_state}")
        if hasattr(self, "server_sync_add_current_btn"):
            self.server_sync_add_current_btn.setEnabled(bool(self.plex_server))
        if hasattr(self, "server_sync_add_job_btn"):
            profile = self.server_sync_profile_combo.currentData() if hasattr(self, "server_sync_profile_combo") else None
            self.server_sync_add_job_btn.setEnabled(bool(self.plex_server) and isinstance(profile, dict) and bool(getattr(self, "source_server_playlists", [])))
        if hasattr(self, "server_sync_run_due_btn"):
            self.server_sync_run_due_btn.setEnabled(bool(getattr(self, "server_sync_jobs", [])))
        if hasattr(self, "server_sync_preview_btn"):
            has_source_playlist = bool(getattr(self, "source_server_playlists", []))
            self.server_sync_preview_btn.setEnabled(bool(self.plex_server) and has_source_playlist)
        if hasattr(self, "server_sync_transfer_btn"):
            has_source_playlist = bool(getattr(self, "source_server_playlists", []))
            self.server_sync_transfer_btn.setEnabled(bool(self.plex_server) and has_source_playlist)
        self.update_dashboard_metrics()
        self.refresh_smart_match_cache_status()

    def update_dashboard_metrics(self):
        if hasattr(self, "metric_playlists"):
            self.metric_playlists.setText(f"Playlists\n{len(self.playlists or [])}")
        if hasattr(self, "metric_sync_jobs"):
            sync_rows = self.sync_configs_table.rowCount() if hasattr(self, "sync_configs_table") else 0
            self.metric_sync_jobs.setText(f"Sync Jobs\n{sync_rows}")
        if hasattr(self, "metric_user"):
            self.metric_user.setText(f"Active User\n{self.current_user_name if self.current_user_name else 'Guest'}")

    def apply_settings_from_controls(self, save=True, show_message=False):
        if self._suspend_settings_apply:
            return

        self.feature_flags = {
            "metadata_fixer": self.metadata_fixer_feature_cb.isChecked() if hasattr(self, "metadata_fixer_feature_cb") else self.feature_flags.get("metadata_fixer", False),
            "ui_refresh_v2": self.ui_refresh_feature_cb.isChecked() if hasattr(self, "ui_refresh_feature_cb") else self.feature_flags.get("ui_refresh_v2", False),
            "auto_fetch_playlists_on_startup": self.auto_fetch_on_startup_cb.isChecked() if hasattr(self, "auto_fetch_on_startup_cb") else self.feature_flags.get("auto_fetch_playlists_on_startup", False),
        }
        self.smart_match_settings = {
            "persist_cache": bool(self.smart_match_settings.get("persist_cache", True)),
            "preload_on_connect": bool(self.smart_match_settings.get("preload_on_connect", True)),
            "cache_db": str(self.smart_match_settings.get("cache_db", APP_CONFIG_DEFAULTS["smart_match"]["cache_db"]) or APP_CONFIG_DEFAULTS["smart_match"]["cache_db"]).strip(),
        }
        _set_smart_match_runtime_settings(self.smart_match_settings)

        if hasattr(self, "metadata_user_agent_input"):
            self.metadata_settings["user_agent"] = self.metadata_user_agent_input.text().strip() or APP_CONFIG_DEFAULTS["metadata"]["user_agent"]
        if hasattr(self, "metadata_rate_spin"):
            self.metadata_settings["rate_limit_rps"] = float(self.metadata_rate_spin.value())
        if hasattr(self, "metadata_ttl_spin"):
            self.metadata_settings["cache_ttl_hours"] = int(self.metadata_ttl_spin.value())
        if hasattr(self, "metadata_auto_apply_spin"):
            self.metadata_settings["auto_apply_threshold"] = int(self.metadata_auto_apply_spin.value())
        if hasattr(self, "metadata_review_spin"):
            self.metadata_settings["review_threshold"] = int(self.metadata_review_spin.value())

        self.setup_metadata_service()
        if not self.plex_server:
            self._startup_auto_fetch_pending = bool(self.feature_flags.get("auto_fetch_playlists_on_startup", False))
        self.refresh_feature_dependent_ui()
        self.refresh_smart_match_cache_status()
        if save:
            self.save_config()
        if show_message:
            self.statusBar().showMessage("Settings applied", 2500)

    def on_feature_flags_changed(self):
        self.apply_settings_from_controls(save=True, show_message=False)

    def apply_settings_clicked(self):
        self.apply_settings_from_controls(save=True, show_message=True)

    def create_settings_page(self):
        """Create settings page with global configuration options"""
        page = QWidget()
        layout = QVBoxLayout(page)
        self.add_unified_page_header(layout, "Settings", "Adjust feature flags, metadata behavior, and matching preferences", "settings")

        # Feature flags
        feature_group = QGroupBox("🧪 Runtime Features")
        feature_layout = QFormLayout(feature_group)
        self.metadata_fixer_feature_cb = QCheckBox("Enable File Metadata Fixer (MusicBrainz)")
        self.metadata_fixer_feature_cb.setChecked(self.feature_flags.get("metadata_fixer", False))
        self.ui_refresh_feature_cb = QCheckBox("Enable UI Refresh v2")
        self.ui_refresh_feature_cb.setChecked(self.feature_flags.get("ui_refresh_v2", False))
        self.auto_fetch_on_startup_cb = QCheckBox("Auto-fetch playlists on startup")
        self.auto_fetch_on_startup_cb.setChecked(self.feature_flags.get("auto_fetch_playlists_on_startup", False))
        feature_layout.addRow("File Metadata Fixer", self.metadata_fixer_feature_cb)
        feature_layout.addRow("UI Refresh v2", self.ui_refresh_feature_cb)
        feature_layout.addRow("Auto-fetch Playlists", self.auto_fetch_on_startup_cb)
        self.metadata_fixer_feature_cb.stateChanged.connect(self.on_feature_flags_changed)
        self.ui_refresh_feature_cb.stateChanged.connect(self.on_feature_flags_changed)
        self.auto_fetch_on_startup_cb.stateChanged.connect(self.on_feature_flags_changed)
        layout.addWidget(feature_group)

        metadata_group = QGroupBox("🧬 File Metadata Fixer Settings")
        metadata_layout = QFormLayout(metadata_group)
        self.metadata_user_agent_input = QLineEdit(self.metadata_settings.get("user_agent", APP_CONFIG_DEFAULTS["metadata"]["user_agent"]))
        self.metadata_rate_spin = QDoubleSpinBox()
        self.metadata_rate_spin.setRange(0.1, 10.0)
        self.metadata_rate_spin.setSingleStep(0.1)
        self.metadata_rate_spin.setValue(float(self.metadata_settings.get("rate_limit_rps", 1.0)))
        self.metadata_ttl_spin = QSpinBox()
        self.metadata_ttl_spin.setRange(1, 720)
        self.metadata_ttl_spin.setValue(int(self.metadata_settings.get("cache_ttl_hours", 168)))
        self.metadata_auto_apply_spin = QSpinBox()
        self.metadata_auto_apply_spin.setRange(50, 100)
        self.metadata_auto_apply_spin.setValue(int(self.metadata_settings.get("auto_apply_threshold", 95)))
        self.metadata_review_spin = QSpinBox()
        self.metadata_review_spin.setRange(1, 100)
        self.metadata_review_spin.setValue(int(self.metadata_settings.get("review_threshold", 80)))
        metadata_layout.addRow("User Agent", self.metadata_user_agent_input)
        metadata_layout.addRow("Rate Limit (req/sec)", self.metadata_rate_spin)
        metadata_layout.addRow("Cache TTL (hours)", self.metadata_ttl_spin)
        metadata_layout.addRow("Auto-Apply Threshold", self.metadata_auto_apply_spin)
        metadata_layout.addRow("Review Threshold", self.metadata_review_spin)
        layout.addWidget(metadata_group)

        # Track Matching Filters Section
        filters_group = QGroupBox("🎯 Track Matching Filters")
        filters_group.setToolTip("These filters apply to all playlist imports (streaming services, M3U files, etc.)")
        filters_layout = QVBoxLayout()

        # Enable filters checkbox
        self.enable_filters_checkbox = QCheckBox("Enable smart filtering for better track matching")
        self.enable_filters_checkbox.setChecked(True)
        self.enable_filters_checkbox.setStyleSheet("""
            QCheckBox {
                font-weight: bold;
                color: #2196F3;
                padding: 8px;
                font-size: 14px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #2196F3;
                background-color: transparent;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #2196F3;
                background-color: #2196F3;
                border-radius: 3px;
            }
        """)
        filters_layout.addWidget(self.enable_filters_checkbox)

        # Filter options with better styling
        filter_options_layout = QVBoxLayout()
        filter_options_layout.setContentsMargins(20, 10, 0, 0)  # Indent

        self.filter_live_checkbox = QCheckBox("🎤 Avoid 'Live' versions (prioritize studio recordings)")
        self.filter_live_checkbox.setChecked(True)
        self.filter_live_checkbox.setToolTip("Reduces priority of albums containing 'live', 'concert', or 'tour'")

        self.filter_compilation_checkbox = QCheckBox("📀 Avoid 'Best Of' and 'Greatest Hits' compilations")
        self.filter_compilation_checkbox.setChecked(True)
        self.filter_compilation_checkbox.setToolTip("Reduces priority of albums containing 'best of', 'greatest hits', 'collection', or 'anthology'")

        self.filter_remaster_checkbox = QCheckBox("🔄 Deprioritize 'Remaster' and 'Remastered' versions")
        self.filter_remaster_checkbox.setChecked(False)  # Some people prefer remasters
        self.filter_remaster_checkbox.setToolTip("Reduces priority of albums containing 'remaster' or 'remastered'")

        self.filter_deluxe_checkbox = QCheckBox("💿 Deprioritize 'Deluxe', 'Special', and 'Extended' editions")
        self.filter_deluxe_checkbox.setChecked(False)
        self.filter_deluxe_checkbox.setToolTip("Reduces priority of albums containing 'deluxe', 'special', 'extended', 'expanded', or 'anniversary'")

        # Style the filter checkboxes
        filter_style = """
            QCheckBox {
                color: #ffffff;
                padding: 6px;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #4CAF50;
                background-color: transparent;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #4CAF50;
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """

        for checkbox in [self.filter_live_checkbox, self.filter_compilation_checkbox,
                        self.filter_remaster_checkbox, self.filter_deluxe_checkbox]:
            checkbox.setStyleSheet(filter_style)

        filter_options_layout.addWidget(self.filter_live_checkbox)
        filter_options_layout.addWidget(self.filter_compilation_checkbox)
        filter_options_layout.addWidget(self.filter_remaster_checkbox)
        filter_options_layout.addWidget(self.filter_deluxe_checkbox)

        filters_layout.addLayout(filter_options_layout)

        # Info section
        info_label = QLabel("ℹ️ These filters help prioritize the correct versions of tracks when multiple versions exist in your Plex library (e.g., studio vs live, original vs compilation).")
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #dceaff; font-style: italic; padding: 10px; background-color: #1c2a40; border: 1px solid #3f587a; border-radius: 6px; margin: 10px 0;")
        filters_layout.addWidget(info_label)

        filters_group.setLayout(filters_layout)
        layout.addWidget(filters_group)

        # Path Mappings Section
        path_mappings_group = QGroupBox("🗺️ Path Mappings for M3U Playlist Uploads")
        path_mappings_group.setToolTip("Configure path transformations for cross-platform playlist imports (Windows ↔ Linux/Mac/NAS)")
        path_mappings_layout = QVBoxLayout()

        # Info section
        path_info = QLabel(
            "📁 Path mappings help when your M3U playlists contain paths that don't match your Plex server's paths.\n"
            "Common scenarios: Windows PC → Linux/Mac/Synology NAS, Local drives → Network shares\n\n"
            "Example: Replace 'C:\\Music\\' with '/volume1/music/' for Synology NAS"
        )
        path_info.setWordWrap(True)
        path_info.setStyleSheet("color: #dceaff; padding: 10px; background-color: #1c2a40; border: 1px solid #3f587a; border-radius: 6px; margin: 5px 0;")
        path_mappings_layout.addWidget(path_info)

        # Detect Plex paths button
        detect_btn_layout = QHBoxLayout()
        self.detect_plex_paths_btn = ModernButton('🔍 Auto-Detect Plex Library Paths')
        self.detect_plex_paths_btn.clicked.connect(self.detect_and_show_plex_paths)
        detect_btn_layout.addWidget(self.detect_plex_paths_btn)
        detect_btn_layout.addStretch()
        path_mappings_layout.addLayout(detect_btn_layout)

        # Path mappings list
        self.path_mappings_list = QListWidget()
        self.path_mappings_list.setMaximumHeight(200)
        path_mappings_layout.addWidget(QLabel("Configured Path Mappings:"))
        path_mappings_layout.addWidget(self.path_mappings_list)

        # Add new mapping controls
        add_mapping_layout = QHBoxLayout()
        add_mapping_layout.setContentsMargins(0, 0, 0, 0)
        add_mapping_layout.setSpacing(6)

        self.source_path_input = ModernLineEdit()
        self.source_path_input.setMinimumHeight(34)
        self.source_path_input.setPlaceholderText("Source path (e.g., C:\\Music or //NAS/Music)")

        self.target_path_input = ModernLineEdit()
        self.target_path_input.setMinimumHeight(34)
        self.target_path_input.setPlaceholderText("Target path (e.g., /volume1/music or /mnt/music)")

        add_mapping_btn = ModernButton('➕ Add Mapping')
        add_mapping_btn.setFixedHeight(34)
        add_mapping_btn.clicked.connect(self.add_path_mapping)

        remove_mapping_btn = ModernButton('➖ Remove Selected')
        remove_mapping_btn.setFixedHeight(34)
        remove_mapping_btn.clicked.connect(self.remove_path_mapping)

        add_mapping_layout.addWidget(QLabel("Source:"))
        add_mapping_layout.addWidget(self.source_path_input)
        add_mapping_layout.addWidget(QLabel("→ Target:"))
        add_mapping_layout.addWidget(self.target_path_input)
        add_mapping_layout.addWidget(add_mapping_btn)
        add_mapping_layout.setAlignment(add_mapping_btn, Qt.AlignmentFlag.AlignVCenter)
        add_mapping_layout.addWidget(remove_mapping_btn)
        add_mapping_layout.setAlignment(remove_mapping_btn, Qt.AlignmentFlag.AlignVCenter)

        path_mappings_layout.addLayout(add_mapping_layout)

        # Common presets
        presets_label = QLabel("Quick Presets:")
        presets_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        path_mappings_layout.addWidget(presets_label)

        presets_layout = QHBoxLayout()

        win_to_synology_btn = ModernButton('Windows → Synology')
        win_to_synology_btn.clicked.connect(lambda: self.apply_path_preset('win_synology'))
        win_to_synology_btn.setToolTip("C:\\ → /volume1/")

        win_to_linux_btn = ModernButton('Windows → Linux/Mac')
        win_to_linux_btn.clicked.connect(lambda: self.apply_path_preset('win_linux'))
        win_to_linux_btn.setToolTip("C:\\ → /mnt/")

        unc_to_synology_btn = ModernButton('UNC → Synology')
        unc_to_synology_btn.clicked.connect(lambda: self.apply_path_preset('unc_synology'))
        unc_to_synology_btn.setToolTip("\\\\NAS\\ → /volume1/")

        presets_layout.addWidget(win_to_synology_btn)
        presets_layout.addWidget(win_to_linux_btn)
        presets_layout.addWidget(unc_to_synology_btn)
        presets_layout.addStretch()

        path_mappings_layout.addLayout(presets_layout)

        path_mappings_group.setLayout(path_mappings_layout)
        layout.addWidget(path_mappings_group)

        # Refresh the path mappings list
        self.refresh_path_mappings_list()

        # M3U Matching Mode Section
        matching_mode_group = QGroupBox("🎵 M3U Playlist Matching Mode")
        matching_mode_group.setToolTip("Choose how M3U playlists match tracks in your Plex library")
        matching_mode_layout = QVBoxLayout()

        # Info section
        matching_info = QLabel(
            "Choose how to match tracks from M3U playlists:\n\n"
            "🎯 <b>Smart Matching (Recommended for NAS/Remote)</b>: Uses track title and artist metadata. Perfect for "
            "remote servers, NAS setups, or when file paths don't match. Works across different mount points.\n\n"
            "📁 <b>Path Matching</b>: Uses exact file paths from M3U. Best for local servers where M3U paths "
            "match exactly with Plex library paths. Fastest but requires identical paths."
        )
        matching_info.setWordWrap(True)
        matching_info.setTextFormat(Qt.RichText)
        matching_info.setStyleSheet("color: #dceaff; padding: 10px; background-color: #1c2a40; border: 1px solid #3f587a; border-radius: 6px; margin: 5px 0;")
        matching_mode_layout.addWidget(matching_info)

        # Radio buttons for matching mode
        self.m3u_smart_matching_radio = QCheckBox("🎯 Smart Matching (metadata-based)")
        self.m3u_smart_matching_radio.setChecked(False)  # Default to path matching for backward compatibility
        self.m3u_smart_matching_radio.setToolTip("Match tracks by title and artist using Plex search API. Ideal for NAS/remote servers.")
        self.m3u_smart_matching_radio.stateChanged.connect(self.on_m3u_matching_mode_changed)

        self.m3u_path_matching_radio = QCheckBox("📁 Path Matching (file path-based)")
        self.m3u_path_matching_radio.setChecked(True)  # Default
        self.m3u_path_matching_radio.setToolTip("Match tracks by exact file paths. Requires M3U paths to match Plex library paths.")
        self.m3u_path_matching_radio.stateChanged.connect(self.on_m3u_matching_mode_changed)

        # Style the radio buttons
        radio_style = """
            QCheckBox {
                color: #ffffff;
                padding: 8px;
                font-size: 13px;
                font-weight: bold;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #2196F3;
                background-color: transparent;
                border-radius: 9px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #2196F3;
                background-color: #2196F3;
                border-radius: 9px;
            }
        """

        self.m3u_smart_matching_radio.setStyleSheet(radio_style)
        self.m3u_path_matching_radio.setStyleSheet(radio_style)

        matching_mode_layout.addWidget(self.m3u_smart_matching_radio)
        matching_mode_layout.addWidget(self.m3u_path_matching_radio)

        # Warning for path matching
        path_warning = QLabel(
            "⚠️ <b>Note</b>: If you experience issues with tracks not being found (especially with NAS/remote servers), "
            "switch to Smart Matching mode."
        )
        path_warning.setWordWrap(True)
        path_warning.setTextFormat(Qt.RichText)
        path_warning.setStyleSheet("color: #ffc56a; font-style: italic; padding: 10px; background-color: #1a2435; border: 1px solid #7a6436; border-radius: 6px; margin: 5px 0;")
        matching_mode_layout.addWidget(path_warning)

        smart_match_cache_group = QGroupBox("Smart Match Cache")
        smart_match_cache_layout = QVBoxLayout(smart_match_cache_group)

        self.smart_match_cache_status_label = QLabel("Status: No library selected")
        self.smart_match_cache_status_label.setWordWrap(True)
        self.smart_match_cache_status_label.setStyleSheet("color: #dceaff; padding: 6px 0;")
        smart_match_cache_layout.addWidget(self.smart_match_cache_status_label)

        self.smart_match_cache_detail_label = QLabel("Built: n/a • Indexed tracks: 0")
        self.smart_match_cache_detail_label.setStyleSheet("color: #9cb2d2; font-size: 12px;")
        smart_match_cache_layout.addWidget(self.smart_match_cache_detail_label)

        smart_match_cache_buttons = QHBoxLayout()
        self.smart_match_rebuild_btn = ModernButton("Rebuild Smart Match Index")
        self.smart_match_rebuild_btn.clicked.connect(lambda: self.start_smart_match_preload(force_rebuild=True, show_dialog=True))
        smart_match_cache_buttons.addWidget(self.smart_match_rebuild_btn)
        self.smart_match_clear_btn = ModernButton("Clear Smart Match Cache")
        self.smart_match_clear_btn.clicked.connect(self.clear_smart_match_cache)
        smart_match_cache_buttons.addWidget(self.smart_match_clear_btn)
        smart_match_cache_buttons.addStretch()
        smart_match_cache_layout.addLayout(smart_match_cache_buttons)

        matching_mode_layout.addWidget(smart_match_cache_group)

        matching_mode_group.setLayout(matching_mode_layout)
        layout.addWidget(matching_mode_group)

        settings_actions_layout = QHBoxLayout()
        settings_actions_layout.addStretch()
        self.apply_settings_btn = ModernButton("Apply Settings")
        self.apply_settings_btn.clicked.connect(self.apply_settings_clicked)
        settings_actions_layout.addWidget(self.apply_settings_btn)
        layout.addLayout(settings_actions_layout)

        layout.addStretch()
        self._add_page_to_stack(page)

    def create_local_tracks_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.add_unified_page_header(layout, "Local Tracks", "Scan folders and build M3U or Plex playlists from local files", "local_tracks")
    
        # Folder selection section
        folder_group = QGroupBox("Select Music Folder")
        folder_layout = QVBoxLayout()
    
        folder_select_layout = QHBoxLayout()
        folder_select_layout.setContentsMargins(0, 0, 0, 0)
        folder_select_layout.setSpacing(6)
        self.folder_path_input = ModernLineEdit()
        self.folder_path_input.setMinimumHeight(34)
        self.folder_path_input.setPlaceholderText("Select a folder containing music tracks")
        folder_select_layout.addWidget(self.folder_path_input)
    
        browse_folder_button = ModernButton('Browse')
        browse_folder_button.setFixedHeight(34)
        browse_folder_button.clicked.connect(self.browse_music_folder)
        folder_select_layout.addWidget(browse_folder_button)
        folder_select_layout.setAlignment(browse_folder_button, Qt.AlignmentFlag.AlignVCenter)
        folder_layout.addLayout(folder_select_layout)
    
        # Option to include subfolders
        self.include_subfolders_checkbox = QCheckBox("Include subfolders")
        self.include_subfolders_checkbox.setChecked(True)
        folder_layout.addWidget(self.include_subfolders_checkbox)
    
        folder_group.setLayout(folder_layout)
        layout.addWidget(folder_group)
    
        # Track list section
        track_group = QGroupBox("Available Tracks")
        track_layout = QVBoxLayout()
    
        self.track_listwidget = QListWidget()
        self.track_listwidget.setSelectionMode(QListWidget.ExtendedSelection)
        track_layout.addWidget(self.track_listwidget)
    
        # Controls for track list
        track_controls_layout = QHBoxLayout()
        self.scan_folder_button = ModernButton('Scan Folder')
        self.scan_folder_button.clicked.connect(self.scan_music_folder)
        track_controls_layout.addWidget(self.scan_folder_button)
    
        self.select_all_tracks_checkbox = QCheckBox("Select All")
        self.select_all_tracks_checkbox.stateChanged.connect(self.select_all_tracks)
        track_controls_layout.addWidget(self.select_all_tracks_checkbox)
        track_layout.addLayout(track_controls_layout)
    
        track_group.setLayout(track_layout)
        layout.addWidget(track_group)
    
        # Playlist creation section
        playlist_group = QGroupBox("Create Playlist")
        playlist_layout = QVBoxLayout()
    
        # Playlist name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Playlist Name:"))
        self.local_playlist_name_input = ModernLineEdit()
        self.local_playlist_name_input.setPlaceholderText("Enter a name for your playlist")
        name_layout.addWidget(self.local_playlist_name_input)
        playlist_layout.addLayout(name_layout)
    
        # Action buttons
        buttons_layout = QHBoxLayout()
        
        self.create_m3u_button = ModernButton('Create M3U File')
        self.create_m3u_button.clicked.connect(self.create_m3u_from_selection)
        buttons_layout.addWidget(self.create_m3u_button)
        
        self.add_to_plex_button = ModernButton('Add to Plex')
        self.add_to_plex_button.clicked.connect(self.add_tracks_to_plex)
        buttons_layout.addWidget(self.add_to_plex_button)
        
        playlist_layout.addLayout(buttons_layout)
        playlist_group.setLayout(playlist_layout)
        layout.addWidget(playlist_group)
    
        self._add_page_to_stack(page)

    def spotify_login(self):
        """Handle Spotify login with improved system"""
        dialog = SpotifyLoginDialog(self)
        if dialog.exec() == QDialog.Accepted:
            if dialog.login_successful and dialog.sp_dc_cookie:
                # Save cookie to global variable and config
                global SP_DC_COOKIE, SPOTIFY_LOGGED_IN
                SP_DC_COOKIE = dialog.sp_dc_cookie
                SPOTIFY_LOGGED_IN = True
                
                # Save to config file
                self.save_spotify_config(dialog.sp_dc_cookie)
                
                # Update UI
                self.update_spotify_login_status(True)
                
                # Get user info
                try:
                    self.get_spotify_user_info()
                    QMessageBox.information(self, "Login Successful", 
                                          "✅ Successfully logged in to Spotify!\n\n"
                                          "Your authentication has been saved and you can now:\n"
                                          "• Import your own playlists\n"
                                          "• Import any public Spotify playlist")
                except Exception as e:
                    logging.warning(f"Could not get user info: {e}")
                    QMessageBox.information(self, "Login Successful", 
                                          "✅ Successfully logged in to Spotify!")

    def spotify_logout(self):
        """Handle Spotify logout"""
        global SP_DC_COOKIE, SPOTIFY_LOGGED_IN, SPOTIFY_USER_INFO
        
        reply = QMessageBox.question(self, "Logout", 
                                    "Are you sure you want to logout from Spotify?",
                                    QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            SP_DC_COOKIE = ""
            SPOTIFY_LOGGED_IN = False
            SPOTIFY_USER_INFO = {}
            
            # Remove from config
            self.save_spotify_config("")
            
            # Update UI
            self.update_spotify_login_status(False)
            
            QMessageBox.information(self, "Logout Successful", "✅ Successfully logged out from Spotify.")
    
    def update_spotify_login_status(self, logged_in):
        """Update the UI based on login status"""
        if logged_in:
            user_name = SPOTIFY_USER_INFO.get('display_name', 'Spotify User')
            self.spotify_status_label.setText(f"✅ Logged in as: {user_name}")
            self.spotify_status_label.setStyleSheet("color: #1DB954; font-weight: bold;")
            self.spotify_login_btn.setEnabled(False)
            self.spotify_logout_btn.setEnabled(True)
        else:
            self.spotify_status_label.setText("❌ Not logged in")
            self.spotify_status_label.setStyleSheet("color: #888888; font-weight: bold;")
            self.spotify_login_btn.setEnabled(True)
            self.spotify_logout_btn.setEnabled(False)
    
    def get_spotify_user_info(self):
        """
        Get current user info from Spotify.
        Note: /v1/me endpoint is no longer accessible with cookie-based tokens
        due to Spotify restrictions introduced Dec 22, 2025.
        """
        global SPOTIFY_USER_INFO
        logging.info("User info retrieval from /v1/me is no longer supported due to Spotify API changes")
        # Return empty dict as user info is not critical for playlist operations
        return {}
    
    def import_multiple_spotify_playlists(self, playlists):
        """Import multiple Spotify playlists"""
        self._show_streaming_feedback("Importing Spotify playlists...")
        self.streaming_progress.setValue(0)
        self.cancel_streaming_button.setVisible(False)
        self.cancel_streaming_button.setEnabled(False)
        
        # Start import thread
        self.multi_import_thread = MultiplePlaylistImportThread(playlists, self.plex_server, 
                                                               self.section_combo.currentData(), self)
        self.multi_import_thread.progress_update.connect(self.update_multi_import_progress)
        self.multi_import_thread.playlist_imported.connect(self.on_playlist_imported)
        self.multi_import_thread.finished.connect(self.on_multi_import_finished)
        self.multi_import_thread.error.connect(self.on_multi_import_error)
        self.multi_import_thread.start()
    
    def handle_track_match_confirmation(self, source_track, plex_track, match_score):
        """Handle track match confirmation dialog on main thread"""
        try:
            dialog = TrackMatchConfirmationDialog(source_track, plex_track, match_score, self)
            
            if dialog.exec() == QDialog.Accepted:
                # Send response back to the converter thread
                if hasattr(self, 'converter_thread') and self.converter_thread:
                    self.converter_thread.set_user_response(dialog.user_choice)
            else:
                # Dialog was cancelled - treat as skip
                if hasattr(self, 'converter_thread') and self.converter_thread:
                    self.converter_thread.set_user_response("skip")
                    
        except Exception as e:
            logging.error(f"Error handling track match confirmation: {str(e)}")
            # Fallback - skip the track
            if hasattr(self, 'converter_thread') and self.converter_thread:
                self.converter_thread.set_user_response("skip")

    def update_multi_import_progress(self, current, total, playlist_name):
        """Update progress for multiple playlist import"""
        progress = int((current / total) * 100)
        self.streaming_progress.setValue(progress)
        self.update_streaming_status(f"Importing {playlist_name}... ({current}/{total})")
    
    def on_playlist_imported(self, playlist_name, track_count):
        """Handle individual playlist import completion"""
        logging.info(f"Imported playlist: {playlist_name} with {track_count} tracks")
    
    def on_multi_import_finished(self, imported_count, total_count):
        """Handle multiple import completion"""
        self._hide_streaming_feedback()
        self.statusBar().showMessage(f"Import completed: {imported_count}/{total_count} playlists")
        
        message = f"✅ Import completed!\n\nSuccessfully imported {imported_count} out of {total_count} playlists."
        if imported_count < total_count:
            message += f"\n\n{total_count - imported_count} playlists failed - check logs for details."
        
        QMessageBox.information(self, "Import Complete", message)
        self.fetch_playlists()  # Refresh playlist list
    
    def on_multi_import_error(self, error_message):
        self._hide_streaming_feedback()
        QMessageBox.critical(self, "Import Error", f"Import failed: {error_message}")
        QMessageBox.critical(self, "Import Error", f"Import failed: {error_message}")
    
    def save_spotify_config(self, sp_dc_cookie, oauth_client_id=None, oauth_client_secret=None):
        """Save Spotify configuration including cookie and OAuth credentials"""
        try:
            # Load existing config
            config = {}
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config = deep_merge(APP_CONFIG_DEFAULTS, json.load(f))

            # Update with Spotify info
            config['sp_dc_cookie'] = sp_dc_cookie
            config['spotify_logged_in'] = bool(sp_dc_cookie)
            config['spotify_user_info'] = SPOTIFY_USER_INFO

            # Save OAuth credentials if provided
            if oauth_client_id is not None:
                config['sp_app_client_id'] = oauth_client_id
            if oauth_client_secret is not None:
                config['sp_app_client_secret'] = oauth_client_secret

            # Save config
            with open(CONFIG_FILE, 'w') as f:
                json.dump(config, f, indent=4)

            # Update global variables
            global SP_DC_COOKIE, SPOTIFY_LOGGED_IN, SP_APP_CLIENT_ID, SP_APP_CLIENT_SECRET
            SP_DC_COOKIE = sp_dc_cookie
            SPOTIFY_LOGGED_IN = bool(sp_dc_cookie)
            if oauth_client_id is not None:
                SP_APP_CLIENT_ID = oauth_client_id
            if oauth_client_secret is not None:
                SP_APP_CLIENT_SECRET = oauth_client_secret

            logging.info("Spotify configuration saved successfully")
        except Exception as e:
            logging.error(f"Error saving Spotify config: {e}")
    
    def load_spotify_config(self):
        """Load Spotify configuration including OAuth credentials"""
        global SP_DC_COOKIE, SPOTIFY_LOGGED_IN, SPOTIFY_USER_INFO, SP_APP_CLIENT_ID, SP_APP_CLIENT_SECRET

        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    config = deep_merge(APP_CONFIG_DEFAULTS, json.load(f))

                SP_DC_COOKIE = config.get('sp_dc_cookie', '')
                SPOTIFY_LOGGED_IN = config.get('spotify_logged_in', False)
                SPOTIFY_USER_INFO = config.get('spotify_user_info', {})

                # Load OAuth credentials from config (if not set via environment variables)
                if not SP_APP_CLIENT_ID:
                    SP_APP_CLIENT_ID = config.get('sp_app_client_id', '')
                if not SP_APP_CLIENT_SECRET:
                    SP_APP_CLIENT_SECRET = config.get('sp_app_client_secret', '')

                # Update UI if logged in
                if SPOTIFY_LOGGED_IN and SP_DC_COOKIE:
                    self.update_spotify_login_status(True)
                else:
                    SPOTIFY_LOGGED_IN = False
                    SP_DC_COOKIE = ''
        except Exception as e:
            logging.error(f"Error loading Spotify config: {e}")        
    
    def show_playlist_context_menu(self, position):
        """Show context menu for main playlist list"""
        item = self.playlist_listwidget.itemAt(position)
        if not item:
            return
        
        # Create context menu
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2a2a2a;
                color: #ffffff;
                border: 1px solid #3a3a3a;
            }
            QMenu::item {
                padding: 8px 20px;
            }
            QMenu::item:selected {
                background-color: #4CAF50;
            }
        """)
        
        # Add actions
        sort_action = menu.addAction("🔄 Sort by Streaming Service...")
        menu.addSeparator()
        edit_action = menu.addAction("✏️ Edit Playlist")
        delete_action = menu.addAction("🗑️ Delete Playlist")
        
        # Show menu and handle selection
        action = menu.exec(self.playlist_listwidget.mapToGlobal(position))
        
        if action == sort_action:
            self.sort_playlist_by_streaming_service(item)
        elif action == edit_action:
            self.edit_playlist_item(item)
        elif action == delete_action:
            # Temporarily select the item and delete
            self.playlist_listwidget.setCurrentItem(item)
            item.setCheckState(Qt.Checked)
            self.delete_selected_playlist()

    def sort_playlist_by_streaming_service(self, playlist_item):
        """Sort playlist by streaming service order"""
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return
        
        # Get playlist object
        playlist = playlist_item.data(Qt.UserRole)
        if not playlist:
            # Fallback: find by name
            playlist_name = playlist_item.text().split(' (')[0].replace('🎵 ', '').replace('📂 ', '').replace('⏳ ', '')
            playlist = next((p for p in self.playlists if p.title == playlist_name), None)
        
        if not playlist:
            QMessageBox.warning(self, "Playlist Not Found", "Could not find the playlist.")
            return
        
        # Show URL input dialog
        url, ok = QInputDialog.getText(
            self,
            "Sort by Streaming Service",
            f"Enter Spotify, Deezer, or Tidal playlist URL to sort '{playlist.title}' by:\n\n"
            "The playlist will be reordered to match the streaming service order.",
            text=""
        )
        
        if ok and url.strip():
            self.start_playlist_sorting(playlist, url.strip())
    
    def start_playlist_sorting(self, playlist, streaming_url):
        """Start the playlist sorting process"""
        if not streaming_url:
            return
        
        # Validate URL
        if not any(service in streaming_url for service in ['spotify.com', 'deezer.com', 'tidal.com']):
            QMessageBox.warning(self, "Invalid URL", "Please enter a valid Spotify, Deezer, or Tidal playlist URL.")
            return
        
        # Show loading dialog
        self.show_loading("Sorting playlist...", "Fetching streaming service playlist...")
        
        # Start sorting thread
        self.sort_thread = PlaylistSortingThread(playlist, streaming_url, self.plex_server, self)
        self.sort_thread.progress_update.connect(self.update_sorting_progress)
        self.sort_thread.sorting_complete.connect(self.on_sorting_complete)
        self.sort_thread.error.connect(self.on_sorting_error)
        self.sort_thread.start()
    
    def update_sorting_progress(self, message, percentage):
        """Update sorting progress"""
        if self.loading_dialog:
            self.loading_dialog.update_progress(message, percentage)
    
    def on_sorting_complete(self, playlist_name, matched_count, total_count):
        """Handle sorting completion"""
        self.hide_loading()
        QMessageBox.information(self, "Sorting Complete", 
                              f"✅ Sorted '{playlist_name}' successfully!\n\n"
                              f"Matched {matched_count} out of {total_count} tracks from streaming service.")
        self.fetch_playlists()  # Refresh playlist list
    
    def on_sorting_error(self, error_message):
        """Handle sorting error"""
        self.hide_loading()
        QMessageBox.critical(self, "Sorting Error", f"Failed to sort playlist:\n{error_message}")

    def browse_music_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Music Folder")
        if folder:
            self.folder_path_input.setText(folder)
            self.scan_music_folder()
    
    def scan_music_folder(self):
        folder_path = self.folder_path_input.text()
        if not folder_path or not os.path.isdir(folder_path):
            QMessageBox.warning(self, "Invalid Folder", "Please select a valid folder.")
            return
        
        self.track_listwidget.clear()
        
        # Supported audio file extensions
        audio_extensions = ['.mp3', '.flac', '.m4a', '.wav', '.ogg', '.aac', '.wma']
        
        try:
            if self.include_subfolders_checkbox.isChecked():
                # Walk through the directory and all subdirectories
                for root, dirs, files in os.walk(folder_path):
                    for file in files:
                        file_ext = os.path.splitext(file)[1].lower()
                        if file_ext in audio_extensions:
                            full_path = os.path.join(root, file)
                            # Display relative path from the selected folder
                            relative_path = os.path.relpath(full_path, folder_path)
                            item = QListWidgetItem(relative_path)
                            item.setData(Qt.UserRole, full_path)  # Store the full path as data
                            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                            item.setCheckState(Qt.Unchecked)
                            self.track_listwidget.addItem(item)
            else:
                # Only list files in the current directory, not subdirectories
                for file in os.listdir(folder_path):
                    file_path = os.path.join(folder_path, file)
                    if os.path.isfile(file_path):
                        file_ext = os.path.splitext(file)[1].lower()
                        if file_ext in audio_extensions:
                            item = QListWidgetItem(file)
                            item.setData(Qt.UserRole, file_path)  # Store the full path as data
                            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                            item.setCheckState(Qt.Unchecked)
                            self.track_listwidget.addItem(item)

            # Keep newly scanned items in sync with the current "Select All" toggle.
            if self.select_all_tracks_checkbox.isChecked():
                self.select_all_tracks(Qt.CheckState.Checked)
            
            self.statusBar().showMessage(f"Found {self.track_listwidget.count()} audio files.")
        except Exception as e:
            logging.error(f"Error scanning music folder: {str(e)}", exc_info=True)
            QMessageBox.warning(self, "Scan Error", f"Error scanning folder: {str(e)}")
    
    def select_all_tracks(self, state):
        try:
            state_value = state.value if isinstance(state, Qt.CheckState) else int(state)
            is_checked = state_value == Qt.CheckState.Checked.value
        except Exception:
            is_checked = bool(state == Qt.Checked)

        target_state = Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked
        for index in range(self.track_listwidget.count()):
            item = self.track_listwidget.item(index)
            item.setCheckState(target_state)
    
    def get_selected_tracks(self):
        selected_tracks = []
        for index in range(self.track_listwidget.count()):
            item = self.track_listwidget.item(index)
            if item.checkState() == Qt.Checked:
                selected_tracks.append(item.data(Qt.UserRole))  # Get the full path
        return selected_tracks
    
    def create_m3u_from_selection(self):
        selected_tracks = self.get_selected_tracks()
        if not selected_tracks:
            QMessageBox.warning(self, "No Selection", "Please select tracks to include in the playlist.")
            return
        
        playlist_name = self.local_playlist_name_input.text() or "New Playlist"
        save_path, _ = QFileDialog.getSaveFileName(self, "Save M3U Playlist", 
                                                 f"{playlist_name}.m3u", 
                                                 "M3U Playlist (*.m3u)")
        if not save_path:
            return
        
        try:
            with open(save_path, 'w', encoding='utf-8') as file:
                file.write("#EXTM3U\n")
                for track_path in selected_tracks:
                    # Normalize path separators for cross-platform compatibility
                    # PRESERVE CASE - very important for UNC paths
                    normalized_path = track_path.replace('\\', '/')

                    # Log the path to help debug case issues
                    logging.debug(f"Writing track path to M3U: {normalized_path}")
                    file.write(f"{normalized_path}\n")
            
            self.statusBar().showMessage(f"Playlist saved to {save_path}")
            
            reply = QMessageBox.question(self, 'Import to Plex', 
                                       'Would you like to import this playlist to Plex?',
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                self.upload_playlist(save_path)
        except Exception as e:
            logging.error(f"Error creating M3U file: {str(e)}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to create playlist file: {str(e)}")
    
    def add_tracks_to_plex(self):
        selected_tracks = self.get_selected_tracks()
        if not selected_tracks:
            QMessageBox.warning(self, "No Selection", "Please select tracks to add to Plex.")
            return
        
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return
        
        playlist_name = self.local_playlist_name_input.text() or "New Playlist"
        
        section_id = self.section_combo.currentData()
        if not section_id:
            QMessageBox.warning(self, "No Library Selected", "Please select a music library section.")
            return
        
        try:
            # Create a temporary M3U file
            temp_dir = tempfile.gettempdir()
            temp_file = os.path.join(temp_dir, f"{playlist_name}.m3u")
            
            with open(temp_file, 'w', encoding='utf-8') as file:
                file.write("#EXTM3U\n")
                for track_path in selected_tracks:
                    # Normalize path separators for cross-platform compatibility
                    normalized_path = track_path.replace('\\', '/')
                    file.write(f"{normalized_path}\n")
            
            # Upload the playlist to Plex
            self.upload_playlist(temp_file)
            
            # Delete the temporary file
            try:
                os.remove(temp_file)
            except:
                pass
                
        except Exception as e:
            logging.error(f"Error adding tracks to Plex: {str(e)}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to add tracks to Plex: {str(e)}")    

    def create_connection_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.add_unified_page_header(layout, "Connection", "Connect to Plex, authenticate, and select your music library", "connection")

        form_layout = QVBoxLayout()
        form_layout.setSpacing(10)

        self.plex_username_input = ModernLineEdit()
        self.plex_username_input.setPlaceholderText("Plex Username")
        form_layout.addWidget(self.plex_username_input)

        self.plex_password_input = ModernLineEdit()
        self.plex_password_input.setPlaceholderText("Plex Password")
        self.plex_password_input.setEchoMode(QLineEdit.Password)
        form_layout.addWidget(self.plex_password_input)

        self.plex_2fa_input = ModernLineEdit()
        self.plex_2fa_input.setPlaceholderText("Plex 2FA Code (optional)")
        self.plex_2fa_input.setMaxLength(8)
        self.plex_2fa_input.setToolTip("Enter your current Plex 2FA code if two-factor authentication is enabled.")
        form_layout.addWidget(self.plex_2fa_input)

        self.server_ip_input = ModernLineEdit()
        self.server_ip_input.setPlaceholderText("Plex Server IP")
        form_layout.addWidget(self.server_ip_input)

        self.server_port_input = ModernLineEdit()
        self.server_port_input.setPlaceholderText("Plex Server Port")
        form_layout.addWidget(self.server_port_input)

        self.token_input = ModernLineEdit()
        self.token_input.setPlaceholderText("Plex Auth Token (optional)")
        self.token_input.setToolTip("Optional: direct token login (useful when account login is blocked by 2FA).")
        form_layout.addWidget(self.token_input)

        self.section_combo = QComboBox()
        self.section_combo.addItem("Library Section")
        self.section_combo.setCurrentIndex(0)
        self.section_combo.currentIndexChanged.connect(self.on_library_section_changed)
        form_layout.addWidget(self.section_combo)

        layout.addLayout(form_layout)

        # Button layout
        button_layout = QHBoxLayout()

        connect_button = ModernButton('Connect to Plex')
        self._set_button_icon(connect_button, "plex_connect", QStyle.StandardPixmap.SP_DialogApplyButton)
        connect_button.clicked.connect(self.connect_to_plex)
        button_layout.addWidget(connect_button)

        self.switch_user_button = ModernButton('Switch User')
        self._set_button_icon(self.switch_user_button, "users", QStyle.StandardPixmap.SP_DirHomeIcon)
        self.switch_user_button.clicked.connect(self.switch_user)
        self.switch_user_button.setToolTip("Switch between Plex users")
        button_layout.addWidget(self.switch_user_button)

        layout.addLayout(button_layout)

        # Current user label
        self.current_user_label = QLabel("Not connected")
        self.current_user_label.setStyleSheet("""
            color: #aaaaaa;
            font-style: italic;
            padding: 10px;
            font-size: 12px;
        """)
        self.current_user_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.current_user_label)

        layout.addStretch()
        self._add_page_to_stack(page)

    def create_playlists_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.add_unified_page_header(layout, "Playlists", "Import, export, edit, and maintain Plex playlists", "playlists")
        
        # Top buttons row
        buttons_layout = QHBoxLayout()
        self.fetch_playlists_button = ModernButton('Fetch Playlists')
        self.fetch_playlists_button.clicked.connect(self.fetch_playlists)
        buttons_layout.addWidget(self.fetch_playlists_button)
        
        self.delete_playlist_button = ModernButton('Delete Selected')
        self.delete_playlist_button.clicked.connect(self.delete_selected_playlist)
        buttons_layout.addWidget(self.delete_playlist_button)
        
        self.edit_playlist_button = ModernButton('Edit Selected')
        self.edit_playlist_button.clicked.connect(self.edit_selected_playlist)
        buttons_layout.addWidget(self.edit_playlist_button)
        
        # Cache management buttons
        self.refresh_all_button = ModernButton('Refresh All Counts')
        self.refresh_all_button.clicked.connect(self.refresh_all_track_counts)
        self.refresh_all_button.setToolTip("Refresh track counts for all playlists")
        buttons_layout.addWidget(self.refresh_all_button)
        
        self.clear_cache_button = ModernButton('Clear Cache')
        self.clear_cache_button.clicked.connect(self.clear_playlist_cache)
        self.clear_cache_button.setToolTip("Clear all cached playlist data")
        buttons_layout.addWidget(self.clear_cache_button)
        
        layout.addLayout(buttons_layout)
        
        # Info label with better instructions
        self.cache_info_label = QLabel("💡 Track counts load instantly when cached. Click any playlist to load tracks on-demand. Double-click to edit.")
        self.cache_info_label.setStyleSheet("color: #888888; font-style: italic; padding: 5px;")
        layout.addWidget(self.cache_info_label)
        
        # NEW: Import/Export section
        import_export_group = QGroupBox("Import && Export")
        ie_layout = QVBoxLayout(import_export_group)
        
        # Import section
        import_layout = QHBoxLayout()
        self.playlist_input = ModernLineEdit()
        self.playlist_input.setPlaceholderText("Path to .m3u Playlist or Directory")
        import_layout.addWidget(self.playlist_input)
        
        self.import_browse_button = ModernButton('Browse')
        self.import_browse_button.setObjectName("importBrowseButton")
        self.import_browse_button.clicked.connect(self.browse_files)
        import_layout.setAlignment(self.import_browse_button, Qt.AlignmentFlag.AlignTop)
        import_layout.addWidget(self.import_browse_button)

        self.import_playlist_button = ModernButton('Import Playlist(s)')
        self.import_playlist_button.setObjectName("importPlaylistButton")
        self.import_playlist_button.clicked.connect(self.import_playlist)
        import_layout.setAlignment(self.import_playlist_button, Qt.AlignmentFlag.AlignTop)
        import_layout.addWidget(self.import_playlist_button)
        
        ie_layout.addLayout(import_layout)
        
        # Progress bar
        self.import_progress = QProgressBar()
        self.import_progress.setVisible(False)
        ie_layout.addWidget(self.import_progress)
        
        # Export button
        export_button = ModernButton('Export Selected Playlists')
        export_button.clicked.connect(self.export_selected_playlists)
        ie_layout.addWidget(export_button)
        
        layout.addWidget(import_export_group)
        
        # Playlist list
        self.playlist_listwidget = QListWidget()
        self.playlist_listwidget.setSelectionMode(QListWidget.ExtendedSelection)
        self.playlist_listwidget.itemDoubleClicked.connect(self.edit_playlist_item)
        # NEW: Add single-click handler for responsive track count loading
        self.playlist_listwidget.itemClicked.connect(self.on_playlist_clicked)

        self.playlist_listwidget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.playlist_listwidget.customContextMenuRequested.connect(self.show_playlist_context_menu)

        layout.addWidget(self.playlist_listwidget)
        
        self.select_all_checkbox = QCheckBox("Select All")
        self.select_all_checkbox.stateChanged.connect(self.select_all_playlists)
        layout.addWidget(self.select_all_checkbox)
        
        self._add_page_to_stack(page)
    
    def on_playlist_clicked(self, item):
        """Handle single click on playlist to load track count responsively"""
        try:
            playlist = item.data(Qt.UserRole)
            if not playlist:
                return
            
            playlist_id = str(playlist.ratingKey)
            cached_count = self.playlist_cache.get_track_count(playlist_id)
            
            # If not cached, load track count with minimal UI feedback
            if cached_count is None and playlist_id not in self.track_count_threads:
                # Update status bar immediately to show responsiveness
                self.statusBar().showMessage(f"Loading track count for '{playlist.title}'...")
                
                # Start async loading without blocking dialog
                self.load_track_count_on_demand_silent(playlist)
                
        except Exception as e:
            logging.error(f"Error handling playlist click: {str(e)}")
    
    def load_track_count_on_demand_silent(self, playlist):
        """Load track count silently in background without blocking UI"""
        playlist_id = str(playlist.ratingKey)
        
        if playlist_id in self.track_count_threads:
            return  # Already loading
        
        # Update UI to show loading immediately (non-blocking)
        self.update_playlist_item_loading(playlist_id)
        
        # Start background loading
        thread = LoadTrackCountThread(playlist, self.playlist_cache, self)
        thread.progress_update.connect(lambda msg, pct: self.statusBar().showMessage(f"{msg}"))
        thread.track_count_loaded.connect(self.on_track_count_loaded_silent)
        thread.error.connect(self.on_track_count_error)
        thread.finished.connect(lambda: self.track_count_threads.pop(playlist_id, None))
        
        self.track_count_threads[playlist_id] = thread
        thread.start()
    
    def on_track_count_loaded_silent(self, playlist_id, track_count):
        """Handle track count loaded silently (for single clicks)"""
        # Update the display
        self.update_playlist_item_count(playlist_id, track_count)
        
        # Update the playlist_data cache in memory
        for i, (playlist, _) in enumerate(self.playlist_data):
            if str(playlist.ratingKey) == playlist_id:
                self.playlist_data[i] = (playlist, track_count)
                break
        
        # Show completion in status bar
        self.statusBar().showMessage(f"Loaded {track_count} tracks", 2000)  # Clear after 2 seconds

    def create_streaming_services_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        self.add_unified_page_header(layout, "Streaming Import", "Bring playlists from Spotify, Deezer, Tidal, ListenBrainz, and Apple Music XML into Plex", "streaming_import")
        tabs = QTabWidget()

        streaming_tab = QWidget()
        streaming_tab_layout = QVBoxLayout(streaming_tab)

        spotify_login_group = QGroupBox("Spotify Account Login")
        spotify_login_layout = QVBoxLayout(spotify_login_group)

        self.spotify_status_label = QLabel("Not logged in")
        self.spotify_status_label.setStyleSheet("color: #888888; font-weight: bold;")
        spotify_login_layout.addWidget(self.spotify_status_label)

        login_buttons_layout = QHBoxLayout()

        self.spotify_login_btn = QPushButton("🔑 Login to Spotify")
        self.spotify_login_btn.clicked.connect(self.spotify_login)
        self.spotify_login_btn.setStyleSheet("""
            QPushButton {
                background-color: #1DB954;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1ed760;
            }
        """)
        login_buttons_layout.addWidget(self.spotify_login_btn)

        self.spotify_logout_btn = QPushButton("🚪 Logout")
        self.spotify_logout_btn.clicked.connect(self.spotify_logout)
        self.spotify_logout_btn.setEnabled(False)
        login_buttons_layout.addWidget(self.spotify_logout_btn)

        login_buttons_layout.addStretch()
        spotify_login_layout.addLayout(login_buttons_layout)
        streaming_tab_layout.addWidget(spotify_login_group)

        streaming_group = QGroupBox("Import from Streaming Services")
        streaming_layout = QVBoxLayout()
        streaming_group.setLayout(streaming_layout)

        self.playlist_url_input = QLineEdit()
        self.playlist_url_input.setPlaceholderText("Enter Spotify, Deezer, or Tidal playlist URL")
        streaming_layout.addWidget(self.playlist_url_input)

        self.add_to_sync_checkbox = QCheckBox("🔄 Add to sync manager after import")
        self.add_to_sync_checkbox.setToolTip("Automatically add this playlist to sync manager to keep it updated")
        self.add_to_sync_checkbox.setStyleSheet("""
            QCheckBox {
                font-weight: bold;
                color: #4CAF50;
                padding: 5px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QCheckBox::indicator:unchecked {
                border: 2px solid #4CAF50;
                background-color: transparent;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                border: 2px solid #4CAF50;
                background-color: #4CAF50;
                border-radius: 3px;
            }
        """)
        streaming_layout.addWidget(self.add_to_sync_checkbox)

        self.import_playlist_button = QPushButton("Import Playlist to Plex")
        self.import_playlist_button.clicked.connect(self.import_streaming_playlist)
        streaming_layout.addWidget(self.import_playlist_button)

        progress_layout = QHBoxLayout()
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(8)

        self.streaming_progress = QProgressBar()
        self.streaming_progress.setVisible(False)
        progress_layout.addWidget(self.streaming_progress)

        self.cancel_streaming_button = QPushButton('Cancel')
        self.cancel_streaming_button.setVisible(False)
        self.cancel_streaming_button.setEnabled(False)
        self.cancel_streaming_button.clicked.connect(self.cancel_streaming_import)
        progress_layout.addWidget(self.cancel_streaming_button)
        progress_layout.addStretch()

        streaming_layout.addLayout(progress_layout)

        self.streaming_status_label = QLabel('')
        self.streaming_status_label.setVisible(False)
        self.streaming_status_label.setStyleSheet('color: #cccccc; padding: 4px 0;')
        streaming_layout.addWidget(self.streaming_status_label)

        streaming_tab_layout.addWidget(streaming_group)
        streaming_tab_layout.addStretch()
        tabs.addTab(streaming_tab, "Streaming Services")

        listenbrainz_tab = QWidget()
        listenbrainz_tab_layout = QVBoxLayout(listenbrainz_tab)
        listenbrainz_group = QGroupBox("ListenBrainz Integration")
        listenbrainz_layout = QVBoxLayout(listenbrainz_group)

        auth_row = QHBoxLayout()
        self.listenbrainz_user_input = ModernLineEdit()
        self.listenbrainz_user_input.setPlaceholderText("ListenBrainz username")
        auth_row.addWidget(self.listenbrainz_user_input)
        self.listenbrainz_token_input = ModernLineEdit()
        self.listenbrainz_token_input.setPlaceholderText("ListenBrainz token (required for export/private playlists)")
        self.listenbrainz_token_input.setEchoMode(QLineEdit.Password)
        auth_row.addWidget(self.listenbrainz_token_input)
        listenbrainz_layout.addLayout(auth_row)

        import_row = QHBoxLayout()
        import_row.setContentsMargins(0, 0, 0, 0)
        import_row.setSpacing(6)
        self.listenbrainz_playlist_combo = QComboBox()
        self.listenbrainz_playlist_combo.setMinimumHeight(34)
        self.listenbrainz_playlist_combo.addItem("Select ListenBrainz playlist...")
        import_row.addWidget(self.listenbrainz_playlist_combo, 1)
        self.listenbrainz_load_btn = ModernButton("Load ListenBrainz Playlists")
        self.listenbrainz_load_btn.setFixedHeight(34)
        self.listenbrainz_load_btn.clicked.connect(self.load_listenbrainz_playlists)
        import_row.addWidget(self.listenbrainz_load_btn)
        import_row.setAlignment(self.listenbrainz_load_btn, Qt.AlignmentFlag.AlignVCenter)
        self.listenbrainz_import_btn = ModernButton("Import Selected to Plex")
        self.listenbrainz_import_btn.setFixedHeight(34)
        self.listenbrainz_import_btn.clicked.connect(self.import_selected_listenbrainz_playlist)
        import_row.addWidget(self.listenbrainz_import_btn)
        import_row.setAlignment(self.listenbrainz_import_btn, Qt.AlignmentFlag.AlignVCenter)
        listenbrainz_layout.addLayout(import_row)

        export_row = QHBoxLayout()
        export_row.setContentsMargins(0, 0, 0, 0)
        export_row.setSpacing(6)
        self.listenbrainz_export_combo = QComboBox()
        self.listenbrainz_export_combo.setMinimumHeight(34)
        self.listenbrainz_export_combo.addItem("Select Plex playlist to export...")
        export_row.addWidget(self.listenbrainz_export_combo, 1)
        self.listenbrainz_export_btn = ModernButton("Export Plex Playlist to ListenBrainz")
        self.listenbrainz_export_btn.setFixedHeight(34)
        self.listenbrainz_export_btn.clicked.connect(self.export_selected_playlist_to_listenbrainz)
        export_row.addWidget(self.listenbrainz_export_btn)
        export_row.setAlignment(self.listenbrainz_export_btn, Qt.AlignmentFlag.AlignVCenter)
        listenbrainz_layout.addLayout(export_row)

        listenbrainz_hint = QLabel(
            "ListenBrainz uses JSPF playlists. Syncra imports from ListenBrainz URLs or your user playlist list and can export Plex playlists as JSPF."
        )
        listenbrainz_hint.setWordWrap(True)
        listenbrainz_hint.setStyleSheet("color: #b8c9df; font-size: 12px;")
        listenbrainz_layout.addWidget(listenbrainz_hint)

        listenbrainz_tab_layout.addWidget(listenbrainz_group)
        listenbrainz_tab_layout.addStretch()
        tabs.addTab(listenbrainz_tab, "ListenBrainz")

        apple_music_tab = QWidget()
        apple_music_tab_layout = QVBoxLayout(apple_music_tab)
        apple_music_group = QGroupBox("Apple Music XML Import")
        apple_music_layout = QVBoxLayout(apple_music_group)

        xml_row = QHBoxLayout()
        xml_row.setContentsMargins(0, 0, 0, 0)
        xml_row.setSpacing(6)
        self.apple_music_xml_input = ModernLineEdit()
        self.apple_music_xml_input.setMinimumHeight(34)
        self.apple_music_xml_input.setPlaceholderText("Select Apple Music Library XML export file")
        xml_row.addWidget(self.apple_music_xml_input, 1)
        self.apple_music_browse_btn = ModernButton("Browse XML")
        self.apple_music_browse_btn.setFixedHeight(34)
        self.apple_music_browse_btn.clicked.connect(self.browse_apple_music_xml)
        xml_row.addWidget(self.apple_music_browse_btn)
        xml_row.setAlignment(self.apple_music_browse_btn, Qt.AlignmentFlag.AlignVCenter)
        self.apple_music_load_btn = ModernButton("Load Library")
        self.apple_music_load_btn.setFixedHeight(34)
        self.apple_music_load_btn.clicked.connect(self.load_apple_music_xml)
        xml_row.addWidget(self.apple_music_load_btn)
        xml_row.setAlignment(self.apple_music_load_btn, Qt.AlignmentFlag.AlignVCenter)
        apple_music_layout.addLayout(xml_row)

        options_row = QHBoxLayout()
        self.apple_music_include_internal_cb = QCheckBox("Include internal playlists (Library/Music/etc.)")
        self.apple_music_include_internal_cb.setChecked(False)
        options_row.addWidget(self.apple_music_include_internal_cb)
        self.apple_music_import_ratings_cb = QCheckBox("Import ratings to Plex (user rating)")
        self.apple_music_import_ratings_cb.setChecked(True)
        options_row.addWidget(self.apple_music_import_ratings_cb)
        options_row.addStretch()
        apple_music_layout.addLayout(options_row)

        self.apple_music_playlist_list = QListWidget()
        self.apple_music_playlist_list.setSelectionMode(QListWidget.ExtendedSelection)
        self.apple_music_playlist_list.setMinimumHeight(250)
        apple_music_layout.addWidget(self.apple_music_playlist_list)

        playlist_actions_row = QHBoxLayout()
        self.apple_music_select_all_btn = ModernButton("Select All")
        self.apple_music_select_all_btn.clicked.connect(lambda: self.set_all_apple_music_playlist_checks(True))
        playlist_actions_row.addWidget(self.apple_music_select_all_btn)
        self.apple_music_clear_selection_btn = ModernButton("Clear Selection")
        self.apple_music_clear_selection_btn.clicked.connect(lambda: self.set_all_apple_music_playlist_checks(False))
        playlist_actions_row.addWidget(self.apple_music_clear_selection_btn)
        self.apple_music_preview_btn = ModernButton("Dry Run Preview")
        self.apple_music_preview_btn.clicked.connect(self.preview_apple_music_import)
        playlist_actions_row.addWidget(self.apple_music_preview_btn)
        playlist_actions_row.addStretch()
        self.apple_music_import_btn = ModernButton("Import Selected to Plex")
        self.apple_music_import_btn.clicked.connect(self.import_selected_apple_music_playlists)
        playlist_actions_row.addWidget(self.apple_music_import_btn)
        apple_music_layout.addLayout(playlist_actions_row)

        self.apple_music_preview_table = QTableWidget(0, 6)
        self.apple_music_preview_table.setHorizontalHeaderLabels(
            ["Playlist", "Tracks", "Matched", "Missing", "Match %", "Rating Candidates"]
        )
        self.apple_music_preview_table.verticalHeader().setVisible(False)
        self.apple_music_preview_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.apple_music_preview_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.apple_music_preview_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.apple_music_preview_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3, 4, 5):
            self.apple_music_preview_table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.apple_music_preview_table.setMinimumHeight(170)
        apple_music_layout.addWidget(self.apple_music_preview_table)

        self.apple_music_preview_details = QTextEdit()
        self.apple_music_preview_details.setReadOnly(True)
        self.apple_music_preview_details.setMinimumHeight(120)
        self.apple_music_preview_details.setPlaceholderText("Dry run details and missing track samples will appear here.")
        apple_music_layout.addWidget(self.apple_music_preview_details)

        self.apple_music_status_label = QLabel("Load an Apple Music XML export to preview playlists.")
        self.apple_music_status_label.setWordWrap(True)
        self.apple_music_status_label.setStyleSheet("color: #b8c9df; font-size: 12px;")
        apple_music_layout.addWidget(self.apple_music_status_label)

        apple_music_tab_layout.addWidget(apple_music_group)
        apple_music_tab_layout.addStretch()
        tabs.addTab(apple_music_tab, "Apple Music XML")

        layout.addWidget(tabs)
        self.refresh_listenbrainz_export_combo()
        layout.addStretch()
        self._add_page_to_stack(page)

    def refresh_listenbrainz_export_combo(self):
        if not hasattr(self, "listenbrainz_export_combo"):
            return
        self.listenbrainz_export_combo.blockSignals(True)
        self.listenbrainz_export_combo.clear()
        self.listenbrainz_export_combo.addItem("Select Plex playlist to export...", None)

        playlists = self.playlists if isinstance(self.playlists, list) else []
        if not playlists and getattr(self, "playlist_data", None):
            playlists = [playlist for playlist, _ in self.playlist_data]

        for playlist in playlists:
            try:
                self.listenbrainz_export_combo.addItem(playlist.title, playlist)
            except Exception:
                continue
        self.listenbrainz_export_combo.blockSignals(False)

    def load_listenbrainz_playlists(self):
        username = self.listenbrainz_user_input.text().strip() if hasattr(self, "listenbrainz_user_input") else ""
        token = self.listenbrainz_token_input.text().strip() if hasattr(self, "listenbrainz_token_input") else ""
        if not username:
            QMessageBox.warning(self, "Missing Username", "Enter a ListenBrainz username first.")
            return

        self.show_loading("ListenBrainz", "Loading playlists...")
        self.listenbrainz_load_btn.setEnabled(False)
        self.listenbrainz_load_thread = ListenBrainzPlaylistLoadThread(username, token, self)
        self.listenbrainz_load_thread.progress_update.connect(self.on_listenbrainz_load_progress)
        self.listenbrainz_load_thread.playlists_loaded.connect(self.on_listenbrainz_playlists_loaded)
        self.listenbrainz_load_thread.error.connect(self.on_listenbrainz_load_error)
        self.listenbrainz_load_thread.finished.connect(lambda: self.listenbrainz_load_btn.setEnabled(True))
        self.listenbrainz_load_thread.start()

    def on_listenbrainz_load_progress(self, message, percentage):
        if self.loading_dialog:
            self.loading_dialog.update_progress(message, percentage)

    def on_listenbrainz_playlists_loaded(self, playlists):
        self.hide_loading()
        self.listenbrainz_playlist_combo.clear()
        self.listenbrainz_playlist_combo.addItem("Select ListenBrainz playlist...", None)
        for playlist in playlists:
            playlist_id = playlist.get("playlist_id")
            title = playlist.get("title") or "Untitled"
            track_count = playlist.get("track_count")
            label = f"{title} ({track_count} tracks)" if isinstance(track_count, int) else title
            self.listenbrainz_playlist_combo.addItem(label, playlist_id)

        username = self.listenbrainz_user_input.text().strip() if hasattr(self, "listenbrainz_user_input") else ""
        self.statusBar().showMessage(f"Loaded {len(playlists)} ListenBrainz playlists for {username}", 3500)
        self.save_config()

    def on_listenbrainz_load_error(self, error_message):
        self.hide_loading()
        logging.error(f"Error loading ListenBrainz playlists: {error_message}")
        QMessageBox.warning(self, "ListenBrainz Error", f"Failed to load playlists: {error_message}")

    def import_selected_listenbrainz_playlist(self):
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return

        playlist_id = self.listenbrainz_playlist_combo.currentData() if hasattr(self, "listenbrainz_playlist_combo") else None
        if not playlist_id:
            QMessageBox.warning(self, "No Playlist Selected", "Select a ListenBrainz playlist first.")
            return

        token = self.listenbrainz_token_input.text().strip() if hasattr(self, "listenbrainz_token_input") else ""
        playlist_url = f"https://listenbrainz.org/playlist/{playlist_id}"
        if hasattr(self, "playlist_url_input"):
            self.playlist_url_input.setText(playlist_url)
        self.start_playlist_conversion(playlist_url, listenbrainz_token=token or None)

    def browse_apple_music_xml(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Apple Music Library XML",
            "",
            "Apple Music Library (*.xml *.plist);;XML Files (*.xml);;All Files (*)",
        )
        if path and hasattr(self, "apple_music_xml_input"):
            self.apple_music_xml_input.setText(path)
            self.save_config()

    def set_all_apple_music_playlist_checks(self, checked):
        if not hasattr(self, "apple_music_playlist_list"):
            return
        check_state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.apple_music_playlist_list.count()):
            item = self.apple_music_playlist_list.item(row)
            if item:
                item.setCheckState(check_state)

    def _apple_music_location_to_path(self, location):
        if not location:
            return ""
        raw_value = str(location).strip()
        if not raw_value:
            return ""

        if raw_value.lower().startswith("file://"):
            parsed = urllib.parse.urlparse(raw_value)
            decoded_path = urllib.parse.unquote(parsed.path or "")
            host = (parsed.netloc or "").strip()

            if host and host.lower() != "localhost":
                if not decoded_path.startswith("/"):
                    decoded_path = "/" + decoded_path
                return f"//{host}{decoded_path}"

            if (
                len(decoded_path) >= 3
                and decoded_path[0] == "/"
                and decoded_path[2] == ":"
                and decoded_path[1].isalpha()
            ):
                # Handle /C:/... URLs generated on Windows.
                decoded_path = decoded_path[1:]
            return decoded_path

        return urllib.parse.unquote(raw_value)

    def _canonical_file_path(self, value):
        if not value:
            return ""
        normalized = str(value).strip().replace("\\", "/")
        return normalized.lower()

    def _is_internal_apple_playlist(self, playlist_dict):
        if playlist_dict.get("Distinguished Kind") is not None:
            return True

        internal_names = {
            "library",
            "music",
            "downloaded",
            "tv shows",
            "movies",
            "audiobooks",
            "podcasts",
            "music videos",
            "purchased",
            "recently added",
            "recently played",
            "songs",
        }
        name = str(playlist_dict.get("Name", "") or "").strip().lower()
        return name in internal_names

    def _parse_apple_music_library(self, xml_path, include_internal=False):
        with open(xml_path, "rb") as handle:
            library_data = plistlib.load(handle)

        raw_tracks = library_data.get("Tracks", {}) or {}
        tracks = {}
        for key, track_data in raw_tracks.items():
            if not isinstance(track_data, dict):
                continue
            track_id = track_data.get("Track ID", key)
            try:
                track_id = int(track_id)
            except Exception:
                continue

            location_path = self._apple_music_location_to_path(track_data.get("Location", ""))
            rating_value = track_data.get("Rating", 0) or 0
            try:
                rating_value = int(rating_value)
            except Exception:
                rating_value = 0
            play_count_value = track_data.get("Play Count", 0) or 0
            try:
                play_count_value = int(play_count_value)
            except Exception:
                play_count_value = 0

            tracks[track_id] = {
                "track_id": track_id,
                "name": str(track_data.get("Name", "") or "").strip(),
                "artist": str(track_data.get("Artist", "") or "").strip(),
                "album": str(track_data.get("Album", "") or "").strip(),
                "location_path": location_path,
                "rating": rating_value,
                "play_count": play_count_value,
            }

        playlists = []
        for playlist_data in (library_data.get("Playlists", []) or []):
            if not isinstance(playlist_data, dict):
                continue
            if playlist_data.get("Folder"):
                continue
            if not include_internal and self._is_internal_apple_playlist(playlist_data):
                continue

            name = str(playlist_data.get("Name", "") or "").strip() or "Untitled"
            playlist_items = playlist_data.get("Playlist Items", []) or []
            track_ids = []
            for item in playlist_items:
                if not isinstance(item, dict):
                    continue
                track_id = item.get("Track ID")
                if track_id is None:
                    continue
                try:
                    track_id = int(track_id)
                except Exception:
                    continue
                if track_id in tracks:
                    track_ids.append(track_id)

            if not track_ids:
                continue

            playlists.append(
                {
                    "name": name,
                    "track_ids": track_ids,
                    "track_count": len(track_ids),
                    "is_smart": bool(playlist_data.get("Smart Info") or playlist_data.get("Smart Criteria")),
                    "persistent_id": str(playlist_data.get("Playlist Persistent ID", "") or ""),
                }
            )

        return {"tracks": tracks, "playlists": playlists}

    def load_apple_music_xml(self):
        xml_path = self.apple_music_xml_input.text().strip() if hasattr(self, "apple_music_xml_input") else ""
        if not xml_path:
            QMessageBox.warning(self, "Missing File", "Select an Apple Music XML file first.")
            return
        if not os.path.exists(xml_path):
            QMessageBox.warning(self, "File Not Found", f"Could not find file:\n{xml_path}")
            return

        include_internal = bool(self.apple_music_include_internal_cb.isChecked()) if hasattr(self, "apple_music_include_internal_cb") else False

        self.show_loading("Apple Music XML", "Parsing exported library...")
        try:
            parsed = self._parse_apple_music_library(xml_path, include_internal=include_internal)
            self.apple_music_library_data = parsed

            if hasattr(self, "apple_music_playlist_list"):
                self.apple_music_playlist_list.clear()
                for playlist in parsed.get("playlists", []):
                    kind_label = "Smart" if playlist.get("is_smart") else "Static"
                    item_label = f"{playlist.get('name', 'Untitled')} ({playlist.get('track_count', 0)} tracks) · {kind_label}"
                    item = QListWidgetItem(item_label)
                    item.setData(Qt.UserRole, playlist)
                    item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.CheckState.Checked)
                    self.apple_music_playlist_list.addItem(item)

            playlist_count = len(parsed.get("playlists", []))
            track_count = len(parsed.get("tracks", {}))
            smart_count = sum(1 for pl in parsed.get("playlists", []) if pl.get("is_smart"))
            self.apple_music_status_label.setText(
                f"Loaded {playlist_count} playlists ({smart_count} smart) and {track_count} tracks from Apple Music XML."
            )
            self.statusBar().showMessage(f"Apple Music XML loaded: {playlist_count} playlists", 3500)
            self.save_config()
        except Exception as parse_error:
            logging.error(f"Failed to parse Apple Music XML: {parse_error}", exc_info=True)
            QMessageBox.critical(self, "Apple Music XML Error", f"Failed to parse library export:\n{parse_error}")
        finally:
            self.hide_loading()

    def _selected_apple_music_playlists(self):
        selected = []
        if not hasattr(self, "apple_music_playlist_list"):
            return selected
        for row in range(self.apple_music_playlist_list.count()):
            item = self.apple_music_playlist_list.item(row)
            if not item:
                continue
            item_checked = item.checkState() == Qt.CheckState.Checked
            if item_checked or item.isSelected():
                playlist_data = item.data(Qt.UserRole)
                if isinstance(playlist_data, dict):
                    selected.append(playlist_data)
        return selected

    def _apple_rating_to_plex(self, apple_rating):
        try:
            score = int(apple_rating)
        except Exception:
            return None
        if score <= 0:
            return None
        return max(1, min(10, int(round(score / 10.0))))

    def _register_apple_rating_candidate(self, lookup, path_value, rating_value):
        if not path_value:
            return
        candidates = [path_value]
        try:
            mapped = self.apply_path_mappings(path_value)
            if mapped:
                candidates.append(mapped)
        except Exception:
            pass
        try:
            normalized = self.normalize_path_for_os(path_value)
            if normalized:
                candidates.append(normalized)
        except Exception:
            pass

        for candidate in candidates:
            key = self._canonical_file_path(candidate)
            if not key:
                continue
            existing = lookup.get(key, 0)
            if rating_value > existing:
                lookup[key] = rating_value

    def _resolve_track_part_path(self, plex_track):
        try:
            if hasattr(plex_track, "iterParts"):
                for part in plex_track.iterParts():
                    file_path = getattr(part, "file", None)
                    if file_path and isinstance(file_path, str):
                        return file_path
        except Exception:
            return ""
        return ""

    def _apply_apple_ratings_to_playlist(self, plex_playlist, rating_lookup, already_rated_keys):
        attempted = 0
        applied = 0
        if not plex_playlist or not rating_lookup:
            return attempted, applied

        try:
            playlist_items = list(plex_playlist.items())
        except Exception as playlist_error:
            logging.warning(f"Failed to read playlist items for rating import: {playlist_error}")
            return attempted, applied

        for plex_track in playlist_items:
            rating_key = str(getattr(plex_track, "ratingKey", "") or "")
            if rating_key and rating_key in already_rated_keys:
                continue

            track_path = self._resolve_track_part_path(plex_track)
            if not track_path:
                continue

            lookup_key = self._canonical_file_path(track_path)
            rating_value = rating_lookup.get(lookup_key)
            if rating_value is None:
                mapped_key = self._canonical_file_path(self.apply_path_mappings(track_path))
                rating_value = rating_lookup.get(mapped_key)
            if rating_value is None:
                continue

            plex_rating = self._apple_rating_to_plex(rating_value)
            if plex_rating is None:
                continue

            attempted += 1
            try:
                plex_track.rate(plex_rating)
                applied += 1
                if rating_key:
                    already_rated_keys.add(rating_key)
            except Exception as rating_error:
                logging.warning(
                    f"Failed to apply Plex rating for track '{getattr(plex_track, 'title', 'Unknown')}': {rating_error}"
                )

        return attempted, applied

    def _get_plex_track_paths(self, plex_track):
        paths = []
        try:
            if hasattr(plex_track, "iterParts"):
                for part in plex_track.iterParts():
                    file_path = getattr(part, "file", None)
                    if file_path and isinstance(file_path, str):
                        canonical = self._canonical_file_path(file_path)
                        if canonical:
                            paths.append(canonical)
        except Exception:
            return []
        return paths

    def _paths_match_for_dry_run(self, apple_paths, plex_paths):
        if not apple_paths or not plex_paths:
            return False

        apple_set = {p for p in apple_paths if p}
        if not apple_set:
            return False

        for plex_path in plex_paths:
            for apple_path in apple_set:
                if plex_path == apple_path:
                    return True
                if plex_path.endswith(apple_path) or apple_path.endswith(plex_path):
                    return True

                apple_parts = [part for part in apple_path.split("/") if part]
                plex_parts = [part for part in plex_path.split("/") if part]
                if len(apple_parts) >= 3 and len(plex_parts) >= 3:
                    if apple_parts[-3:] == plex_parts[-3:]:
                        return True
        return False

    def _score_metadata_match(self, plex_track, track_name, track_artist):
        title = (getattr(plex_track, "title", "") or "").strip()
        if not title:
            return 0.0
        title_score = float(fuzz.token_set_ratio(track_name.lower(), title.lower())) if track_name else 0.0

        artist_value = ""
        try:
            artist_value = (getattr(plex_track, "originalTitle", "") or "").strip()
            if not artist_value and hasattr(plex_track, "artist") and plex_track.artist():
                artist_value = (plex_track.artist().title or "").strip()
        except Exception:
            artist_value = (getattr(plex_track, "grandparentTitle", "") or "").strip()

        if track_artist and artist_value:
            artist_score = float(fuzz.token_set_ratio(track_artist.lower(), artist_value.lower()))
        elif track_artist:
            artist_score = 0.0
        else:
            artist_score = 80.0

        return (title_score * 0.7) + (artist_score * 0.3)

    def _dry_run_match_apple_track(self, library_section, track_info, search_cache):
        location_path = str(track_info.get("location_path", "") or "").strip()
        track_name = str(track_info.get("name", "") or "").strip()
        track_artist = str(track_info.get("artist", "") or "").strip()

        apple_paths = []
        if location_path:
            apple_paths.append(self._canonical_file_path(location_path))
            try:
                mapped_path = self.apply_path_mappings(location_path)
                if mapped_path:
                    apple_paths.append(self._canonical_file_path(mapped_path))
            except Exception:
                pass
            try:
                normalized = self.normalize_path_for_os(location_path)
                if normalized:
                    apple_paths.append(self._canonical_file_path(normalized))
            except Exception:
                pass

        file_basename = ""
        file_no_ext = ""
        if location_path:
            try:
                file_basename = os.path.basename(location_path).strip()
                file_no_ext = os.path.splitext(file_basename)[0].strip()
            except Exception:
                file_basename = ""
                file_no_ext = ""

        candidate_tracks = []
        seen_keys = set()

        def _cached_search(query):
            key = (query or "").strip().lower()
            if not key:
                return []
            if key not in search_cache:
                try:
                    search_cache[key] = list(library_section.searchTracks(title=query, limit=80) or [])
                except Exception:
                    search_cache[key] = []
            return search_cache[key]

        for query in [file_no_ext, track_name]:
            for candidate in _cached_search(query):
                rating_key = str(getattr(candidate, "ratingKey", "") or "")
                if rating_key and rating_key in seen_keys:
                    continue
                if rating_key:
                    seen_keys.add(rating_key)
                candidate_tracks.append(candidate)

        if not candidate_tracks:
            return False, "no_candidates"

        for candidate in candidate_tracks:
            plex_paths = self._get_plex_track_paths(candidate)
            if self._paths_match_for_dry_run(apple_paths, plex_paths):
                return True, "path"

        best_score = 0.0
        for candidate in candidate_tracks:
            best_score = max(best_score, self._score_metadata_match(candidate, track_name, track_artist))
        if best_score >= 88.0:
            return True, "metadata"
        return False, "missing"

    def preview_apple_music_import(self):
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return
        section_id = self.section_combo.currentData()
        if not section_id:
            QMessageBox.warning(self, "No Library Selected", "Please select a Plex music library section first.")
            return
        if not self.apple_music_library_data:
            QMessageBox.warning(self, "No Library Loaded", "Load an Apple Music XML export first.")
            return

        selected_playlists = self._selected_apple_music_playlists()
        if not selected_playlists:
            QMessageBox.warning(self, "No Playlists Selected", "Select one or more Apple Music playlists first.")
            return

        tracks_by_id = self.apple_music_library_data.get("tracks", {})
        if not tracks_by_id:
            QMessageBox.warning(self, "No Tracks", "No tracks were found in the loaded Apple Music export.")
            return

        try:
            library_section = self.plex_server.library.sectionByID(section_id)
        except Exception as section_error:
            QMessageBox.critical(self, "Plex Error", f"Could not access selected library section:\n{section_error}")
            return

        if hasattr(self, "apple_music_preview_table"):
            self.apple_music_preview_table.setRowCount(0)
        if hasattr(self, "apple_music_preview_details"):
            self.apple_music_preview_details.clear()

        self.show_loading("Apple Music Dry Run", "Previewing playlist matches against Plex library...")

        search_cache = {}
        total_tracks = 0
        total_matched = 0
        total_missing = 0
        total_rating_candidates = 0
        details_lines = []

        try:
            playlist_total = len(selected_playlists)
            for playlist_index, playlist in enumerate(selected_playlists, 1):
                playlist_name = str(playlist.get("name", "Untitled") or "Untitled").strip() or "Untitled"
                track_ids = list(playlist.get("track_ids", []) or [])
                track_count = len(track_ids)
                matched = 0
                missing = 0
                rating_candidates = 0
                missing_samples = []

                for idx, track_id in enumerate(track_ids, 1):
                    track_info = tracks_by_id.get(track_id)
                    if not track_info:
                        missing += 1
                        continue
                    total_tracks += 1
                    if int(track_info.get("rating", 0) or 0) > 0:
                        rating_candidates += 1
                        total_rating_candidates += 1

                    found, reason = self._dry_run_match_apple_track(library_section, track_info, search_cache)
                    if found:
                        matched += 1
                        total_matched += 1
                    else:
                        missing += 1
                        total_missing += 1
                        if len(missing_samples) < 5:
                            sample_title = track_info.get("name") or "Unknown Title"
                            sample_artist = track_info.get("artist") or "Unknown Artist"
                            missing_samples.append(f"- {sample_artist} - {sample_title} ({reason})")

                    if self.loading_dialog and track_count > 0:
                        playlist_progress = int((idx / track_count) * 100)
                        global_progress = int((((playlist_index - 1) + (playlist_progress / 100.0)) / max(playlist_total, 1)) * 100)
                        self.loading_dialog.update_progress(
                            f"Dry run: {playlist_name} ({idx}/{track_count})",
                            global_progress,
                        )
                        QApplication.processEvents()

                match_pct = (matched / track_count * 100.0) if track_count else 0.0
                if hasattr(self, "apple_music_preview_table"):
                    row = self.apple_music_preview_table.rowCount()
                    self.apple_music_preview_table.insertRow(row)
                    self.apple_music_preview_table.setItem(row, 0, QTableWidgetItem(playlist_name))
                    self.apple_music_preview_table.setItem(row, 1, QTableWidgetItem(str(track_count)))
                    self.apple_music_preview_table.setItem(row, 2, QTableWidgetItem(str(matched)))
                    self.apple_music_preview_table.setItem(row, 3, QTableWidgetItem(str(missing)))
                    self.apple_music_preview_table.setItem(row, 4, QTableWidgetItem(f"{match_pct:.1f}%"))
                    self.apple_music_preview_table.setItem(row, 5, QTableWidgetItem(str(rating_candidates)))

                details_lines.append(f"{playlist_name}: {matched}/{track_count} matched ({match_pct:.1f}%)")
                if missing_samples:
                    details_lines.append("  Missing samples:")
                    details_lines.extend([f"  {line}" for line in missing_samples])

            overall_pct = (total_matched / total_tracks * 100.0) if total_tracks else 0.0
            summary_line = (
                f"Dry run complete: {len(selected_playlists)} playlist(s), "
                f"{total_matched}/{total_tracks} tracks matched ({overall_pct:.1f}%), "
                f"{total_missing} missing, ratings candidates: {total_rating_candidates}."
            )
            if hasattr(self, "apple_music_status_label"):
                self.apple_music_status_label.setText(summary_line)
            if hasattr(self, "apple_music_preview_details"):
                self.apple_music_preview_details.setPlainText("\n".join(details_lines) if details_lines else "No preview details available.")
            self.statusBar().showMessage(summary_line, 5000)
        except Exception as preview_error:
            logging.error(f"Apple Music dry run failed: {preview_error}", exc_info=True)
            QMessageBox.critical(self, "Apple Music Dry Run Error", f"Dry run failed:\n{preview_error}")
        finally:
            self.hide_loading()

    def import_selected_apple_music_playlists(self):
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return
        if not self.section_combo.currentData():
            QMessageBox.warning(self, "No Library Selected", "Please select a Plex music library section first.")
            return

        if not self.apple_music_library_data:
            QMessageBox.warning(self, "No Library Loaded", "Load an Apple Music XML export first.")
            return

        selected_playlists = self._selected_apple_music_playlists()
        if not selected_playlists:
            QMessageBox.warning(self, "No Playlists Selected", "Select one or more Apple Music playlists to import.")
            return

        tracks_by_id = self.apple_music_library_data.get("tracks", {})
        if not tracks_by_id:
            QMessageBox.warning(self, "No Tracks", "No tracks were found in the loaded Apple Music export.")
            return

        import_ratings = bool(self.apple_music_import_ratings_cb.isChecked()) if hasattr(self, "apple_music_import_ratings_cb") else False

        self.show_loading("Apple Music Import", "Importing playlists into Plex...")
        processed = 0
        skipped = 0
        ratings_attempted = 0
        ratings_applied = 0
        rated_track_keys = set()

        used_names = set()

        try:
            total = len(selected_playlists)
            for index, playlist in enumerate(selected_playlists, 1):
                playlist_name = str(playlist.get("name", "Untitled") or "Untitled").strip() or "Untitled"
                base_name = playlist_name
                suffix = 2
                while playlist_name.lower() in used_names:
                    playlist_name = f"{base_name} ({suffix})"
                    suffix += 1
                used_names.add(playlist_name.lower())

                track_paths = []
                rating_lookup = {}
                for track_id in playlist.get("track_ids", []):
                    track_info = tracks_by_id.get(track_id)
                    if not track_info:
                        continue
                    location_path = track_info.get("location_path", "")
                    if not location_path:
                        continue
                    track_paths.append(location_path)

                    if import_ratings:
                        rating_value = track_info.get("rating", 0) or 0
                        if rating_value > 0:
                            self._register_apple_rating_candidate(rating_lookup, location_path, rating_value)

                if not track_paths:
                    skipped += 1
                    continue

                if self.loading_dialog:
                    progress = int(((index - 1) / max(total, 1)) * 100)
                    self.loading_dialog.update_progress(f"Importing '{playlist_name}'...", progress)
                QApplication.processEvents()

                safe_playlist_name = re.sub(r'[<>:"/\\\\|?*]+', '_', playlist_name).strip().rstrip('. ')
                if not safe_playlist_name:
                    safe_playlist_name = "Apple Playlist"
                temp_dir = tempfile.mkdtemp(prefix="syncra_apple_")
                temp_m3u_path = os.path.join(temp_dir, f"{safe_playlist_name}.m3u")
                try:
                    with open(temp_m3u_path, "w", encoding="utf-8", newline="\n") as handle:
                        handle.write("#EXTM3U\n")
                        for path_value in track_paths:
                            handle.write(f"{path_value}\n")

                    self._perform_upload(temp_m3u_path, custom_name=playlist_name)
                    processed += 1

                    if import_ratings and rating_lookup:
                        playlist_obj = self.check_playlist_exists(playlist_name)
                        attempted, applied = self._apply_apple_ratings_to_playlist(
                            playlist_obj, rating_lookup, rated_track_keys
                        )
                        ratings_attempted += attempted
                        ratings_applied += applied
                finally:
                    try:
                        if os.path.exists(temp_m3u_path):
                            os.remove(temp_m3u_path)
                    except Exception:
                        pass
                    try:
                        if os.path.isdir(temp_dir):
                            os.rmdir(temp_dir)
                    except Exception:
                        pass

            if self.loading_dialog:
                self.loading_dialog.update_progress("Apple Music import complete", 100)
            QApplication.processEvents()
        except Exception as import_error:
            logging.error(f"Apple Music playlist import failed: {import_error}", exc_info=True)
            QMessageBox.critical(self, "Apple Music Import Error", f"Import failed:\n{import_error}")
            return
        finally:
            self.hide_loading()
            self.save_config()

        summary = f"Processed {processed} Apple Music playlist(s)."
        if skipped:
            summary += f"\nSkipped {skipped} playlist(s) with no usable file paths."
        if import_ratings:
            summary += f"\nRatings applied: {ratings_applied}/{ratings_attempted} matched track(s)."
        QMessageBox.information(self, "Apple Music Import Complete", summary)
        self.statusBar().showMessage("Apple Music playlist import complete", 3500)

    def _extract_musicbrainz_recording_mbid(self, track):
        mbid_pattern = re.compile(r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})")
        candidates = []
        if getattr(track, "guid", None):
            candidates.append(str(track.guid))
        if hasattr(track, "guids") and track.guids:
            for guid in track.guids:
                guid_id = getattr(guid, "id", None)
                if guid_id:
                    candidates.append(str(guid_id))

        recording_patterns = [
            re.compile(r"/recording/([0-9a-fA-F-]{36})", re.IGNORECASE),
            re.compile(r"recording[:/]{1}([0-9a-fA-F-]{36})", re.IGNORECASE),
            re.compile(r"recording_mbid[=/]([0-9a-fA-F-]{36})", re.IGNORECASE),
            re.compile(r"mbid://([0-9a-fA-F-]{36})", re.IGNORECASE),
        ]
        for candidate in candidates:
            lower = candidate.lower()
            if "musicbrainz" in lower or "mbid" in lower:
                for pattern in recording_patterns:
                    strict_match = pattern.search(candidate)
                    if strict_match:
                        strict_mbid = strict_match.group(1).lower()
                        if mbid_pattern.fullmatch(strict_mbid):
                            return strict_mbid
                match = mbid_pattern.search(candidate)
                if match:
                    return match.group(1).lower()
        return None

    def _resolve_recording_mbid_for_export(self, track, title, artist_name, album_name, mbid_cache):
        """Resolve a valid MusicBrainz recording MBID for ListenBrainz export."""
        direct_mbid = self._extract_musicbrainz_recording_mbid(track)
        if direct_mbid:
            provider = self.metadata_service.provider if (self.metadata_service and hasattr(self.metadata_service, "provider")) else None
            if provider and hasattr(provider, "validate_recording_mbid"):
                try:
                    if provider.validate_recording_mbid(direct_mbid):
                        return direct_mbid, "plex_guid"
                    logging.info(f"Discarding non-recording/invalid MBID from Plex GUID: {direct_mbid}")
                except Exception as e:
                    logging.warning(f"Failed to validate direct MBID {direct_mbid}: {e}")
            else:
                return direct_mbid, "plex_guid"

        cache_key = f"{title.lower()}::{artist_name.lower()}::{album_name.lower()}"
        if cache_key in mbid_cache:
            return mbid_cache[cache_key], "musicbrainz_search" if mbid_cache[cache_key] else "missing"

        provider = self.metadata_service.provider if (self.metadata_service and hasattr(self.metadata_service, "provider")) else None
        if not provider:
            self.setup_metadata_service()
            provider = self.metadata_service.provider if (self.metadata_service and hasattr(self.metadata_service, "provider")) else None
        if not provider:
            mbid_cache[cache_key] = None
            return None, "missing"

        try:
            candidate = provider.search_track(
                TrackIdentity(
                    rating_key=str(getattr(track, "ratingKey", "") or ""),
                    title=title,
                    artist=artist_name,
                    album=album_name,
                    year=getattr(track, "year", None),
                    plex_track=track,
                )
            )
            mbid = (candidate.recording_mbid or "").strip().lower() if candidate else None
            mbid_cache[cache_key] = mbid or None
            if mbid:
                return mbid, "musicbrainz_search"
        except Exception as e:
            logging.warning(f"MusicBrainz fallback lookup failed for '{title}' - '{artist_name}': {e}")

        mbid_cache[cache_key] = None
        return None, "missing"

    def _build_listenbrainz_jspf_track(self, track, mbid_cache):
        title = (getattr(track, "title", None) or "").strip()
        if not title:
            return None, "missing_title"

        artist_name = ""
        try:
            artist_name = (track.originalTitle or "").strip()
            if not artist_name and hasattr(track, "artist") and track.artist():
                artist_name = (track.artist().title or "").strip()
        except Exception:
            artist_name = ""

        album_name = ""
        try:
            if hasattr(track, "album") and track.album():
                album_name = (track.album().title or "").strip()
        except Exception:
            album_name = ""

        recording_mbid, mbid_source = self._resolve_recording_mbid_for_export(
            track,
            title,
            artist_name,
            album_name,
            mbid_cache,
        )
        if not recording_mbid:
            return None, "missing_mbid"

        entry = {
            "title": title,
            "identifier": [f"https://musicbrainz.org/recording/{recording_mbid}"],
            "extension": {"https://musicbrainz.org/doc/jspf#track": {}},
        }
        if artist_name:
            entry["creator"] = artist_name
        if album_name:
            entry["album"] = album_name
        if getattr(track, "duration", None):
            entry["duration"] = int(track.duration)

        return entry, mbid_source

    def export_selected_playlist_to_listenbrainz(self):
        token = self.listenbrainz_token_input.text().strip() if hasattr(self, "listenbrainz_token_input") else ""
        if not token:
            QMessageBox.warning(self, "Missing Token", "ListenBrainz token is required for playlist export.")
            return

        playlist = self.listenbrainz_export_combo.currentData() if hasattr(self, "listenbrainz_export_combo") else None
        if not playlist:
            QMessageBox.warning(self, "No Playlist Selected", "Select a Plex playlist to export first.")
            return

        username = self.listenbrainz_user_input.text().strip() if hasattr(self, "listenbrainz_user_input") else ""
        self.show_loading("ListenBrainz Export", "Preparing export...")
        self.listenbrainz_export_btn.setEnabled(False)
        self.listenbrainz_export_thread = ListenBrainzExportThread(
            playlist=playlist,
            token=token,
            username=username,
            track_builder=self._build_listenbrainz_jspf_track,
            parent=self,
        )
        self.listenbrainz_export_thread.progress_update.connect(self.on_listenbrainz_export_progress)
        self.listenbrainz_export_thread.export_complete.connect(self.on_listenbrainz_export_complete)
        self.listenbrainz_export_thread.error.connect(self.on_listenbrainz_export_error)
        self.listenbrainz_export_thread.finished.connect(lambda: self.listenbrainz_export_btn.setEnabled(True))
        self.listenbrainz_export_thread.start()

    def on_listenbrainz_export_progress(self, message, percentage):
        if self.loading_dialog:
            self.loading_dialog.update_progress(message, percentage)
        self.statusBar().showMessage(message)

    def on_listenbrainz_export_complete(self, result):
        self.hide_loading()
        playlist_title = result.get("playlist_title", "Playlist")
        exported_count = int(result.get("exported_count", 0))
        playlist_url = result.get("playlist_url", "Unknown URL")
        skipped_missing_mbid = int(result.get("skipped_missing_mbid", 0))
        skipped_missing_title = int(result.get("skipped_missing_title", 0))
        guid_resolved_count = int(result.get("guid_resolved_count", 0))
        search_resolved_count = int(result.get("search_resolved_count", 0))

        self.statusBar().showMessage(f"Exported '{playlist_title}' to ListenBrainz", 3500)
        summary = f"Exported '{playlist_title}' ({exported_count} tracks) to ListenBrainz."
        if skipped_missing_mbid:
            summary += f"\n\nSkipped {skipped_missing_mbid} tracks without MusicBrainz recording MBIDs."
        if skipped_missing_title:
            summary += f"\nSkipped {skipped_missing_title} tracks with empty titles."
        summary += f"\n\nMBID source: {guid_resolved_count} from Plex GUIDs, {search_resolved_count} from MusicBrainz lookup."

        QMessageBox.information(
            self,
            "ListenBrainz Export Complete",
            f"{summary}\n\n{playlist_url}",
        )
        self.save_config()

    def on_listenbrainz_export_error(self, error_message):
        self.hide_loading()
        logging.error(f"Error exporting playlist to ListenBrainz: {error_message}")
        QMessageBox.warning(self, "ListenBrainz Export Error", f"Failed to export playlist: {error_message}")

    def add_playlist_to_sync_manager(self, playlist_name, source_url):
        """Add a playlist to the sync manager automatically"""
        try:
            # Get the current library section ID
            library_section_id = self.section_combo.currentData()
            if not library_section_id:
                raise Exception("No library section selected")
            
            # Check if this sync config already exists
            for row in range(self.sync_configs_table.rowCount()):
                existing_playlist = self.sync_configs_table.item(row, 0).text()
                existing_source = self.sync_configs_table.item(row, 1).text()
                
                if existing_playlist.lower() == playlist_name.lower():
                    # Update existing entry with new source URL
                    logging.info(f"Updating existing sync config for '{playlist_name}'")
                    source_item = QTableWidgetItem(source_url)
                    source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
                    self.sync_configs_table.setItem(row, 1, source_item)
                    
                    # Update last sync time
                    sync_item = QTableWidgetItem("Never")
                    sync_item.setFlags(sync_item.flags() & ~Qt.ItemIsEditable)
                    self.sync_configs_table.setItem(row, 2, sync_item)
                    
                    # Refresh action buttons for this row
                    self.create_action_buttons_for_row(row)
                    
                    # Save config
                    self.save_sync_config()
                    return
            
            # Add new sync configuration
            row = self.sync_configs_table.rowCount()
            self.sync_configs_table.insertRow(row)
            
            # Create read-only items
            playlist_item = QTableWidgetItem(playlist_name)
            playlist_item.setFlags(playlist_item.flags() & ~Qt.ItemIsEditable)
            self.sync_configs_table.setItem(row, 0, playlist_item)
            
            source_item = QTableWidgetItem(source_url)
            source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
            self.sync_configs_table.setItem(row, 1, source_item)
            
            sync_item = QTableWidgetItem("Never")
            sync_item.setFlags(sync_item.flags() & ~Qt.ItemIsEditable)
            self.sync_configs_table.setItem(row, 2, sync_item)
            
            self._set_clear_on_sync_checkbox(row, False)

            # Create action buttons for the new row
            self.create_action_buttons_for_row(row)
            
            # Save the sync configuration
            self.save_sync_config()
            
            logging.info(f"✅ Added '{playlist_name}' to sync manager with source: {source_url}")
            
            # Update the sync manager UI if it's visible
            if hasattr(self, 'sync_log'):
                current_time = datetime.now().strftime('%H:%M:%S')
                self.sync_log.append(f"[{current_time}] Added '{playlist_name}' to sync manager")
            
        except Exception as e:
            logging.error(f"Error adding playlist to sync manager: {str(e)}")
            raise

    # Enhanced playlist management methods
    def edit_playlist_item(self, item):
        """Handle double-click on playlist item - opens immediately, no blocking"""
        try:
            # Get the playlist name from the item text (remove track count)
            playlist_name = item.text().split(' (')[0].replace('🎵 ', '').replace('📂 ', '').replace('⏳ ', '').replace('❌ ', '')
            
            # Immediate feedback in status bar
            self.statusBar().showMessage(f"🎵 Opening '{playlist_name}' for editing...")
            
            # Open editor without any blocking
            self.edit_playlist_by_name(playlist_name)
            
        except Exception as e:
            logging.error(f"Error handling playlist double-click: {str(e)}")
            QMessageBox.warning(self, "Error", f"Failed to open playlist editor: {str(e)}")
    
    def edit_selected_playlist(self):
        """Open playlist editor for selected playlist - completely non-blocking"""
        current_item = self.playlist_listwidget.currentItem()
        if not current_item:
            # Try to get checked items if no current selection
            selected_items = []
            for index in range(self.playlist_listwidget.count()):
                item = self.playlist_listwidget.item(index)
                if item.checkState() == Qt.Checked:
                    selected_items.append(item)
            
            if not selected_items:
                QMessageBox.warning(self, "No Selection", "Please select a playlist to edit.")
                return
            
            if len(selected_items) > 1:
                QMessageBox.warning(self, "Multiple Selection", "Please select only one playlist to edit.")
                return
            
            current_item = selected_items[0]
        
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return
        
        # Get the playlist name from the item text (remove track count and emojis)
        playlist_name = current_item.text().split(' (')[0].replace('🎵 ', '').replace('📂 ', '').replace('⏳ ', '').replace('❌ ', '')
        
        # Immediate feedback
        self.statusBar().showMessage(f"🎵 Opening '{playlist_name}' for editing...")
        
        # Open editor without blocking
        self.edit_playlist_by_name(playlist_name)
    
    def edit_playlist_by_name(self, playlist_name):
        """Edit playlist by name with on-demand loading"""
        try:
            # Find the playlist object
            playlist = None
            for plex_playlist, _ in self.playlist_data:
                if plex_playlist.title == playlist_name:
                    playlist = plex_playlist
                    break
            
            if not playlist:
                # Fallback: search in the original playlists list
                for plex_playlist in self.playlists:
                    if plex_playlist.title == playlist_name:
                        playlist = plex_playlist
                        break
            
            if playlist:
                # Load track count on-demand if not already loaded
                self.load_track_count_on_demand(playlist)
                
                try:
                    dialog = PlaylistEditorDialog(playlist, self.plex_server, self)
                    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
                    if not hasattr(self, "_open_playlist_editors"):
                        self._open_playlist_editors = []
                    self._open_playlist_editors.append(dialog)
                    dialog.finished.connect(
                        lambda result, playlist_ref=playlist, dialog_ref=dialog: self._on_playlist_editor_finished(
                            result,
                            playlist_ref,
                            dialog_ref,
                        )
                    )
                    dialog.open()
                        
                except Exception as dialog_error:
                    logging.error(f"Error opening playlist editor: {str(dialog_error)}")
                    QMessageBox.critical(self, "Editor Error", f"Failed to open playlist editor: {str(dialog_error)}")
            else:
                QMessageBox.warning(self, "Playlist Not Found", f"Could not find playlist: {playlist_name}")
                
        except Exception as e:
            logging.error(f"Error editing playlist: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to edit playlist: {str(e)}")

    def _on_playlist_editor_finished(self, result, playlist, dialog):
        try:
            if hasattr(self, "_open_playlist_editors"):
                self._open_playlist_editors = [editor for editor in self._open_playlist_editors if editor is not dialog]

            if result == QDialog.DialogCode.Accepted:
                playlist_id = str(playlist.ratingKey)
                self.playlist_cache.remove_playlist(playlist_id)
                self.fetch_playlists()
        except Exception as e:
            logging.error(f"Error finalizing playlist editor close: {str(e)}")
    
    def show_loading(self, message="Loading...", detail="Please wait...", can_cancel=False, cancel_callback=None, cancel_text="Cancel"):
        """Show loading dialog"""
        if not self.loading_dialog:
            self.loading_dialog = LoadingDialog(self)
        
        self.loading_dialog.message_label.setText(message)
        self.loading_dialog.detail_label.setText(detail)
        self.loading_dialog.progress_bar.setValue(0)
        self.loading_dialog.configure_cancel(
            callback=cancel_callback,
            visible=can_cancel,
            button_text=cancel_text,
        )
        self.loading_dialog.show()
        QApplication.processEvents()  # Update UI immediately
    
    def hide_loading(self):
        """Hide loading dialog"""
        if self.loading_dialog:
            self.loading_dialog.configure_cancel(callback=None, visible=False)
            self.loading_dialog.hide()
    
    def show_playlist_merger(self):
        """Show playlist merger dialog"""
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return
        
        if not self.playlists:
            QMessageBox.warning(self, "No Playlists", "Please fetch playlists first.")
            return
        
        dialog = PlaylistMergerDialog(self.playlists, self.plex_server, self)
        if dialog.exec() == QDialog.Accepted:
            self.fetch_playlists()  # Refresh playlist list
    
    # Sync management methods
    def toggle_auto_sync(self, state):
        """Toggle auto-sync functionality"""
        if state == Qt.Checked:
            interval = self.sync_interval_spinbox.value() * 60 * 1000  # Convert to milliseconds
            self.auto_sync_timer.start(interval)
            self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Auto-sync enabled (interval: {self.sync_interval_spinbox.value()} minutes)")
        else:
            self.auto_sync_timer.stop()
            self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Auto-sync disabled")

        # Save the auto-sync state to config file
        self.save_sync_config()

    def toggle_scheduled_sync(self, state):
        """Toggle scheduled sync functionality"""
        from PyQt6.QtCore import QDateTime

        if state == Qt.Checked:
            scheduled_time = self.scheduled_datetime.dateTime()
            current_time = QDateTime.currentDateTime()

            # Validate that scheduled time is in the future
            if scheduled_time <= current_time:
                QMessageBox.warning(self, "Invalid Time",
                    "Scheduled time must be in the future. Please select a later date/time.")
                self.scheduled_sync_checkbox.setChecked(False)
                return

            # Update status label with repeat info
            self.update_scheduled_status_label()

            repeat_type = self.repeat_combo.currentText()
            self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Scheduled sync enabled: {repeat_type}")
        else:
            self.scheduled_status_label.setText("No scheduled sync")
            self.scheduled_status_label.setStyleSheet("color: #888; font-style: italic;")
            self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Scheduled sync disabled")

        # Save settings
        self.save_sync_config()

    def on_scheduled_datetime_changed(self):
        """Handle scheduled datetime changes"""
        if self.scheduled_sync_checkbox.isChecked():
            # Update the status label when time changes
            self.update_scheduled_status_label()

        # Save settings
        self.save_sync_config()

    def on_repeat_changed(self):
        """Handle repeat interval changes"""
        if self.scheduled_sync_checkbox.isChecked():
            self.update_scheduled_status_label()

        # Save settings
        self.save_sync_config()

    def update_scheduled_status_label(self):
        """Update the status label with current schedule info"""
        from PyQt6.QtCore import QDateTime

        scheduled_time = self.scheduled_datetime.dateTime()
        current_time = QDateTime.currentDateTime()

        if scheduled_time > current_time:
            seconds_until = current_time.secsTo(scheduled_time)
            hours = seconds_until // 3600
            minutes = (seconds_until % 3600) // 60

            time_str = scheduled_time.toString("yyyy-MM-dd HH:mm")
            repeat_type = self.repeat_combo.currentData()

            # Build status message based on repeat type
            if repeat_type == "once":
                status = f"⏰ Scheduled for {time_str} (in {hours}h {minutes}m)"
            elif repeat_type == "daily":
                status = f"⏰ Next sync: {time_str} (in {hours}h {minutes}m) • Repeats daily"
            elif repeat_type == "weekdays":
                status = f"⏰ Next sync: {time_str} (in {hours}h {minutes}m) • Repeats weekdays"
            elif repeat_type == "weekly":
                status = f"⏰ Next sync: {time_str} (in {hours}h {minutes}m) • Repeats weekly"
            elif repeat_type == "biweekly":
                status = f"⏰ Next sync: {time_str} (in {hours}h {minutes}m) • Repeats bi-weekly"
            elif repeat_type == "monthly":
                status = f"⏰ Next sync: {time_str} (in {hours}h {minutes}m) • Repeats monthly"
            else:
                status = f"⏰ Scheduled for {time_str} (in {hours}h {minutes}m)"

            self.scheduled_status_label.setText(status)
            self.scheduled_status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            self.scheduled_status_label.setText("⚠️ Scheduled time is in the past")
            self.scheduled_status_label.setStyleSheet("color: #FF9800; font-weight: bold;")

    def check_scheduled_sync(self):
        """Check if it's time to run scheduled sync (called every minute)"""
        # Always process cross-server scheduled jobs, independent of legacy sync scheduler toggle.
        self.check_server_sync_jobs(force_run_due=False)

        if not self.scheduled_sync_checkbox.isChecked():
            return

        from PyQt6.QtCore import QDateTime
        scheduled_time = self.scheduled_datetime.dateTime()
        current_time = QDateTime.currentDateTime()

        # Check if current time has passed or equals the scheduled time
        if current_time >= scheduled_time:
            repeat_type = self.repeat_combo.currentData()

            self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] ⏰ Executing scheduled sync...")

            # Perform the sync
            self.sync_all_playlists()

            # Handle repeat logic
            if repeat_type == "once":
                # One-time sync, disable after execution
                self.scheduled_sync_checkbox.setChecked(False)
                self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] One-time scheduled sync completed")
            elif repeat_type == "daily":
                # Schedule next day at same time
                next_sync = scheduled_time.addDays(1)
                self.scheduled_datetime.setDateTime(next_sync)
                self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Daily sync completed. Next sync: {next_sync.toString('yyyy-MM-dd HH:mm')}")
            elif repeat_type == "weekdays":
                # Schedule next weekday at same time
                next_sync = scheduled_time.addDays(1)
                # Skip weekends (Saturday = 6, Sunday = 7)
                while next_sync.date().dayOfWeek() in [6, 7]:
                    next_sync = next_sync.addDays(1)
                self.scheduled_datetime.setDateTime(next_sync)
                self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Weekday sync completed. Next sync: {next_sync.toString('yyyy-MM-dd HH:mm')}")
            elif repeat_type == "weekly":
                # Schedule 7 days later
                next_sync = scheduled_time.addDays(7)
                self.scheduled_datetime.setDateTime(next_sync)
                self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Weekly sync completed. Next sync: {next_sync.toString('yyyy-MM-dd HH:mm')}")
            elif repeat_type == "biweekly":
                # Schedule 14 days later
                next_sync = scheduled_time.addDays(14)
                self.scheduled_datetime.setDateTime(next_sync)
                self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Bi-weekly sync completed. Next sync: {next_sync.toString('yyyy-MM-dd HH:mm')}")
            elif repeat_type == "monthly":
                # Schedule 30 days later
                next_sync = scheduled_time.addDays(30)
                self.scheduled_datetime.setDateTime(next_sync)
                self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Monthly sync completed. Next sync: {next_sync.toString('yyyy-MM-dd HH:mm')}")

            # Save the updated schedule
            self.save_sync_config()
        else:
            # Update countdown display
            self.update_scheduled_status_label()

    def add_sync_config(self):
        """Add new sync configuration"""
        playlist_name = self.sync_playlist_combo.currentText()
        source_url = self.sync_source_input.text().strip()
        
        if not playlist_name or playlist_name == "Select playlist...":
            QMessageBox.warning(self, "Invalid Selection", "Please select a playlist.")
            return
        
        if not source_url:
            QMessageBox.warning(self, "Invalid Source", "Please enter a source URL or file path.")
            return
        
        # Add to sync configurations table
        row = self.sync_configs_table.rowCount()
        self.sync_configs_table.insertRow(row)
        
        # Create read-only items
        playlist_item = QTableWidgetItem(playlist_name)
        playlist_item.setFlags(playlist_item.flags() & ~Qt.ItemIsEditable)
        self.sync_configs_table.setItem(row, 0, playlist_item)
        
        source_item = QTableWidgetItem(source_url)
        source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
        self.sync_configs_table.setItem(row, 1, source_item)
        
        sync_item = QTableWidgetItem("Never")
        sync_item.setFlags(sync_item.flags() & ~Qt.ItemIsEditable)
        self.sync_configs_table.setItem(row, 2, sync_item)
        
        self._set_clear_on_sync_checkbox(row, False)

        # Create better styled action buttons
        self.create_action_buttons_for_row(row)
        
        # Clear inputs
        self.sync_source_input.clear()
        
        self.save_sync_config()
        self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Added sync config for '{playlist_name}'")
    
    def _set_clear_on_sync_checkbox(self, row, checked=False):
        """Add or update the clear-before-sync checkbox for a table row."""
        checkbox = QCheckBox()
        checkbox.setChecked(bool(checked))
        checkbox.setToolTip("Clear the Plex playlist before adding new tracks during sync")
        checkbox.stateChanged.connect(lambda _state: self.save_sync_config())

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignCenter)
        layout.addWidget(checkbox)

        self.sync_configs_table.setCellWidget(row, 3, container)
        return checkbox

    def _is_clear_before_sync_enabled(self, row):
        """Read the clear-before-sync checkbox state for a table row."""
        container = self.sync_configs_table.cellWidget(row, 3)
        if not container:
            return False
        checkbox = container.findChild(QCheckBox)
        return checkbox.isChecked() if checkbox else False

    def create_action_buttons_for_row(self, row):
        """Create properly sized and visible action buttons for sync config row"""
        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(2, 2, 2, 2)
        actions_layout.setSpacing(5)
        
        # FIXED: Properly sized buttons with clear text labels
        sync_btn = QPushButton("Sync Now")
        sync_btn.setToolTip("Sync this playlist now")
        sync_btn.setFixedSize(80, 32)  # Fixed size for visibility
        sync_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        sync_btn.clicked.connect(lambda: self.sync_single_playlist(row))
        actions_layout.addWidget(sync_btn)
        
        # Delete button with proper sizing
        delete_btn = QPushButton("Delete")
        delete_btn.setToolTip("Delete this sync configuration")
        delete_btn.setFixedSize(80, 32)  # Fixed size for visibility
        delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 12px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #c1170a;
            }
        """)
        delete_btn.clicked.connect(lambda: self.delete_sync_config(row))
        actions_layout.addWidget(delete_btn)
        
        # FIXED: Set the widget properly and ensure table row height accommodates buttons
        self.sync_configs_table.setCellWidget(row, 4, actions_widget)
        self.sync_configs_table.setRowHeight(row, 40)  # Ensure row is tall enough
    
    def sync_single_playlist(self, row):
        """Sync a single playlist"""
        try:
            playlist_name = self.sync_configs_table.item(row, 0).text()
            source_url = self.sync_configs_table.item(row, 1).text()
            
            config = {
                playlist_name: {
                    'source_url': source_url,
                    'library_section': self.section_combo.currentData(),
                    'clear_before_sync': self._is_clear_before_sync_enabled(row)
                }
            }
            
            self.start_sync(config)
        except Exception as e:
            logging.error(f"Error syncing single playlist: {str(e)}")
            QMessageBox.warning(self, "Sync Error", f"Failed to sync playlist: {str(e)}")
    
    def delete_sync_config(self, row):
        """Delete sync configuration"""
        try:
            playlist_name = self.sync_configs_table.item(row, 0).text()
            reply = QMessageBox.question(self, "Confirm Deletion", 
                                       f"Delete sync configuration for '{playlist_name}'?",
                                       QMessageBox.Yes | QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                self.sync_configs_table.removeRow(row)
                self.save_sync_config()
                self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Deleted sync config for '{playlist_name}'")
                # FIXED: Refresh buttons after deletion to maintain correct row indices
                self.refresh_sync_table_buttons()
                self.update_dashboard_metrics()
        except Exception as e:
            logging.error(f"Error deleting sync config: {str(e)}")
            QMessageBox.warning(self, "Delete Error", f"Failed to delete sync config: {str(e)}")
    
    def refresh_sync_table_buttons(self):
        """Refresh all sync table buttons after row operations"""
        for row in range(self.sync_configs_table.rowCount()):
            self.create_action_buttons_for_row(row)
    
    def load_sync_config(self):
        """Load sync configurations from file"""
        try:
            if os.path.exists(SYNC_CONFIG_FILE):
                with open(SYNC_CONFIG_FILE, 'r') as f:
                    sync_config = json.load(f)

                logging.info(f"Loading sync config from {SYNC_CONFIG_FILE}")

                # Load sync configurations into table
                playlists = sync_config.get('sync_playlists', {})
                logging.info(f"Found {len(playlists)} sync playlist configuration(s)")

                for playlist_name, config in playlists.items():
                    row = self.sync_configs_table.rowCount()
                    self.sync_configs_table.insertRow(row)
                    
                    # Create read-only items
                    playlist_item = QTableWidgetItem(playlist_name)
                    playlist_item.setFlags(playlist_item.flags() & ~Qt.ItemIsEditable)
                    self.sync_configs_table.setItem(row, 0, playlist_item)
                    
                    source_item = QTableWidgetItem(config.get('source_url', ''))
                    source_item.setFlags(source_item.flags() & ~Qt.ItemIsEditable)
                    self.sync_configs_table.setItem(row, 1, source_item)
                    
                    sync_item = QTableWidgetItem(config.get('last_sync', 'Never'))
                    sync_item.setFlags(sync_item.flags() & ~Qt.ItemIsEditable)
                    self.sync_configs_table.setItem(row, 2, sync_item)

                    self._set_clear_on_sync_checkbox(row, config.get('clear_before_sync', False))
                    
                    # Add styled action buttons
                    self.create_action_buttons_for_row(row)
                
                # Load auto-sync settings
                self.auto_sync_checkbox.setChecked(sync_config.get('auto_sync', False))
                self.sync_interval_spinbox.setValue(sync_config.get('sync_interval', 60))

                # Load scheduled sync settings
                from PyQt6.QtCore import QDateTime
                scheduled_enabled = sync_config.get('scheduled_sync_enabled', False)
                scheduled_datetime_str = sync_config.get('scheduled_sync_datetime', '')
                scheduled_repeat = sync_config.get('scheduled_sync_repeat', 'once')

                # Load repeat setting
                repeat_index = self.repeat_combo.findData(scheduled_repeat)
                if repeat_index >= 0:
                    self.repeat_combo.setCurrentIndex(repeat_index)

                if scheduled_datetime_str:
                    try:
                        scheduled_dt = QDateTime.fromString(scheduled_datetime_str, "yyyy-MM-dd HH:mm")
                        # Only load if the scheduled time is still in the future (or if it's a recurring sync)
                        if scheduled_dt > QDateTime.currentDateTime() or scheduled_repeat != 'once':
                            self.scheduled_datetime.setDateTime(scheduled_dt)
                            self.scheduled_sync_checkbox.setChecked(scheduled_enabled)
                        else:
                            # Past one-time scheduled sync, reset to default (1 hour from now)
                            self.scheduled_datetime.setDateTime(QDateTime.currentDateTime().addSecs(3600))
                            logging.info("One-time scheduled sync time was in the past, resetting to default")
                    except Exception as dt_error:
                        logging.warning(f"Could not parse scheduled datetime: {dt_error}")
                        self.scheduled_datetime.setDateTime(QDateTime.currentDateTime().addSecs(3600))
            else:
                logging.info(f"Sync config file not found: {SYNC_CONFIG_FILE}")

        except Exception as e:
            logging.error(f"Error loading sync config: {str(e)}")
            import traceback
            logging.error(traceback.format_exc())
        self.update_dashboard_metrics()
    
    def sync_selected_playlists(self):
        """Sync selected playlists from the table"""
        flow_id = new_flow_id("sync")
        self._active_sync_flow_id = flow_id
        self._active_sync_start = time.perf_counter()
        log_event("sync_selected_requested", flow_id=flow_id, source="ui")
        selected_configs = {}
        
        for row in range(self.sync_configs_table.rowCount()):
            if self.sync_configs_table.item(row, 0).isSelected():
                playlist_name = self.sync_configs_table.item(row, 0).text()
                source_url = self.sync_configs_table.item(row, 1).text()
                selected_configs[playlist_name] = {
                    'source_url': source_url,
                    'library_section': self.section_combo.currentData(),
                    'clear_before_sync': self._is_clear_before_sync_enabled(row)
                }
        
        if not selected_configs:
            QMessageBox.warning(self, "No Selection", "Please select sync configurations to sync.")
            return
        
        self.start_sync(selected_configs)
    
    def sync_all_playlists(self):
        """Sync all configured playlists"""
        all_configs = {}
        
        for row in range(self.sync_configs_table.rowCount()):
            playlist_name = self.sync_configs_table.item(row, 0).text()
            source_url = self.sync_configs_table.item(row, 1).text()
            all_configs[playlist_name] = {
                'source_url': source_url,
                'library_section': self.section_combo.currentData(),
                'clear_before_sync': self._is_clear_before_sync_enabled(row)
            }
        
        if not all_configs:
            QMessageBox.warning(self, "No Configurations", "No sync configurations found.")
            return
        
        self.start_sync(all_configs)
    
    def start_sync(self, sync_configs):
        """Start sync process"""
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return
        flow_id = getattr(self, "_active_sync_flow_id", new_flow_id("sync"))
        log_event("sync_started", flow_id=flow_id, playlist_count=len(sync_configs), source="ui")
        
        self.sync_progress_group.setVisible(True)
        self.sync_status_label.setText("Initializing sync...")
        self.sync_progress_bar.setValue(0)
        
        self.sync_thread = SyncThread(sync_configs, self.plex_server, self)
        self.sync_thread.progress_update.connect(self.update_sync_progress)
        self.sync_thread.sync_complete.connect(self.sync_playlist_complete)
        self.sync_thread.error.connect(self.sync_error)
        self.sync_thread.finished.connect(self.sync_finished)
        self.sync_thread.start()
    
    def update_sync_progress(self, message, percentage):
        """Update sync progress"""
        self.sync_status_label.setText(message)
        self.sync_progress_bar.setValue(percentage)
    
    def sync_playlist_complete(self, playlist_name, added_tracks, total_tracks):
        """Handle individual playlist sync completion"""
        flow_id = getattr(self, "_active_sync_flow_id", None)
        log_event(
            "sync_playlist_complete",
            flow_id=flow_id,
            playlist_id=playlist_name,
            added_tracks=added_tracks,
            total_tracks=total_tracks,
            source="sync_thread",
        )
        message = f"[{datetime.now().strftime('%H:%M:%S')}] {playlist_name}: Added {added_tracks} new tracks"
        self.sync_log.append(message)
        
        # Update last sync time in table
        for row in range(self.sync_configs_table.rowCount()):
            if self.sync_configs_table.item(row, 0).text() == playlist_name:
                sync_time_item = QTableWidgetItem(datetime.now().strftime('%Y-%m-%d %H:%M'))
                sync_time_item.setFlags(sync_time_item.flags() & ~Qt.ItemIsEditable)
                self.sync_configs_table.setItem(row, 2, sync_time_item)
                break
    
    def sync_error(self, error_message):
        """Handle sync error"""
        flow_id = getattr(self, "_active_sync_flow_id", None)
        log_event("sync_error", flow_id=flow_id, error=error_message, source="sync_thread")
        self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {error_message}")
        QMessageBox.warning(self, "Sync Error", error_message)
    
    def sync_finished(self):
        """Handle sync completion"""
        flow_id = getattr(self, "_active_sync_flow_id", None)
        start = getattr(self, "_active_sync_start", None)
        if start:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            log_event("sync_finished", flow_id=flow_id, elapsed_ms=elapsed_ms, source="sync_thread")
        self.sync_progress_group.setVisible(False)
        self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Sync completed")
        self.statusBar().showMessage("Sync completed")
    
    def stop_sync(self):
        """Stop sync process"""
        if self.sync_thread and self.sync_thread.isRunning():
            self.sync_thread.stop()
            self.sync_thread.wait()
            self.sync_progress_group.setVisible(False)
            self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Sync stopped by user")
    
    def perform_auto_sync(self):
        """Perform automatic sync"""
        if self.auto_sync_checkbox.isChecked():
            self.sync_log.append(f"[{datetime.now().strftime('%H:%M:%S')}] Starting auto-sync...")
            self.sync_all_playlists()
    
    def save_sync_config(self):
        """Save sync configurations to file"""
        try:
            configs = {}
            for row in range(self.sync_configs_table.rowCount()):
                playlist_name = self.sync_configs_table.item(row, 0).text()
                source_url = self.sync_configs_table.item(row, 1).text()
                last_sync = self.sync_configs_table.item(row, 2).text()
                
                configs[playlist_name] = {
                    'source_url': source_url,
                    'last_sync': last_sync,
                    'library_section': self.section_combo.currentData(),
                    'clear_before_sync': self._is_clear_before_sync_enabled(row)
                }
            
            sync_config = {
                'sync_playlists': configs,
                'auto_sync': self.auto_sync_checkbox.isChecked(),
                'sync_interval': self.sync_interval_spinbox.value(),
                'scheduled_sync_enabled': self.scheduled_sync_checkbox.isChecked(),
                'scheduled_sync_datetime': self.scheduled_datetime.dateTime().toString("yyyy-MM-dd HH:mm"),
                'scheduled_sync_repeat': self.repeat_combo.currentData()
            }

            with open(SYNC_CONFIG_FILE, 'w') as f:
                json.dump(sync_config, f, indent=4)
                
        except Exception as e:
            logging.error(f"Error saving sync config: {str(e)}")

    # Tools and utilities methods
    def find_duplicate_tracks(self):
        """Find duplicate tracks in entire music library using background thread"""
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return

        # Prevent multiple simultaneous scans
        if hasattr(self, 'duplicates_thread') and self.duplicates_thread.isRunning():
            QMessageBox.information(self, "Scan in Progress", "Library duplicate scan is already running. Please wait...")
            return

        # Create custom dialog for scan options
        scan_dialog = QDialog(self)
        scan_dialog.setWindowTitle("Library Duplicate Scan Options")
        scan_dialog.setModal(True)
        scan_dialog.resize(500, 300)

        layout = QVBoxLayout(scan_dialog)

        # Header
        header = QLabel("🔍 Configure Library Duplicate Scan")
        header.setStyleSheet("font-size: 16px; font-weight: bold; color: #2196F3; padding: 10px;")
        layout.addWidget(header)

        # Description
        desc = QLabel("This will scan your entire music library for duplicate tracks based on title and artist matching.")
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; padding: 10px; font-size: 14px;")
        layout.addWidget(desc)

        # Options group
        options_group = QGroupBox("Scan Options")
        options_layout = QVBoxLayout(options_group)

        # Playlist checking option
        check_playlists_cb = QCheckBox("📝 Check which playlists contain duplicates")
        check_playlists_cb.setChecked(True)
        check_playlists_cb.setStyleSheet("font-size: 14px; padding: 8px;")
        options_layout.addWidget(check_playlists_cb)

        playlist_warning = QLabel("⚠️ Playlist checking can add significant time for large libraries but provides valuable information for decision-making.")
        playlist_warning.setWordWrap(True)
        playlist_warning.setStyleSheet("color: #ff9800; font-size: 12px; font-style: italic; padding: 5px 20px;")
        options_layout.addWidget(playlist_warning)

        # Fast scan info
        fast_info = QLabel("💨 Disable playlist checking for faster scanning (you can still see full track details and delete safely)")
        fast_info.setWordWrap(True)
        fast_info.setStyleSheet("color: #4CAF50; font-size: 12px; padding: 5px 20px;")
        options_layout.addWidget(fast_info)

        layout.addWidget(options_group)

        # Time estimate
        time_estimate = QLabel("⏱️ Estimated time: 30 seconds - 5 minutes depending on library size and options")
        time_estimate.setStyleSheet("color: #666; font-style: italic; padding: 10px; text-align: center;")
        layout.addWidget(time_estimate)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(scan_dialog.reject)
        button_layout.addWidget(cancel_btn)

        start_btn = QPushButton("🚀 Start Scan")
        start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        start_btn.clicked.connect(scan_dialog.accept)
        start_btn.setDefault(True)
        button_layout.addWidget(start_btn)

        layout.addLayout(button_layout)

        # Show dialog and get result
        if scan_dialog.exec() != QDialog.Accepted:
            return

        # Get scan options
        include_playlist_check = check_playlists_cb.isChecked()

        # Show loading dialog
        self.show_loading("Scanning music library for duplicates...", "Initializing library scan...")

        # Disable the button to prevent multiple clicks
        self.find_duplicates_btn.setEnabled(False)
        self.find_duplicates_btn.setText("Scanning Library...")

        # Start background scan with options
        self.duplicates_thread = LibraryDuplicateFinderThread(self.plex_server, self)
        self.duplicates_thread.include_playlist_check = include_playlist_check
        self.duplicates_thread.progress_update.connect(self.update_duplicates_progress)
        self.duplicates_thread.duplicates_found.connect(self.on_library_duplicates_found)
        self.duplicates_thread.error.connect(self.on_duplicates_error)
        self.duplicates_thread.finished.connect(self.on_duplicates_finished)
        self.duplicates_thread.start()
    
    def sanitize_filename(self, filename, max_length=255):
        """
        Sanitize filename by replacing invalid characters with safe alternatives
        """
        import re
        
        # Dictionary of replacements for common invalid characters
        replacements = {
            '/': '_',           # Forward slash
            '\\': '_',          # Backslash  
            ':': ' -',          # Colon
            '*': '',            # Asterisk
            '?': '',            # Question mark
            '"': "'",           # Double quote to single quote
            '<': '(',           # Less than
            '>': ')',           # Greater than
            '|': '-',           # Pipe
            '\n': ' ',          # Newline
            '\r': ' ',          # Carriage return
            '\t': ' ',          # Tab
        }
        
        # Apply character replacements
        sanitized = filename
        for invalid_char, replacement in replacements.items():
            sanitized = sanitized.replace(invalid_char, replacement)
        
        # Remove any remaining control characters
        sanitized = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', sanitized)
        
        # Clean up multiple spaces and trim
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        
        # Handle Windows reserved names
        windows_reserved = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 
                           'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 
                           'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9']
        
        name_without_ext = sanitized.rsplit('.', 1)[0] if '.' in sanitized else sanitized
        if name_without_ext.upper() in windows_reserved:
            sanitized = f"Playlist_{sanitized}"
        
        # Ensure filename isn't empty
        if not sanitized or sanitized.isspace():
            sanitized = "Unnamed_Playlist"
        
        # Truncate if too long (leave room for .m3u extension)
        if len(sanitized) > max_length - 4:
            sanitized = sanitized[:max_length - 4].rstrip()
        
        # Remove trailing periods (Windows issue)
        sanitized = sanitized.rstrip('.')
        
        return sanitized

    def update_duplicates_progress(self, message, percentage):
        """Update duplicate scan progress"""
        if self.loading_dialog:
            self.loading_dialog.update_progress(message, percentage)
        self.statusBar().showMessage(f"{message} ({percentage}%)")
    
    def on_duplicates_found(self, duplicate_tracks):
        """Handle duplicate tracks found"""
        self.hide_loading()
        
        if duplicate_tracks:
            # Display duplicates in a dialog
            dialog = QDialog(self)
            dialog.setWindowTitle("Duplicate Tracks Found")
            dialog.resize(600, 400)
            
            layout = QVBoxLayout(dialog)
            layout.addWidget(QLabel(f"Found {len(duplicate_tracks)} duplicate tracks:"))
            
            text_edit = QTextEdit()
            text_edit.setReadOnly(True)
            
            for signature, occurrences in duplicate_tracks:
                text_edit.append(f"\nTrack: {signature.replace('_', ' - ')}")
                for playlist_name, track in occurrences:
                    text_edit.append(f"  - In playlist: {playlist_name}")
            
            layout.addWidget(text_edit)
            
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(dialog.close)
            layout.addWidget(close_btn)
            
            dialog.exec()
            
            self.statusBar().showMessage(f"Found {len(duplicate_tracks)} duplicate tracks")
        else:
            QMessageBox.information(self, "No Duplicates", "No duplicate tracks found across playlists.")
            self.statusBar().showMessage("No duplicate tracks found")
    
    def on_duplicates_error(self, error_message):
        """Handle duplicate scan error"""
        self.hide_loading()
        logging.error(f"Duplicate scan error: {error_message}")
        QMessageBox.critical(self, "Scan Error", f"Error scanning for duplicates: {error_message}")
        self.statusBar().showMessage("Duplicate scan failed")
    
    def on_library_duplicates_found(self, duplicate_groups):
        """Handle library duplicate scan results with professional management UI"""
        self.hide_loading()

        if not duplicate_groups:
            QMessageBox.information(self, "No Duplicates Found",
                                  "🎉 Great news! No duplicate tracks were found in your music library.\n\n"
                                  "Your library is clean and well-organized!")
            return

        # Create professional duplicate management dialog
        dialog = LibraryDuplicateManagerDialog(duplicate_groups, self.plex_server, self)
        dialog.exec()

    def on_duplicates_finished(self):
        """Handle duplicate scan completion"""
        # Re-enable the button
        self.find_duplicates_btn.setEnabled(True)
        self.find_duplicates_btn.setText("🔍 Find Library Duplicates")
    
    def backup_all_playlists(self):
        """FIXED: Backup all playlists using background thread to prevent UI freezing"""
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return
        
        backup_dir = QFileDialog.getExistingDirectory(self, "Select Backup Directory")
        if not backup_dir:
            return
        
        # Prevent multiple simultaneous backups
        if self.backup_thread and self.backup_thread.isRunning():
            QMessageBox.information(self, "Backup in Progress", "A backup is already in progress. Please wait...")
            return
        
        # Show loading dialog
        self.show_loading("Starting backup...", "Preparing playlist backup...")
        
        # Disable backup button to prevent multiple clicks
        self.backup_playlists_btn.setEnabled(False)
        self.backup_playlists_btn.setText("Backing up...")
        
        # Start background backup
        self.backup_thread = BackupThread(self.plex_server, backup_dir, self)
        self.backup_thread.progress_update.connect(self.update_backup_progress)
        self.backup_thread.backup_complete.connect(self.on_backup_complete)
        self.backup_thread.error.connect(self.on_backup_error)
        self.backup_thread.finished.connect(self.on_backup_finished)
        self.backup_thread.start()
    
    def update_backup_progress(self, message, percentage):
        """Update backup progress"""
        if self.loading_dialog:
            self.loading_dialog.update_progress(message, percentage)
        self.statusBar().showMessage(f"{message} ({percentage}%)")
    
    def on_backup_complete(self, backed_up_count, backup_folder):
        """Handle backup completion"""
        self.hide_loading()
        QMessageBox.information(self, "Backup Complete", 
                              f"Successfully backed up {backed_up_count} playlists to:\n{backup_folder}")
        self.statusBar().showMessage(f"Backup completed: {backed_up_count} playlists")
    
    def on_backup_error(self, error_message):
        """Handle backup error"""
        self.hide_loading()
        logging.error(f"Backup error: {error_message}")
        QMessageBox.critical(self, "Backup Error", f"Backup failed: {error_message}")
        self.statusBar().showMessage("Backup failed")
    
    def on_backup_finished(self):
        """Handle backup thread finished (success or error)"""
        # Re-enable backup button
        self.backup_playlists_btn.setEnabled(True)
        self.backup_playlists_btn.setText("Backup All Playlists")
    
    def restore_playlists(self):
        """Restore playlists from backup directory"""
        backup_dir = QFileDialog.getExistingDirectory(self, "Select Backup Directory")
        if not backup_dir:
            return
        
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return
        
        try:
            m3u_files = [f for f in os.listdir(backup_dir) if f.endswith('.m3u')]
            
            if not m3u_files:
                QMessageBox.warning(self, "No Files", "No M3U files found in the selected directory.")
                return
            
            reply = QMessageBox.question(self, "Confirm Restore", 
                                       f"Found {len(m3u_files)} playlist files. Restore all?",
                                       QMessageBox.Yes | QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                restored = 0
                for m3u_file in m3u_files:
                    try:
                        file_path = os.path.join(backup_dir, m3u_file)
                        self.upload_playlist(file_path)
                        restored += 1
                    except Exception as file_error:
                        logging.error(f"Error restoring {m3u_file}: {str(file_error)}")
                        continue
                
                QMessageBox.information(self, "Restore Complete", 
                                      f"Successfully restored {restored} playlists.")
                self.fetch_playlists()  # Refresh playlist list
                
        except Exception as e:
            logging.error(f"Error during restore: {str(e)}")
            QMessageBox.critical(self, "Restore Error", f"Failed to restore playlists: {str(e)}")
    
    def update_playlist_statistics(self):
        """Update and display playlist statistics"""
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return
        
        try:
            playlists = self.plex_server.playlists()
            
            total_playlists = len(playlists)
            total_tracks = 0
            playlist_sizes = []
            largest_playlist = None
            smallest_playlist = None
            largest_count = 0
            smallest_count = None
            
            for playlist in playlists:
                try:
                    track_count = len(list(playlist.items()))
                    total_tracks += track_count
                    playlist_sizes.append(track_count)
                    
                    if largest_playlist is None or track_count > largest_count:
                        largest_playlist = playlist
                        largest_count = track_count
                    
                    if smallest_playlist is None or smallest_count is None or track_count < smallest_count:
                        smallest_playlist = playlist
                        smallest_count = track_count
                        
                except Exception as playlist_error:
                    logging.warning(f"Error analyzing playlist {playlist.title}: {str(playlist_error)}")
                    continue
            
            if playlist_sizes:
                avg_tracks = sum(playlist_sizes) / len(playlist_sizes)
                
                stats_text = f"""
Playlist Statistics:
━━━━━━━━━━━━━━━━━━━━━━

📊 Total Playlists: {total_playlists}
🎵 Total Tracks: {total_tracks:,}
📈 Average Tracks per Playlist: {avg_tracks:.1f}

📍 Largest Playlist: {largest_playlist.title if largest_playlist else 'N/A'} ({largest_count if largest_playlist else 0} tracks)
📍 Smallest Playlist: {smallest_playlist.title if smallest_playlist else 'N/A'} ({smallest_count if smallest_playlist else 0} tracks)

🔢 Distribution:
  • Empty playlists: {sum(1 for size in playlist_sizes if size == 0)}
  • Small (1-10 tracks): {sum(1 for size in playlist_sizes if 1 <= size <= 10)}
  • Medium (11-50 tracks): {sum(1 for size in playlist_sizes if 11 <= size <= 50)}
  • Large (51-100 tracks): {sum(1 for size in playlist_sizes if 51 <= size <= 100)}
  • Very Large (100+ tracks): {sum(1 for size in playlist_sizes if size > 100)}

Last Updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                """
                
                self.stats_text.setText(stats_text)
            else:
                self.stats_text.setText("No playlist data available.")
                
        except Exception as e:
            logging.error(f"Error updating statistics: {str(e)}")
            QMessageBox.critical(self, "Statistics Error", f"Failed to update statistics: {str(e)}")
    
    def analyze_music_library(self):
        """Analyze the music library"""
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return
        
        section_id = self.section_combo.currentData()
        if not section_id:
            QMessageBox.warning(self, "No Library Selected", "Please select a music library section.")
            return
        
        try:
            library_section = self.plex_server.library.sectionByID(section_id)
            
            # Get artists, albums, and tracks
            artists = library_section.searchArtists()
            albums = library_section.searchAlbums()
            tracks = library_section.searchTracks()
            
            # Calculate total duration
            total_duration = 0
            for track in tracks[:1000]:  # Limit to first 1000 tracks for performance
                if hasattr(track, 'duration') and track.duration:
                    total_duration += track.duration
            
            # Estimate total duration based on sample
            if len(tracks) > 1000:
                avg_duration = total_duration / 1000
                estimated_total = avg_duration * len(tracks)
            else:
                estimated_total = total_duration
            
            # Convert milliseconds to hours
            total_hours = estimated_total / (1000 * 60 * 60)
            
            # Get top genres (if available)
            genres = set()
            for track in tracks[:500]:  # Sample for genres
                if hasattr(track, 'genres'):
                    for genre in track.genres:
                        genres.add(genre.tag)
            
            analysis_text = f"""
Music Library Analysis:
━━━━━━━━━━━━━━━━━━━━━━

📚 Library: {library_section.title}
🎤 Artists: {len(artists):,}
💿 Albums: {len(albums):,}
🎵 Tracks: {len(tracks):,}

⏱️ Total Duration: ~{total_hours:.1f} hours
📊 Average Album Size: {len(tracks) / len(albums) if albums else 0:.1f} tracks

🎭 Unique Genres: {len(genres)}
Top Genres: {', '.join(list(genres)[:10]) if genres else 'Not available'}

📈 Collection Insights:
  • Tracks per Artist: {len(tracks) / len(artists) if artists else 0:.1f}
  • Albums per Artist: {len(albums) / len(artists) if artists else 0:.1f}
  • Your library would take ~{total_hours / 24:.1f} days to play through

🔍 Quality Metrics:
  • {"Well-organized" if len(albums) / len(artists) > 2 else "Could use more albums per artist"}
  • {"Rich collection" if len(tracks) > 1000 else "Growing collection"}

Last Analyzed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            self.analysis_text.setText(analysis_text)
            
        except Exception as e:
            logging.error(f"Error analyzing library: {str(e)}")
            QMessageBox.critical(self, "Analysis Error", f"Failed to analyze library: {str(e)}")

    def fetch_playlists(self):
        """Fetch playlists with on-demand track count loading"""
        flow_id = new_flow_id("fetch")
        self._active_fetch_flow_id = flow_id
        self._active_fetch_start = time.perf_counter()
        log_event("playlist_fetch_requested", flow_id=flow_id, source="ui")
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return

        # Prevent multiple simultaneous fetches
        if self.fetch_thread and self.fetch_thread.isRunning():
            QMessageBox.information(self, "Already Loading", "Playlists are already being fetched. Please wait...")
            return

        try:
            with timed("playlist_fetch_start", flow_id=flow_id, source="ui"):
                # Show loading dialog
                if not self.loading_dialog:
                    self.loading_dialog = LoadingDialog(self)

                self.loading_dialog.update_progress("Initializing...", 0)
                self.loading_dialog.show()

                # Disable fetch button to prevent multiple clicks
                self.fetch_playlists_button.setEnabled(False)
                self.fetch_playlists_button.setText("Loading...")

                # Start background fetch (now much faster - no track counts!)
                self.fetch_thread = FetchPlaylistsThread(self.plex_server, self.playlist_cache, self)
                self.fetch_thread.progress_update.connect(self.update_fetch_progress)
                self.fetch_thread.playlists_fetched.connect(self.on_playlists_fetched)
                self.fetch_thread.error.connect(self.on_fetch_error)
                self.fetch_thread.finished.connect(self.on_fetch_finished)
                self.fetch_thread.start()
            
        except Exception as e:
            self.on_fetch_error(f"Failed to start playlist fetch: {str(e)}")

    def update_fetch_progress(self, message, percentage):
        """Update fetch progress"""
        if self.loading_dialog:
            self.loading_dialog.update_progress(message, percentage)
        
        # Also update status bar
        self.statusBar().showMessage(f"{message} ({percentage}%)")

    def on_playlists_fetched(self, playlist_data):
        """Handle successful playlist fetch"""
        try:
            flow_id = getattr(self, "_active_fetch_flow_id", None)
            self.playlist_data = playlist_data
            self.playlists = [playlist for playlist, _ in playlist_data]
            self.update_playlist_listwidget()
            self.populate_sync_playlist_combo()  # Update sync combo too
            self.refresh_listenbrainz_export_combo()
            
            total_playlists = len(self.playlists)
            cached_count = sum(1 for _, count in playlist_data if count is not None)
            
            status_msg = f"Loaded {total_playlists} playlists ({cached_count} with cached track counts)"
            self.statusBar().showMessage(status_msg)
            log_event("playlist_fetch_success", flow_id=flow_id, total_playlists=total_playlists, cached_counts=cached_count)
            
            # Update cache info
            self.cache_info_label.setText(f"💡 {total_playlists} playlists loaded. {cached_count} have cached track counts. Click 'Refresh All Counts' to load missing counts.")
            self.update_dashboard_metrics()
            
        except Exception as e:
            logging.error(f"Error processing fetched playlists: {str(e)}")
            self.statusBar().showMessage(f"Error processing playlists: {str(e)}")

    def on_fetch_error(self, error_message):
        """Handle fetch error"""
        flow_id = getattr(self, "_active_fetch_flow_id", None)
        log_event("playlist_fetch_error", flow_id=flow_id, error=error_message)
        logging.error(f"Playlist fetch error: {error_message}")
        QMessageBox.critical(self, "Fetch Error", f"Error fetching playlists:\n{error_message}")
        self.statusBar().showMessage("Failed to fetch playlists.")

    def on_fetch_finished(self):
        """Handle fetch completion (success or error)"""
        flow_id = getattr(self, "_active_fetch_flow_id", None)
        start = getattr(self, "_active_fetch_start", None)
        if start:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            log_event("playlist_fetch_finished", flow_id=flow_id, elapsed_ms=elapsed_ms)
        # Hide loading dialog
        if self.loading_dialog:
            self.loading_dialog.hide()
        
        # Re-enable fetch button
        self.fetch_playlists_button.setEnabled(True)
        self.fetch_playlists_button.setText("Fetch Playlists")

    def update_playlist_listwidget(self):
        """Update playlist list widget with on-demand track count loading"""
        self.playlist_listwidget.clear()
        
        for playlist, track_count in self.playlist_data:
            try:
                # Display playlist with track count (or "..." if not cached)
                if track_count is not None:
                    item_text = f"{playlist.title} ({track_count} tracks)"
                else:
                    item_text = f"{playlist.title} (click to load tracks...)"
                
                item = QListWidgetItem(item_text)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                
                # Store playlist object for easy access
                item.setData(Qt.UserRole, playlist)
                
                self.playlist_listwidget.addItem(item)
                
            except Exception as e:
                logging.warning(f"Error adding playlist {playlist.title} to list: {str(e)}")
                # Fallback: add without track count
                item = QListWidgetItem(playlist.title)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                item.setData(Qt.UserRole, playlist)
                self.playlist_listwidget.addItem(item)

    def load_track_count_on_demand(self, playlist):
        """Load track count for a specific playlist on-demand"""
        playlist_id = str(playlist.ratingKey)  # Convert to string
        
        if playlist_id in self.track_count_threads:
            return  # Already loading
        
        # Check if already cached
        cached_count = self.playlist_cache.get_track_count(playlist_id)
        if cached_count is not None:
            self.update_playlist_item_count(playlist_id, cached_count)
            return
        
        # Start background loading
        thread = LoadTrackCountThread(playlist, self.playlist_cache, self)
        thread.track_count_loaded.connect(self.on_track_count_loaded)
        thread.error.connect(self.on_track_count_error)
        thread.finished.connect(lambda: self.track_count_threads.pop(playlist_id, None))
        
        self.track_count_threads[playlist_id] = thread
        thread.start()
        
        # Update UI to show loading
        self.update_playlist_item_loading(playlist_id)

    def on_track_count_loaded(self, playlist_id, track_count):
        """Handle track count loaded event"""
        self.update_playlist_item_count(playlist_id, track_count)
        
        # Update the playlist_data cache in memory too
        for i, (playlist, _) in enumerate(self.playlist_data):
            if str(playlist.ratingKey) == playlist_id:  # Convert to string for comparison
                self.playlist_data[i] = (playlist, track_count)
                break

    def on_track_count_error(self, playlist_id, error_message):
        """Handle track count loading error"""
        logging.error(f"Error loading track count for playlist {playlist_id}: {error_message}")
        self.update_playlist_item_error(playlist_id)

    def update_playlist_item_count(self, playlist_id, track_count):
        """Update playlist item with track count"""
        for i in range(self.playlist_listwidget.count()):
            item = self.playlist_listwidget.item(i)
            playlist = item.data(Qt.UserRole)
            if playlist and str(playlist.ratingKey) == playlist_id:  # Convert to string for comparison
                item.setText(f"{playlist.title} ({track_count} tracks)")
                break

    def update_playlist_item_loading(self, playlist_id):
        """Update playlist item to show loading state"""
        for i in range(self.playlist_listwidget.count()):
            item = self.playlist_listwidget.item(i)
            playlist = item.data(Qt.UserRole)
            if playlist and str(playlist.ratingKey) == playlist_id:  # Convert to string for comparison
                item.setText(f"{playlist.title} (loading...)")
                break

    def update_playlist_item_error(self, playlist_id):
        """Update playlist item to show error state"""
        for i in range(self.playlist_listwidget.count()):
            item = self.playlist_listwidget.item(i)
            playlist = item.data(Qt.UserRole)
            if playlist and str(playlist.ratingKey) == playlist_id:  # Convert to string for comparison
                item.setText(f"{playlist.title} (error loading tracks)")
                break

    def refresh_all_track_counts(self):
        """FIXED: Refresh track counts for all playlists using optimized batch processing"""
        if not self.playlists:
            QMessageBox.warning(self, "No Playlists", "Please fetch playlists first.")
            return
        
        # Prevent multiple simultaneous refresh operations
        if self.batch_track_count_thread and self.batch_track_count_thread.isRunning():
            QMessageBox.information(self, "Already Loading", "Track counts are already being refreshed. Please wait...")
            return
        
        reply = QMessageBox.question(self, "Refresh All Track Counts", 
                                   f"This will load track counts for all {len(self.playlists)} playlists. This may take a while. Continue?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            # Show loading dialog
            self.show_loading("Loading track counts...", "Initializing batch processing...")
            
            # Disable refresh button
            self.refresh_all_button.setEnabled(False)
            self.refresh_all_button.setText("Loading...")
            
            # Start batch track count loading
            self.batch_track_count_thread = BatchTrackCountThread(self.playlist_data, self.playlist_cache, max_concurrent=3, parent=self)
            self.batch_track_count_thread.progress_update.connect(self.update_batch_progress)
            self.batch_track_count_thread.all_complete.connect(self.on_batch_complete)
            self.batch_track_count_thread.error.connect(self.on_batch_error)
            self.batch_track_count_thread.finished.connect(self.on_batch_finished)
            self.batch_track_count_thread.start()
    
    def update_batch_progress(self, message, percentage):
        """Update batch track count loading progress"""
        if self.loading_dialog:
            self.loading_dialog.update_progress(message, percentage)
        self.statusBar().showMessage(message)
    
    def on_batch_complete(self):
        """Handle batch track count loading completion"""
        self.hide_loading()
        # Refresh the playlist display to show all loaded counts
        self.fetch_playlists()
        QMessageBox.information(self, "Refresh Complete", "All track counts have been loaded and cached.")
    
    def on_batch_error(self, error_message):
        """Handle batch track count loading error"""
        self.hide_loading()
        logging.error(f"Batch track count error: {error_message}")
        QMessageBox.warning(self, "Loading Error", f"Some track counts failed to load: {error_message}")
    
    def on_batch_finished(self):
        """Handle batch track count loading finished"""
        # Re-enable refresh button
        self.refresh_all_button.setEnabled(True)
        self.refresh_all_button.setText("Refresh All Counts")

    def clear_playlist_cache(self):
        """Clear the playlist cache"""
        reply = QMessageBox.question(self, "Clear Cache", 
                                   "This will clear all cached playlist data. Track counts will need to be reloaded. Continue?",
                                   QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.playlist_cache.clear_cache()
            QMessageBox.information(self, "Cache Cleared", "Playlist cache has been cleared.")
            
            # Refresh the display
            if self.playlists:
                # Reset playlist_data to remove cached counts
                self.playlist_data = [(playlist, None) for playlist, _ in self.playlist_data]
                self.update_playlist_listwidget()
                self.cache_info_label.setText("💡 Cache cleared. Track counts will load on-demand.")

    def _create_plex_account(self, username, password):
        """Create a Plex account, using 2FA code when provided."""
        if not username or not password:
            raise ValueError("Plex username and password are required.")

        auth_kwargs = {}
        two_factor_code = self.plex_2fa_input.text().strip() if hasattr(self, "plex_2fa_input") else ""
        if two_factor_code:
            auth_kwargs["code"] = two_factor_code

        try:
            return MyPlexAccount(username, password, **auth_kwargs)
        except Exception as auth_error:
            err_text = str(auth_error).lower()
            is_2fa_related = any(token in err_text for token in [
                "two-factor", "2fa", "verification code", "verification", "otp", "code required"
            ])
            if is_2fa_related and not two_factor_code:
                raise Exception(
                    "This Plex account requires 2FA. Enter your current 2FA code in "
                    "'Plex 2FA Code (optional)' and try again."
                ) from auth_error
            if is_2fa_related and two_factor_code:
                raise Exception(
                    "Invalid or expired Plex 2FA code. Enter a fresh code and try again."
                ) from auth_error
            raise

    def connect_to_plex(self):

        self.section_combo.clear()
        self.section_combo.addItem("Library Section")
        self.section_combo.setCurrentIndex(0)

        try:
            username = self.plex_username_input.text()
            password = self.plex_password_input.text()
            server_ip = self.server_ip_input.text()
            server_port = self.server_port_input.text()
            token = self.token_input.text()

            base_url = f"http://{server_ip}:{server_port}"

            if token:
                # Use token-only auth first to avoid unnecessary 2FA prompts on startup.
                # Account-level login remains available when switching users.
                self.plex_account = None
                self.plex_server = PlexServer(base_url, token)
                # Best-effort: build account context from token so Switch User can work
                # without forcing username/password+2FA each launch.
                try:
                    self.plex_account = MyPlexAccount(token=token)
                except Exception as token_account_error:
                    logging.info(f"Token-based account context unavailable: {token_account_error}")
            else:
                # Authenticate with username and password to get the token
                account = self._create_plex_account(username, password)
                self.plex_account = account
                token = account.authenticationToken
                self.token_input.setText(token)
                self.plex_server = PlexServer(base_url, token)

            # Auto-select saved user during auto-connect
            auto_select_user = getattr(self, '_auto_select_user', None)
            if auto_select_user:
                self._auto_select_user = None  # Reset one-shot flag

            if auto_select_user and self.plex_account:
                logging.info(f"Auto-reconnecting as saved user: {auto_select_user}")

                # Find and switch to the saved user
                if auto_select_user == self.plex_account.username:
                    # Admin user - already connected
                    self.current_user_name = auto_select_user
                    self.is_admin = True
                    self.update_window_title()
                else:
                    # Home user - need to switch
                    try:
                        target_user = None
                        for user in self.plex_account.users():
                            user_name = user.title if hasattr(user, 'title') else str(user)
                            if user_name == auto_select_user:
                                target_user = user
                                break

                        if target_user:
                            # Switch to home user
                            switched_account = self.plex_account.switchHomeUser(target_user)

                            # Connect via resource
                            found_server = False
                            for resource in switched_account.resources():
                                if resource.provides == 'server':
                                    self.plex_server = resource.connect()
                                    found_server = True
                                    logging.info(f"Auto-reconnected to server as '{auto_select_user}' via resource")
                                    break

                            if not found_server:
                                raise Exception("Could not find server resource for home user")

                            self.current_user_name = auto_select_user
                            self.is_admin = False
                            self.update_window_title()
                        else:
                            logging.warning(f"Saved user '{auto_select_user}' not found, using admin")
                            self.current_user_name = self.plex_account.username
                            self.is_admin = True
                            self.update_window_title()

                    except Exception as switch_error:
                        logging.error(f"Failed to auto-switch to home user: {switch_error}")
                        QMessageBox.warning(self, "Auto-Login Failed",
                            f"Could not auto-login as '{auto_select_user}'.\n"
                            f"Logged in as administrator instead.\n\n"
                            f"Error: {str(switch_error)}")
                        self.current_user_name = self.plex_account.username
                        self.is_admin = True
                        self.update_window_title()

            elif auto_select_user and not self.plex_account:
                # Token-only startup path: keep last selected display user without forcing account re-auth.
                self.current_user_name = auto_select_user
                self.is_admin = bool(getattr(self, "_saved_is_admin", True))
                self.update_window_title()

            elif self.plex_account:
                user_dialog = UserSelectionDialog(self.plex_account, self)
                if user_dialog.exec() == QDialog.Accepted:
                    self.current_user = user_dialog.selected_user
                    self.current_user_name = user_dialog.selected_user_name
                    self.is_admin = user_dialog.is_admin

                    # If a home user was selected, use their switched account
                    if not self.is_admin and user_dialog.selected_account:
                        try:
                            # Use the switched account to connect to the server
                            # Find the server resource matching our server IP
                            found_server = False
                            for resource in user_dialog.selected_account.resources():
                                if resource.provides == 'server':
                                    # Connect to this server with the home user's credentials
                                    self.plex_server = resource.connect()
                                    self.token_input.setText(user_dialog.selected_user_token)
                                    found_server = True
                                    logging.info(f"Connected to server via home user resource: {resource.name}")
                                    break

                            if not found_server:
                                # Fallback: try direct connection with user token
                                self.plex_server = PlexServer(base_url, user_dialog.selected_user_token)
                                self.token_input.setText(user_dialog.selected_user_token)
                                logging.info(f"Connected to server with home user token (fallback)")

                        except Exception as user_error:
                            logging.error(f"Failed to connect as home user: {user_error}")
                            QMessageBox.critical(self, "Connection Error",
                                f"Failed to connect as '{self.current_user_name}'.\n\n"
                                f"Error: {str(user_error)}")
                            return
                    else:
                        # Admin user - already connected above
                        pass

                    # Update window title to show current user
                    self.update_window_title()

                    logging.info(f"Logged in as: {self.current_user_name}")
                else:
                    # User cancelled - default to admin
                    self.current_user = None
                    self.current_user_name = self.plex_account.username
                    self.is_admin = True
            else:
                # Token-only manual connect fallback when no account object is available.
                if not self.current_user_name:
                    self.current_user_name = "Connected User"
                self.update_window_title()

            self.populate_library_sections()
            self.populate_sync_playlist_combo()
            self.statusBar().showMessage(f"Successfully connected to Plex as {self.current_user_name}")
            self.save_config()
            self.refresh_feature_dependent_ui()
            if self._startup_auto_fetch_pending:
                self._startup_auto_fetch_pending = False
                QTimer.singleShot(0, self.fetch_playlists)
        except Exception as e:
            logging.error(f"Error connecting to Plex: {str(e)}", exc_info=True)
            QMessageBox.critical(self, "Connection Error", f"Error connecting to Plex: {str(e)}")
            self.refresh_feature_dependent_ui()

    def update_window_title(self):
        """Update window title and user label to show current user"""
        base_title = 'Syncra - Playlist Manager'
        if self.current_user_name:
            if self.is_admin:
                self.setWindowTitle(f"{base_title} - 👤 {self.current_user_name} (Administrator)")
                user_status = f"✅ Connected as: {self.current_user_name} (Administrator)"
            else:
                self.setWindowTitle(f"{base_title} - 👤 {self.current_user_name}")
                user_status = f"✅ Connected as: {self.current_user_name}"

            # Update label if it exists
            if hasattr(self, 'current_user_label'):
                self.current_user_label.setText(user_status)
                self.current_user_label.setStyleSheet("""
                    color: #4CAF50;
                    font-weight: bold;
                    padding: 10px;
                    font-size: 12px;
                """)
        else:
            self.setWindowTitle(base_title)
            if hasattr(self, 'current_user_label'):
                self.current_user_label.setText("Not connected")
                self.current_user_label.setStyleSheet("""
                    color: #aaaaaa;
                    font-style: italic;
                    padding: 10px;
                    font-size: 12px;
                """)

    def switch_user(self):
        """Show user selection dialog to switch active user"""
        # If we don't have plex_account, first try token-based account restore.
        if not self.plex_account:
            token = self.token_input.text().strip()
            if token:
                try:
                    self.plex_account = MyPlexAccount(token=token)
                    logging.info("Recreated Plex account from token for user switching")
                except Exception as token_error:
                    logging.info(f"Token-based account restore failed for switch_user: {token_error}")

        # If token restore did not work, fall back to credentials (+2FA if required).
        if not self.plex_account:
            username = self.plex_username_input.text()
            password = self.plex_password_input.text()

            if not username or not password:
                QMessageBox.warning(self, "Authentication Required",
                    "Please enter your Plex username and password to switch users.\n\n"
                    "If your Plex account uses 2FA, also enter the current code in "
                    "'Plex 2FA Code (optional)' on the Connection tab.")
                return

            try:
                # Recreate the account for user switching
                self.plex_account = self._create_plex_account(username, password)
                logging.info("Recreated Plex account for user switching")
            except Exception as auth_error:
                QMessageBox.critical(self, "Authentication Failed",
                    f"Failed to authenticate with Plex:\n{str(auth_error)}\n\n"
                    f"Please check your credentials in the Connection tab.")
                return

        user_dialog = UserSelectionDialog(self.plex_account, self)
        if user_dialog.exec() == QDialog.Accepted:
            self.current_user = user_dialog.selected_user
            self.current_user_name = user_dialog.selected_user_name
            self.is_admin = user_dialog.is_admin

            # Reconnect with new user's credentials
            try:
                server_ip = self.server_ip_input.text()
                server_port = self.server_port_input.text()
                base_url = f"http://{server_ip}:{server_port}"

                # If a home user was selected, use their switched account
                if not self.is_admin and user_dialog.selected_account:
                    # Use the switched account to connect to the server
                    found_server = False
                    for resource in user_dialog.selected_account.resources():
                        if resource.provides == 'server':
                            self.plex_server = resource.connect()
                            self.token_input.setText(user_dialog.selected_user_token)
                            found_server = True
                            logging.info(f"Switched to server via home user resource: {resource.name}")
                            break

                    if not found_server:
                        # Fallback: try direct connection with user token
                        self.plex_server = PlexServer(base_url, user_dialog.selected_user_token)
                        self.token_input.setText(user_dialog.selected_user_token)
                        logging.info(f"Switched with home user token (fallback)")
                else:
                    # Admin user - use admin token
                    self.plex_server = PlexServer(base_url, user_dialog.selected_user_token)
                    self.token_input.setText(user_dialog.selected_user_token)

                # Update UI
                self.update_window_title()
                self.fetch_playlists()  # Refresh playlists for new user
                self.statusBar().showMessage(f"Switched to user: {self.current_user_name}")
                self.save_config()
                self.refresh_feature_dependent_ui()

                logging.info(f"Switched to user: {self.current_user_name}")
            except Exception as e:
                logging.error(f"Error switching user: {str(e)}")
                QMessageBox.critical(self, "Switch Error", f"Failed to switch user: {str(e)}")
                self.refresh_feature_dependent_ui()

    def populate_library_sections(self):
        try:
            self.section_combo.clear()
            music_sections = []
            for section in self.plex_server.library.sections():
                if section.type == 'artist':  # Assuming 'artist' type for music
                    music_sections.append(section)
                    self.section_combo.addItem(section.title, section.key)
            
            if music_sections:
                target_index = 0
                saved_section = getattr(self, 'last_section_id', None)
                if saved_section is not None:
                    for idx in range(self.section_combo.count()):
                        if self.section_combo.itemData(idx) == saved_section:
                            target_index = idx
                            break
                self.section_combo.setCurrentIndex(target_index)
                selected_section_id = self.section_combo.currentData()
                self.last_section_id = selected_section_id
                if saved_section is not None and selected_section_id == saved_section:
                    logging.info(f"Restored previously selected music library: {self.section_combo.currentText()}")
                else:
                    logging.info(f"Auto-selected music library: {self.section_combo.currentText()}")
                self.refresh_smart_match_cache_status()
                if self.plex_server and bool(self.smart_match_settings.get("preload_on_connect", True)):
                    QTimer.singleShot(0, lambda: self.start_smart_match_preload(force_rebuild=False, show_dialog=False))
            elif self.section_combo.count() == 0:
                QMessageBox.warning(self, "No Music Sections", "No music library sections found in your Plex server.")
        except Exception as e:
            logging.error(f"Error populating library sections: {str(e)}", exc_info=True)
            QMessageBox.warning(self, "Section Error", f"Error loading library sections: {str(e)}")

    def _current_smart_match_library_section(self):
        if not self.plex_server or not hasattr(self, "section_combo"):
            return None
        section_id = self.section_combo.currentData()
        if not section_id:
            return None
        try:
            return self.plex_server.library.sectionByID(section_id)
        except Exception:
            return None

    def refresh_smart_match_cache_status(self):
        if not hasattr(self, "smart_match_cache_status_label"):
            return
        library_section = self._current_smart_match_library_section()
        if not library_section:
            self.smart_match_cache_status_label.setText("Status: No library selected")
            if hasattr(self, "smart_match_cache_detail_label"):
                self.smart_match_cache_detail_label.setText("Built: n/a • Indexed tracks: 0")
            if hasattr(self, "smart_match_rebuild_btn"):
                self.smart_match_rebuild_btn.setEnabled(False)
            if hasattr(self, "smart_match_clear_btn"):
                self.smart_match_clear_btn.setEnabled(False)
            return

        if getattr(self, "_startup_splash_active", False):
            self._update_startup_progress("Checking Smart Match Cache...", 56)

        session_key = _get_library_match_session_key(library_section)
        meta = None
        state = None
        if session_key:
            try:
                meta = _get_smart_match_cache_store().get_meta(session_key)
            except Exception:
                meta = None
            with _SYNCRA_LIBRARY_MATCH_BUILD_STATES_LOCK:
                state = _SYNCRA_LIBRARY_MATCH_BUILD_STATES.get(session_key)

        fingerprint = None
        if meta:
            try:
                fingerprint = _probe_library_match_fingerprint(library_section)
            except Exception:
                fingerprint = None

        if state and not state.get("event").is_set():
            status_text = f"Status: Building • {state.get('message', 'Preparing Smart Match cache...')}"
        elif meta and fingerprint and _library_fingerprint_matches(meta, fingerprint):
            status_text = "Status: Ready"
        elif meta:
            status_text = "Status: Stale"
        else:
            status_text = "Status: Missing"
        self.smart_match_cache_status_label.setText(status_text)

        built_at = str(meta.get("built_at", "") or "n/a") if meta else "n/a"
        row_count = int(meta.get("row_count", 0) or 0) if meta else 0
        if hasattr(self, "smart_match_cache_detail_label"):
            self.smart_match_cache_detail_label.setText(f"Built: {built_at} • Indexed tracks: {row_count:,}")
        if hasattr(self, "smart_match_rebuild_btn"):
            self.smart_match_rebuild_btn.setEnabled(True)
        if hasattr(self, "smart_match_clear_btn"):
            self.smart_match_clear_btn.setEnabled(bool(meta))
        if getattr(self, "_startup_splash_active", False):
            splash_message = status_text.replace("Status:", "Smart Match Cache:").strip()
            self._update_startup_progress(splash_message, 66)

    def on_library_section_changed(self):
        self.last_section_id = self.section_combo.currentData() if hasattr(self, "section_combo") else None
        if not self._suspend_settings_apply:
            self.save_config()
        self.refresh_smart_match_cache_status()
        if self.plex_server and bool(self.smart_match_settings.get("preload_on_connect", True)):
            QTimer.singleShot(0, lambda: self.start_smart_match_preload(force_rebuild=False, show_dialog=False))

    def start_smart_match_preload(self, force_rebuild=False, show_dialog=False):
        library_section = self._current_smart_match_library_section()
        if not library_section:
            self.refresh_smart_match_cache_status()
            return

        session_key = _get_library_match_session_key(library_section) or ""
        existing_thread = getattr(self, "smart_match_preload_thread", None)
        if existing_thread and existing_thread.isRunning():
            if self.smart_match_preload_session_key == session_key and show_dialog:
                self.smart_match_preload_show_dialog = True
                self.show_loading("Smart Match Cache", "Preparing Smart Match cache...", can_cancel=True, cancel_callback=self.cancel_smart_match_preload, cancel_text="Cancel Build")
            return

        self.smart_match_preload_thread = SmartMatchIndexBuildThread(library_section, force_rebuild=force_rebuild, parent=self)
        self.smart_match_preload_session_key = session_key
        self.smart_match_preload_show_dialog = bool(show_dialog)
        self.smart_match_preload_thread.progress_update.connect(self.on_smart_match_preload_progress)
        self.smart_match_preload_thread.build_complete.connect(self.on_smart_match_preload_complete)
        self.smart_match_preload_thread.build_error.connect(self.on_smart_match_preload_error)
        self.smart_match_preload_thread.finished.connect(self.on_smart_match_preload_finished)
        if show_dialog:
            self.show_loading("Smart Match Cache", "Preparing Smart Match cache...", can_cancel=True, cancel_callback=self.cancel_smart_match_preload, cancel_text="Cancel Build")
        self.smart_match_preload_thread.start()
        self.refresh_smart_match_cache_status()

    def on_smart_match_preload_progress(self, message, percentage):
        if self.loading_dialog:
            self.loading_dialog.update_progress(message, percentage)
        self.statusBar().showMessage(message)
        self.refresh_smart_match_cache_status()

    def on_smart_match_preload_complete(self, result):
        if self.loading_dialog and self.loading_dialog.windowTitle() == "Smart Match Cache":
            self.hide_loading()
        row_count = int(result.get("row_count", 0) or 0)
        self.statusBar().showMessage(f"Smart Match cache ready ({row_count:,} tracks).", 4000)
        self.refresh_smart_match_cache_status()

    def on_smart_match_preload_error(self, error_message):
        if self.loading_dialog and self.loading_dialog.windowTitle() == "Smart Match Cache":
            self.hide_loading()
        if str(error_message or "").strip().lower() != "smart matching canceled.":
            logging.error(f"Smart Match preload failed: {error_message}")
            if self.smart_match_preload_show_dialog:
                QMessageBox.warning(self, "Smart Match Cache", f"Failed to build Smart Match cache:\n{error_message}")
        self.refresh_smart_match_cache_status()

    def on_smart_match_preload_finished(self):
        self.smart_match_preload_thread = None
        self.smart_match_preload_session_key = ""
        self.smart_match_preload_show_dialog = False
        self.refresh_smart_match_cache_status()

    def cancel_smart_match_preload(self):
        thread = getattr(self, "smart_match_preload_thread", None)
        if thread and thread.isRunning():
            thread.stop()
        if self.loading_dialog:
            self.loading_dialog.detail_label.setText("Cancel requested. Finishing current step...")
            self.loading_dialog.cancel_button.setEnabled(False)

    def clear_smart_match_cache(self):
        library_section = self._current_smart_match_library_section()
        if not library_section:
            QMessageBox.warning(self, "Smart Match Cache", "Select a music library section first.")
            return
        session_key = _get_library_match_session_key(library_section)
        if not session_key:
            QMessageBox.warning(self, "Smart Match Cache", "Could not determine the current library cache key.")
            return
        reply = QMessageBox.question(
            self,
            "Clear Smart Match Cache",
            "Clear the Smart Match cache for the current Plex music library?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        _clear_library_match_caches(library_section=library_section, session_key=session_key, clear_disk=True)
        self.refresh_smart_match_cache_status()
        self.statusBar().showMessage("Smart Match cache cleared.", 3000)

    def populate_sync_playlist_combo(self):
        """Populate the sync playlist combo box"""
        try:
            self.sync_playlist_combo.clear()
            self.sync_playlist_combo.addItem("Select playlist...")
            
            for playlist in self.plex_server.playlists():
                self.sync_playlist_combo.addItem(playlist.title, playlist)
                
        except Exception as e:
            logging.error(f"Error populating sync playlist combo: {str(e)}")

    def select_all_playlists(self, state):
        for index in range(self.playlist_listwidget.count()):
            item = self.playlist_listwidget.item(index)
            item.setCheckState(Qt.Checked if state == Qt.Checked else Qt.Unchecked)

    def get_selected_playlists(self):
        selected_playlists = []
        for index in range(self.playlist_listwidget.count()):
            item = self.playlist_listwidget.item(index)
            if item.checkState() == Qt.Checked or item.isSelected():
                selected_playlists.append(item)
        return selected_playlists

    def delete_selected_playlist(self):
        selected_items = self.get_selected_playlists()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select playlists to delete.")
            return

        reply = QMessageBox.question(self, 'Confirm Deletion', 
                                     f"Are you sure you want to delete {len(selected_items)} playlist(s)?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            deleted_count = 0
            for item in selected_items:
                # Get playlist object from item data
                playlist = item.data(Qt.UserRole)
                if playlist:
                    try:
                        playlist.delete()
                        deleted_count += 1
                    except Exception as e:
                        QMessageBox.warning(self, "Deletion Error", f"Error deleting {playlist.title}: {str(e)}")
                else:
                    # Fallback: try to find by name
                    playlist_name = item.text().split(' (')[0]
                    playlist = next((p for p in self.playlists if p.title == playlist_name), None)
                    if playlist:
                        try:
                            playlist.delete()
                            deleted_count += 1
                        except Exception as e:
                            QMessageBox.warning(self, "Deletion Error", f"Error deleting {playlist.title}: {str(e)}")
            
            if deleted_count > 0:
                self.fetch_playlists()
                self.statusBar().showMessage(f"Deleted {deleted_count} playlist(s).")

    def import_playlist(self):
        flow_id = new_flow_id("import")
        log_event("playlist_import_requested", flow_id=flow_id, source="ui")
        m3u_path = self.playlist_input.text()
        if os.path.isdir(m3u_path):  # If it's a directory, perform bulk upload
            imported_playlists = []
            with timed("playlist_import_bulk", flow_id=flow_id, source="filesystem"):
                for filename in os.listdir(m3u_path):
                    if filename.endswith('.m3u') or filename.endswith('.m3u8'):
                        full_path = os.path.join(m3u_path, filename)
                        self.upload_playlist(full_path)
                        imported_playlists.append(os.path.basename(full_path))
            self.statusBar().showMessage("Imported: " + ", ".join(imported_playlists))
        else:  # Single file upload
            with timed("playlist_import_single", flow_id=flow_id, source="filesystem"):
                self.upload_playlist(m3u_path)

    def upload_playlist(self, path):
        # Enhanced upload with conflict detection
        if not os.path.exists(path):
            QMessageBox.warning(self, "File Not Found", f"File not found: {path}")
            return
            
        # Get playlist name from file
        playlist_name = os.path.splitext(os.path.basename(path))[0]
        
        # Check if playlist already exists
        existing_playlist = None
        try:
            for playlist in self.plex_server.playlists():
                if playlist.title.lower() == playlist_name.lower():
                    existing_playlist = playlist
                    break
        except:
            pass  # If we can't check, proceed with upload
        
        if existing_playlist:
            # Show conflict resolution dialog
            dialog = QMessageBox(self)
            dialog.setWindowTitle("Playlist Conflict")
            dialog.setText(f"A playlist named '{playlist_name}' already exists.")
            dialog.setInformativeText("What would you like to do?")
            
            replace_btn = dialog.addButton("Replace", QMessageBox.DestructiveRole)
            merge_btn = dialog.addButton("Merge", QMessageBox.AcceptRole)
            rename_btn = dialog.addButton("Rename New", QMessageBox.AcceptRole)
            cancel_btn = dialog.addButton("Cancel", QMessageBox.RejectRole)
            
            dialog.exec()
            
            if dialog.clickedButton() == cancel_btn:
                return
            elif dialog.clickedButton() == replace_btn:
                # Delete existing playlist
                existing_playlist.delete()
                # Proceed with normal upload
                self._perform_upload(path)
            elif dialog.clickedButton() == merge_btn:
                # Merge with existing playlist
                self._merge_with_existing(path, existing_playlist)
                return
            elif dialog.clickedButton() == rename_btn:
                # Rename and upload
                new_name, ok = QInputDialog.getText(self, "Rename Playlist", 
                                                  "Enter new name:", text=f"{playlist_name}_new")
                if ok and new_name:
                    self._perform_upload(path, new_name)
                return
        else:
            # No conflict, proceed with normal upload
            self._perform_upload(path)

    # ==================== PATH MAPPING SYSTEM ====================

    def detect_plex_library_paths(self):
        """Detect Plex library root paths from the API"""
        try:
            if not self.plex_server:
                return []

            library_paths = []
            section_id = self.section_combo.currentData()

            if section_id:
                library_section = self.plex_server.library.sectionByID(section_id)
                # Get all locations for this library
                for location in library_section.locations:
                    library_paths.append(location)
                    logging.info(f"Detected Plex library path: {location}")

            self.plex_library_paths = library_paths
            return library_paths
        except Exception as e:
            logging.error(f"Error detecting Plex library paths: {str(e)}")
            return []

    def normalize_path_for_os(self, path):
        """Normalize path format based on OS patterns"""
        # Detect path type
        is_windows = '\\' in path or (len(path) > 1 and path[1] == ':')
        is_unc = path.startswith('\\\\') or path.startswith('//')
        is_unix = path.startswith('/') and not is_unc

        # Return normalized version
        if is_unc:
            # UNC path - convert to Windows format
            return path.replace('/', '\\')
        elif is_windows:
            # Windows path
            return path.replace('/', '\\')
        elif is_unix:
            # Unix/Linux/Mac path
            return path.replace('\\', '/')
        else:
            # Unknown format, return as-is
            return path

    def apply_path_mappings(self, file_path):
        """Apply user-defined path mappings to transform paths"""
        original_path = file_path

        # Try each mapping in order
        for mapping in self.path_mappings:
            source = mapping.get('source', '')
            target = mapping.get('target', '')

            if not source or not target:
                continue

            # Normalize separators for comparison (case-insensitive)
            normalized_file_compare = file_path.replace('\\', '/').lower()
            normalized_source_compare = source.replace('\\', '/').lower()

            if normalized_file_compare.startswith(normalized_source_compare):
                # Get the remainder from the ORIGINAL file_path to preserve case
                normalized_file_original = file_path.replace('\\', '/')
                remainder = normalized_file_original[len(source.replace('\\', '/')):]

                # Clean up any leading separators
                while remainder.startswith('/'):
                    remainder = remainder[1:]

                # Determine target separator style
                target_sep = '\\' if '\\' in target else '/'

                # Normalize target path
                clean_target = target.rstrip('\\/')

                # Combine with consistent separators
                if remainder:
                    new_path = clean_target + target_sep + remainder.replace('/', target_sep)
                else:
                    new_path = clean_target

                logging.info(f"Applied mapping: {original_path} -> {new_path}")
                return new_path

        return file_path

    def suggest_path_mapping(self, local_path):
        """Suggest a path mapping based on detected Plex library paths"""
        if not self.plex_library_paths:
            self.detect_plex_library_paths()

        suggestions = []

        # Extract the likely music folder name from local path
        local_normalized = local_path.replace('\\', '/').lower()

        # Common patterns to extract base path
        for keyword in ['music', 'audio', 'media', 'library']:
            if keyword in local_normalized:
                # Find the segment containing this keyword
                parts = local_normalized.split('/')
                for i, part in enumerate(parts):
                    if keyword in part:
                        local_base = '/'.join(local_path.split('/')[:i+1])

                        # Suggest mapping to each Plex library path
                        for plex_path in self.plex_library_paths:
                            suggestions.append({
                                'source': local_base,
                                'target': plex_path,
                                'confidence': 'medium'
                            })
                        break
                break

        # Also check for drive letter mappings (Windows to NAS)
        if len(local_path) > 1 and local_path[1] == ':':
            drive_letter = local_path[0]
            for plex_path in self.plex_library_paths:
                suggestions.append({
                    'source': f"{drive_letter}:",
                    'target': plex_path,
                    'confidence': 'low'
                })

        return suggestions

    def create_upload_diagnostic_log(self, m3u_path, failed_tracks):
        """Create a detailed diagnostic log for failed uploads"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            log_filename = f"upload_diagnostic_{timestamp}.log"

            # Use temp folder
            if hasattr(sys, '_MEIPASS'):
                script_dir = os.path.dirname(sys.executable)
            else:
                script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

            log_folder = os.path.join(script_dir, "upload_logs")
            if not os.path.exists(log_folder):
                os.makedirs(log_folder)

            log_path = os.path.join(log_folder, log_filename)

            with open(log_path, 'w', encoding='utf-8') as log_file:
                log_file.write("=" * 80 + "\n")
                log_file.write("SYNCRA - PLAYLIST UPLOAD DIAGNOSTIC LOG\n")
                log_file.write("=" * 80 + "\n\n")

                log_file.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                log_file.write(f"Playlist File: {m3u_path}\n")
                log_file.write(f"Operating System: {platform.system()} {platform.release()}\n\n")

                log_file.write("=" * 80 + "\n")
                log_file.write("PLEX SERVER INFORMATION\n")
                log_file.write("=" * 80 + "\n")
                log_file.write(f"Server IP: {self.server_ip_input.text()}\n")
                log_file.write(f"Server Port: {self.server_port_input.text()}\n")

                if self.plex_library_paths:
                    log_file.write(f"\nDetected Plex Library Paths:\n")
                    for path in self.plex_library_paths:
                        log_file.write(f"  - {path}\n")
                else:
                    log_file.write(f"\nNo Plex library paths detected\n")

                log_file.write(f"\n" + "=" * 80 + "\n")
                log_file.write("CONFIGURED PATH MAPPINGS\n")
                log_file.write("=" * 80 + "\n")
                if self.path_mappings:
                    for i, mapping in enumerate(self.path_mappings, 1):
                        log_file.write(f"{i}. {mapping['source']} -> {mapping['target']}\n")
                else:
                    log_file.write("No path mappings configured\n")

                log_file.write(f"\n" + "=" * 80 + "\n")
                log_file.write(f"FAILED TRACKS ({len(failed_tracks)} total)\n")
                log_file.write("=" * 80 + "\n\n")

                for i, track_info in enumerate(failed_tracks[:50], 1):  # Limit to first 50
                    track_path = track_info.get('path', 'Unknown')
                    reason = track_info.get('reason', 'Unknown error')

                    log_file.write(f"Track #{i}:\n")
                    log_file.write(f"  Path: {track_path}\n")
                    log_file.write(f"  Reason: {reason}\n")

                    # Add path analysis
                    if track_path != 'Unknown':
                        log_file.write(f"  Analysis:\n")
                        if track_path.startswith('\\\\') or track_path.startswith('//'):
                            log_file.write(f"    - Type: UNC Network Path\n")
                        elif len(track_path) > 1 and track_path[1] == ':':
                            log_file.write(f"    - Type: Windows Local Path (Drive {track_path[0]}:)\n")
                        elif track_path.startswith('/'):
                            log_file.write(f"    - Type: Unix/Linux/Mac Path\n")
                        else:
                            log_file.write(f"    - Type: Relative or Unknown Path\n")

                        # Check if it would match any Plex library paths
                        if self.plex_library_paths:
                            found_match = False
                            for plex_path in self.plex_library_paths:
                                if track_path.replace('\\', '/').lower().startswith(plex_path.replace('\\', '/').lower()):
                                    log_file.write(f"    - Matches Plex library: {plex_path}\n")
                                    found_match = True
                            if not found_match:
                                log_file.write(f"    - Does NOT match any Plex library paths\n")

                    log_file.write("\n")

                if len(failed_tracks) > 50:
                    log_file.write(f"... and {len(failed_tracks) - 50} more failed tracks\n\n")

                log_file.write("=" * 80 + "\n")
                log_file.write("RECOMMENDATIONS\n")
                log_file.write("=" * 80 + "\n\n")

                if not self.path_mappings:
                    log_file.write("1. No path mappings configured. This is likely the cause of the failure.\n")
                    log_file.write("   Go to Settings -> Path Mappings to configure path transformations.\n\n")

                if failed_tracks:
                    sample_path = failed_tracks[0].get('path', '')
                    if sample_path:
                        suggestions = self.suggest_path_mapping(sample_path)
                        if suggestions:
                            log_file.write("2. Suggested path mappings based on your setup:\n")
                            for suggestion in suggestions[:3]:  # Top 3 suggestions
                                log_file.write(f"   Source: {suggestion['source']}\n")
                                log_file.write(f"   Target: {suggestion['target']}\n")
                                log_file.write(f"   Confidence: {suggestion['confidence']}\n\n")

                log_file.write("\n" + "=" * 80 + "\n")
                log_file.write("END OF DIAGNOSTIC LOG\n")
                log_file.write("=" * 80 + "\n")

            return log_path
        except Exception as e:
            logging.error(f"Error creating diagnostic log: {str(e)}")
            return None

    def detect_and_show_plex_paths(self):
        """Detect and display Plex library paths"""
        paths = self.detect_plex_library_paths()

        if paths:
            paths_str = '\n'.join(f"  • {path}" for path in paths)
            QMessageBox.information(self, "Plex Library Paths Detected",
                                  f"Found {len(paths)} Plex library path(s):\n\n{paths_str}\n\n"
                                  f"Use these paths as 'Target' when creating path mappings.")
        else:
            QMessageBox.warning(self, "No Paths Detected",
                              "Could not detect Plex library paths.\n\n"
                              "Make sure you're connected to Plex and have selected a music library.")

    def add_path_mapping(self):
        """Add a new path mapping"""
        source = self.source_path_input.text().strip()
        target = self.target_path_input.text().strip()

        if not source or not target:
            QMessageBox.warning(self, "Invalid Mapping",
                              "Both source and target paths are required.")
            return

        # Check for duplicates
        for mapping in self.path_mappings:
            if mapping['source'].lower() == source.lower():
                reply = QMessageBox.question(self, "Duplicate Source",
                                           f"A mapping for '{source}' already exists.\n\nReplace it?",
                                           QMessageBox.Yes | QMessageBox.No)
                if reply == QMessageBox.Yes:
                    self.path_mappings.remove(mapping)
                else:
                    return

        self.path_mappings.append({'source': source, 'target': target})
        self.refresh_path_mappings_list()
        self.save_config()

        self.source_path_input.clear()
        self.target_path_input.clear()

        logging.info(f"Added path mapping: {source} -> {target}")

    def remove_path_mapping(self):
        """Remove selected path mapping"""
        current_row = self.path_mappings_list.currentRow()

        if current_row < 0:
            QMessageBox.warning(self, "No Selection",
                              "Please select a path mapping to remove.")
            return

        if current_row < len(self.path_mappings):
            removed = self.path_mappings.pop(current_row)
            self.refresh_path_mappings_list()
            self.save_config()
            logging.info(f"Removed path mapping: {removed['source']} -> {removed['target']}")

    def refresh_path_mappings_list(self):
        """Refresh the path mappings list display"""
        self.path_mappings_list.clear()

        if not self.path_mappings:
            item = QListWidgetItem("No path mappings configured")
            item.setForeground(QColor('#888888'))
            self.path_mappings_list.addItem(item)
        else:
            for mapping in self.path_mappings:
                item_text = f"{mapping['source']}  →  {mapping['target']}"
                self.path_mappings_list.addItem(item_text)

    def on_m3u_matching_mode_changed(self, state):
        """Handle M3U matching mode radio button changes"""
        sender = self.sender()

        if sender == self.m3u_smart_matching_radio and state == Qt.Checked:
            # User selected smart matching
            self.m3u_path_matching_radio.setChecked(False)
            logging.info("M3U matching mode changed to: Smart Matching (metadata-based)")
        elif sender == self.m3u_path_matching_radio and state == Qt.Checked:
            # User selected path matching
            self.m3u_smart_matching_radio.setChecked(False)
            logging.info("M3U matching mode changed to: Path Matching (file path-based)")

        # Save the setting
        self.save_config()

    def apply_path_preset(self, preset_type):
        """Apply a predefined path mapping preset"""
        presets = {
            'win_synology': {
                'message': 'Windows → Synology NAS preset.\n\nEnter your Windows drive letter (e.g., C) and Synology volume (e.g., volume1):',
                'source_template': '{drive}:',
                'target_template': '/volume{vol}',
                'inputs': ['Drive letter (C, D, E...)', 'Volume number (1, 2, 3...)']
            },
            'win_linux': {
                'message': 'Windows → Linux/Mac preset.\n\nEnter your Windows drive letter (e.g., C) and mount point (e.g., mnt/music):',
                'source_template': '{drive}:',
                'target_template': '/{mount}',
                'inputs': ['Drive letter (C, D, E...)', 'Mount path (e.g., mnt/music)']
            },
            'unc_synology': {
                'message': 'UNC Network Path → Synology preset.\n\nEnter your UNC server name and Synology volume:',
                'source_template': '\\\\{server}',
                'target_template': '/volume{vol}',
                'inputs': ['Server/NAS name', 'Volume number (1, 2, 3...)']
            }
        }

        preset = presets.get(preset_type)
        if not preset:
            return

        # Show input dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Configure Path Preset")
        dialog.setMinimumWidth(400)
        dialog_layout = QVBoxLayout(dialog)

        dialog_layout.addWidget(QLabel(preset['message']))

        inputs = []
        for input_label in preset['inputs']:
            layout = QHBoxLayout()
            layout.addWidget(QLabel(f"{input_label}:"))
            input_field = QLineEdit()
            layout.addWidget(input_field)
            dialog_layout.addLayout(layout)
            inputs.append(input_field)

        buttons = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Cancel")
        ok_btn.clicked.connect(dialog.accept)
        cancel_btn.clicked.connect(dialog.reject)
        buttons.addWidget(ok_btn)
        buttons.addWidget(cancel_btn)
        dialog_layout.addLayout(buttons)

        if dialog.exec() == QDialog.Accepted:
            values = [inp.text().strip() for inp in inputs]

            if not all(values):
                QMessageBox.warning(self, "Invalid Input", "All fields are required.")
                return

            # Build source and target from template
            if preset_type == 'win_synology':
                source = preset['source_template'].format(drive=values[0].upper())
                target = preset['target_template'].format(vol=values[1])
            elif preset_type == 'win_linux':
                source = preset['source_template'].format(drive=values[0].upper())
                target = preset['target_template'].format(mount=values[1].strip('/'))
            elif preset_type == 'unc_synology':
                source = preset['source_template'].format(server=values[0])
                target = preset['target_template'].format(vol=values[1])

            self.source_path_input.setText(source)
            self.target_path_input.setText(target)

            # Auto-add the mapping
            self.add_path_mapping()

    # ==================== END PATH MAPPING SYSTEM ====================

    def _prepare_playlist_for_upload(self, path):
        """Normalize playlist file for Plex upload (handle relative paths, path separators, and Unicode)."""
        temp_path = None

        logging.info(f"=== STARTING PLAYLIST NORMALIZATION FOR: {path} ===")

        # Try multiple encodings to handle special characters
        try:
            encodings = ['utf-8-sig', 'utf-8', 'cp1252', 'latin1']
            lines = None
            for encoding in encodings:
                try:
                    with open(path, 'r', encoding=encoding) as original:
                        lines = original.readlines()
                    logging.info(f"Successfully read playlist with encoding: {encoding}")
                    break
                except UnicodeDecodeError:
                    continue

            if lines is None:
                # Fallback to original behavior
                with open(path, 'r', encoding='latin-1', errors='replace') as original:
                    lines = original.readlines()
                logging.info("Used fallback latin-1 encoding")
        except Exception as e:
            logging.error(f"Failed to read playlist file {path}: {e}")
            return None

        logging.info(f"Read {len(lines)} lines from playlist")

        # Check if we need normalization (various path types that might cause issues)
        needs_normalization = False
        for line in lines:
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            file_path = line.strip()
            logging.debug(f"Checking path for normalization: '{file_path}'")

            # Force normalization for UNC paths regardless of other conditions
            if file_path.startswith('//') or file_path.startswith('\\\\'):
                logging.debug(f"UNC path detected, forcing normalization: {file_path}")
                needs_normalization = True
                break

            if (not os.path.isabs(file_path) or          # Relative path
                '\\' in file_path or                      # Backslashes (includes \\UNC)
                file_path.startswith('smb://') or         # SMB protocol
                file_path.startswith('cifs://') or        # CIFS protocol
                file_path.startswith('ftp://') or         # FTP protocol
                file_path.startswith('sftp://') or        # SFTP protocol
                file_path.startswith('file://') or        # File protocol
                '://' in file_path or                     # Any protocol scheme
                any(ord(c) > 127 for c in file_path)):    # Non-ASCII chars
                needs_normalization = True
                break

        if not needs_normalization:
            logging.info(f"=== NO NORMALIZATION NEEDED FOR: {path} ===")
            return None  # No temp file needed

        # Perform normalization
        logging.info(f"=== NORMALIZING PLAYLIST: {path} - UNC/problematic paths detected ===")
        logging.info(f"Total lines to process: {len(lines)}")
        playlist_dir = os.path.dirname(os.path.abspath(path))
        normalized_lines = []

        # Ensure M3U header is present
        has_header = False
        for line in lines:
            if line.strip() == '#EXTM3U':
                has_header = True
                break

        if not has_header:
            normalized_lines.append('#EXTM3U\n')
            logging.info("Added missing #EXTM3U header")

        for line in lines:
            if not line.strip() or line.lstrip().startswith('#'):
                normalized_lines.append(line)
                continue

            file_path = line.strip()

            # Handle different path types
            if file_path.startswith('\\\\') or file_path.startswith('//'):
                # UNC network path - convert to Windows backslash format (user confirmed this works)
                if file_path.startswith('//'):
                    # Convert from Unix format to Windows format, preserving case
                    normalized_path = file_path.replace('/', '\\')
                else:
                    # Already Windows format, just ensure it's clean
                    normalized_path = file_path

                # Ensure we have exactly two backslashes at the start
                if not normalized_path.startswith('\\\\'):
                    if normalized_path.startswith('\\'):
                        normalized_path = '\\' + normalized_path
                    else:
                        normalized_path = '\\\\' + normalized_path

                # CRITICAL: Fix case sensitivity issue for server names
                # Extract server name (first part after \\) and ensure proper case
                parts = normalized_path.split('\\')
                if len(parts) >= 3 and parts[2]:  # parts[0]='', parts[1]='', parts[2]=server_name
                    server_name = parts[2]
                    # Check if server name is all lowercase and try to fix it
                    if server_name.islower() and '-' in server_name:
                        # Common pattern: desktop-xxxxx should be Desktop-xxxxx
                        if server_name.startswith('desktop-'):
                            parts[2] = 'Desktop-' + server_name[8:]  # Replace 'desktop-' with 'Desktop-'
                            normalized_path = '\\'.join(parts)
                            logging.info(f"Fixed server name case: {server_name} -> {parts[2]}")

                logging.info(f"Normalized UNC path: {file_path} -> {normalized_path}")

            elif any(file_path.startswith(proto) for proto in ['smb://', 'cifs://', 'ftp://', 'sftp://', 'file://']):
                # Protocol-based network paths
                # Keep the protocol but normalize separators
                normalized_path = file_path.replace('\\', '/')
                logging.debug(f"Normalized protocol path: {file_path} -> {normalized_path}")

            elif '://' in file_path:
                # Any other protocol scheme - preserve but normalize separators
                normalized_path = file_path.replace('\\', '/')
                logging.debug(f"Normalized other protocol path: {file_path} -> {normalized_path}")

            elif not os.path.isabs(file_path):
                # Handle relative paths
                abs_path = os.path.join(playlist_dir, file_path)
                abs_path = os.path.normpath(abs_path)

                # Try to resolve the path
                if os.path.exists(abs_path):
                    file_path = abs_path
                    logging.debug(f"Resolved relative path: {line.strip()} -> {file_path}")
                else:
                    # Try with alternate separators
                    alt_path = file_path.replace('\\', '/') if '\\' in file_path else file_path.replace('/', '\\')
                    alt_abs_path = os.path.join(playlist_dir, alt_path)
                    alt_abs_path = os.path.normpath(alt_abs_path)

                    if os.path.exists(alt_abs_path):
                        file_path = alt_abs_path
                        logging.debug(f"Resolved with alt separators: {line.strip()} -> {file_path}")
                    else:
                        # Keep trying to resolve, use best guess
                        file_path = abs_path
                        logging.warning(f"Could not verify path exists: {file_path}")

                # Normalize path separators for Plex (forward slashes)
                normalized_path = file_path.replace('\\', '/')

            else:
                # Absolute local path (C:\, /mnt/, etc.) - just normalize separators
                normalized_path = file_path.replace('\\', '/')
                if file_path != normalized_path:
                    logging.debug(f"Normalized separators: {file_path} -> {normalized_path}")

            # APPLY USER-DEFINED PATH MAPPINGS
            if self.path_mappings:
                mapped_path = self.apply_path_mappings(normalized_path)
                if mapped_path != normalized_path:
                    logging.info(f"Path mapping applied: {normalized_path} -> {mapped_path}")
                    normalized_path = mapped_path

            normalized_lines.append(normalized_path + '\n')

        # Create temp folder for playlist processing
        try:
            # Get script directory - handle both .py and .exe scenarios
            if hasattr(sys, '_MEIPASS'):
                # Running as PyInstaller bundle
                script_dir = os.path.dirname(sys.executable)
            else:
                # Running as Python script
                script_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

            # Create temp folder
            temp_folder = os.path.join(script_dir, "playlist_temp")
            if not os.path.exists(temp_folder):
                os.makedirs(temp_folder)
                logging.debug(f"Created temp folder: {temp_folder}")

            # Clean up old temp files - keep only last 3 files
            try:
                temp_files = []
                for file in os.listdir(temp_folder):
                    if file.endswith('.m3u'):
                        file_path = os.path.join(temp_folder, file)
                        temp_files.append((file_path, os.path.getmtime(file_path)))

                # Sort by modification time (newest first)
                temp_files.sort(key=lambda x: x[1], reverse=True)

                # Remove all but the 3 newest files
                if len(temp_files) > 3:
                    for file_path, _ in temp_files[3:]:
                        try:
                            os.remove(file_path)
                            logging.debug(f"Removed old temp file: {os.path.basename(file_path)}")
                        except OSError:
                            pass  # Ignore if file is in use or can't be deleted

                logging.debug(f"Temp folder cleanup: keeping {min(len(temp_files), 3)} most recent files")
            except Exception as e:
                logging.debug(f"Temp folder cleanup failed: {e}")

            # Use original filename (not _normalized suffix)
            original_filename = os.path.basename(path)
            temp_path = os.path.join(temp_folder, original_filename)

            # Remove existing temp file if it exists
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                    logging.debug(f"Removed existing temp file: {temp_path}")
                except OSError as e:
                    logging.warning(f"Could not remove existing temp file: {e}")

            logging.info(f"Processing playlist in temp folder: {temp_folder}")

            with open(temp_path, 'w', encoding='utf-8', newline='') as temp_file:
                temp_file.writelines(normalized_lines)

            # Ensure file is properly written and ready
            import time
            time.sleep(0.1)  # Small delay to ensure file is written

            # Verify file was created successfully and is readable
            if not os.path.exists(temp_path):
                raise OSError(f"Temp file was not created: {temp_path}")

            file_size = os.path.getsize(temp_path)
            if file_size == 0:
                raise OSError(f"Temp file is empty: {temp_path}")

            # Verify we can read the file back
            try:
                with open(temp_path, 'r', encoding='utf-8') as verify_file:
                    verify_lines = verify_file.readlines()
                if len(verify_lines) != len(normalized_lines):
                    raise OSError(f"Temp file verification failed: expected {len(normalized_lines)} lines, got {len(verify_lines)}")
            except Exception as e:
                raise OSError(f"Cannot read temp file for verification: {e}")

            logging.info(f"=== SUCCESSFULLY CREATED TEMP PLAYLIST: {original_filename} in temp folder ===")
            logging.info(f"Temp file full path: {temp_path}")
            logging.info(f"Temp file size: {file_size} bytes, lines: {len(verify_lines)}")
            return temp_path

        except Exception as e:
            logging.warning(f"Failed to create temp playlist in script dir: {e}")

            # Fallback to system temp directory
            import tempfile
            try:
                temp_fd, temp_path = tempfile.mkstemp(suffix='.m3u', prefix='syncra_playlist_')
                with os.fdopen(temp_fd, 'w', encoding='utf-8', newline='') as temp_file:
                    temp_file.writelines(normalized_lines)
                logging.info(f"Created normalized playlist in system temp: {temp_path}")
                return temp_path
            except Exception as e2:
                logging.error(f"Failed to create temp playlist anywhere: {e2}")
                return None

    def _perform_upload(self, path, custom_name=None):
        """Perform the actual playlist upload with conflict checking"""
        try:
            # Get playlist name
            playlist_name = custom_name or os.path.splitext(os.path.basename(path))[0]

            # Check if smart matching is enabled
            use_smart_matching = self.m3u_smart_matching_radio.isChecked()

            if use_smart_matching and (path.endswith('.m3u') or path.endswith('.m3u8')):
                # Use smart matching approach for M3U files
                logging.info(f"Using smart matching for M3U upload: {playlist_name}")
                self._perform_smart_m3u_upload(path, playlist_name)
                return

            # Check for existing playlist BEFORE uploading
            existing_playlist = self.check_playlist_exists(playlist_name)
            
            if existing_playlist:
                # Show conflict resolution dialog
                dialog = QMessageBox(self)
                dialog.setWindowTitle("Playlist Already Exists")
                dialog.setText(f"A playlist named '{playlist_name}' already exists in your Plex server.")
                dialog.setInformativeText("What would you like to do?")
                
                overwrite_btn = dialog.addButton("🔄 Overwrite", QMessageBox.DestructiveRole)
                rename_btn = dialog.addButton("📝 Rename New", QMessageBox.AcceptRole)
                cancel_btn = dialog.addButton("❌ Cancel", QMessageBox.RejectRole)
                
                dialog.exec()
                
                if dialog.clickedButton() == cancel_btn:
                    self.statusBar().showMessage("Import cancelled by user")
                    return
                
                elif dialog.clickedButton() == overwrite_btn:
                    # Delete existing playlist
                    existing_playlist.delete()
                    logging.info(f"Deleted existing playlist: {playlist_name}")
                    self.statusBar().showMessage(f"Overwriting existing playlist: {playlist_name}")
                
                elif dialog.clickedButton() == rename_btn:
                    # Generate new name with timestamp
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
                    new_playlist_name = f"{playlist_name}_{timestamp}"
                    
                    # Double-check the new name doesn't exist
                    counter = 1
                    while self.check_playlist_exists(new_playlist_name):
                        new_playlist_name = f"{playlist_name}_{timestamp}_{counter}"
                        counter += 1
                    
                    playlist_name = new_playlist_name
                    logging.info(f"Renamed playlist to: {playlist_name}")
            
            # Rename .m3u8 to .m3u if necessary
            if path.endswith('.m3u8'):
                new_path = path.rsplit('.', 1)[0] + '.m3u'
                os.rename(path, new_path)
                path = new_path
        
            plex_server = self.server_ip_input.text()
            plex_port = self.server_port_input.text()
            library_section_id = self.section_combo.currentData()
            plex_token = self.token_input.text()
        
            if not library_section_id:
                self.statusBar().showMessage("Please select a library section before importing.")
                return
        
            url = f"http://{plex_server}:{plex_port}/playlists/upload"
            params = {'X-Plex-Token': plex_token, 'sectionID': library_section_id}
            data = {}

            upload_success = False
            upload_errors = []

            if os.path.isfile(path):
                normalized_temp_path = None
                try:
                    normalized_temp_path = self._prepare_playlist_for_upload(path)
                    upload_file_path = normalized_temp_path or path

                    # If playlist was renamed and we have a temp file, rename the temp file too
                    if normalized_temp_path and playlist_name != os.path.splitext(os.path.basename(path))[0]:
                        temp_folder = os.path.dirname(normalized_temp_path)
                        new_temp_filename = f"{playlist_name}.m3u"
                        new_temp_path = os.path.join(temp_folder, new_temp_filename)

                        try:
                            os.rename(normalized_temp_path, new_temp_path)
                            normalized_temp_path = new_temp_path
                            upload_file_path = new_temp_path
                            logging.info(f"Renamed temp file to match new playlist name: {new_temp_filename}")
                        except OSError as e:
                            logging.warning(f"Could not rename temp file: {e}")

                    # Use the playlist name for upload (which may be renamed)
                    upload_filename = f"{playlist_name}.m3u"

                    logging.info(f"Uploading file: {upload_file_path} as {upload_filename}")

                    with open(upload_file_path, 'rb') as playlist_file:
                        files = {
                            'file': (
                                upload_filename,  # Keep original name
                                playlist_file,
                                'audio/x-mpegurl'
                            )
                        }
                        response = requests.post(
                            url,
                            params=params,
                            files=files,
                            timeout=30
                        )
                    response.raise_for_status()
                    upload_success = True
                    logging.info(f"Uploaded playlist '{playlist_name}' via direct file upload.")
                except requests.RequestException as upload_error:
                    upload_errors.append(f"Direct upload failed: {upload_error}")
                    logging.warning(f"Direct playlist upload failed, will retry using server path: {upload_error}")
                finally:
                    # Clean up temp folder after upload attempt
                    if normalized_temp_path and os.path.exists(normalized_temp_path):
                        temp_folder = os.path.dirname(normalized_temp_path)
                        if upload_success:
                            # Remove only this specific temp file after successful upload
                            try:
                                os.remove(normalized_temp_path)
                                logging.info(f"Cleaned up temp file after successful upload: {os.path.basename(normalized_temp_path)}")
                            except OSError as e:
                                logging.warning(f"Could not clean up temp file: {e}")
                        else:
                            # Keep temp files for debugging failed uploads
                            logging.info(f"KEEPING TEMP FILE FOR INSPECTION (upload failed): {os.path.basename(normalized_temp_path)}")
            else:
                upload_errors.append('Playlist file is not accessible locally for direct upload.')

            if not upload_success:
                # Check if this is a localhost/local server
                is_local_server = plex_server in ['127.0.0.1', 'localhost', '::1'] or plex_server.startswith('192.168.') or plex_server.startswith('10.') or plex_server.startswith('172.')

                if is_local_server:
                    # For local servers, try server-side path upload with normalized temp file if available
                    upload_path = normalized_temp_path if normalized_temp_path else path
                    fallback_params = {'sectionID': library_section_id, 'path': upload_path, 'X-Plex-Token': plex_token}
                    logging.info(f"Server-side upload using file: {upload_path}")
                    try:
                        response = requests.post(url, params=fallback_params, timeout=30)
                        response.raise_for_status()
                        upload_success = True
                        logging.info(f"Uploaded playlist '{playlist_name}' using server-side path fallback.")
                    except requests.RequestException as fallback_error:
                        upload_errors.append(f"Server path upload failed: {fallback_error}")
                        logging.error(f"Server-side fallback failed for local server: {fallback_error}")
                else:
                    # For remote servers, don't attempt server-side fallback
                    logging.info(f"Skipping server-side fallback for remote server {plex_server}")

                # If still not successful, create diagnostic log and raise error
                if not upload_success:
                    combined_error = '; '.join(upload_errors)
                    logging.error(f"Playlist upload failed for '{playlist_name}': {combined_error}")

                    # Create diagnostic log if temp file exists
                    if normalized_temp_path and os.path.exists(normalized_temp_path):
                        try:
                            diagnostic_log_path = self.create_upload_diagnostic_log(normalized_temp_path, [])
                            if diagnostic_log_path:
                                logging.info(f"Created diagnostic log: {diagnostic_log_path}")
                                QMessageBox.warning(self, "Upload Failed - Diagnostic Created",
                                    f"Playlist upload failed: {combined_error}\n\n"
                                    f"Diagnostic log created at:\n{diagnostic_log_path}\n\n"
                                    f"Temp playlist kept at:\n{normalized_temp_path}")
                        except Exception as diag_error:
                            logging.warning(f"Could not create diagnostic log: {diag_error}")

                    raise requests.RequestException(combined_error)

            if upload_success:
                self.statusBar().showMessage(f"'{playlist_name}' imported successfully.")
            
        except requests.RequestException as e:
            error_message = f"Failed to import {os.path.basename(path)}. Error: {str(e)}"
            self.statusBar().showMessage(error_message)
            QMessageBox.critical(self, "Import Error", error_message)
        except Exception as e:
            error_message = f"Error during import: {str(e)}"
            self.statusBar().showMessage(error_message)
            QMessageBox.critical(self, "Import Error", error_message)
        
        # Refresh the playlist list after import
        self.fetch_playlists()

    def _perform_smart_m3u_upload(self, m3u_path, playlist_name):
        """Upload M3U playlist using smart matching (for remote/NAS servers)"""
        try:
            current_thread = getattr(self, "_smart_upload_thread", None)
            if current_thread and current_thread.isRunning():
                self.statusBar().showMessage("A smart match import is already running.")
                QMessageBox.information(self, "Import In Progress", "Wait for the current smart match import to finish or cancel it first.")
                return
            # Reset auto-skip flag for new upload
            self._auto_skip_uncertain = False
            self._smart_upload_progress_state = ("Preparing smart matching...", 0)
            # Check for existing playlist
            existing_playlist = self.check_playlist_exists(playlist_name)

            if existing_playlist:
                # Show conflict resolution dialog
                dialog = QMessageBox(self)
                dialog.setWindowTitle("Playlist Already Exists")
                dialog.setText(f"A playlist named '{playlist_name}' already exists in your Plex server.")
                dialog.setInformativeText("What would you like to do?")

                overwrite_btn = dialog.addButton("🔄 Overwrite", QMessageBox.DestructiveRole)
                rename_btn = dialog.addButton("📝 Rename New", QMessageBox.AcceptRole)
                cancel_btn = dialog.addButton("❌ Cancel", QMessageBox.RejectRole)

                dialog.exec()

                if dialog.clickedButton() == cancel_btn:
                    self.statusBar().showMessage("Import cancelled by user")
                    return

                elif dialog.clickedButton() == overwrite_btn:
                    # Delete existing playlist
                    existing_playlist.delete()
                    logging.info(f"Deleted existing playlist: {playlist_name}")
                    self.statusBar().showMessage(f"Overwriting existing playlist: {playlist_name}")

                elif dialog.clickedButton() == rename_btn:
                    # Generate new name with timestamp
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
                    new_playlist_name = f"{playlist_name}_{timestamp}"

                    # Double-check the new name doesn't exist
                    counter = 1
                    while self.check_playlist_exists(new_playlist_name):
                        new_playlist_name = f"{playlist_name}_{timestamp}_{counter}"
                        counter += 1

                    playlist_name = new_playlist_name
                    logging.info(f"Renamed playlist to: {playlist_name}")

            # Parse M3U file to get track info
            self.statusBar().showMessage(f"Parsing M3U file: {playlist_name}...")
            track_infos = _parse_m3u_entries(m3u_path)

            if not track_infos:
                raise Exception("No tracks found in M3U file")

            logging.info(f"Found {len(track_infos)} tracks in M3U file")

            # Get library section
            library_section_id = self.section_combo.currentData()
            if not library_section_id:
                raise Exception("Please select a library section")

            library_section = self.plex_server.library.sectionByID(library_section_id)

            # Store playlist name for later use
            self._pending_playlist_name = playlist_name

            # Start thread for track matching (prevents UI freezing)
            self.show_loading(
                "Smart Match Import",
                "Preparing smart matching...",
                can_cancel=True,
                cancel_callback=self.cancel_smart_upload,
                cancel_text="Cancel Import",
            )
            self._set_playlist_import_busy(True)
            if self.loading_dialog:
                self.loading_dialog.setWindowTitle("Smart Match Import")
                self.loading_dialog.progress_bar.setValue(0)
            self.statusBar().showMessage(f"Finding tracks in Plex library... (0/{len(track_infos)})")

            self._smart_upload_thread = SmartM3UUploadThread(m3u_path, track_infos, library_section, self)
            self._smart_upload_thread.progress_update.connect(self._on_smart_upload_progress)
            self._smart_upload_thread.track_prompt_needed.connect(self._on_smart_upload_prompt)
            self._smart_upload_thread.upload_complete.connect(self._on_smart_upload_complete)
            self._smart_upload_thread.upload_error.connect(self._on_smart_upload_error)
            self._smart_upload_thread.start()

        except Exception as e:
            self._set_playlist_import_busy(False)
            error_message = f"Failed to start smart M3U upload. Error: {str(e)}"
            self.statusBar().showMessage(error_message)
            QMessageBox.critical(self, "Import Error", error_message)
            logging.error(f"Smart M3U upload failed: {str(e)}")

    def _set_playlist_import_busy(self, busy):
        for attr_name in ("import_playlist_button", "import_browse_button"):
            widget = getattr(self, attr_name, None)
            if widget:
                widget.setEnabled(not busy)

    def _on_smart_upload_progress(self, message, percentage):
        """Handle progress updates from smart upload thread"""
        self.statusBar().showMessage(message)
        self._smart_upload_progress_state = (message, percentage)
        if self.loading_dialog:
            self.loading_dialog.message_label.setText("Smart Match Import")
            self.loading_dialog.detail_label.setText(message)
            self.loading_dialog.progress_bar.setValue(max(0, min(100, int(percentage))))

    def _on_smart_upload_prompt(self, title, artist, candidates, current_index, total_tracks, result_holder):
        """Handle track selection prompt from thread"""
        # Check if auto-skip is enabled
        if self._auto_skip_uncertain:
            result_holder['skipped'] = True
            return

        self.hide_loading()
        # Show selection dialog on main thread
        user_choice = self._prompt_track_selection(title, artist, candidates, current_index, total_tracks)

        if user_choice:
            result_holder['track'] = user_choice
        else:
            result_holder['skipped'] = True

        if getattr(self, "_smart_upload_thread", None) and self._smart_upload_thread.isRunning():
            message, percentage = getattr(self, "_smart_upload_progress_state", ("Resuming smart matching...", 0))
            self.show_loading(
                "Smart Match Import",
                message,
                can_cancel=True,
                cancel_callback=self.cancel_smart_upload,
                cancel_text="Cancel Import",
            )
            if self.loading_dialog:
                self.loading_dialog.setWindowTitle("Smart Match Import")
                self.loading_dialog.progress_bar.setValue(max(0, min(100, int(percentage))))

    def _on_smart_upload_complete(self, matched_count, total_count, not_found_list, matched_rating_keys):
        """Handle upload completion from thread"""
        try:
            self.hide_loading()
            self._set_playlist_import_busy(False)
            playlist_name = self._pending_playlist_name

            # Create playlist with matched tracks
            library_section_id = self.section_combo.currentData()
            library_section = self.plex_server.library.sectionByID(library_section_id) if library_section_id else None
            matched_tracks = _hydrate_plex_tracks_by_rating_keys(library_section, matched_rating_keys or []) if library_section else []
            matched_count = len(matched_tracks)
            if matched_count > 0:
                self.statusBar().showMessage(f"Creating playlist with {matched_count} tracks...")
                new_playlist = self.plex_server.createPlaylist(playlist_name, items=matched_tracks)
                logging.info(f"Created playlist '{playlist_name}' with {matched_count} tracks")

                # Show success message
                success_msg = f"✅ Successfully imported '{playlist_name}' using smart matching!\n\n"
                success_msg += f"📊 Found: {matched_count}/{total_count} tracks"

                if not_found_list:
                    success_msg += f"\n\n⚠️ Could not find {len(not_found_list)} tracks:\n"
                    success_msg += "\n".join(not_found_list[:10])
                    if len(not_found_list) > 10:
                        success_msg += f"\n...and {len(not_found_list) - 10} more"

                QMessageBox.information(self, "Import Complete", success_msg)
                self.statusBar().showMessage(f"'{playlist_name}' imported successfully ({matched_count} tracks)")

                # Refresh playlist list
                self.fetch_playlists()
            else:
                raise Exception("No tracks could be matched in your Plex library")

        except Exception as e:
            self._set_playlist_import_busy(False)
            error_message = f"Failed to create playlist. Error: {str(e)}"
            self.statusBar().showMessage(error_message)
            QMessageBox.critical(self, "Import Error", error_message)
            logging.error(f"Smart M3U playlist creation failed: {str(e)}")
        finally:
            self._smart_upload_thread = None

    def _on_smart_upload_error(self, error_msg):
        """Handle error from smart upload thread"""
        self.hide_loading()
        self._set_playlist_import_busy(False)
        self._smart_upload_thread = None
        if str(error_msg or "").strip().lower() == "smart matching canceled.":
            self.statusBar().showMessage("Smart match import canceled.")
            return
        error_message = f"Smart M3U upload error: {error_msg}"
        self.statusBar().showMessage(error_message)
        QMessageBox.critical(self, "Import Error", error_message)

    def cancel_smart_upload(self):
        thread = getattr(self, "_smart_upload_thread", None)
        if not thread or not thread.isRunning():
            self.hide_loading()
            return
        thread.stop()
        if self.loading_dialog:
            self.loading_dialog.detail_label.setText("Cancel requested. Finishing current step...")
            self.loading_dialog.cancel_button.setEnabled(False)

    def _prompt_track_selection(self, original_title, original_artist, candidates, current_index, total_tracks):
        """Show dialog for user to manually select the correct track from candidates

        Args:
            original_title: The title from the M3U file
            original_artist: The artist from the M3U file
            candidates: List of (track, score, artist) tuples sorted by score
            current_index: Current track number being processed
            total_tracks: Total number of tracks

        Returns:
            Selected Plex track object or None if skipped
        """
        dialog = QDialog(self)
        dialog.setWindowTitle(f"🎵 Select Correct Track ({current_index}/{total_tracks})")
        dialog.setMinimumWidth(700)
        dialog.setMinimumHeight(450)

        # Apply dark theme styling to dialog
        dialog.setStyleSheet("""
            QDialog {
                background-color: #1a1a1a;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QScrollArea {
                background-color: #1a1a1a;
                border: none;
            }
        """)

        layout = QVBoxLayout(dialog)

        # Original track info
        original_info = QLabel(
            f"<h3 style='color: #2196F3; margin-bottom: 5px;'>Looking for:</h3>"
            f"<p style='font-size: 14px; line-height: 1.6;'>"
            f"<b style='color: #4CAF50;'>Title:</b> <span style='color: #ffffff;'>{original_title}</span><br>"
            f"<b style='color: #4CAF50;'>Artist:</b> <span style='color: #ffffff;'>{original_artist or 'Unknown'}</span></p>"
        )
        original_info.setTextFormat(Qt.RichText)
        original_info.setStyleSheet("""
            background-color: #2a2a2a;
            padding: 15px;
            border-radius: 5px;
            border: 1px solid #3a3a3a;
        """)
        layout.addWidget(original_info)

        # Instructions
        instructions = QLabel(
            "<span style='color: #FF9800;'>⚠️</span> "
            "<span style='color: #ffffff;'>No exact match found. Please select the correct track from the options below, or skip if none match:</span>"
        )
        instructions.setTextFormat(Qt.RichText)
        instructions.setWordWrap(True)
        instructions.setStyleSheet("""
            padding: 12px;
            background-color: #2a2a2a;
            border-left: 3px solid #FF9800;
            border-radius: 3px;
            margin-top: 10px;
            margin-bottom: 10px;
        """)
        layout.addWidget(instructions)

        # Candidates list
        candidates_label = QLabel("<h4 style='color: #2196F3; margin-bottom: 8px;'>Available matches:</h4>")
        candidates_label.setTextFormat(Qt.RichText)
        candidates_label.setStyleSheet("padding: 5px;")
        layout.addWidget(candidates_label)

        # Create radio button group
        button_group = QButtonGroup(dialog)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #1a1a1a;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #1a1a1a;
                width: 12px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: #4a4a4a;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #5a5a5a;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        scroll_widget = QWidget()
        scroll_widget.setStyleSheet("background-color: #1a1a1a;")
        scroll_layout = QVBoxLayout(scroll_widget)

        radio_buttons = []
        for i, (track, score, track_artist) in enumerate(candidates):
            try:
                # Get album info
                album = track.parentTitle if hasattr(track, 'parentTitle') else 'Unknown Album'

                # Get year
                year = ""
                if hasattr(track, 'parentYear'):
                    year = f" ({track.parentYear})"

                # Create radio button with track info
                confidence = "🟢" if score >= 80 else "🟡" if score >= 50 else "🔴"
                confidence_color = "#4CAF50" if score >= 80 else "#FF9800" if score >= 50 else "#f44336"

                radio_text = (
                    f"{confidence} <b style='color: #ffffff; font-size: 14px;'>{track.title}</b> "
                    f"<span style='color: #aaaaaa;'>by</span> "
                    f"<span style='color: #2196F3;'>{track_artist}</span><br>"
                    f"<span style='color: #888888; font-size: 12px;'>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                    f"Album: <i style='color: #aaaaaa;'>{album}{year}</i></span><br>"
                    f"<span style='color: {confidence_color}; font-size: 11px; font-weight: bold;'>"
                    f"&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Match confidence: {score}%</span>"
                )

                radio = QRadioButton()
                radio.setText("")  # We'll use a label for rich text
                radio.setStyleSheet("""
                    QRadioButton::indicator {
                        width: 18px;
                        height: 18px;
                    }
                    QRadioButton::indicator::unchecked {
                        border: 2px solid #555555;
                        background-color: #1a1a1a;
                        border-radius: 9px;
                    }
                    QRadioButton::indicator::unchecked:hover {
                        border: 2px solid #2196F3;
                        background-color: #2a2a2a;
                    }
                    QRadioButton::indicator::checked {
                        border: 2px solid #2196F3;
                        background-color: #2196F3;
                        border-radius: 9px;
                    }
                """)

                label = QLabel(radio_text)
                label.setTextFormat(Qt.RichText)
                label.setWordWrap(True)
                label.setStyleSheet("""
                    QLabel {
                        padding: 12px;
                        background-color: #1e1e1e;
                        border-radius: 5px;
                        border: 1px solid #3a3a3a;
                        margin: 3px 0px;
                    }
                    QLabel:hover {
                        background-color: #2a2a2a;
                        border: 1px solid #2196F3;
                    }
                """)

                # Make label clickable
                label.mousePressEvent = lambda event, r=radio: r.setChecked(True)

                row_layout = QHBoxLayout()
                row_layout.addWidget(radio)
                row_layout.addWidget(label, 1)
                scroll_layout.addLayout(row_layout)

                button_group.addButton(radio, i)
                radio_buttons.append((radio, track))

                # Select first option by default
                if i == 0:
                    radio.setChecked(True)

            except Exception as e:
                logging.error(f"Error displaying track option: {e}")

        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)

        # Buttons
        button_layout = QHBoxLayout()

        select_btn = ModernButton("✅ Use Selected Track")
        select_btn.clicked.connect(dialog.accept)

        skip_btn = ModernButton("⏭️ Skip This Track")
        skip_btn.clicked.connect(dialog.reject)

        skip_all_btn = ModernButton("❌ Auto-Skip All Uncertain")
        skip_all_btn.setToolTip("Skip this and all remaining uncertain matches")
        skip_all_btn.clicked.connect(lambda: dialog.done(2))  # Custom return code

        button_layout.addWidget(select_btn)
        button_layout.addWidget(skip_btn)
        button_layout.addWidget(skip_all_btn)
        button_layout.addStretch()

        layout.addLayout(button_layout)

        # Show dialog
        result = dialog.exec()

        if result == QDialog.Accepted:
            # Find selected track
            for radio, track in radio_buttons:
                if radio.isChecked():
                    return track
        elif result == 2:
            # User wants to skip all uncertain matches
            # Set a flag to auto-skip remaining uncertain matches
            if not hasattr(self, '_auto_skip_uncertain'):
                self._auto_skip_uncertain = True

        return None

    def _merge_with_existing(self, file_path, existing_playlist):
        """Merge M3U file tracks with existing playlist"""
        try:
            # Read tracks from M3U file with proper encoding handling
            encodings = ['utf-8-sig', 'utf-8', 'cp1252', 'latin1']
            content = None
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as file:
                        content = file.readlines()
                    break
                except UnicodeDecodeError:
                    continue

            if content is None:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as file:
                    content = file.readlines()

            # Process tracks with basic path normalization for merge
            playlist_dir = os.path.dirname(os.path.abspath(file_path))
            new_tracks = []

            for line in content:
                if not line.strip() or line.lstrip().startswith('#'):
                    continue

                track_path = line.strip()

                # Handle relative paths for merge
                if not os.path.isabs(track_path):
                    abs_path = os.path.join(playlist_dir, track_path)
                    abs_path = os.path.normpath(abs_path)
                    if os.path.exists(abs_path):
                        track_path = abs_path

                # Normalize separators
                track_path = track_path.replace('\\', '/')
                new_tracks.append(track_path)
            
            if not new_tracks:
                QMessageBox.warning(self, "Empty Playlist", "No tracks found in the M3U file.")
                return
            
            # Get library section
            library_section_id = self.section_combo.currentData()
            library_section = self.plex_server.library.sectionByID(library_section_id)
            
            # Get existing tracks in playlist
            existing_tracks = set()
            for track in existing_playlist.items():
                signature = f"{track.title}_{track.originalTitle or (track.artist().title if hasattr(track, 'artist') and track.artist() else '')}"
                existing_tracks.add(signature.lower())
            
            # Find new tracks to add
            tracks_to_add = []
            for track_info in new_tracks:
                track_signature = track_info.lower()
                if track_signature not in existing_tracks:
                    # Try to find track in Plex library
                    plex_track = self.find_best_match_for_merge(library_section, track_info)
                    if plex_track:
                        tracks_to_add.append(plex_track)
            
            if tracks_to_add:
                existing_playlist.addItems(tracks_to_add)
                QMessageBox.information(self, "Merge Complete", 
                                      f"Added {len(tracks_to_add)} new tracks to '{existing_playlist.title}'.")
            else:
                QMessageBox.information(self, "No New Tracks", 
                                      "No new tracks found to add to the existing playlist.")
            
            self.fetch_playlists()  # Refresh playlist list
            
        except Exception as e:
            logging.error(f"Error merging playlist: {str(e)}")
            QMessageBox.critical(self, "Merge Error", f"Failed to merge playlist: {str(e)}")
    
    def find_best_match_for_merge(self, library_section, track):
        """Find best match for a track during merge operation"""
        try:
            title, artist = self.parse_track_info(track)
            all_tracks = library_section.searchTracks(title=title)

            best_match = None
            best_score = 0

            for plex_track in all_tracks:
                plex_title = plex_track.title if plex_track.title else ''
                title_score = fuzz.token_set_ratio(title.lower(), plex_title.lower())

                artist_score = 0
                if artist and plex_track.originalTitle:
                    artist_score = fuzz.token_set_ratio(artist.lower(), plex_track.originalTitle.lower())
                elif hasattr(plex_track, 'artist') and plex_track.artist():
                    artist_score = fuzz.token_set_ratio(artist.lower(), plex_track.artist().title.lower())

                combined_score = (title_score * 0.7) + (artist_score * 0.3)

                if combined_score > best_score:
                    best_score = combined_score
                    best_match = plex_track

            if best_score >= 70:
                return best_match
            else:
                return None

        except Exception as e:
            logging.error(f"Error finding match for track: {str(e)}")
            return None

    def parse_track_info(self, track):
        """Parse track info into title and artist"""
        parts = track.split(' - ', 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
        else:
            return track.strip(), ''

    def export_selected_playlists(self):
        selected_items = [self.playlist_listwidget.item(i) for i in range(self.playlist_listwidget.count()) 
                          if self.playlist_listwidget.item(i).checkState() == Qt.Checked]
        
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select playlists to export.")
            return

        export_dir = QFileDialog.getExistingDirectory(self, "Select Export Directory")
        if not export_dir:
            return

        # Get playlist objects from selected items
        playlists_to_export = []
        for item in selected_items:
            playlist = item.data(Qt.UserRole)
            if playlist:
                playlists_to_export.append(playlist)
            else:
                # Fallback: find by name
                playlist_name = item.text().split(' (')[0]
                playlist = next((p for p in self.playlists if p.title == playlist_name), None)
                if playlist:
                    playlists_to_export.append(playlist)

        if not playlists_to_export:
            QMessageBox.warning(self, "No Playlists", "No valid playlists found to export.")
            return

        # Show loading dialog and start background export
        self.show_loading("Exporting playlists...", f"0 of {len(playlists_to_export)} exported")
        
        # Start export thread
        self.export_thread = ExportThread(playlists_to_export, export_dir, self)
        self.export_thread.progress_update.connect(self.update_export_progress)
        self.export_thread.export_complete.connect(self.on_export_complete)
        self.export_thread.error.connect(self.on_export_error)
        self.export_thread.start()

    def update_export_progress(self, message, percentage):
        """Update export progress"""
        if self.loading_dialog:
            self.loading_dialog.update_progress(message, percentage)

    def on_export_complete(self, exported_count):
        """Handle export completion"""
        self.hide_loading()
        self.statusBar().showMessage(f"Successfully exported {exported_count} playlist(s).")
        QMessageBox.information(self, "Export Complete", f"Successfully exported {exported_count} playlist(s).")

    def on_export_error(self, error_message):
        """Handle export error"""
        self.hide_loading()
        logging.error(f"Export error: {error_message}")
        QMessageBox.critical(self, "Export Error", f"Export failed: {error_message}")

    def export_playlist(self, playlist, export_dir):
        safe_name = self.sanitize_filename(playlist.title)
        filename = f"{safe_name}.m3u"
        filepath = os.path.join(export_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as file:
            file.write("#EXTM3U\n")
            file.write(f"# Exported from Plex on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            for item in playlist.items():
                try:
                    # Use the actual file path from Plex, not just track info
                    for part in item.iterParts():
                        if hasattr(part, 'file') and part.file:
                            # Normalize path separators for cross-platform compatibility
                            normalized_path = part.file.replace('\\', '/')
                            file.write(f"{normalized_path}\n")
                            break
                    else:
                        # Fallback: if no file path available, use track info
                        artist = item.originalTitle or (item.artist().title if hasattr(item, 'artist') and item.artist() else "Unknown Artist")
                        file.write(f"#EXTINF:-1,{item.title} - {artist}\n")
                        file.write(f"{item.title} - {artist}\n")
                except Exception as e:
                    logging.warning(f"Error exporting track: {str(e)}")
                    continue

    def browse_files(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Open file', '', "Playlist files (*.m3u *.m3u8)")
        if path:
            self.playlist_input.setText(path)

    def import_streaming_playlist(self):
        playlist_url = self.playlist_url_input.text()
        if not playlist_url:
            QMessageBox.warning(self, "Missing Information", "Please enter a Spotify, Deezer, Tidal, or ListenBrainz playlist URL.")
            return

        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return

        token = self.listenbrainz_token_input.text().strip() if "listenbrainz.org" in playlist_url and hasattr(self, "listenbrainz_token_input") else None
        self.start_playlist_conversion(playlist_url, listenbrainz_token=token)

    def start_playlist_conversion(self, playlist_url, listenbrainz_token=None):
        """Start playlist conversion with conflict checking done on main thread"""
        if not self.plex_server:
            QMessageBox.warning(self, "Not Connected", "Please connect to Plex server first.")
            return
        
        # Show loading indicator while we get the playlist name
        self._show_streaming_feedback('Getting playlist information...')
        self.update_streaming_status('Getting playlist information...')
        self.streaming_progress.setValue(10)

        
        # Start a quick thread just to get the playlist name first
        self.name_fetch_thread = PlaylistNameFetchThread(playlist_url, self, listenbrainz_token=listenbrainz_token)
        self.name_fetch_thread.name_fetched.connect(self.handle_playlist_name_fetched)
        self.name_fetch_thread.error.connect(self.conversion_error)
        self.name_fetch_thread.start()
    
    def handle_playlist_name_fetched(self, playlist_url, playlist_name):
        """Handle playlist name fetched, check for conflicts on main thread"""
        try:
            # Check for existing playlist (on main thread - safe for dialogs)
            existing_playlist = self.check_playlist_exists(playlist_name)
            
            action = "create"  # Default action
            final_name = playlist_name
            
            if existing_playlist:
                # Show conflict resolution dialog (safe - we're on main thread)
                dialog = QMessageBox(self)
                dialog.setWindowTitle("Playlist Already Exists")
                dialog.setText(f"A playlist named '{playlist_name}' already exists in your Plex server.")
                dialog.setInformativeText("What would you like to do?")
                
                overwrite_btn = dialog.addButton("🔄 Overwrite", QMessageBox.DestructiveRole)
                rename_btn = dialog.addButton("📝 Rename New", QMessageBox.AcceptRole)
                cancel_btn = dialog.addButton("❌ Cancel", QMessageBox.RejectRole)
                
                result = dialog.exec()
                
                if dialog.clickedButton() == cancel_btn:
                    self._hide_streaming_feedback()
                    self.statusBar().showMessage("Import cancelled by user")
                    return
                
                elif dialog.clickedButton() == overwrite_btn:
                    action = "overwrite"
                    self.statusBar().showMessage(f"Will overwrite existing playlist: {playlist_name}")
                
                elif dialog.clickedButton() == rename_btn:
                    action = "rename"
                    # Generate new name with timestamp
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
                    final_name = f"{playlist_name}_{timestamp}"
                    
                    # Double-check the new name doesn't exist
                    counter = 1
                    while self.check_playlist_exists(final_name):
                        final_name = f"{playlist_name}_{timestamp}_{counter}"
                        counter += 1
                    
                    self.statusBar().showMessage(f"Will create playlist as: {final_name}")
            
            # Now start the actual conversion with the decision made
            self.streaming_progress.setValue(20)
            lb_token = getattr(self.name_fetch_thread, "listenbrainz_token", None)
            self.start_actual_conversion(playlist_url, final_name, action, existing_playlist, listenbrainz_token=lb_token)
            
        except Exception as e:
            logging.error(f"Error in conflict checking: {str(e)}")
            self.conversion_error(str(e))
    
    def start_actual_conversion(self, playlist_url, final_name, action, existing_playlist, listenbrainz_token=None):
        """Start the actual conversion after conflict resolution"""
        try:
            self.converter_thread = PlaylistConverterThread(
                playlist_url, 
                self.plex_server, 
                self.section_combo.currentData(),
                listenbrainz_token=listenbrainz_token,
                parent=self,
            )
            
            # Store the decision for the converter thread
            self.converter_thread.target_playlist_name = final_name
            self.converter_thread.conflict_action = action
            self.converter_thread.existing_playlist = existing_playlist
            
            # STORE THE SYNC MANAGER INFO
            self.converter_thread.original_url = playlist_url
            self.converter_thread.add_to_sync = self.add_to_sync_checkbox.isChecked()
            
            # NEW: Connect the track match confirmation signal
            self.converter_thread.track_match_confirmation_needed.connect(self.handle_track_match_confirmation)
            
            self.converter_thread.progress_message.connect(self.update_streaming_status)
            self.converter_thread.cancelled.connect(self.on_streaming_cancelled)
            self.converter_thread.progress_update.connect(self.update_streaming_progress)
            self.converter_thread.finished.connect(self.conversion_finished)
            self.converter_thread.error.connect(self.conversion_error)
            
            self.streaming_progress.setValue(20)
            self.update_streaming_status(f"Preparing to import '{final_name}'...")
            self.converter_thread.start()
            
        except Exception as e:
            logging.error(f"Error starting conversion: {str(e)}")
            self.conversion_error(str(e))
    
    def create_plex_playlist_with_conflict_check(self, tracks, playlist_name, playlist_image_url, original_create_method):
        """Create playlist with conflict checking"""
        try:
            # Check for existing playlist
            existing_playlist = self.check_playlist_exists(playlist_name)
            
            if existing_playlist:
                # Show conflict resolution dialog
                dialog = QMessageBox(self)
                dialog.setWindowTitle("Playlist Already Exists")
                dialog.setText(f"A playlist named '{playlist_name}' already exists in your Plex server.")
                dialog.setInformativeText("What would you like to do?")
                
                overwrite_btn = dialog.addButton("🔄 Overwrite", QMessageBox.DestructiveRole)
                rename_btn = dialog.addButton("📝 Rename New", QMessageBox.AcceptRole)
                cancel_btn = dialog.addButton("❌ Cancel", QMessageBox.RejectRole)
                
                dialog.exec()
                
                if dialog.clickedButton() == cancel_btn:
                    raise ValueError("Import cancelled by user")
                
                elif dialog.clickedButton() == overwrite_btn:
                    # Delete existing playlist
                    existing_playlist.delete()
                    logging.info(f"Deleted existing playlist: {playlist_name}")
                    # Proceed with original creation
                    original_create_method(tracks, playlist_name, playlist_image_url)
                
                elif dialog.clickedButton() == rename_btn:
                    # Generate new name with timestamp
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
                    new_name = f"{playlist_name}_{timestamp}"
                    
                    # Double-check the new name doesn't exist
                    counter = 1
                    while self.check_playlist_exists(new_name):
                        new_name = f"{playlist_name}_{timestamp}_{counter}"
                        counter += 1
                    
                    logging.info(f"Renamed playlist from '{playlist_name}' to '{new_name}'")
                    # Create with new name
                    original_create_method(tracks, new_name, playlist_image_url)
            else:
                # No conflict, proceed normally
                original_create_method(tracks, playlist_name, playlist_image_url)
                
        except Exception as e:
            logging.error(f"Error in playlist creation with conflict check: {str(e)}")
            raise

    def update_streaming_progress(self, value):
        self.streaming_progress.setValue(value)

    def update_streaming_status(self, message):
        if message:
            self.streaming_status_label.setVisible(True)
            self.streaming_status_label.setText(message)
            self.statusBar().showMessage(message)
        else:
            self.streaming_status_label.setVisible(False)
            self.streaming_status_label.setText('')

    def _show_streaming_feedback(self, status_text=''):
        self.streaming_progress.setVisible(True)
        self.streaming_progress.setValue(0)
        self.streaming_status_label.setVisible(bool(status_text))
        self.streaming_status_label.setText(status_text)
        self.cancel_streaming_button.setVisible(True)
        self.cancel_streaming_button.setEnabled(True)

    def _hide_streaming_feedback(self):
        self.streaming_progress.setVisible(False)
        self.streaming_status_label.setVisible(False)
        self.streaming_status_label.setText('')
        self.cancel_streaming_button.setVisible(False)
        self.cancel_streaming_button.setEnabled(False)

    def cancel_streaming_import(self):
        if hasattr(self, 'converter_thread') and self.converter_thread and self.converter_thread.isRunning():
            self.cancel_streaming_button.setEnabled(False)
            self.update_streaming_status('Cancelling...')
            self.converter_thread.request_cancel()
        elif hasattr(self, "name_fetch_thread") and self.name_fetch_thread and self.name_fetch_thread.isRunning():
            self.name_fetch_thread.terminate()
            self.name_fetch_thread.wait(1000)
            self.on_streaming_cancelled()
        else:
            self._hide_streaming_feedback()
    def on_streaming_cancelled(self):
        self._hide_streaming_feedback()
        self.statusBar().showMessage('Streaming import cancelled.')
        self.converter_thread = None


    def conversion_finished(self):
        """Handle conversion completion and add to sync manager if requested"""
        self._hide_streaming_feedback()
        self.statusBar().showMessage("Playlist conversion completed successfully.")
        
        # Check if we should add to sync manager
        if hasattr(self.converter_thread, 'add_to_sync') and self.converter_thread.add_to_sync:
            try:
                playlist_name = getattr(self.converter_thread, 'target_playlist_name', 'Unknown')
                source_url = getattr(self.converter_thread, 'original_url', '')
                
                if playlist_name and source_url:
                    # Add to sync manager
                    self.add_playlist_to_sync_manager(playlist_name, source_url)
                    
                    # Update status message
                    self.statusBar().showMessage(f"✅ Playlist imported and added to sync manager!")
                    
                    # Show success notification
                    QMessageBox.information(self, "Import Complete", 
                                          f"🎉 Successfully imported '{playlist_name}' and added to sync manager!\n\n"
                                          f"The playlist will now automatically sync with updates from the source.")
                
            except Exception as e:
                logging.error(f"Error adding to sync manager: {str(e)}")
                # Don't fail the whole process, just show warning
                QMessageBox.warning(self, "Sync Manager Warning", 
                                  f"Playlist imported successfully, but failed to add to sync manager:\n{str(e)}")
        
        # Refresh playlist list
        self.fetch_playlists()
        self.converter_thread = None

    def conversion_error(self, error_msg):
        self._hide_streaming_feedback()
        logging.error(f"Conversion error: {error_msg}")
        self.statusBar().showMessage(f"Conversion error: {error_msg}")
        QMessageBox.warning(self, "Conversion Error", f"Error during playlist conversion: {error_msg}")
        self.converter_thread = None


    def load_config(self):
        '''Load saved configuration values and optionally auto-connect to Plex.'''
        try:
            if not os.path.exists(CONFIG_FILE):
                logging.info('Config file not found; using defaults.')
                self.load_spotify_config()
                self.refresh_feature_dependent_ui()
                return

            with open(CONFIG_FILE, 'r') as config_file:
                config = deep_merge(APP_CONFIG_DEFAULTS, json.load(config_file))
        except Exception as e:
            logging.error(f'Error loading configuration: {str(e)}')
            self.load_spotify_config()
            self.refresh_feature_dependent_ui()
            return

        username = config.get('plex_username', '')
        self.plex_username_input.setText(username)
        self.feature_flags = config.get("features", APP_CONFIG_DEFAULTS.get("features", {})).copy()
        self.smart_match_settings = config.get("smart_match", APP_CONFIG_DEFAULTS.get("smart_match", {})).copy()
        _set_smart_match_runtime_settings(self.smart_match_settings)
        self.metadata_settings = config.get("metadata", APP_CONFIG_DEFAULTS.get("metadata", {})).copy()
        if hasattr(self, "metadata_fixer_feature_cb"):
            self.metadata_fixer_feature_cb.setChecked(self.feature_flags.get("metadata_fixer", False))
        if hasattr(self, "ui_refresh_feature_cb"):
            self.ui_refresh_feature_cb.setChecked(self.feature_flags.get("ui_refresh_v2", False))
        if hasattr(self, "auto_fetch_on_startup_cb"):
            self.auto_fetch_on_startup_cb.setChecked(self.feature_flags.get("auto_fetch_playlists_on_startup", False))
        if hasattr(self, "metadata_user_agent_input"):
            self.metadata_user_agent_input.setText(self.metadata_settings.get("user_agent", APP_CONFIG_DEFAULTS["metadata"]["user_agent"]))
        if hasattr(self, "metadata_rate_spin"):
            self.metadata_rate_spin.setValue(float(self.metadata_settings.get("rate_limit_rps", 1.0)))
        if hasattr(self, "metadata_ttl_spin"):
            self.metadata_ttl_spin.setValue(int(self.metadata_settings.get("cache_ttl_hours", 168)))
        if hasattr(self, "metadata_auto_apply_spin"):
            self.metadata_auto_apply_spin.setValue(int(self.metadata_settings.get("auto_apply_threshold", 95)))
        if hasattr(self, "metadata_review_spin"):
            self.metadata_review_spin.setValue(int(self.metadata_settings.get("review_threshold", 80)))

        # Load password from secure credential storage
        if username:
            password = credential_manager.get_password(username)
            if password:
                self.plex_password_input.setText(password)
                logging.info("Password loaded from secure credential storage")
            else:
                # Migration: Check for old base64-encoded password in config
                encoded_password = config.get('plex_password_encoded', '')
                if encoded_password:
                    try:
                        decoded_password = base64.b64decode(encoded_password.encode()).decode()
                        self.plex_password_input.setText(decoded_password)
                        # Migrate to secure storage
                        credential_manager.save_password(username, decoded_password)
                        logging.info("Migrated password from config file to secure storage")
                    except Exception as decode_error:
                        logging.error(f"Error decoding old password: {decode_error}")

        self.server_ip_input.setText(config.get('server_ip', ''))
        port_value = config.get('server_port', '')
        if port_value is None:
            port_value = ''
        self.server_port_input.setText(str(port_value))

        token_value = config.get('token', '') or ''
        self.token_input.setText(token_value)
        self.plex_server_profiles = config.get("plex_server_profiles", []) if isinstance(config.get("plex_server_profiles", []), list) else []
        self.server_sync_policy = str(config.get("server_sync_policy", "keep_extras") or "keep_extras").strip().lower()
        raw_jobs = config.get("server_sync_jobs", [])
        self.server_sync_jobs = []
        if isinstance(raw_jobs, list):
            for raw_job in raw_jobs:
                if not isinstance(raw_job, dict):
                    continue
                normalized_job = {
                    "id": str(raw_job.get("id", "") or secrets.token_hex(8)),
                    "enabled": bool(raw_job.get("enabled", True)),
                    "source_profile": raw_job.get("source_profile", {}) if isinstance(raw_job.get("source_profile", {}), dict) else {},
                    "source_playlist_title": str(raw_job.get("source_playlist_title", "") or "").strip(),
                    "target_profile": raw_job.get("target_profile", {}) if isinstance(raw_job.get("target_profile", {}), dict) else {},
                    "target_section_id": raw_job.get("target_section_id"),
                    "target_section_title": str(raw_job.get("target_section_title", "") or "").strip(),
                    "target_mode": str(raw_job.get("target_mode", "overwrite") or "overwrite").strip().lower(),
                    "sync_policy": str(raw_job.get("sync_policy", "keep_extras") or "keep_extras").strip().lower(),
                    "target_playlist_name": str(raw_job.get("target_playlist_name", raw_job.get("source_playlist_title", "")) or "").strip(),
                    "interval_minutes": max(5, int(raw_job.get("interval_minutes", 60) or 60)),
                    "next_run": str(raw_job.get("next_run", "") or ""),
                    "last_run": str(raw_job.get("last_run", "") or ""),
                    "last_status": str(raw_job.get("last_status", "") or ""),
                }
                if not normalized_job["next_run"]:
                    normalized_job["next_run"] = self._server_sync_format_datetime(self._server_sync_next_run(normalized_job["interval_minutes"]))
                self.server_sync_jobs.append(normalized_job)
        if hasattr(self, "server_sync_profile_combo"):
            self.refresh_server_sync_profiles_ui()
        if hasattr(self, "server_sync_policy_combo"):
            policy_index = self.server_sync_policy_combo.findData(self.server_sync_policy)
            self.server_sync_policy_combo.setCurrentIndex(policy_index if policy_index >= 0 else 2)
        if hasattr(self, "server_sync_jobs_list"):
            self.refresh_server_sync_jobs_ui()
        if hasattr(self, "listenbrainz_token_input"):
            self.listenbrainz_token_input.setText(config.get("listenbrainz_token", ""))
        if hasattr(self, "listenbrainz_user_input"):
            self.listenbrainz_user_input.setText(config.get("listenbrainz_user", ""))
        if hasattr(self, "apple_music_xml_input"):
            self.apple_music_xml_input.setText(config.get("apple_music_xml_path", ""))
        if hasattr(self, "apple_music_import_ratings_cb"):
            self.apple_music_import_ratings_cb.setChecked(bool(config.get("apple_music_import_ratings", True)))

        # Load saved user selection
        self._saved_user_name = config.get('selected_user_name', None)
        self._saved_is_admin = config.get('is_admin', True)

        self.last_section_id = config.get('last_section') or None

        # Load path mappings
        self.path_mappings = config.get('path_mappings', [])
        if self.path_mappings:
            logging.info(f'Loaded {len(self.path_mappings)} path mapping(s)')
            # Refresh the UI to display loaded mappings
            self.refresh_path_mappings_list()

        # Load M3U matching mode
        use_smart_matching = config.get('m3u_use_smart_matching', False)
        self.m3u_smart_matching_radio.setChecked(use_smart_matching)
        self.m3u_path_matching_radio.setChecked(not use_smart_matching)

        # Refresh Spotify login state using the saved config
        self.load_spotify_config()

        # Load sync configurations
        self.load_sync_config()

        self._startup_auto_fetch_pending = bool(self.feature_flags.get("auto_fetch_playlists_on_startup", False))

        # Auto-connect if we have a saved token
        if token_value and self.server_ip_input.text() and self.server_port_input.text():
            logging.info(f'Auto-connecting to Plex as saved user: {self._saved_user_name}')
            # Set flag to auto-select saved user during auto-connect
            self._auto_select_user = self._saved_user_name
            QTimer.singleShot(0, self.connect_to_plex)

        self.refresh_feature_dependent_ui()
        self.refresh_smart_match_cache_status()

    def save_config(self):
        """Save configuration while preserving existing settings"""
        try:
            # Load existing config first to preserve Spotify settings
            existing_config = {}
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r') as f:
                    existing_config = deep_merge(APP_CONFIG_DEFAULTS, json.load(f))
            
            # Update only Plex-related settings, preserve everything else
            config = existing_config.copy()  # Start with existing config
            
            # Update Plex settings
            # Save password securely using platform-specific credential storage
            active_token = self.token_input.text().strip()
            if not active_token and self.plex_account:
                active_token = self.plex_account.authenticationToken
            username = self.plex_username_input.text()
            password = self.plex_password_input.text()
            self.feature_flags = {
                "metadata_fixer": self.metadata_fixer_feature_cb.isChecked() if hasattr(self, "metadata_fixer_feature_cb") else self.feature_flags.get("metadata_fixer", False),
                "ui_refresh_v2": self.ui_refresh_feature_cb.isChecked() if hasattr(self, "ui_refresh_feature_cb") else self.feature_flags.get("ui_refresh_v2", False),
                "auto_fetch_playlists_on_startup": self.auto_fetch_on_startup_cb.isChecked() if hasattr(self, "auto_fetch_on_startup_cb") else self.feature_flags.get("auto_fetch_playlists_on_startup", False),
            }
            if hasattr(self, "metadata_user_agent_input"):
                self.metadata_settings = {
                    "user_agent": self.metadata_user_agent_input.text().strip() or APP_CONFIG_DEFAULTS["metadata"]["user_agent"],
                    "rate_limit_rps": float(self.metadata_rate_spin.value()),
                    "cache_ttl_hours": int(self.metadata_ttl_spin.value()),
                    "auto_apply_threshold": int(self.metadata_auto_apply_spin.value()),
                    "review_threshold": int(self.metadata_review_spin.value()),
                }
            if hasattr(self, "server_sync_policy_combo"):
                selected_policy = self.server_sync_policy_combo.currentData()
                self.server_sync_policy = str(selected_policy or "keep_extras").strip().lower()

            # Save password to secure storage (Windows Credential Manager, macOS Keychain, etc.)
            if username and password:
                credential_manager.save_password(username, password)
                logging.info("Password saved to secure credential storage")

            config.update({
                "plex_username": username,
                # Password NOT stored in config file - stored in secure OS keyring/encrypted file
                "server_ip": self.server_ip_input.text(),
                "server_port": self.server_port_input.text(),
                "token": active_token,  # Save currently active token for true token-first auto-reconnect
                "plex_server_profiles": self.plex_server_profiles if isinstance(self.plex_server_profiles, list) else [],
                "server_sync_policy": self.server_sync_policy,
                "server_sync_jobs": self.server_sync_jobs if isinstance(self.server_sync_jobs, list) else [],
                "listenbrainz_token": self.listenbrainz_token_input.text().strip() if hasattr(self, "listenbrainz_token_input") else existing_config.get("listenbrainz_token", ""),
                "listenbrainz_user": self.listenbrainz_user_input.text().strip() if hasattr(self, "listenbrainz_user_input") else existing_config.get("listenbrainz_user", ""),
                "apple_music_xml_path": self.apple_music_xml_input.text().strip() if hasattr(self, "apple_music_xml_input") else existing_config.get("apple_music_xml_path", ""),
                "apple_music_import_ratings": bool(self.apple_music_import_ratings_cb.isChecked()) if hasattr(self, "apple_music_import_ratings_cb") else existing_config.get("apple_music_import_ratings", True),
                "selected_user_name": self.current_user_name,  # Save which user was selected
                "is_admin": self.is_admin,  # Save if it's admin or home user
                "last_section": self.section_combo.currentData(),
                "path_mappings": self.path_mappings,
                "m3u_use_smart_matching": self.m3u_smart_matching_radio.isChecked(),
                "features": self.feature_flags,
                "smart_match": self.smart_match_settings,
                "metadata": self.metadata_settings,
            })
            
            # Save merged config
            with open(CONFIG_FILE, 'w') as config_file:
                json.dump(config, config_file, indent=4)
            logging.info("Configuration saved successfully (Spotify settings preserved).")
        except Exception as e:
            logging.error(f"Error saving configuration: {str(e)}")

    def check_playlist_exists(self, playlist_name):
       """Check if a playlist with the given name already exists in Plex"""
       try:
           if not self.plex_server:
               return False
           
           for playlist in self.plex_server.playlists():
               if playlist.title.lower() == playlist_name.lower():
                   return playlist
           return False
       except Exception as e:
           logging.error(f"Error checking playlist existence: {str(e)}")
           return False           

    def get_stylesheet(self):
        return MAIN_STYLESHEET

    def closeEvent(self, event):
        """Handle application close event"""
        try:
            # Stop any running threads
            if self.sync_thread and self.sync_thread.isRunning():
                self.sync_thread.stop()
                self.sync_thread.wait(3000)  # Wait up to 3 seconds
            
            if self.fetch_thread and self.fetch_thread.isRunning():
                self.fetch_thread.terminate()
                self.fetch_thread.wait(3000)
            
            if self.backup_thread and self.backup_thread.isRunning():
                self.backup_thread.terminate()
                self.backup_thread.wait(3000)
            
            if self.batch_track_count_thread and self.batch_track_count_thread.isRunning():
                self.batch_track_count_thread.stop()
                self.batch_track_count_thread.wait(3000)
                
            if hasattr(self, 'duplicates_thread') and self.duplicates_thread.isRunning():
                self.duplicates_thread.terminate()
                self.duplicates_thread.wait(3000)

            if self.source_playlist_load_thread and self.source_playlist_load_thread.isRunning():
                self.source_playlist_load_thread.terminate()
                self.source_playlist_load_thread.wait(2000)

            if self.server_playlist_transfer_thread and self.server_playlist_transfer_thread.isRunning():
                self.server_playlist_transfer_thread.terminate()
                self.server_playlist_transfer_thread.wait(3000)

            if self.server_sync_job_thread and self.server_sync_job_thread.isRunning():
                self.server_sync_job_thread.terminate()
                self.server_sync_job_thread.wait(3000)

            if self.smart_match_preload_thread and self.smart_match_preload_thread.isRunning():
                self.smart_match_preload_thread.stop()
                self.smart_match_preload_thread.wait(3000)

            if hasattr(self, 'name_fetch_thread') and self.name_fetch_thread and self.name_fetch_thread.isRunning():
                self.name_fetch_thread.terminate()
                self.name_fetch_thread.wait(2000)

            if hasattr(self, 'converter_thread') and self.converter_thread and self.converter_thread.isRunning():
                self.converter_thread.request_cancel()
                self.converter_thread.wait(3000)
            
            # Stop track count loading threads
            for thread in list(self.track_count_threads.values()):
                if thread.isRunning():
                    thread.terminate()
                    thread.wait(1000)
            
            # Stop auto-sync timer
            if self.auto_sync_timer.isActive():
                self.auto_sync_timer.stop()

            # Stop scheduled sync timer
            if self.scheduled_sync_timer.isActive():
                self.scheduled_sync_timer.stop()

            # Save configuration and cache
            self.save_config()
            self.save_sync_config()
            self.playlist_cache.save_cache()
            
            # Close loading dialog if open
            if self.loading_dialog:
                self.loading_dialog.close()
            
            event.accept()
            
        except Exception as e:
            logging.error(f"Error during application close: {str(e)}")
            event.accept()  # Close anyway

class PlaylistNameFetchThread(QThread):
    name_fetched = pyqtSignal(str, str)  # playlist_url, playlist_name
    error = pyqtSignal(str)
    
    def __init__(self, playlist_url, parent=None, listenbrainz_token=None):
        super().__init__(parent)
        self.playlist_url = playlist_url
        self.listenbrainz_token = listenbrainz_token.strip() if listenbrainz_token else None
        self.spotify_auth = SpotifyAnonymousAuth()
    
    def run(self):
        try:
            if "open.spotify.com" in self.playlist_url:
                playlist_name = self.get_spotify_playlist_name()
            elif "deezer.com" in self.playlist_url:
                playlist_name = self.get_deezer_playlist_name()
            elif "tidal.com" in self.playlist_url:
                playlist_name = self.get_tidal_playlist_name()
            elif "listenbrainz.org" in self.playlist_url:
                playlist_name = self.get_listenbrainz_playlist_name()
            else:
                raise ValueError("Unsupported playlist source")
            
            self.name_fetched.emit(self.playlist_url, playlist_name)
            
        except Exception as e:
            logging.error(f"Error fetching playlist name: {str(e)}")
            self.error.emit(str(e))
    
    def get_spotify_playlist_name(self):
        """
        Get Spotify playlist name using cookie-based auth with proper rate limit handling.
        """
        playlist_id = self.playlist_url.split('/')[-1].split('?')[0]
        max_retries = 5
        base_wait_time = 2

        for attempt in range(max_retries):
            try:
                # Respect global rate limiting
                global SPOTIFY_LAST_REQUEST_TIME
                now = time.time()
                time_since_last = now - SPOTIFY_LAST_REQUEST_TIME
                if time_since_last < SPOTIFY_REQUEST_MIN_INTERVAL:
                    time.sleep(SPOTIFY_REQUEST_MIN_INTERVAL - time_since_last)
                SPOTIFY_LAST_REQUEST_TIME = time.time()

                # Get cookie-based token and client ID
                token = self.spotify_auth.refresh_token_if_needed()
                client_id = self.spotify_auth.cached_client_id
                headers = {
                    'Authorization': f'Bearer {token}',
                    'Client-Id': client_id,  # CRITICAL: Required for cookie-based tokens (Dec 22, 2025 change)
                    'User-Agent': self.spotify_auth.user_agent,
                    'Accept': 'application/json',  # Request JSON instead of protobuf
                }

                # Use spclient endpoint (required for cookie-based auth as of Dec 22, 2025)
                response = requests.get(
                    f'https://spclient.wg.spotify.com/playlist/v2/playlist/{playlist_id}',
                    headers=headers,
                    timeout=30
                )

                # Success!
                if response.status_code == 200:
                    playlist_data = response.json()
                    # Parse spclient response structure
                    playlist_name = playlist_data.get('attributes', {}).get('name', 'Unknown Playlist')
                    return playlist_name

                # Rate limited - try public token fallback first
                if response.status_code == 429:
                    # Try public token fallback
                    public_token = get_public_spotify_token()
                    if public_token and attempt < 2:  # Try fallback max 2 times
                        logging.info("Using public token fallback for playlist name...")
                        headers['Authorization'] = f'Bearer {public_token}'
                        time.sleep(1)
                        continue

                    # If fallback failed, wait for rate limit to clear
                    retry_after = int(response.headers.get('Retry-After', base_wait_time * (attempt + 1)))
                    logging.warning(f"Rate limited (attempt {attempt + 1}/{max_retries}), waiting {retry_after}s")
                    time.sleep(retry_after)
                    continue

                # Other error - raise it
                response.raise_for_status()
                playlist_data = response.json()
                return playlist_data['name']

            except requests.exceptions.HTTPError as e:
                if e.response and e.response.status_code == 429:
                    # Rate limit - retry with exponential backoff
                    wait_time = base_wait_time * (2 ** attempt)
                    logging.warning(f"Rate limited (attempt {attempt + 1}/{max_retries}), waiting {wait_time}s")
                    time.sleep(wait_time)
                    continue
                else:
                    # Non-rate-limit error, raise it
                    raise
            except Exception as e:
                if attempt == max_retries - 1:
                    # Last attempt, raise the error
                    raise
                # Other error, retry with backoff
                wait_time = base_wait_time * (attempt + 1)
                logging.warning(f"Error on attempt {attempt + 1}/{max_retries}: {e}, retrying in {wait_time}s")
                time.sleep(wait_time)
                continue

        raise Exception(f"Failed to get playlist name after {max_retries} attempts")
    
    def get_deezer_playlist_name(self):
        """Get Deezer playlist name"""
        try:
            import deezer
            client = deezer.Client()
            playlist_id = self.playlist_url.split('/')[-1]
            playlist = client.get_playlist(playlist_id)
            return playlist.title
        except Exception as e:
            logging.error(f"Error getting Deezer playlist name: {str(e)}")
            raise
    
    def get_tidal_playlist_name(self):
        """Get Tidal playlist name"""
        try:
            client = TidalClient()
            playlist_uuid = self.playlist_url.split('/')[-1]
            playlist_data = client.get_playlist(playlist_uuid)
            return playlist_data['title']
        except Exception as e:
            logging.error(f"Error getting Tidal playlist name: {str(e)}")
            raise

    def get_listenbrainz_playlist_name(self):
        """Get ListenBrainz playlist title."""
        try:
            client = ListenBrainzClient(token=self.listenbrainz_token)
            playlist = client.get_playlist(self.playlist_url)
            return playlist.get("title") or "ListenBrainz Playlist"
        except Exception as e:
            logging.error(f"Error getting ListenBrainz playlist name: {str(e)}")
            raise
class MultiplePlaylistImportThread(QThread):
    progress_update = pyqtSignal(int, int, str)  # current, total, playlist_name
    playlist_imported = pyqtSignal(str, int)  # playlist_name, track_count
    finished = pyqtSignal(int, int)  # imported_count, total_count
    error = pyqtSignal(str)
    
    def __init__(self, playlists, plex_server, library_section, parent=None):
        super().__init__(parent)
        self.playlists = playlists
        self.plex_server = plex_server
        self.library_section = library_section
        self.spotify_auth = SpotifyAnonymousAuth()
    
    def run(self):
        imported_count = 0
        total_count = len(self.playlists)
        
        for i, playlist in enumerate(self.playlists):
            try:
                playlist_name = playlist['name']
                playlist_id = playlist['id']
                
                self.progress_update.emit(i + 1, total_count, playlist_name)
                
                # Create playlist URL
                playlist_url = f"https://open.spotify.com/playlist/{playlist_id}"
                
                # Use existing converter
                converter = PlaylistConverterThread(playlist_url, self.plex_server, self.library_section)
                converter.spotify_auth = self.spotify_auth
                
                # Get playlist info and tracks
                tracks, name, image_url = converter.get_spotify_playlist_info()
                
                # Create Plex playlist
                converter.create_plex_playlist(tracks, name, image_url)
                
                imported_count += 1
                self.playlist_imported.emit(playlist_name, len(tracks))
                
            except Exception as e:
                logging.error(f"Error importing playlist {playlist.get('name', 'Unknown')}: {e}")
                continue
        
        self.finished.emit(imported_count, total_count)

def main():
    setup_logging()
    initialize_config()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # This can help with some styling issues
    splash = StartupSplashScreen()
    splash.show()
    splash.update_progress("Starting Syncra...", 5)
    ex = PlexPlaylistManager(startup_splash=splash)
    ex.show()
    splash.finish_for(ex)
    ex._startup_splash_active = False
    sys.exit(app.exec())

if __name__ == '__main__':
    main()



