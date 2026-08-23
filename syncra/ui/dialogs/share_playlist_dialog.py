"""Share a playlist with the other Plex accounts on this server.

Plex playlists belong to whoever created them, and Plex offers no way to give one to
another member of the household. On a server with several users that means every
playlist the admin builds is invisible to everyone else.

The work runs on a thread because each user costs a token lookup plus a write, and the
report is per-user: one person failing never hides what happened to the others.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from syncra.qt_compat import Qt
from syncra.services.playlist_sharing import (
    MODE_CREATE,
    MODE_MERGE,
    MODE_REPLACE,
    STATUS_CREATED,
    STATUS_FAILED,
    STATUS_SKIPPED,
    STATUS_UPDATED,
    list_household_users,
    playlist_rating_keys,
    share_playlist,
)
from syncra.theme.styles import (
    CONTROL_HEIGHT,
    GROUP_MARGIN,
    GROUP_SPACING,
    PAGE_MARGIN,
    PAGE_SPACING,
    SPACE_SM,
    TOKENS,
)

COL_USER, COL_KIND, COL_RESULT = range(3)


def _result_colours():
    """Row colours, read from the live palette so they follow the theme."""
    return {
        STATUS_CREATED: TOKENS["ok_fg"],
        STATUS_UPDATED: TOKENS["ok_fg"],
        STATUS_SKIPPED: TOKENS["txt_muted"],
        STATUS_FAILED: TOKENS["danger_fg"],
    }


class ShareWorker(QThread):
    progress = pyqtSignal(str)
    finished_report = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, *, account, base_url, machine_identifier, title, rating_keys,
                 targets, mode, parent=None):
        super().__init__(parent)
        self.account = account
        self.base_url = base_url
        self.machine_identifier = machine_identifier
        self.title = title
        self.rating_keys = rating_keys
        self.targets = targets
        self.mode = mode
        self._cancelled = False

    def stop(self):
        self._cancelled = True

    def run(self):
        try:
            report = share_playlist(
                account=self.account,
                base_url=self.base_url,
                machine_identifier=self.machine_identifier,
                title=self.title,
                rating_keys=self.rating_keys,
                targets=self.targets,
                mode=self.mode,
                progress=self.progress.emit,
                should_cancel=lambda: self._cancelled,
            )
            self.finished_report.emit(report)
        except Exception as error:
            logging.error(f"Sharing failed: {error}", exc_info=True)
            self.failed.emit(str(error))


class SharePlaylistDialog(QDialog):
    def __init__(self, playlist, plex_server, account, parent=None):
        super().__init__(parent)
        self.playlist = playlist
        self.plex_server = plex_server
        self.account = account
        self.worker = None
        self.users = []
        self.rating_keys = []

        self.setWindowTitle(f"Share \"{playlist.title}\" with your household")
        self.setModal(True)
        self.resize(720, 560)
        self.setMinimumSize(560, 460)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        layout.setSpacing(PAGE_SPACING)

        heading = QLabel(
            f"<b>{playlist.title}</b> belongs to your account only. "
            "Plex has no way to hand a playlist to another user, so pick who should "
            "get their own copy on this server."
        )
        heading.setWordWrap(True)
        layout.addWidget(heading)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["User", "Account", "Result"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        header = self.tree.header()
        header.setSectionResizeMode(COL_USER, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_KIND, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_RESULT, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.tree, 1)

        select_row = QHBoxLayout()
        select_row.setSpacing(SPACE_SM)
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(lambda: self._set_all(True))
        select_row.addWidget(self.select_all_btn)
        self.select_none_btn = QPushButton("Select None")
        self.select_none_btn.clicked.connect(lambda: self._set_all(False))
        select_row.addWidget(self.select_none_btn)
        select_row.addStretch()
        layout.addLayout(select_row)

        mode_label = QLabel("If they already have a playlist with this name:")
        layout.addWidget(mode_label)

        self.mode_skip = QRadioButton("Leave theirs alone (skip)")
        self.mode_skip.setChecked(True)
        self.mode_merge = QRadioButton("Add only the tracks they are missing")
        self.mode_replace = QRadioButton("Replace theirs with this one (deletes their copy)")
        for button in (self.mode_skip, self.mode_merge, self.mode_replace):
            layout.addWidget(button)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        self.status_label = QLabel("")
        self.status_label.setObjectName("mutedText")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        buttons = QHBoxLayout()
        buttons.setSpacing(SPACE_SM)
        buttons.addStretch()
        self.share_btn = QPushButton("Share")
        self.share_btn.setProperty("variant", "primary")
        self.share_btn.setMinimumHeight(CONTROL_HEIGHT)
        self.share_btn.clicked.connect(self.start_share)
        buttons.addWidget(self.share_btn)
        self.close_btn = QPushButton("Close")
        self.close_btn.setMinimumHeight(CONTROL_HEIGHT)
        self.close_btn.clicked.connect(self.reject)
        buttons.addWidget(self.close_btn)
        layout.addLayout(buttons)

        self.load_users()

    # ------------------------------------------------------------------ setup

    def load_users(self):
        self.users = list_household_users(self.account)
        self.tree.clear()

        if not self.users:
            self.status_label.setText(
                "No other accounts share this server, so there is nobody to share with."
            )
            self.share_btn.setEnabled(False)
            return

        for user in self.users:
            item = QTreeWidgetItem([user.title, user.kind, ""])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(COL_USER, Qt.CheckState.Unchecked)
            item.setData(COL_USER, Qt.ItemDataRole.UserRole, user)
            if user.email:
                item.setToolTip(COL_USER, user.email)
            self.tree.addTopLevelItem(item)

        self.status_label.setText(
            f"{len(self.users)} account(s) share this server."
        )

    def _set_all(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for index in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(index).setCheckState(COL_USER, state)

    def selected_users(self):
        chosen = []
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            if item.checkState(COL_USER) == Qt.CheckState.Checked:
                chosen.append(item.data(COL_USER, Qt.ItemDataRole.UserRole))
        return chosen

    def selected_mode(self):
        if self.mode_replace.isChecked():
            return MODE_REPLACE
        if self.mode_merge.isChecked():
            return MODE_MERGE
        return MODE_CREATE

    # ------------------------------------------------------------------ run

    def start_share(self):
        targets = self.selected_users()
        if not targets:
            QMessageBox.information(self, "Nobody Selected",
                                    "Tick at least one account to share with.")
            return

        mode = self.selected_mode()
        names = ", ".join(user.title for user in targets)

        if mode == MODE_REPLACE:
            # This deletes a playlist belonging to somebody else.
            confirm = QMessageBox.warning(
                self,
                "Replace Their Playlist?",
                f"If {names} already have a playlist called \"{self.playlist.title}\", "
                f"their copy will be deleted and replaced.\n\nThis cannot be undone. Continue?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return

        try:
            self.rating_keys = playlist_rating_keys(self.playlist)
        except Exception as error:
            QMessageBox.critical(self, "Could Not Read Playlist",
                                 f"Could not read the tracks in this playlist.\n\n{error}")
            return

        if not self.rating_keys:
            QMessageBox.information(self, "Empty Playlist",
                                    "This playlist has no tracks to share.")
            return

        for index in range(self.tree.topLevelItemCount()):
            self.tree.topLevelItem(index).setText(COL_RESULT, "")

        self._set_busy(True)
        self.status_label.setText(f"Sharing {len(self.rating_keys)} track(s)...")

        self.worker = ShareWorker(
            account=self.account,
            base_url=self.plex_server._baseurl,
            machine_identifier=self.plex_server.machineIdentifier,
            title=self.playlist.title,
            rating_keys=self.rating_keys,
            targets=targets,
            mode=mode,
            parent=self,
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_report.connect(self._on_finished)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _set_busy(self, busy):
        self.progress.setVisible(busy)
        self.share_btn.setEnabled(not busy)
        self.select_all_btn.setEnabled(not busy)
        self.select_none_btn.setEnabled(not busy)
        for button in (self.mode_skip, self.mode_merge, self.mode_replace):
            button.setEnabled(not busy)

    def _on_progress(self, name):
        self.status_label.setText(f"Sharing with {name}...")

    def _row_for(self, name):
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            if item.text(COL_USER) == name:
                return item
        return None

    def _on_finished(self, report):
        from PyQt6.QtGui import QColor

        for outcome in report.outcomes:
            item = self._row_for(outcome.user)
            if item is None:
                continue
            item.setText(COL_RESULT, outcome.message or outcome.status)
            colour = _result_colours().get(outcome.status)
            if colour:
                item.setForeground(COL_RESULT, QColor(colour))

        self._set_busy(False)
        parts = []
        if report.succeeded:
            parts.append(f"{report.succeeded} shared")
        if report.skipped:
            parts.append(f"{report.skipped} skipped")
        if report.failed:
            parts.append(f"{report.failed} failed")
        self.status_label.setText("; ".join(parts) or "Nothing to do.")

    def _on_failed(self, message):
        self._set_busy(False)
        self.status_label.setText("Sharing failed.")
        QMessageBox.critical(self, "Sharing Failed", message)

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(5000)
        super().closeEvent(event)
