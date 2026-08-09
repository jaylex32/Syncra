"""Sonic Discovery: generate playlists from Plex's own audio analysis.

Two modes share one surface because they produce the same thing -- an ordered track
list you review and then save:

    More Like This   one seed track  -> its sonic neighbours
    Sonic Adventure  two tracks      -> the gradual path between them

Generation runs on a worker thread: on a large library Plex can take several seconds
to answer, and a frozen dialog reads as a crash.
"""

from __future__ import annotations

import logging

from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from syncra.qt_compat import Qt
from syncra.services import sonic_discovery
from syncra.services.sonic_discovery import SonicUnavailable, track_label
from syncra.ui.widgets.track_picker import TrackPicker
from syncra.theme.styles import (
    CONTROL_HEIGHT,
    FIELD_MAX_WIDTH,
    FIELD_SPACING,
    GROUP_MARGIN,
    GROUP_SPACING,
    LABEL_COLUMN,
    PAGE_MARGIN,
    PAGE_SPACING,
    SPACE_MD,
    SPACE_SM,
    SPACE_XS,
)

MODE_SIMILAR = "similar"
MODE_ADVENTURE = "adventure"

COL_INDEX, COL_LOCK, COL_TITLE, COL_ARTIST, COL_ALBUM, COL_TIME = range(6)

# Width of the left control column. Everything beyond this belongs to the playlist.
CONTROL_PANEL_WIDTH = 340


class SonicGenerateThread(QThread):
    """Ask Plex for neighbours or a path without blocking the dialog."""

    generated = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, mode, library_section, seeds, target, limit, max_distance,
                 locked=(), variety=0.0, collapse_same_song=True, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.library_section = library_section
        self.seeds = list(seeds or [])
        self.target = target
        self.locked = list(locked or [])
        self.variety = variety
        self.collapse_same_song = collapse_same_song
        self.limit = limit
        self.max_distance = max_distance

    def run(self):
        try:
            if self.mode == MODE_ADVENTURE:
                result = sonic_discovery.sonic_adventure(
                    self.library_section, self.seeds[0], self.target
                )
            else:
                result = sonic_discovery.generate_mix(
                    self.seeds,
                    limit=self.limit,
                    max_distance=self.max_distance,
                    locked=self.locked,
                    variety=self.variety,
                    collapse_same_song=self.collapse_same_song,
                )
            self.generated.emit(result)
        except SonicUnavailable as error:
            self.failed.emit(str(error))
        except Exception as error:
            logging.error(f"Sonic generation failed: {error}", exc_info=True)
            self.failed.emit(str(error))


class SonicDiscoveryDialog(QDialog):
    def __init__(self, plex_server, library_section, seed_track=None,
                 mode=MODE_SIMILAR, parent=None):
        super().__init__(parent)
        self.plex_server = plex_server
        self.library_section = library_section
        self.seed_track = seed_track
        self.target_track = None
        self.result = None
        self.generate_thread = None

        self.setWindowTitle("Sonic Discovery")
        self.setMinimumSize(1040, 620)
        self._build_ui()
        self._set_mode(mode)
        if seed_track is not None:
            self._show_seed(seed_track)

    # ---------------------------------------------------------------------- ui

    def _build_ui(self):
        """Two columns: fixed-width controls on the left, results filling the right.

        Stacking everything vertically gave the setup card ~660px and left the result
        table showing two rows. Side by side, the controls take a constant amount of
        space and every extra pixel of window height goes to the playlist.
        """
        layout = QVBoxLayout(self)
        layout.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        layout.setSpacing(SPACE_SM)

        intro = QLabel(
            "Build playlists from Plex's own analysis of your files. "
            "Nothing leaves your server."
        )
        intro.setObjectName("helperText")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # A splitter rather than a fixed pane, so the controls can be narrowed on a
        # small screen or widened to read long track names.
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(self._build_source_panel())
        splitter.addWidget(self._build_results_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([CONTROL_PANEL_WIDTH, 720])
        layout.addWidget(splitter, 1)

        save_row = QHBoxLayout()
        save_row.setSpacing(FIELD_SPACING)
        save_row.addWidget(QLabel("Playlist name:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Named automatically from your selection")
        self.name_input.setMinimumHeight(CONTROL_HEIGHT)
        save_row.addWidget(self.name_input, 1)
        self.save_btn = QPushButton("Save as Plex Playlist")
        self.save_btn.setProperty("variant", "primary")
        self.save_btn.setMinimumHeight(CONTROL_HEIGHT)
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self.save_playlist)
        save_row.addWidget(self.save_btn)
        close_btn = QPushButton("Close")
        close_btn.setMinimumHeight(CONTROL_HEIGHT)
        close_btn.clicked.connect(self.reject)
        save_row.addWidget(close_btn)
        layout.addLayout(save_row)

    def _build_source_panel(self):
        setup = QGroupBox("Source")
        setup.setMinimumWidth(CONTROL_PANEL_WIDTH)
        setup.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        column = QVBoxLayout(setup)
        column.setContentsMargins(GROUP_MARGIN, GROUP_MARGIN, GROUP_MARGIN, GROUP_MARGIN)
        column.setSpacing(SPACE_SM)

        column.addWidget(self._caption("Mode"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("More Like This", MODE_SIMILAR)
        self.mode_combo.addItem("Sonic Adventure", MODE_ADVENTURE)
        self.mode_combo.setMinimumHeight(CONTROL_HEIGHT)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        column.addWidget(self.mode_combo)

        column.addWidget(self._caption("Find a track"))
        self.seed_picker = TrackPicker(
            self.library_section, "Search tracks, artists or albums..."
        )
        self.seed_picker.results.setMinimumHeight(110)
        self.seed_picker.results.itemDoubleClicked.connect(
            lambda _item: self._add_current_seed()
        )
        column.addWidget(self.seed_picker, 1)

        self.target_label = self._caption("End track")
        column.addWidget(self.target_label)
        self.target_picker = TrackPicker(
            self.library_section, "Search tracks, artists or albums..."
        )
        self.target_picker.results.setMinimumHeight(110)
        column.addWidget(self.target_picker, 1)

        # Multi-seed list: Plex answers /nearest per track, so several seeds are
        # blended client-side. Only meaningful in More Like This.
        self.seeds_label = self._caption("Seeds")
        column.addWidget(self.seeds_label)
        self.seeds_list = QListWidget()
        self.seeds_list.setMinimumHeight(70)
        self.seeds_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        column.addWidget(self.seeds_list, 1)

        seed_buttons = QHBoxLayout()
        seed_buttons.setContentsMargins(0, 0, 0, 0)
        seed_buttons.setSpacing(SPACE_XS)
        self.add_seed_btn = QPushButton("Add")
        self.add_seed_btn.setToolTip("Add the selected search result as a seed")
        self.add_seed_btn.clicked.connect(self._add_current_seed)
        self.remove_seed_btn = QPushButton("Remove")
        self.remove_seed_btn.clicked.connect(self._remove_selected_seeds)
        self.clear_seeds_btn = QPushButton("Clear")
        self.clear_seeds_btn.clicked.connect(self._clear_seeds)
        for button in (self.add_seed_btn, self.remove_seed_btn, self.clear_seeds_btn):
            button.setMinimumHeight(CONTROL_HEIGHT)
            seed_buttons.addWidget(button)
        column.addLayout(seed_buttons)

        # Tuning stacks as label/field pairs, which fits a narrow column better than
        # the single wide row this used to be.
        tuning = QGridLayout()
        tuning.setContentsMargins(0, SPACE_SM, 0, 0)
        tuning.setHorizontalSpacing(SPACE_SM)
        tuning.setVerticalSpacing(SPACE_XS)
        tuning.setColumnStretch(1, 1)

        self.tuning_label = QLabel("Tracks:")
        tuning.addWidget(self.tuning_label, 0, 0)
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(sonic_discovery.MIN_RESULTS, sonic_discovery.MAX_RESULTS)
        self.limit_spin.setValue(sonic_discovery.DEFAULT_RESULTS)
        self.limit_spin.setMinimumHeight(CONTROL_HEIGHT)
        tuning.addWidget(self.limit_spin, 0, 1)

        self.distance_caption = QLabel("Similarity:")
        tuning.addWidget(self.distance_caption, 1, 0)
        self.distance_combo = QComboBox()
        for caption, distance in sonic_discovery.DISTANCE_PRESETS:
            self.distance_combo.addItem(caption, distance)
        default_index = self.distance_combo.findData(sonic_discovery.DEFAULT_MAX_DISTANCE)
        self.distance_combo.setCurrentIndex(max(0, default_index))
        self.distance_combo.setMinimumHeight(CONTROL_HEIGHT)
        tuning.addWidget(self.distance_combo, 1, 1)

        self.variety_caption = QLabel("Variety:")
        tuning.addWidget(self.variety_caption, 2, 0)
        self.variety_combo = QComboBox()
        # 0.0 is reproducible; above that Generate samples a widening window so the
        # same seeds give a different mix each press.
        self.variety_combo.addItem("Focused (same every time)", 0.0)
        self.variety_combo.addItem("Balanced", 0.4)
        self.variety_combo.addItem("Surprising", 0.8)
        self.variety_combo.setCurrentIndex(1)
        self.variety_combo.setMinimumHeight(CONTROL_HEIGHT)
        tuning.addWidget(self.variety_combo, 2, 1)

        self.dedupe_check = QCheckBox("Hide repeats of the same song")
        self.dedupe_check.setChecked(True)
        self.dedupe_check.setToolTip(
            "A library often holds the same recording on a single, an album and a "
            "compilation. With this on, only the first copy is kept."
        )
        tuning.addWidget(self.dedupe_check, 3, 0, 1, 2)
        column.addLayout(tuning)

        self.generate_btn = QPushButton("Generate")
        self.generate_btn.setProperty("variant", "primary")
        self.generate_btn.setMinimumHeight(CONTROL_HEIGHT + 4)
        self.generate_btn.clicked.connect(self.generate)
        column.addWidget(self.generate_btn)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)  # indeterminate: Plex gives no progress signal
        self.progress.setVisible(False)
        column.addWidget(self.progress)

        return setup

    def _build_results_panel(self):
        panel = QGroupBox("Playlist")
        column = QVBoxLayout(panel)
        column.setContentsMargins(GROUP_MARGIN, GROUP_MARGIN, GROUP_MARGIN, GROUP_MARGIN)
        column.setSpacing(SPACE_SM)

        self.status_label = QLabel("Pick a seed on the left, then press Generate.")
        self.status_label.setObjectName("helperText")
        self.status_label.setWordWrap(True)
        column.addWidget(self.status_label)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["#", "Lock", "Title", "Artist", "Album", "Time"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        # The table is the point of the window, so it gets a real minimum and all the
        # stretch; everything else keeps its natural height.
        self.table.setMinimumHeight(320)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        header = self.table.horizontalHeader()
        for col in (COL_INDEX, COL_LOCK, COL_TIME):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        for col in (COL_TITLE, COL_ARTIST, COL_ALBUM):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(lambda _item: self._refresh_summary())
        column.addWidget(self.table, 1)

        edit_row = QHBoxLayout()
        edit_row.setContentsMargins(0, 0, 0, 0)
        edit_row.setSpacing(SPACE_XS)
        for caption, slot, tip in (
            ("Remove", self._remove_selected_rows, "Drop the selected tracks"),
            ("Up", lambda: self._move_selected(-1), "Move the selection up"),
            ("Down", lambda: self._move_selected(1), "Move the selection down"),
            ("Shuffle", self._shuffle_rows, "Shuffle the running order"),
            ("Lock", lambda: self._set_locked_for_selection(True),
             "Keep these tracks when you press Generate again"),
            ("Unlock", lambda: self._set_locked_for_selection(False), "Release the lock"),
            ("Add Track", self._add_searched_track,
             "Add the track selected in the search box on the left"),
        ):
            button = QPushButton(caption)
            button.setMinimumHeight(CONTROL_HEIGHT)
            button.setToolTip(tip)
            button.clicked.connect(slot)
            edit_row.addWidget(button)
        edit_row.addStretch()
        self.summary_label = QLabel("")
        self.summary_label.setObjectName("helperText")
        edit_row.addWidget(self.summary_label)
        column.addLayout(edit_row)

        return panel

    @staticmethod
    def _caption(text):
        """Small uppercase section caption for the narrow control column."""
        label = QLabel(text.upper())
        label.setObjectName("metricCaption")
        return label

    @staticmethod
    def _label(text):
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return label

    # -------------------------------------------------------------------- mode

    def _set_mode(self, mode):
        index = self.mode_combo.findData(mode)
        if index >= 0:
            self.mode_combo.setCurrentIndex(index)
        self._on_mode_changed()

    def current_mode(self):
        return self.mode_combo.currentData() or MODE_SIMILAR

    def _on_mode_changed(self):
        adventure = self.current_mode() == MODE_ADVENTURE
        for widget in (self.target_label, self.target_picker):
            widget.setVisible(adventure)
        for widget in (self.seeds_label, self.seeds_list, self.add_seed_btn,
                       self.remove_seed_btn, self.clear_seeds_btn):
            widget.setVisible(not adventure)
        # Plex decides the length and spacing of an adventure itself.
        for widget in (self.tuning_label, self.limit_spin,
                       self.distance_caption, self.distance_combo,
                       self.variety_caption, self.variety_combo, self.dedupe_check):
            widget.setVisible(not adventure)

    # ------------------------------------------------------------------ search

    def _show_seed(self, tracks):
        """Prefill from one track or a list of them."""
        if not isinstance(tracks, (list, tuple)):
            tracks = [tracks]
        tracks = [t for t in tracks if t is not None]
        if not tracks:
            return
        self.seed_picker.set_track(tracks[0])
        for track in tracks:
            self._add_seed(track)

    def seed_tracks(self):
        return [
            self.seeds_list.item(row).data(Qt.ItemDataRole.UserRole)
            for row in range(self.seeds_list.count())
        ]

    def _add_seed(self, track):
        if track is None:
            return False
        key = str(getattr(track, "ratingKey", "") or "")
        for existing in self.seed_tracks():
            if str(getattr(existing, "ratingKey", "") or "") == key:
                return False
        item = QListWidgetItem(track_label(track))
        item.setData(Qt.ItemDataRole.UserRole, track)
        self.seeds_list.addItem(item)
        return True

    def _add_current_seed(self):
        track = self.seed_picker.selected_track()
        if track is None:
            QMessageBox.information(
                self, "Pick a Track", "Search for a track and select it first."
            )
            return
        if not self._add_seed(track):
            self.status_label.setText("That track is already a seed.")

    def _remove_selected_seeds(self):
        for item in self.seeds_list.selectedItems():
            self.seeds_list.takeItem(self.seeds_list.row(item))

    def _clear_seeds(self):
        self.seeds_list.clear()

    # -------------------------------------------------------------- generation

    def generate(self):
        adventure = self.current_mode() == MODE_ADVENTURE

        if adventure:
            seeds = [self.seed_picker.selected_track()]
            if seeds[0] is None:
                QMessageBox.information(
                    self, "Pick a Track", "Search for and select a start track."
                )
                return
            target = self.target_picker.selected_track()
            if target is None:
                QMessageBox.information(self, "Pick a Track", "Select an end track too.")
                return
        else:
            target = None
            # Fall back to whatever is highlighted, so a single track still works
            # without making the user press Add first.
            seeds = self.seed_tracks() or [self.seed_picker.selected_track()]
            seeds = [track for track in seeds if track is not None]
            if not seeds:
                QMessageBox.information(
                    self, "Pick a Track",
                    "Search for a track and add at least one seed.",
                )
                return

        self._set_busy(True, "Asking Plex...")
        self.generate_thread = SonicGenerateThread(
            self.current_mode(),
            self.library_section,
            seeds,
            target,
            self.limit_spin.value(),
            self.distance_combo.currentData(),
            locked=self.locked_tracks(),
            variety=self.variety_combo.currentData() or 0.0,
            collapse_same_song=self.dedupe_check.isChecked(),
            parent=self,
        )
        self.generate_thread.generated.connect(self._on_generated)
        self.generate_thread.failed.connect(self._fail)
        self.generate_thread.finished.connect(lambda: self._set_busy(False))
        self.generate_thread.start()

    def _on_generated(self, result):
        self.result = result
        self._set_rows(result.tracks, keep_locks=True)
        self.status_label.setText(result.description)
        if not self.name_input.text().strip():
            self.name_input.setText(result.title)

    # ------------------------------------------------------------ result table

    def current_tracks(self):
        return [
            self.table.item(row, COL_TITLE).data(Qt.ItemDataRole.UserRole)
            for row in range(self.table.rowCount())
        ]

    def locked_tracks(self):
        return [
            self.table.item(row, COL_TITLE).data(Qt.ItemDataRole.UserRole)
            for row in range(self.table.rowCount())
            if self._is_locked(row)
        ]

    def _is_locked(self, row):
        item = self.table.item(row, COL_LOCK)
        return bool(item and item.checkState() == Qt.CheckState.Checked)

    def _set_rows(self, tracks, keep_locks=False):
        """Rebuild the table, optionally preserving which tracks were locked."""
        locked_keys = set()
        if keep_locks:
            locked_keys = {
                sonic_discovery.track_key(track) for track in self.locked_tracks()
            }

        self.table.blockSignals(True)
        self.table.setRowCount(len(tracks))
        for row, track in enumerate(tracks):
            index_item = QTableWidgetItem()
            index_item.setData(Qt.ItemDataRole.DisplayRole, row + 1)
            self.table.setItem(row, COL_INDEX, index_item)

            lock_item = QTableWidgetItem()
            lock_item.setFlags(
                Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
                | Qt.ItemFlag.ItemIsSelectable
            )
            lock_item.setCheckState(
                Qt.CheckState.Checked
                if sonic_discovery.track_key(track) in locked_keys
                else Qt.CheckState.Unchecked
            )
            lock_item.setToolTip("Locked tracks survive the next Generate")
            self.table.setItem(row, COL_LOCK, lock_item)

            title_item = QTableWidgetItem(str(getattr(track, "title", "") or ""))
            # The track object rides on the title cell; every lookup goes through it.
            title_item.setData(Qt.ItemDataRole.UserRole, track)
            self.table.setItem(row, COL_TITLE, title_item)
            self.table.setItem(
                row, COL_ARTIST,
                QTableWidgetItem(str(getattr(track, "grandparentTitle", "") or "")),
            )
            self.table.setItem(
                row, COL_ALBUM,
                QTableWidgetItem(str(getattr(track, "parentTitle", "") or "")),
            )
            time_item = QTableWidgetItem(
                sonic_discovery.format_duration(getattr(track, "duration", 0))
            )
            time_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.table.setItem(row, COL_TIME, time_item)
        self.table.blockSignals(False)

        self._refresh_summary()

    def _renumber(self):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, COL_INDEX)
            if item is not None:
                item.setData(Qt.ItemDataRole.DisplayRole, row + 1)

    def _refresh_summary(self):
        tracks = self.current_tracks()
        locked = len(self.locked_tracks())
        duration = sonic_discovery.format_duration(
            sonic_discovery.total_duration_ms(tracks)
        )
        note = f" | {locked} locked" if locked else ""
        self.summary_label.setText(f"{len(tracks)} tracks | {duration}{note}")
        self.save_btn.setEnabled(bool(tracks))

    def _selected_rows(self):
        model = self.table.selectionModel()
        if model is None:
            return []
        return sorted({index.row() for index in model.selectedRows()})

    def _remove_selected_rows(self):
        rows = self._selected_rows()
        if not rows:
            self.status_label.setText("Select rows in the list first.")
            return
        for row in reversed(rows):
            self.table.removeRow(row)
        self._renumber()
        self._refresh_summary()

    def _move_selected(self, offset):
        rows = self._selected_rows()
        if not rows:
            return
        tracks = self.current_tracks()
        locked = {row for row in range(self.table.rowCount()) if self._is_locked(row)}

        order = rows if offset < 0 else list(reversed(rows))
        moved = set()
        for row in order:
            target = row + offset
            if target < 0 or target >= len(tracks) or target in moved:
                continue
            tracks[row], tracks[target] = tracks[target], tracks[row]
            if (row in locked) != (target in locked):
                locked.symmetric_difference_update({row, target})
            moved.add(target)

        self._rebuild_with_locks(tracks, locked)
        self.table.clearSelection()
        for row in sorted(moved):
            self.table.selectRow(row)

    def _shuffle_rows(self):
        import random

        tracks = self.current_tracks()
        if len(tracks) < 2:
            return
        locked_keys = {sonic_discovery.track_key(t) for t in self.locked_tracks()}
        random.shuffle(tracks)
        self._set_rows(tracks)
        # Locks follow the track, not the row, so re-apply them after reordering.
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            track = self.table.item(row, COL_TITLE).data(Qt.ItemDataRole.UserRole)
            if sonic_discovery.track_key(track) in locked_keys:
                self.table.item(row, COL_LOCK).setCheckState(Qt.CheckState.Checked)
        self.table.blockSignals(False)
        self._refresh_summary()

    def _rebuild_with_locks(self, tracks, locked_rows):
        self._set_rows(tracks)
        self.table.blockSignals(True)
        for row in locked_rows:
            if 0 <= row < self.table.rowCount():
                self.table.item(row, COL_LOCK).setCheckState(Qt.CheckState.Checked)
        self.table.blockSignals(False)
        self._refresh_summary()

    def _set_locked_for_selection(self, locked):
        rows = self._selected_rows()
        if not rows:
            self.status_label.setText("Select rows in the list first.")
            return
        state = Qt.CheckState.Checked if locked else Qt.CheckState.Unchecked
        self.table.blockSignals(True)
        for row in rows:
            item = self.table.item(row, COL_LOCK)
            if item is not None:
                item.setCheckState(state)
        self.table.blockSignals(False)
        self._refresh_summary()

    def _add_searched_track(self):
        track = self.seed_picker.selected_track()
        if track is None:
            QMessageBox.information(
                self, "Pick a Track", "Search for a track and select it first."
            )
            return
        existing = {sonic_discovery.track_key(t) for t in self.current_tracks()}
        if sonic_discovery.track_key(track) in existing:
            self.status_label.setText("That track is already in the list.")
            return
        tracks = self.current_tracks() + [track]
        locked = {row for row in range(self.table.rowCount()) if self._is_locked(row)}
        self._rebuild_with_locks(tracks, locked)

    def _fail(self, message):
        self.status_label.setText("")
        QMessageBox.warning(self, "Sonic Discovery", message)

    def _set_busy(self, busy, message=""):
        self.progress.setVisible(busy)
        self.generate_btn.setEnabled(not busy)
        if message:
            self.status_label.setText(message)

    # -------------------------------------------------------------------- save

    def save_playlist(self):
        # Save what is on screen, including any manual edits made since generating.
        tracks = self.current_tracks()
        if not tracks:
            return
        name = self.name_input.text().strip() or (self.result.title if self.result else "")
        try:
            sonic_discovery.create_playlist(self.plex_server, name, tracks)
        except Exception as error:
            QMessageBox.critical(self, "Could Not Save", str(error))
            return
        QMessageBox.information(
            self, "Playlist Created", f"Created '{name}' with {len(tracks)} track(s).",
        )
        self.accept()

    # ---------------------------------------------------------------- teardown

    def closeEvent(self, event):
        self.seed_picker.shutdown()
        self.target_picker.shutdown()
        if self.generate_thread is not None and self.generate_thread.isRunning():
            self.generate_thread.wait(3000)
        super().closeEvent(event)
