"""Search-as-you-type track picker backed by Plex's unified search.

Measured against a live library, `hubSearch` answers in ~67ms and returns artists,
albums and tracks together, where filtering tracks by `artist.title` took ~1270ms for
the same query. So the picker leads with hubSearch and expands the artist and album
hits into their tracks, which is what lets typing an artist or album name find tracks
that do not contain that text in their own title.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QThread, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from syncra.qt_compat import Qt
from syncra.theme.styles import CONTROL_HEIGHT, SPACE_XS

# Wait this long after the last keystroke before querying. Long enough that typing a
# word is one request, short enough to feel immediate.
SEARCH_DEBOUNCE_MS = 250
MIN_QUERY_LENGTH = 2

# Expanding a hit into its tracks costs one request each, so only the strongest few
# artist and album matches are expanded.
MAX_ALBUMS_EXPANDED = 3
MAX_ARTISTS_EXPANDED = 2
MAX_TRACKS_PER_ARTIST = 25
MAX_RESULTS = 80


class LibrarySearchThread(QThread):
    """Resolve a query into tracks, matching on track, album and artist names."""

    # results, query, sequence -- the sequence lets the caller drop stale answers
    found = pyqtSignal(list, str, int)
    failed = pyqtSignal(str, int)

    def __init__(self, library_section, query, sequence, parent=None):
        super().__init__(parent)
        self.library_section = library_section
        self.query = query
        self.sequence = sequence

    def run(self):
        try:
            self.found.emit(self._search(), self.query, self.sequence)
        except Exception as error:
            logging.error(f"Library search failed for {self.query!r}: {error}")
            self.failed.emit(str(error), self.sequence)

    def _search(self):
        section = self.library_section
        tracks, seen = [], set()

        def add(track, reason):
            key = str(getattr(track, "ratingKey", "") or "")
            if not key or key in seen or len(tracks) >= MAX_RESULTS:
                return
            seen.add(key)
            tracks.append((track, reason))

        artists, albums = [], []
        try:
            for hit in section.hubSearch(self.query, limit=20) or []:
                hit_type = getattr(hit, "type", "")
                if hit_type == "track":
                    add(hit, "track")
                elif hit_type == "album":
                    albums.append(hit)
                elif hit_type == "artist":
                    artists.append(hit)
        except Exception as error:
            # hubSearch is the fast path, not the only one -- fall through to the
            # title search below rather than failing the whole lookup.
            logging.info(f"hubSearch unavailable, falling back to title search: {error}")

        # Direct title matches, in case hubSearch ranked them out of its limit.
        try:
            for track in section.searchTracks(title=self.query, maxresults=40) or []:
                add(track, "track")
        except Exception as error:
            logging.info(f"Title search failed: {error}")

        for album in albums[:MAX_ALBUMS_EXPANDED]:
            if len(tracks) >= MAX_RESULTS:
                break
            try:
                for track in album.tracks() or []:
                    add(track, "album")
            except Exception as error:
                logging.debug(f"Could not expand album: {error}")

        for artist in artists[:MAX_ARTISTS_EXPANDED]:
            if len(tracks) >= MAX_RESULTS:
                break
            try:
                for track in (artist.tracks() or [])[:MAX_TRACKS_PER_ARTIST]:
                    add(track, "artist")
            except Exception as error:
                logging.debug(f"Could not expand artist: {error}")

        return tracks


class TrackPicker(QWidget):
    """A search box plus a results list, resolving to one selected Plex track."""

    track_selected = pyqtSignal(object)

    def __init__(self, library_section, placeholder="Search tracks, artists or albums...",
                 parent=None):
        super().__init__(parent)
        self.library_section = library_section
        self._thread = None
        self._sequence = 0
        self._selected = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE_XS)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(placeholder)
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumHeight(CONTROL_HEIGHT)
        self.search_input.textChanged.connect(self._on_text_changed)
        layout.addWidget(self.search_input)

        self.results = QListWidget()
        self.results.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results.setMinimumHeight(150)
        self.results.currentItemChanged.connect(self._on_selection_changed)
        layout.addWidget(self.results, 1)

        self.status = QLabel("Start typing to search your library.")
        self.status.setObjectName("mutedText")
        layout.addWidget(self.status)

        # One shared timer: restarting it on each keystroke collapses a burst of typing
        # into a single request.
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(SEARCH_DEBOUNCE_MS)
        self._debounce.timeout.connect(self._run_search)

    # ------------------------------------------------------------------ public

    def selected_track(self):
        return self._selected

    def set_track(self, track, label=None):
        """Preselect a track, e.g. when seeded from elsewhere in the app."""
        from syncra.services.sonic_discovery import track_label

        self._selected = track
        self.results.clear()
        item = QListWidgetItem(label or track_label(track))
        item.setData(Qt.ItemDataRole.UserRole, track)
        self.results.addItem(item)
        self.results.setCurrentItem(item)

        self.search_input.blockSignals(True)
        self.search_input.setText(str(getattr(track, "title", "") or ""))
        self.search_input.blockSignals(False)
        self.status.setText("Selected. Edit the search to pick a different track.")

    # ----------------------------------------------------------------- search

    def _on_text_changed(self, text):
        if len(text.strip()) < MIN_QUERY_LENGTH:
            self._debounce.stop()
            self.results.clear()
            self._selected = None
            self.status.setText("Type at least two characters.")
            return
        self.status.setText("Searching...")
        self._debounce.start()

    def _run_search(self):
        query = self.search_input.text().strip()
        if len(query) < MIN_QUERY_LENGTH:
            return
        if self.library_section is None:
            self.status.setText("Connect to Plex and select a music library first.")
            return

        self._sequence += 1
        thread = LibrarySearchThread(self.library_section, query, self._sequence, self)
        thread.found.connect(self._on_found)
        thread.failed.connect(self._on_failed)
        self._thread = thread
        thread.start()

    def _on_found(self, results, query, sequence):
        # A slower earlier query can land after a newer one; ignore anything stale.
        if sequence != self._sequence:
            return

        self.results.clear()
        self._selected = None
        if not results:
            self.status.setText(f"No matches for '{query}'.")
            return

        from syncra.services.sonic_discovery import track_label

        for track, reason in results:
            album = str(getattr(track, "parentTitle", "") or "")
            text = track_label(track)
            if album:
                text = f"{text}  ·  {album}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, track)
            if reason == "artist":
                item.setToolTip("Matched the artist name")
            elif reason == "album":
                item.setToolTip("Matched the album name")
            self.results.addItem(item)

        self.results.setCurrentRow(0)
        self.status.setText(f"{len(results)} match(es) for '{query}'.")

    def _on_failed(self, message, sequence):
        if sequence != self._sequence:
            return
        self.status.setText(f"Search failed: {message}")

    def _on_selection_changed(self, current, _previous):
        self._selected = current.data(Qt.ItemDataRole.UserRole) if current else None
        if self._selected is not None:
            self.track_selected.emit(self._selected)

    # --------------------------------------------------------------- teardown

    def shutdown(self):
        self._debounce.stop()
        if self._thread is not None and self._thread.isRunning():
            self._thread.wait(3000)
