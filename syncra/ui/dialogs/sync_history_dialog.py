"""Sync run history, diff inspection, and revert.

Every sync records the playlist contents before and after it ran. This dialog makes
those runs inspectable after the fact and lets a run be undone by restoring the
"before" snapshot, which is the safety net 'Clear on Sync' has always needed.
"""

from __future__ import annotations

import logging

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from syncra.qt_compat import Qt

COL_WHEN, COL_PLAYLIST, COL_CHANGE, COL_UNMATCHED, COL_STATUS = range(5)

_STATUS_COLORS = {
    "success": "#7ee2b8",
    "failed": "#ff9b9b",
    "reverted": "#ffd08a",
    "running": "#9cb2d2",
}


class SyncHistoryDialog(QDialog):
    def __init__(self, store, library_key, revert_callback=None, parent=None):
        super().__init__(parent)
        self.store = store
        self.library_key = library_key
        self.revert_callback = revert_callback
        self._runs = []

        self.setWindowTitle("Sync History")
        self.setMinimumSize(960, 640)
        self._build_ui()
        self.reload()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        intro = QLabel(
            "Every sync run, with the exact playlist contents before and after. "
            "Select a run to see what changed, or revert it to restore the earlier track list."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #b8c9df; font-size: 12px;")
        layout.addWidget(intro)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Playlist:"))
        self.playlist_combo = QComboBox()
        self.playlist_combo.setMinimumHeight(32)
        self.playlist_combo.currentIndexChanged.connect(self._refresh_table)
        filter_row.addWidget(self.playlist_combo, 1)
        layout.addLayout(filter_row)

        splitter = QSplitter(Qt.Orientation.Vertical)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["When", "Playlist", "Change", "Unmatched", "Status"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._show_selected_detail)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_PLAYLIST, QHeaderView.ResizeMode.Stretch)
        for column in (COL_WHEN, COL_CHANGE, COL_UNMATCHED, COL_STATUS):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        splitter.addWidget(self.table)

        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setPlaceholderText("Select a run to see the tracks it added and removed.")
        splitter.addWidget(self.detail)
        splitter.setSizes([320, 260])
        layout.addWidget(splitter, 1)

        button_row = QHBoxLayout()
        self.revert_btn = QPushButton("↩ Revert This Run")
        self.revert_btn.setToolTip("Restore the playlist to its contents from before this run.")
        self.revert_btn.setEnabled(False)
        self.revert_btn.clicked.connect(self.revert_selected)
        button_row.addWidget(self.revert_btn)
        button_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)

    # ------------------------------------------------------------------- data

    def reload(self):
        self._runs = self.store.list_runs(self.library_key)
        names = sorted({run.get("playlist_name", "") for run in self._runs if run.get("playlist_name")})

        self.playlist_combo.blockSignals(True)
        current = self.playlist_combo.currentData()
        self.playlist_combo.clear()
        self.playlist_combo.addItem("All playlists", None)
        for name in names:
            self.playlist_combo.addItem(name, name)
        if current:
            index = self.playlist_combo.findData(current)
            if index >= 0:
                self.playlist_combo.setCurrentIndex(index)
        self.playlist_combo.blockSignals(False)

        self._refresh_table()

    def _visible_runs(self):
        selected = self.playlist_combo.currentData()
        if not selected:
            return list(self._runs)
        return [run for run in self._runs if run.get("playlist_name") == selected]

    def _refresh_table(self):
        runs = self._visible_runs()
        self.table.setRowCount(len(runs))
        for row_index, run in enumerate(runs):
            changes = run.get("changes", {})
            added = run.get("added_count", 0)
            removed = run.get("removed_count", 0)
            if added or removed:
                change_text = f"+{added} / -{removed}"
            elif changes.get("reordered"):
                change_text = "reordered"
            else:
                change_text = "no change"

            self.table.setItem(row_index, COL_WHEN, QTableWidgetItem(run.get("started_at", "")))
            self.table.setItem(row_index, COL_PLAYLIST, QTableWidgetItem(run.get("playlist_name", "")))
            self.table.setItem(row_index, COL_CHANGE, QTableWidgetItem(change_text))
            self.table.setItem(
                row_index, COL_UNMATCHED, QTableWidgetItem(str(run.get("unmatched_count", 0)))
            )
            status_item = QTableWidgetItem(run.get("status", ""))
            color = _STATUS_COLORS.get(run.get("status", ""))
            if color:
                from PyQt6.QtGui import QColor

                status_item.setForeground(QColor(color))
            self.table.setItem(row_index, COL_STATUS, status_item)
        self.detail.clear()
        self.revert_btn.setEnabled(False)

    def _selected_run(self):
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        runs = self._visible_runs()
        index = rows[0].row()
        return runs[index] if 0 <= index < len(runs) else None

    def _show_selected_detail(self):
        run = self._selected_run()
        if run is None:
            self.detail.clear()
            self.revert_btn.setEnabled(False)
            return

        changes = run.get("changes", {})
        lines = [
            f"Playlist: {run.get('playlist_name', '')}",
            f"Source:   {run.get('source', '') or 'n/a'}",
            f"Started:  {run.get('started_at', '')}",
            f"Finished: {run.get('finished_at', '') or 'n/a'}",
            f"Status:   {run.get('status', '')}",
            f"Tracks:   {changes.get('before_count', 0)} → {changes.get('after_count', 0)}",
            "",
        ]
        if run.get("message"):
            lines.extend([str(run["message"]), ""])

        added = changes.get("added", [])
        removed = changes.get("removed", [])
        if added:
            lines.append(f"Added ({len(added)}):")
            lines.extend(f"  + {self._describe(row)}" for row in added[:200])
            if len(added) > 200:
                lines.append(f"  ... and {len(added) - 200} more")
            lines.append("")
        if removed:
            lines.append(f"Removed ({len(removed)}):")
            lines.extend(f"  - {self._describe(row)}" for row in removed[:200])
            if len(removed) > 200:
                lines.append(f"  ... and {len(removed) - 200} more")
            lines.append("")
        if not added and not removed:
            lines.append("Reordered only." if changes.get("reordered") else "No track changes.")

        self.detail.setPlainText("\n".join(lines))

        can_revert = (
            self.revert_callback is not None
            and run.get("status") == "success"
            and bool(run.get("before_snapshot"))
        )
        self.revert_btn.setEnabled(can_revert)

    @staticmethod
    def _describe(row):
        title = row.get("title", "") or "Unknown"
        artist = row.get("artist", "")
        album = row.get("album", "")
        text = f"{artist} - {title}" if artist else title
        return f"{text} [{album}]" if album else text

    # ---------------------------------------------------------------- actions

    def revert_selected(self):
        run = self._selected_run()
        if run is None or self.revert_callback is None:
            return
        before = run.get("before_snapshot", [])
        confirm = QMessageBox.question(
            self,
            "Revert Sync Run",
            f"Restore '{run.get('playlist_name', '')}' to its contents from "
            f"{run.get('started_at', '')}?\n\n"
            f"The playlist will be rebuilt with {len(before)} track(s), replacing what is "
            "in it now.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            ok, message = self.revert_callback(run)
        except Exception as error:
            logging.error(f"Revert failed: {error}", exc_info=True)
            QMessageBox.critical(self, "Revert Failed", str(error))
            return

        if ok:
            self.store.mark_reverted(run.get("run_id", ""))
            self.reload()
            QMessageBox.information(self, "Revert Complete", message or "Playlist restored.")
        else:
            QMessageBox.warning(self, "Revert Failed", message or "Could not restore the playlist.")
