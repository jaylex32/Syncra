"""Export a playlist as audio files you can actually take with you.

The plain .m3u export writes server-side paths, which are meaningless anywhere except
the Plex server. This copies the audio too, so the folder works on a USB stick, a phone
or a car stereo. Transcoding is done by the Plex server, so nothing needs installing.
"""

from __future__ import annotations

import logging
import os

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from syncra.qt_compat import Qt
from syncra.services.playlist_export import (
    FORMAT_MP3_128,
    FORMAT_MP3_192,
    FORMAT_MP3_320,
    FORMAT_ORIGINAL,
    STRUCTURES,
    STRUCTURE_FLAT,
    estimate_total_bytes,
    export_playlist,
    format_bytes,
)
from syncra.theme.styles import (
    CONTROL_HEIGHT,
    PAGE_MARGIN,
    PAGE_SPACING,
    SIDE_LABEL_COLUMN,
    SPACE_MD,
    SPACE_SM,
)

SIZE_PRESETS = (
    ("No limit", None),
    ("1 GB", 1024 ** 3),
    ("2 GB", 2 * 1024 ** 3),
    ("4 GB (FAT32 stick)", 4 * 1024 ** 3),
    ("8 GB", 8 * 1024 ** 3),
    ("16 GB", 16 * 1024 ** 3),
    ("32 GB", 32 * 1024 ** 3),
)


class ExportWorker(QThread):
    progress = pyqtSignal(int, int, str)
    finished_report = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, *, tracks, destination, playlist_name, server, audio_format,
                 structure, max_bytes, parent=None):
        super().__init__(parent)
        self.tracks = tracks
        self.destination = destination
        self.playlist_name = playlist_name
        self.server = server
        self.audio_format = audio_format
        self.structure = structure
        self.max_bytes = max_bytes
        self._cancelled = False

    def stop(self):
        self._cancelled = True

    def run(self):
        try:
            report = export_playlist(
                self.tracks,
                self.destination,
                playlist_name=self.playlist_name,
                server=self.server,
                audio_format=self.audio_format,
                structure=self.structure,
                max_bytes=self.max_bytes,
                progress=lambda done, total, item: self.progress.emit(
                    done, total, item.title
                ),
                should_cancel=lambda: self._cancelled,
            )
            self.finished_report.emit(report)
        except Exception as error:
            logging.error(f"Export failed: {error}", exc_info=True)
            self.failed.emit(str(error))


class ExportFilesDialog(QDialog):
    def __init__(self, playlist, plex_server, parent=None):
        super().__init__(parent)
        self.playlist = playlist
        self.plex_server = plex_server
        self.tracks = []
        self.worker = None

        self.setWindowTitle(f"Export \"{playlist.title}\" with audio files")
        self.setModal(True)
        self.resize(680, 460)
        self.setMinimumSize(560, 420)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        layout.setSpacing(PAGE_SPACING)

        heading = QLabel(
            "Copies the audio itself into a folder with a playlist that uses relative "
            "paths, so it plays on a USB stick, phone or car stereo. Conversion is done "
            "by your Plex server."
        )
        heading.setWordWrap(True)
        layout.addWidget(heading)

        form = QGridLayout()
        form.setHorizontalSpacing(SPACE_MD)
        form.setVerticalSpacing(SPACE_SM)
        form.setColumnMinimumWidth(0, SIDE_LABEL_COLUMN)
        form.setColumnStretch(1, 1)
        row = 0

        form.addWidget(self._label("Destination:"), row, 0)
        destination_row = QHBoxLayout()
        destination_row.setSpacing(SPACE_SM)
        self.destination_input = QLineEdit()
        self.destination_input.setPlaceholderText("Folder or USB drive to export into")
        self.destination_input.setMinimumHeight(CONTROL_HEIGHT)
        destination_row.addWidget(self.destination_input, 1)
        browse = QPushButton("Browse")
        browse.setMinimumHeight(CONTROL_HEIGHT)
        browse.clicked.connect(self.browse_destination)
        destination_row.addWidget(browse)
        form.addLayout(destination_row, row, 1)
        row += 1

        form.addWidget(self._label("Format:"), row, 0)
        self.format_combo = QComboBox()
        self.format_combo.setMinimumHeight(CONTROL_HEIGHT)
        self.format_combo.addItem("Original files (no conversion)", FORMAT_ORIGINAL)
        self.format_combo.addItem("MP3 320 kbps", FORMAT_MP3_320)
        self.format_combo.addItem("MP3 192 kbps", FORMAT_MP3_192)
        self.format_combo.addItem("MP3 128 kbps", FORMAT_MP3_128)
        self.format_combo.currentIndexChanged.connect(self.refresh_estimate)
        form.addWidget(self.format_combo, row, 1)
        row += 1

        form.addWidget(self._label("Folders:"), row, 0)
        self.structure_combo = QComboBox()
        self.structure_combo.setMinimumHeight(CONTROL_HEIGHT)
        for key, label, example in STRUCTURES:
            self.structure_combo.addItem(label, key)
            self.structure_combo.setItemData(
                self.structure_combo.count() - 1, example, Qt.ItemDataRole.ToolTipRole
            )
        self.structure_combo.currentIndexChanged.connect(self.refresh_structure_example)
        form.addWidget(self.structure_combo, row, 1)
        row += 1

        form.addWidget(QLabel(""), row, 0)
        self.structure_example = QLabel("")
        self.structure_example.setObjectName("mutedText")
        form.addWidget(self.structure_example, row, 1)
        row += 1

        form.addWidget(self._label("Size limit:"), row, 0)
        self.size_combo = QComboBox()
        self.size_combo.setMinimumHeight(CONTROL_HEIGHT)
        for label, value in SIZE_PRESETS:
            self.size_combo.addItem(label, value)
        form.addWidget(self.size_combo, row, 1)
        row += 1

        layout.addLayout(form)

        self.estimate_label = QLabel("")
        self.estimate_label.setObjectName("mutedText")
        self.estimate_label.setWordWrap(True)
        layout.addWidget(self.estimate_label)

        layout.addStretch()

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status_label = QLabel("")
        self.status_label.setObjectName("mutedText")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        buttons = QHBoxLayout()
        buttons.setSpacing(SPACE_SM)
        buttons.addStretch()
        self.export_btn = QPushButton("Export")
        self.export_btn.setProperty("variant", "primary")
        self.export_btn.setMinimumHeight(CONTROL_HEIGHT)
        self.export_btn.clicked.connect(self.start_export)
        buttons.addWidget(self.export_btn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setMinimumHeight(CONTROL_HEIGHT)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self.cancel_export)
        buttons.addWidget(self.cancel_btn)
        self.close_btn = QPushButton("Close")
        self.close_btn.setMinimumHeight(CONTROL_HEIGHT)
        self.close_btn.clicked.connect(self.reject)
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)

        self.refresh_structure_example()
        self.load_tracks()

    @staticmethod
    def _label(text):
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return label

    # ------------------------------------------------------------------ setup

    def load_tracks(self):
        try:
            self.tracks = list(self.playlist.items())
        except Exception as error:
            logging.warning(f"Could not read playlist tracks: {error}")
            self.tracks = []
            self.status_label.setText(f"Could not read this playlist: {error}")
            self.export_btn.setEnabled(False)
            return
        self.refresh_estimate()

    def refresh_estimate(self):
        if not self.tracks:
            self.estimate_label.setText("")
            return
        audio_format = self.format_combo.currentData()
        total = estimate_total_bytes(self.tracks, audio_format)
        original = estimate_total_bytes(self.tracks, FORMAT_ORIGINAL)

        text = f"{len(self.tracks)} track(s), about {format_bytes(total)}"
        if audio_format != FORMAT_ORIGINAL and original:
            saved = max(0, original - total)
            text += f" — down from {format_bytes(original)}, saving {format_bytes(saved)}"
        self.estimate_label.setText(text)

    def refresh_structure_example(self):
        """Show the resulting path so the layout choice is concrete."""
        key = self.structure_combo.currentData()
        for structure, _label, example in STRUCTURES:
            if structure == key:
                self.structure_example.setText(f"e.g.  {example}")
                return
        self.structure_example.setText("")

    def browse_destination(self):
        folder = QFileDialog.getExistingDirectory(self, "Choose export folder")
        if folder:
            self.destination_input.setText(folder)

    # ------------------------------------------------------------------ run

    def start_export(self):
        destination = self.destination_input.text().strip()
        if not destination:
            QMessageBox.information(self, "No Destination",
                                    "Choose a folder or drive to export into.")
            return
        if not self.tracks:
            QMessageBox.information(self, "Empty Playlist",
                                    "This playlist has no tracks to export.")
            return

        audio_format = self.format_combo.currentData()
        max_bytes = self.size_combo.currentData()
        estimated = estimate_total_bytes(self.tracks, audio_format)

        confirm = QMessageBox.question(
            self,
            "Start Export?",
            f"Export {len(self.tracks)} track(s) — about {format_bytes(estimated)} — into:\n\n"
            f"{destination}\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        self._set_busy(True)
        self.progress.setRange(0, len(self.tracks))
        self.progress.setValue(0)

        self.worker = ExportWorker(
            tracks=self.tracks,
            destination=destination,
            playlist_name=self.playlist.title,
            server=self.plex_server,
            audio_format=audio_format,
            structure=self.structure_combo.currentData(),
            max_bytes=max_bytes,
            parent=self,
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_report.connect(self._on_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def cancel_export(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.status_label.setText("Finishing the current track, then stopping...")

    def _set_busy(self, busy):
        self.progress.setVisible(busy)
        self.export_btn.setEnabled(not busy)
        self.cancel_btn.setVisible(busy)
        self.close_btn.setEnabled(not busy)
        for widget in (self.format_combo, self.structure_combo,
                       self.size_combo, self.destination_input):
            widget.setEnabled(not busy)

    def _on_progress(self, done, total, title):
        self.progress.setValue(done)
        self.status_label.setText(f"{done}/{total} — {title}")

    def _on_finished(self, report):
        self._set_busy(False)
        parts = [f"{len(report.exported)} exported"]
        if report.skipped:
            parts.append(f"{len(report.skipped)} skipped")
        if report.failed:
            parts.append(f"{len(report.failed)} failed")
        summary = ", ".join(parts) + f" — {format_bytes(report.bytes_written)} written"
        if report.cancelled:
            summary = "Cancelled. " + summary
        self.status_label.setText(summary)

        detail = summary
        if report.playlist_file:
            detail += f"\n\nPlaylist written to:\n{os.path.basename(report.playlist_file)}"
        if report.failed:
            first = report.failed[0]
            detail += f"\n\nFirst failure: {first[0].title} — {first[1]}"
        QMessageBox.information(self, "Export Finished", detail)

    def _on_failed(self, message):
        self._set_busy(False)
        self.status_label.setText("Export failed.")
        QMessageBox.critical(self, "Export Failed", message)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(8000)
        super().closeEvent(event)
