"""QThread workers for metadata fixing."""

from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal


class MetadataScanWorker(QThread):
    progress = pyqtSignal(int, int, str)
    completed = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, service, tracks, parent=None):
        super().__init__(parent)
        self.service = service
        self.tracks = tracks

    def run(self):
        try:
            proposals = self.service.scan(self.tracks, progress_cb=self._progress)
            self.completed.emit(proposals)
        except Exception as exc:
            self.failed.emit(str(exc))

    def _progress(self, current: int, total: int, message: str):
        self.progress.emit(current, total, message)


class MetadataApplyWorker(QThread):
    progress = pyqtSignal(int, int, str)
    completed = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, service, proposals, parent=None):
        super().__init__(parent)
        self.service = service
        self.proposals = proposals

    def run(self):
        try:
            results = self.service.apply(self.proposals, progress_cb=self._progress)
            self.completed.emit(results)
        except Exception as exc:
            self.failed.emit(str(exc))

    def _progress(self, current: int, total: int, message: str):
        self.progress.emit(current, total, message)
