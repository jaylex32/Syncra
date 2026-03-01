"""File Metadata Fixer dialog."""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from syncra.workers.metadata_worker import MetadataApplyWorker, MetadataScanWorker


class MetadataFixerDialog(QDialog):
    def __init__(self, metadata_service, get_tracks_for_scope, playlists, parent=None):
        super().__init__(parent)
        self.metadata_service = metadata_service
        self.get_tracks_for_scope = get_tracks_for_scope
        self.playlists = playlists
        self.proposals = []
        self.scan_worker = None
        self.apply_worker = None

        self.setWindowTitle("File Metadata Fixer")
        self.resize(1200, 700)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel("<h2>File Metadata Fixer (MusicBrainz)</h2>")
        layout.addWidget(header)
        hint = QLabel(
            "Writes metadata directly to local audio files (tags), then refreshes Plex metadata."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #b8c9df; font-size: 12px;")
        layout.addWidget(hint)

        source_group = QGroupBox("Scan Scope")
        source_layout = QVBoxLayout(source_group)

        scope_row = QHBoxLayout()
        scope_row.addWidget(QLabel("Source scope:"))
        self.scope_combo = QComboBox()
        self.scope_combo.addItem("Entire Library", "library")
        self.scope_combo.addItem("Selected Playlists", "playlists")
        self.scope_combo.currentIndexChanged.connect(self._toggle_playlist_selector)
        scope_row.addWidget(self.scope_combo)
        scope_row.addStretch()
        source_layout.addLayout(scope_row)

        self.playlist_picker = QListWidget()
        self.playlist_picker.setMaximumHeight(160)
        for playlist in self.playlists:
            item = QListWidgetItem(getattr(playlist, "title", "Unknown"))
            item.setData(Qt.ItemDataRole.UserRole, playlist)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.playlist_picker.addItem(item)
        source_layout.addWidget(self.playlist_picker)

        layout.addWidget(source_group)

        action_row = QHBoxLayout()
        self.scan_button = QPushButton("Scan File Metadata")
        self.scan_button.clicked.connect(self.start_scan)
        action_row.addWidget(self.scan_button)

        self.apply_button = QPushButton("Write Selected Fixes to Files")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.start_apply)
        action_row.addWidget(self.apply_button)

        action_row.addStretch()
        layout.addLayout(action_row)

        self.status_label = QLabel("Ready (file tag mode)")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels(
            [
                "Apply",
                "Confidence",
                "File",
                "Current Title",
                "Current Artist",
                "Current Album",
                "Proposed Title",
                "Proposed Artist",
                "Proposed Album",
                "Source",
            ]
        )
        layout.addWidget(self.table)

        self._toggle_playlist_selector()

    def _toggle_playlist_selector(self):
        is_playlist_scope = self.scope_combo.currentData() == "playlists"
        self.playlist_picker.setVisible(is_playlist_scope)

    def _selected_playlists(self):
        selected = []
        for i in range(self.playlist_picker.count()):
            item = self.playlist_picker.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.data(Qt.ItemDataRole.UserRole))
        return selected

    def start_scan(self):
        scope = self.scope_combo.currentData()
        playlists = self._selected_playlists()

        if scope == "playlists" and not playlists:
            QMessageBox.warning(self, "No Selection", "Select at least one playlist.")
            return

        tracks = self.get_tracks_for_scope(scope, playlists)
        if not tracks:
            QMessageBox.information(self, "No Tracks", "No tracks found for selected scope.")
            return

        self.table.setRowCount(0)
        self.apply_button.setEnabled(False)
        self.scan_button.setEnabled(False)
        self.status_label.setText("Scanning metadata proposals...")

        self.scan_worker = MetadataScanWorker(self.metadata_service, tracks, self)
        self.scan_worker.progress.connect(self.on_progress)
        self.scan_worker.completed.connect(self.on_scan_complete)
        self.scan_worker.failed.connect(self.on_scan_error)
        self.scan_worker.start()

    def start_apply(self):
        selected = []
        for row in range(self.table.rowCount()):
            widget = self.table.cellWidget(row, 0)
            if widget is None:
                continue
            checkbox = widget.findChild(QCheckBox)
            if checkbox and checkbox.isChecked():
                selected.append(self.proposals[row])

        if not selected:
            QMessageBox.warning(self, "No Selection", "Select at least one proposal to apply.")
            return

        self.apply_button.setEnabled(False)
        self.scan_button.setEnabled(False)
        self.status_label.setText("Writing metadata tags to files...")

        self.apply_worker = MetadataApplyWorker(self.metadata_service, selected, self)
        self.apply_worker.progress.connect(self.on_progress)
        self.apply_worker.completed.connect(self.on_apply_complete)
        self.apply_worker.failed.connect(self.on_apply_error)
        self.apply_worker.start()

    def on_progress(self, current, total, message):
        self.status_label.setText(message)
        pct = int((current / total) * 100) if total else 0
        self.progress_bar.setValue(pct)

    def on_scan_complete(self, proposals):
        self.proposals = proposals
        self.scan_button.setEnabled(True)
        self.apply_button.setEnabled(bool(proposals))
        self.status_label.setText(f"Scan complete: {len(proposals)} proposals")

        self.table.setRowCount(len(proposals))
        for row, proposal in enumerate(proposals):
            container = QWidget()
            layout = QHBoxLayout(container)
            layout.setContentsMargins(6, 0, 6, 0)
            check = QCheckBox()
            check.setChecked(True)
            layout.addWidget(check)
            layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setCellWidget(row, 0, container)

            self.table.setItem(row, 1, QTableWidgetItem(f"{proposal.confidence:.0f}"))
            self.table.setItem(row, 2, QTableWidgetItem(self._track_file_label(proposal.track.plex_track)))
            self.table.setItem(row, 3, QTableWidgetItem(proposal.track.title))
            self.table.setItem(row, 4, QTableWidgetItem(proposal.track.artist))
            self.table.setItem(row, 5, QTableWidgetItem(proposal.track.album))
            self.table.setItem(row, 6, QTableWidgetItem(proposal.candidate.title))
            self.table.setItem(row, 7, QTableWidgetItem(proposal.candidate.artist))
            self.table.setItem(row, 8, QTableWidgetItem(proposal.candidate.album))
            self.table.setItem(row, 9, QTableWidgetItem(proposal.candidate.source))

    def _track_file_label(self, track) -> str:
        try:
            if hasattr(track, "iterParts"):
                for part in track.iterParts():
                    path = getattr(part, "file", None)
                    if path:
                        return os.path.basename(path)
        except Exception:
            pass
        return "(no local file path)"

    def on_scan_error(self, error):
        self.scan_button.setEnabled(True)
        self.apply_button.setEnabled(False)
        self.status_label.setText("Scan failed")
        QMessageBox.critical(self, "Metadata Scan Error", error)

    def on_apply_complete(self, results):
        self.scan_button.setEnabled(True)
        self.apply_button.setEnabled(False)
        success = sum(1 for item in results if item.success)
        failures = len(results) - success
        applied_fields_count = sum(len(item.applied_fields or []) for item in results if item.success)
        failure_lines = [f"- {item.rating_key}: {item.error}" for item in results if not item.success and item.error]
        self.status_label.setText(f"Apply complete: {success} success, {failures} failed")
        details = f"Applied metadata updates.\n\nSuccess: {success}\nFailed: {failures}\nFields changed: {applied_fields_count}"
        if failure_lines:
            preview = "\n".join(failure_lines[:6])
            details += f"\n\nFailure details:\n{preview}"
        QMessageBox.information(
            self,
            "File Metadata Apply Complete",
            details + "\n\nMode: File tags (with Plex refresh)",
        )

    def on_apply_error(self, error):
        self.scan_button.setEnabled(True)
        self.apply_button.setEnabled(True)
        self.status_label.setText("Apply failed")
        QMessageBox.critical(self, "Metadata Apply Error", error)
