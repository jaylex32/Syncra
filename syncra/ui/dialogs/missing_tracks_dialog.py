"""Missing Tracks workspace.

Shows every track an import or sync could not find in the connected Plex library,
deduplicated across runs, with the playlists that wanted it and how often it has been
asked for. From here a track can be re-checked against the library after new music is
added, resolved by hand, ignored, or exported as a shopping list.
"""

from __future__ import annotations

import logging
import os

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from syncra.qt_compat import Qt
from syncra.services.missing_tracks import (
    STATUS_IGNORED,
    STATUS_MISSING,
    STATUS_RESOLVED,
)

COL_ARTIST, COL_TITLE, COL_ALBUM, COL_TIMES, COL_SOURCES, COL_LAST_SEEN = range(6)


class RecheckThread(QThread):
    """Re-runs the matcher over stored missing tracks after the library has grown."""

    progress = pyqtSignal(str, int)
    finished_with_results = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, rows, library_section, matcher, parent=None):
        super().__init__(parent)
        self.rows = rows
        self.library_section = library_section
        self.matcher = matcher
        self.stop_requested = False

    def stop(self):
        self.stop_requested = True

    def run(self):
        try:
            found = []
            total = max(len(self.rows), 1)
            for index, row in enumerate(self.rows):
                if self.stop_requested:
                    break
                self.progress.emit(
                    f"Re-checking {index + 1}/{len(self.rows)}...",
                    int(((index + 1) / total) * 100),
                )
                source_track = {
                    "title": row.get("title", ""),
                    "artist": row.get("artist", ""),
                    "album": row.get("album", ""),
                }
                try:
                    matches = self.matcher(self.library_section, source_track)
                except Exception as match_error:
                    logging.warning(f"Re-check failed for {source_track}: {match_error}")
                    continue
                if matches and matches[0].get("score", 0) >= 82:
                    found.append((row, matches[0]))
            self.finished_with_results.emit(found)
        except Exception as error:
            logging.error(f"Missing-track re-check failed: {error}")
            self.failed.emit(str(error))


class MissingTracksDialog(QDialog):
    def __init__(self, store, library_key, library_section, matcher, parent=None):
        super().__init__(parent)
        self.store = store
        self.library_key = library_key
        self.library_section = library_section
        self.matcher = matcher
        self.recheck_thread = None
        self._rows = []

        self.setWindowTitle("Missing Tracks")
        self.setMinimumSize(940, 620)
        self._build_ui()
        self.reload()

    # ---------------------------------------------------------------------- ui

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        intro = QLabel(
            "Tracks your imports and syncs could not find in this Plex library. "
            "Add the music, then use Re-check Library to move them off this list."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #b8c9df; font-size: 12px;")
        layout.addWidget(intro)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(6)

        self.status_combo = QComboBox()
        self.status_combo.addItem("Still missing", STATUS_MISSING)
        self.status_combo.addItem("Resolved", STATUS_RESOLVED)
        self.status_combo.addItem("Ignored", STATUS_IGNORED)
        self.status_combo.addItem("All", None)
        self.status_combo.setMinimumHeight(32)
        self.status_combo.currentIndexChanged.connect(self.reload)
        filter_row.addWidget(QLabel("Show:"))
        filter_row.addWidget(self.status_combo)

        self.search_input = QLineEdit()
        self.search_input.setMinimumHeight(32)
        self.search_input.setPlaceholderText("Filter by title, artist, or album...")
        self.search_input.textChanged.connect(self.reload)
        filter_row.addWidget(self.search_input, 1)

        layout.addLayout(filter_row)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Artist", "Title", "Album", "Requested", "Wanted by", "Last seen"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_ARTIST, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_TITLE, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_ALBUM, QHeaderView.ResizeMode.Stretch)
        for column in (COL_TIMES, COL_SOURCES, COL_LAST_SEEN):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #9cb2d2; font-size: 12px;")
        layout.addWidget(self.status_label)

        button_row = QHBoxLayout()
        button_row.setSpacing(6)

        self.recheck_btn = QPushButton("🔁 Re-check Library")
        self.recheck_btn.setToolTip(
            "Run the matcher again over every listed track. Anything now present in the "
            "library is marked resolved."
        )
        self.recheck_btn.clicked.connect(self.recheck_library)
        button_row.addWidget(self.recheck_btn)

        self.ignore_btn = QPushButton("Ignore Selected")
        self.ignore_btn.clicked.connect(lambda: self._set_status_for_selection(STATUS_IGNORED))
        button_row.addWidget(self.ignore_btn)

        self.restore_btn = QPushButton("Mark as Missing")
        self.restore_btn.clicked.connect(lambda: self._set_status_for_selection(STATUS_MISSING))
        button_row.addWidget(self.restore_btn)

        self.delete_btn = QPushButton("Remove Selected")
        self.delete_btn.clicked.connect(self.delete_selected)
        button_row.addWidget(self.delete_btn)

        button_row.addStretch()

        self.export_csv_btn = QPushButton("Export CSV")
        self.export_csv_btn.clicked.connect(self.export_csv)
        button_row.addWidget(self.export_csv_btn)

        self.export_txt_btn = QPushButton("Export Tracklist")
        self.export_txt_btn.clicked.connect(self.export_text)
        button_row.addWidget(self.export_txt_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        button_row.addWidget(close_btn)

        layout.addLayout(button_row)

    # ------------------------------------------------------------------- data

    def _current_status(self):
        return self.status_combo.currentData()

    def reload(self):
        self._rows = self.store.list_tracks(
            self.library_key,
            status=self._current_status(),
            search=self.search_input.text(),
        )
        # Sorting must be off while populating or Qt reshuffles rows mid-insert and the
        # fingerprint stored on each row stops lining up with what the user sees.
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._rows))
        for row_index, row in enumerate(self._rows):
            self._set_cell(row_index, COL_ARTIST, row.get("artist", ""), row)
            self._set_cell(row_index, COL_TITLE, row.get("title", ""), row)
            self._set_cell(row_index, COL_ALBUM, row.get("album", ""), row)

            times_item = QTableWidgetItem()
            times_item.setData(Qt.ItemDataRole.DisplayRole, int(row.get("times_seen", 0) or 0))
            times_item.setData(Qt.ItemDataRole.UserRole, row.get("fingerprint", ""))
            self.table.setItem(row_index, COL_TIMES, times_item)

            self._set_cell(row_index, COL_SOURCES, ", ".join(row.get("sources", [])), row)
            self._set_cell(row_index, COL_LAST_SEEN, row.get("last_seen", ""), row)
        self.table.setSortingEnabled(True)

        counts = self.store.counts(self.library_key)
        self.status_label.setText(
            f"{counts.get(STATUS_MISSING, 0)} still missing · "
            f"{counts.get(STATUS_RESOLVED, 0)} resolved · "
            f"{counts.get(STATUS_IGNORED, 0)} ignored"
        )
        self._sync_button_states()

    def _set_cell(self, row_index, column, text, row):
        item = QTableWidgetItem(str(text or ""))
        item.setData(Qt.ItemDataRole.UserRole, row.get("fingerprint", ""))
        self.table.setItem(row_index, column, item)

    def _sync_button_states(self):
        has_rows = self.table.rowCount() > 0
        can_recheck = has_rows and self.library_section is not None and self.matcher is not None
        self.recheck_btn.setEnabled(can_recheck)
        if self.library_section is None:
            self.recheck_btn.setToolTip("Connect to Plex and select a music library to re-check.")
        self.export_csv_btn.setEnabled(has_rows)
        self.export_txt_btn.setEnabled(has_rows)

    def _selected_fingerprints(self):
        fingerprints = []
        for index in self.table.selectionModel().selectedRows():
            item = self.table.item(index.row(), COL_ARTIST)
            if item is None:
                continue
            fingerprint = item.data(Qt.ItemDataRole.UserRole)
            if fingerprint:
                fingerprints.append(fingerprint)
        return fingerprints

    # ---------------------------------------------------------------- actions

    def _show_context_menu(self, position):
        if not self.table.selectionModel().selectedRows():
            return
        menu = QMenu(self)
        menu.addAction("Ignore", lambda: self._set_status_for_selection(STATUS_IGNORED))
        menu.addAction("Mark as missing", lambda: self._set_status_for_selection(STATUS_MISSING))
        menu.addAction("Mark as resolved", lambda: self._set_status_for_selection(STATUS_RESOLVED))
        menu.addSeparator()
        menu.addAction("Copy as text", self.copy_selection)
        menu.addAction("Remove from list", self.delete_selected)
        menu.exec(self.table.viewport().mapToGlobal(position))

    def _set_status_for_selection(self, status):
        fingerprints = self._selected_fingerprints()
        if not fingerprints:
            return
        for fingerprint in fingerprints:
            if status == STATUS_IGNORED:
                self.store.mark_ignored(self.library_key, fingerprint)
            elif status == STATUS_RESOLVED:
                self.store.mark_resolved(self.library_key, fingerprint)
            else:
                self.store.mark_missing(self.library_key, fingerprint)
        self.reload()

    def delete_selected(self):
        fingerprints = self._selected_fingerprints()
        if not fingerprints:
            return
        confirm = QMessageBox.question(
            self,
            "Remove Tracks",
            f"Remove {len(fingerprints)} track(s) from the missing list?\n\n"
            "They will reappear if a future import cannot find them again.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        for fingerprint in fingerprints:
            self.store.delete(self.library_key, fingerprint)
        self.reload()

    def copy_selection(self):
        from PyQt6.QtWidgets import QApplication

        lines = []
        for index in self.table.selectionModel().selectedRows():
            artist = self.table.item(index.row(), COL_ARTIST)
            title = self.table.item(index.row(), COL_TITLE)
            artist_text = artist.text() if artist else ""
            title_text = title.text() if title else ""
            lines.append(f"{artist_text} - {title_text}" if artist_text else title_text)
        if lines:
            QApplication.clipboard().setText("\n".join(lines))
            self.status_label.setText(f"Copied {len(lines)} track(s) to the clipboard.")

    # --------------------------------------------------------------- re-check

    def recheck_library(self):
        if self.library_section is None or self.matcher is None:
            QMessageBox.information(
                self,
                "Not Connected",
                "Connect to Plex and select a music library before re-checking.",
            )
            return
        rows = self.store.list_tracks(self.library_key, status=STATUS_MISSING)
        if not rows:
            QMessageBox.information(self, "Nothing to Re-check", "No missing tracks are listed.")
            return

        self._set_busy(True)
        self.recheck_thread = RecheckThread(rows, self.library_section, self.matcher, self)
        self.recheck_thread.progress.connect(self._on_recheck_progress)
        self.recheck_thread.finished_with_results.connect(self._on_recheck_done)
        self.recheck_thread.failed.connect(self._on_recheck_failed)
        self.recheck_thread.finished.connect(lambda: self._set_busy(False))
        self.recheck_thread.start()

    def _set_busy(self, busy):
        self.progress_bar.setVisible(busy)
        if not busy:
            self.progress_bar.setValue(0)
        for widget in (
            self.recheck_btn,
            self.ignore_btn,
            self.restore_btn,
            self.delete_btn,
            self.status_combo,
            self.search_input,
        ):
            widget.setEnabled(not busy)
        if not busy:
            self._sync_button_states()

    def _on_recheck_progress(self, message, percentage):
        self.progress_bar.setValue(int(percentage))
        self.status_label.setText(message)

    def _on_recheck_done(self, found):
        for row, match in found:
            self.store.mark_resolved(
                self.library_key, row.get("fingerprint", ""), match.get("rating_key", "")
            )
        self.reload()
        if found:
            QMessageBox.information(
                self,
                "Re-check Complete",
                f"{len(found)} track(s) are now in your library and were marked resolved.",
            )
        else:
            QMessageBox.information(
                self,
                "Re-check Complete",
                "None of the listed tracks were found in the library yet.",
            )

    def _on_recheck_failed(self, message):
        QMessageBox.critical(self, "Re-check Failed", message)

    # ---------------------------------------------------------------- exports

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Missing Tracks", os.path.expanduser("~/missing_tracks.csv"), "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            count = self.store.export_csv(self.library_key, path, status=self._current_status())
        except Exception as error:
            QMessageBox.critical(self, "Export Failed", str(error))
            return
        QMessageBox.information(self, "Export Complete", f"Exported {count} track(s) to:\n{path}")

    def export_text(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Tracklist", os.path.expanduser("~/missing_tracks.txt"), "Text Files (*.txt)"
        )
        if not path:
            return
        try:
            count = self.store.export_text(self.library_key, path, status=self._current_status())
        except Exception as error:
            QMessageBox.critical(self, "Export Failed", str(error))
            return
        QMessageBox.information(self, "Export Complete", f"Exported {count} track(s) to:\n{path}")

    # ----------------------------------------------------------------- teardown

    def closeEvent(self, event):
        thread = self.recheck_thread
        if thread is not None and thread.isRunning():
            thread.stop()
            thread.wait(3000)
        super().closeEvent(event)
