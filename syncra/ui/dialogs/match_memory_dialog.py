"""Review and manage learned track-matching decisions.

Match memory is only trustworthy if it is inspectable. This dialog lists every decision
Syncra has learned for the selected library, how often each one has been used, and
allows any of them to be forgotten when a decision turns out to be wrong.
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from syncra.qt_compat import Qt
from syncra.services.match_memory import KIND_MATCH, KIND_MISSING

COL_SOURCE, COL_DECISION, COL_TARGET, COL_USES, COL_UPDATED = range(5)


class MatchMemoryDialog(QDialog):
    def __init__(self, store, library_key, parent=None):
        super().__init__(parent)
        self.store = store
        self.library_key = library_key
        self._rows = []

        self.setWindowTitle("Match Memory")
        self.setMinimumSize(880, 560)
        self._build_ui()
        self.reload()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        intro = QLabel(
            "Decisions Syncra learned from your manual match corrections. These override "
            "automatic scoring, so repeat imports of the same track resolve the same way "
            "without asking again."
        )
        intro.setWordWrap(True)
        intro.setStyleSheet("color: #b8c9df; font-size: 12px;")
        layout.addWidget(intro)

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Show:"))
        self.kind_combo = QComboBox()
        self.kind_combo.addItem("All decisions", None)
        self.kind_combo.addItem("Forced matches", KIND_MATCH)
        self.kind_combo.addItem("Known missing", KIND_MISSING)
        self.kind_combo.setMinimumHeight(32)
        self.kind_combo.currentIndexChanged.connect(self.reload)
        filter_row.addWidget(self.kind_combo)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Source track", "Decision", "Resolves to", "Times used", "Updated"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_SOURCE, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_TARGET, QHeaderView.ResizeMode.Stretch)
        for column in (COL_DECISION, COL_USES, COL_UPDATED):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table, 1)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #9cb2d2; font-size: 12px;")
        layout.addWidget(self.status_label)

        button_row = QHBoxLayout()
        self.forget_btn = QPushButton("Forget Selected")
        self.forget_btn.setToolTip("Remove these decisions so automatic scoring applies again.")
        self.forget_btn.clicked.connect(self.forget_selected)
        button_row.addWidget(self.forget_btn)

        self.clear_btn = QPushButton("Forget All")
        self.clear_btn.clicked.connect(self.clear_all)
        button_row.addWidget(self.clear_btn)

        button_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.reject)
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)

    def reload(self):
        self._rows = self.store.list_overrides(self.library_key, kind=self.kind_combo.currentData())
        self.table.setRowCount(len(self._rows))
        for row_index, row in enumerate(self._rows):
            source = row.get("source_artist", "")
            source_text = (
                f"{source} - {row.get('source_title', '')}" if source else row.get("source_title", "")
            )
            if row.get("kind") == KIND_MISSING:
                decision = "Known missing"
                target_text = "—"
            else:
                decision = "Forced match"
                target_artist = row.get("target_artist", "")
                target_title = row.get("target_title", "")
                target_text = (
                    f"{target_artist} - {target_title}" if target_artist else target_title
                ) or f"ratingKey {row.get('rating_key', '')}"

            self._set_cell(row_index, COL_SOURCE, source_text, row)
            self._set_cell(row_index, COL_DECISION, decision, row)
            self._set_cell(row_index, COL_TARGET, target_text, row)
            self._set_cell(row_index, COL_USES, str(row.get("hit_count", 0)), row)
            self._set_cell(row_index, COL_UPDATED, row.get("updated_at", ""), row)

        total = self.store.count(self.library_key)
        self.status_label.setText(f"{len(self._rows)} shown · {total} learned decision(s) for this library")
        self.forget_btn.setEnabled(bool(self._rows))
        self.clear_btn.setEnabled(total > 0)

    def _set_cell(self, row_index, column, text, row):
        item = QTableWidgetItem(str(text or ""))
        item.setData(Qt.ItemDataRole.UserRole, row.get("fingerprint", ""))
        self.table.setItem(row_index, column, item)

    def _selected_fingerprints(self):
        fingerprints = []
        for index in self.table.selectionModel().selectedRows():
            item = self.table.item(index.row(), COL_SOURCE)
            if item is None:
                continue
            fingerprint = item.data(Qt.ItemDataRole.UserRole)
            if fingerprint:
                fingerprints.append(fingerprint)
        return fingerprints

    def forget_selected(self):
        fingerprints = self._selected_fingerprints()
        if not fingerprints:
            QMessageBox.information(self, "Nothing Selected", "Select one or more decisions first.")
            return
        for fingerprint in fingerprints:
            self.store.forget(self.library_key, fingerprint)
        self.reload()

    def clear_all(self):
        confirm = QMessageBox.question(
            self,
            "Forget All Decisions",
            "Remove every learned matching decision for this library?\n\n"
            "Future imports will fall back to automatic scoring and may ask you to "
            "resolve the same tracks again.",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        removed = self.store.clear(self.library_key)
        self.reload()
        QMessageBox.information(self, "Match Memory Cleared", f"Removed {removed} decision(s).")
