"""Compatibility helpers to smooth PyQt5 -> PyQt6 migration."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QAbstractItemView, QDialog, QFrame, QLineEdit, QListWidget, QMessageBox


def patch_qt_legacy_apis() -> None:
    """Expose selected PyQt5-style enum aliases on PyQt6 classes.

    This allows legacy callsites to keep running while migration is in progress.
    """

    # Qt namespace aliases
    Qt.UserRole = Qt.ItemDataRole.UserRole
    Qt.Checked = Qt.CheckState.Checked
    Qt.Unchecked = Qt.CheckState.Unchecked
    Qt.AlignCenter = Qt.AlignmentFlag.AlignCenter
    Qt.AlignTop = Qt.AlignmentFlag.AlignTop
    Qt.CustomContextMenu = Qt.ContextMenuPolicy.CustomContextMenu
    Qt.ItemIsEditable = Qt.ItemFlag.ItemIsEditable
    Qt.ItemIsUserCheckable = Qt.ItemFlag.ItemIsUserCheckable
    Qt.PointingHandCursor = Qt.CursorShape.PointingHandCursor
    Qt.MoveAction = Qt.DropAction.MoveAction
    Qt.Dialog = Qt.WindowType.Dialog
    Qt.CustomizeWindowHint = Qt.WindowType.CustomizeWindowHint
    Qt.WindowTitleHint = Qt.WindowType.WindowTitleHint
    Qt.WindowCloseButtonHint = Qt.WindowType.WindowCloseButtonHint
    Qt.WindowContextHelpButtonHint = Qt.WindowType.WindowContextHelpButtonHint
    Qt.WindowModal = Qt.WindowModality.WindowModal
    Qt.ScrollBarAlwaysOff = Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    Qt.ScrollBarAsNeeded = Qt.ScrollBarPolicy.ScrollBarAsNeeded
    Qt.Key_Enter = Qt.Key.Key_Enter
    Qt.Key_Return = Qt.Key.Key_Return
    Qt.Key_Escape = Qt.Key.Key_Escape
    Qt.RichText = Qt.TextFormat.RichText

    # QDialog aliases
    QDialog.Accepted = QDialog.DialogCode.Accepted
    QDialog.Rejected = QDialog.DialogCode.Rejected

    # QMessageBox aliases
    QMessageBox.Yes = QMessageBox.StandardButton.Yes
    QMessageBox.No = QMessageBox.StandardButton.No
    QMessageBox.Cancel = QMessageBox.StandardButton.Cancel
    QMessageBox.Ok = QMessageBox.StandardButton.Ok
    QMessageBox.AcceptRole = QMessageBox.ButtonRole.AcceptRole
    QMessageBox.RejectRole = QMessageBox.ButtonRole.RejectRole
    QMessageBox.DestructiveRole = QMessageBox.ButtonRole.DestructiveRole

    # QAbstractItemView aliases
    QAbstractItemView.DragDrop = QAbstractItemView.DragDropMode.DragDrop
    QAbstractItemView.InternalMove = QAbstractItemView.DragDropMode.InternalMove
    QAbstractItemView.SelectRows = QAbstractItemView.SelectionBehavior.SelectRows
    QAbstractItemView.PositionAtCenter = QAbstractItemView.ScrollHint.PositionAtCenter

    # Common widget enum aliases
    QLineEdit.Password = QLineEdit.EchoMode.Password
    QListWidget.ExtendedSelection = QListWidget.SelectionMode.ExtendedSelection
    QFrame.NoFrame = QFrame.Shape.NoFrame
    QFont.Bold = QFont.Weight.Bold
