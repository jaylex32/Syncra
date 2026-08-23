"""Cover-art grid for the Playlists page.

The page used to be a plain QListWidget of "Title (N tracks)" strings. This module
turns the same widget into a poster wall without changing its API: it stays a
QListWidget holding QListWidgetItems whose Qt.UserRole is still the plexapi playlist
object and whose checkState() still drives every bulk operation. Only the presentation
changes, so the ~30 existing call sites keep working untouched.

Two pieces do the work:

* `PlaylistCardDelegate` paints each item as a card -- cover, title, subtitle, checkbox,
  selection ring -- so a 60-playlist grid costs 60 model rows rather than 60 widgets.
* `CoverFetcher` pulls posters off the server on a small thread pool, backed by the
  on-disk `CoverCache`, and hands raw bytes back to the GUI thread (QPixmap must not be
  built off-thread).

Playlists with no art still get a tile: `placeholder_cover` renders a gradient derived
from the title hash with the playlist's initials, so the grid never has holes in it.
"""

from __future__ import annotations

import logging
from typing import Optional

import requests
from PyQt6.QtCore import (
    QEvent,
    QObject,
    QRect,
    QRectF,
    QRunnable,
    QSize,
    Qt,
    QThreadPool,
    pyqtSignal,
)
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QListView, QListWidget, QStyle, QStyledItemDelegate

from ...services.cover_cache import CoverCache, cache_key
from ...theme.styles import (
    RADIUS_CARD,
    SPACE_SM,
    SPACE_XS,
    TOKENS,
    tile_palette,
)

# ---------------------------------------------------------------------------
# Item roles. UserRole itself is left alone -- legacy code stores the playlist there.
# ---------------------------------------------------------------------------

PLAYLIST_ROLE = Qt.ItemDataRole.UserRole          # plexapi playlist (pre-existing)
SUBTITLE_ROLE = Qt.ItemDataRole.UserRole + 1      # "128 tracks" / "loading..."
TITLE_ROLE = Qt.ItemDataRole.UserRole + 5         # canonical title, free of any suffix
COVER_ROLE = Qt.ItemDataRole.UserRole + 2         # rendered QPixmap, ready to blit
COVER_URL_ROLE = Qt.ItemDataRole.UserRole + 3     # str, poster URL for the fetcher
COVER_STATE_ROLE = Qt.ItemDataRole.UserRole + 4   # "idle" | "loading" | "ready" | "none"
POSTER_KEY_ROLE = Qt.ItemDataRole.UserRole + 6    # playlist ratingKey, for poster lookups

# ---------------------------------------------------------------------------
# Card geometry. Multiples of 4 per the design system's grid.
# ---------------------------------------------------------------------------

COVER_SIZE = 168
CARD_PADDING = SPACE_SM          # 8
TEXT_GAP = SPACE_SM              # 8 between cover and title
TITLE_HEIGHT = 18
SUBTITLE_HEIGHT = 15
TEXT_BLOCK = TITLE_HEIGHT + 2 + SUBTITLE_HEIGHT
CARD_WIDTH = COVER_SIZE + CARD_PADDING * 2
CARD_HEIGHT = CARD_PADDING + COVER_SIZE + TEXT_GAP + TEXT_BLOCK + CARD_PADDING
GRID_GAP = SPACE_SM

# Tiles stretch to divide the viewport exactly, so the wall stays flush with both
# edges instead of leaving a ragged dead column on the right. The cap stops a narrow
# window from blowing one lonely tile up to full width.
MAX_CARD_WIDTH = 248

# Tiles shrink as the window narrows rather than holding one size and dropping to a
# single fat column. MIN is the smallest a cover can get and still read as artwork
# with a legible two-line caption under it.
MIN_CARD_WIDTH = 132

# Qt insets item-view content a few pixels inside the viewport, so a row of cells that
# adds up to exactly the viewport width overflows and the last column wraps away --
# which is how a "flush" grid ends up one column short with a wide gap on the right.
GRID_EDGE_ALLOWANCE = 8

CHECK_SIZE = 22
CHECK_MARGIN = SPACE_SM

# Palette gradients for generated placeholders. All are desaturated navies and teals
# drawn from the app's own surface range, so a wall of placeholders still reads as
# Syncra rather than as a set of random colour swatches.
PLACEHOLDER_GRADIENTS = (
    ("#243a57", "#16233a"),
    ("#1f3f4d", "#152833"),
    ("#2b3350", "#181d31"),
    ("#1d4450", "#122a33"),
    ("#333350", "#1d1d31"),
    ("#204a48", "#122b2a"),
    ("#2a3a60", "#171f38"),
    ("#3a2f4f", "#211a2e"),
)


def rounded_cover(pixmap: QPixmap, side: int = COVER_SIZE,
                  radius: float = float(RADIUS_CARD)) -> QPixmap:
    """Centre-crop `pixmap` to a square and round its corners.

    Scaling by expanding and then cropping keeps non-square posters filling the tile
    instead of sitting letterboxed inside it.
    """
    scaled = pixmap.scaled(
        side,
        side,
        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
        Qt.TransformationMode.SmoothTransformation,
    )
    canvas = QPixmap(side, side)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    clip = QPainterPath()
    clip.addRoundedRect(0.0, 0.0, float(side), float(side), radius, radius)
    painter.setClipPath(clip)
    painter.drawPixmap(
        -max(0, (scaled.width() - side) // 2),
        -max(0, (scaled.height() - side) // 2),
        scaled,
    )
    painter.end()
    return canvas


def format_span(milliseconds) -> str:
    """Human-scale duration for a playlist subtitle: "9h 7m", "45m", "38s".

    sonic_discovery.format_duration renders a clock ("9:07:24"), which is right for a
    single track and unreadable as the length of a playlist.
    """
    seconds = max(0, int(milliseconds or 0)) // 1000
    if seconds < 60:
        return f"{seconds}s"
    hours, remainder = divmod(seconds, 3600)
    minutes = remainder // 60
    if hours:
        return f"{hours}h {minutes}m" if minutes else f"{hours}h"
    return f"{minutes}m"


def _initials(title: str) -> str:
    """Up to two characters for a generated tile.

    Multi-word titles use one character per word ("90s Throwback" -> "9T"); a single
    word falls back to its first two ("Workout" -> "WO") so lone letters do not sit
    noticeably smaller than the rest of the wall.
    """
    # Only words that actually contain a letter or digit count -- "*** Party" should
    # fall back to the second character of "Party", not of the asterisks.
    words = [
        [char for char in word if char.isalnum()]
        for word in str(title or "").split()
    ]
    words = [chars for chars in words if chars]

    letters = "".join(chars[0] for chars in words[:2]).upper()
    if len(letters) == 1 and len(words[0]) > 1:
        letters += words[0][1].upper()

    return letters or "?"


def placeholder_cover(title: str, side: int = COVER_SIZE,
                      radius: float = float(RADIUS_CARD)) -> QPixmap:
    """A generated tile for playlists with no poster: gradient plus initials.

    The gradient is picked from a hash of the title, so a given playlist always gets
    the same colours -- the grid stays visually stable between launches.
    """
    name = str(title or "")
    gradients = tile_palette() or PLACEHOLDER_GRADIENTS
    index = sum(ord(c) for c in name) % len(gradients)
    top, bottom = gradients[index]

    canvas = QPixmap(side, side)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    clip = QPainterPath()
    clip.addRoundedRect(0.0, 0.0, float(side), float(side), radius, radius)
    painter.setClipPath(clip)

    gradient = QLinearGradient(0, 0, side, side)
    gradient.setColorAt(0.0, QColor(top))
    gradient.setColorAt(1.0, QColor(bottom))
    painter.fillRect(0, 0, side, side, QBrush(gradient))

    font = QFont()
    font.setPointSizeF(max(14.0, side * 0.24))
    font.setWeight(QFont.Weight.DemiBold)
    painter.setFont(font)
    initial_colour = QColor(TOKENS['txt_0'])
    initial_colour.setAlpha(56)
    painter.setPen(initial_colour)
    painter.drawText(QRect(0, 0, side, side), Qt.AlignmentFlag.AlignCenter, _initials(name))
    painter.end()
    return canvas


# Service badges keep their brand colours in every theme -- Spotify green is
# Spotify green -- so the letter on them is a fixed dark ink chosen for contrast
# against those saturated fills, not a palette colour.
BADGE_TEXT = "#0d1622"

SERVICE_COLOURS = {
    "spotify": ("Spotify", "#1db954"),
    "deezer": ("Deezer", "#a238ff"),
    "tidal": ("TIDAL", "#00c8f4"),
    "listenbrainz": ("ListenBrainz", "#e97a2c"),
    "apple": ("Apple Music", "#fa2d48"),
    "youtube": ("YouTube", "#ff0033"),
}

# Not a brand: a local file or an unrecognised host gets a neutral chip, so this one
# follows the palette rather than being pinned to a colour.
NEUTRAL_SERVICE = "Local file"


def identify_service(source: str):
    """Map a sync source to (label, colour). Falls back to a neutral local-file badge."""
    text = str(source or "").strip().lower()
    neutral = TOKENS["txt_muted"]
    if not text:
        return (NEUTRAL_SERVICE, neutral)
    for key, value in SERVICE_COLOURS.items():
        if key in text:
            return value
    if text.startswith("http://") or text.startswith("https://"):
        return ("Web", neutral)
    return (NEUTRAL_SERVICE, neutral)


def badge_pixmap(label: str, colour: str, size: int = 22) -> QPixmap:
    """A small rounded chip carrying the first letter of a service name."""
    canvas = QPixmap(size, size)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    path = QPainterPath()
    path.addRoundedRect(0.0, 0.0, float(size), float(size), size / 3.2, size / 3.2)
    painter.fillPath(path, QColor(colour))

    font = QFont()
    font.setPointSizeF(max(7.0, size * 0.48))
    font.setWeight(QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(QColor(BADGE_TEXT))
    initial = (str(label or "?").strip() or "?")[0].upper()
    painter.drawText(QRect(0, 0, size, size), Qt.AlignmentFlag.AlignCenter, initial)
    painter.end()
    return canvas


# ---------------------------------------------------------------------------
# Cover fetching
# ---------------------------------------------------------------------------


class _FetchSignals(QObject):
    finished = pyqtSignal(str, bytes)   # url, image bytes (empty on failure)
    resolved = pyqtSignal(str, str)     # request key, resolved image url


class _ResolveTask(QRunnable):
    """Work out an item's real image URL off the GUI thread.

    A playlist's listing entry carries the auto-generated composite even when the user
    has uploaded their own poster; finding the selected one costs a request per
    playlist, which must not happen on the GUI thread.
    """

    def __init__(self, key: str, resolver, signals: _FetchSignals):
        super().__init__()
        self.key = key
        self.resolver = resolver
        self.signals = signals
        self.setAutoDelete(True)

    def run(self):
        url = ""
        try:
            url = str(self.resolver() or "")
        except Exception as error:
            logging.debug(f"Cover resolve failed for {self.key}: {error}")
        try:
            self.signals.resolved.emit(self.key, url)
        except RuntimeError:
            pass


class _CoverTask(QRunnable):
    def __init__(self, url: str, cache: CoverCache, signals: _FetchSignals,
                 user_agent: str):
        super().__init__()
        self.url = url
        self.cache = cache
        self.signals = signals
        self.user_agent = user_agent
        self.setAutoDelete(True)

    def run(self):
        data = b""
        try:
            key = cache_key(self.url)
            cached = self.cache.get(key)
            if cached:
                data = cached
            else:
                response = requests.get(
                    self.url,
                    headers={"User-Agent": self.user_agent},
                    timeout=20,
                )
                response.raise_for_status()
                data = response.content or b""
                if data:
                    self.cache.put(key, data)
        except Exception as error:
            logging.debug(f"Cover fetch failed for {self.url}: {error}")
            data = b""
        try:
            self.signals.finished.emit(self.url, data)
        except RuntimeError:
            # The page was torn down while this was in flight; nothing to deliver to.
            pass


class CoverFetcher(QObject):
    """Fetches poster art on a bounded thread pool, disk-cached.

    Kept deliberately small: four concurrent requests is enough to load a 60-playlist
    wall in about two seconds without flooding the Plex server, and every result is
    cached so subsequent visits are instant.
    """

    cover_ready = pyqtSignal(str, bytes)
    cover_url_resolved = pyqtSignal(str, str)

    def __init__(self, parent=None, max_threads: int = 4, user_agent: str = "Syncra"):
        super().__init__(parent)
        self.cache = CoverCache()
        self.user_agent = user_agent
        self.signals = _FetchSignals()
        self.signals.finished.connect(self._on_finished)
        self.signals.resolved.connect(self.cover_url_resolved)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(max(1, max_threads))
        self._in_flight: set[str] = set()

    def cached_bytes(self, url: str) -> Optional[bytes]:
        """Synchronous cache peek, so already-seen covers paint on the first frame."""
        if not url:
            return None
        return self.cache.get(cache_key(url))

    def request(self, url: str) -> bool:
        """Queue a fetch. Returns False if the URL is empty or already queued."""
        url = str(url or "").strip()
        if not url or url in self._in_flight:
            return False
        self._in_flight.add(url)
        self.pool.start(_CoverTask(url, self.cache, self.signals, self.user_agent))
        return True

    def resolve(self, key: str, resolver) -> bool:
        """Queue a lookup for an item's real image URL, answered on cover_url_resolved."""
        key = str(key or "").strip()
        if not key or resolver is None:
            return False
        self.pool.start(_ResolveTask(key, resolver, self.signals))
        return True

    def _on_finished(self, url: str, data: bytes):
        self._in_flight.discard(url)
        self.cover_ready.emit(url, data)

    def shutdown(self, wait_ms: int = 2000):
        self._in_flight.clear()
        self.pool.clear()
        self.pool.waitForDone(wait_ms)


# ---------------------------------------------------------------------------
# Delegate
# ---------------------------------------------------------------------------


def is_checked(index) -> bool:
    """True when a model index is ticked.

    QListWidgetItem.checkState() hands back a Qt.CheckState, but reading the same
    thing through the model returns a plain int, so comparing the raw value against
    the enum silently never matches. Both shapes are accepted here.
    """
    raw = index.data(Qt.ItemDataRole.CheckStateRole)
    if isinstance(raw, Qt.CheckState):
        return raw == Qt.CheckState.Checked
    try:
        return int(raw) == Qt.CheckState.Checked.value
    except (TypeError, ValueError):
        return False


class PlaylistCardDelegate(QStyledItemDelegate):
    """Paints one playlist as a cover card and handles its checkbox hit area."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._title_font = QFont()
        self._title_font.setPointSize(10)
        self._title_font.setWeight(QFont.Weight.DemiBold)
        self._subtitle_font = QFont()
        self._subtitle_font.setPointSize(8)
        # Updated by PlaylistGridView on every resize so tiles fill the viewport.
        self.card_size = QSize(CARD_WIDTH, CARD_HEIGHT)

    def sizeHint(self, option, index):
        return QSize(self.card_size)

    # -- geometry helpers ---------------------------------------------------

    @staticmethod
    def cover_rect(card: QRect) -> QRect:
        # Derived from the card rather than the constant, so a stretched tile scales
        # its artwork instead of leaving a margin on one side.
        side = max(1, card.width() - CARD_PADDING * 2)
        return QRect(
            card.left() + CARD_PADDING,
            card.top() + CARD_PADDING,
            side,
            side,
        )

    @classmethod
    def check_rect(cls, card: QRect) -> QRect:
        cover = cls.cover_rect(card)
        return QRect(
            cover.right() - CHECK_MARGIN - CHECK_SIZE + 1,
            cover.top() + CHECK_MARGIN,
            CHECK_SIZE,
            CHECK_SIZE,
        )

    # -- painting -----------------------------------------------------------

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        card = QRect(option.rect).adjusted(0, 0, -GRID_GAP, -GRID_GAP)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        checked = is_checked(index)

        self._paint_card_surface(painter, card, selected, hovered, checked)
        self._paint_cover(painter, card, index, hovered)
        self._paint_check(painter, card, checked, hovered)
        self._paint_text(painter, card, index, selected)

        painter.restore()

    def _paint_card_surface(self, painter, card, selected, hovered, checked):
        path = QPainterPath()
        path.addRoundedRect(QRectF(card), RADIUS_CARD + 2, RADIUS_CARD + 2)

        if selected or checked:
            painter.fillPath(path, QColor(TOKENS["bg_3"]))
        elif hovered:
            painter.fillPath(path, QColor(TOKENS["bg_2"]))
        else:
            painter.fillPath(path, QColor(TOKENS['card']))

        if selected or checked:
            pen = QPen(QColor(TOKENS["accent"]), 2)
        elif hovered:
            pen = QPen(QColor(TOKENS['border_soft']), 1)
        else:
            pen = QPen(QColor(TOKENS["border"]), 1)
        painter.setPen(pen)
        painter.drawPath(path)

    def _paint_cover(self, painter, card, index, hovered):
        rect = self.cover_rect(card)
        pixmap = index.data(COVER_ROLE)
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            painter.drawPixmap(rect, pixmap)
        else:
            painter.drawPixmap(rect, placeholder_cover(str(index.data(Qt.ItemDataRole.DisplayRole) or "")))

        # A hover wash over the art reads as "this tile is live" without moving anything.
        if hovered:
            wash = QPainterPath()
            wash.addRoundedRect(QRectF(rect), RADIUS_CARD, RADIUS_CARD)
            wash_colour = QColor(TOKENS['txt_0'])
            wash_colour.setAlpha(16)
            painter.fillPath(wash, wash_colour)

    def _paint_check(self, painter, card, checked, hovered):
        # Unchecked boxes stay faint until the tile is hovered, so a full grid is art
        # first and a form second -- but a ticked box is always obvious.
        if not checked and not hovered:
            return

        rect = self.check_rect(card)
        path = QPainterPath()
        path.addRoundedRect(QRectF(rect), 6, 6)

        if checked:
            painter.fillPath(path, QColor(TOKENS["accent"]))
            painter.setPen(QPen(QColor(TOKENS["accent"]), 1))
            painter.drawPath(path)
            tick = QPainterPath()
            tick.moveTo(rect.left() + 5.5, rect.top() + 11.0)
            tick.lineTo(rect.left() + 9.0, rect.top() + 14.5)
            tick.lineTo(rect.left() + 16.0, rect.top() + 7.0)
            painter.setPen(QPen(QColor(TOKENS["on_accent"]), 2.2,
                                Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                                Qt.PenJoinStyle.RoundJoin))
            painter.drawPath(tick)
        else:
            scrim = QColor(TOKENS['bg_0'])
            scrim.setAlpha(165)
            painter.fillPath(path, scrim)
            outline = QColor(TOKENS['txt_0'])
            outline.setAlpha(130)
            painter.setPen(QPen(outline, 1))
            painter.drawPath(path)

    def _paint_text(self, painter, card, index, selected):
        left = card.left() + CARD_PADDING
        width = card.width() - CARD_PADDING * 2
        top = self.cover_rect(card).bottom() + 1 + TEXT_GAP

        title = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        painter.setFont(self._title_font)
        metrics = QFontMetrics(self._title_font)
        painter.setPen(QColor(TOKENS["txt_title"] if selected else TOKENS["txt_0"]))
        painter.drawText(
            QRect(left, top, width, TITLE_HEIGHT),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            metrics.elidedText(title, Qt.TextElideMode.ElideRight, width),
        )

        subtitle = str(index.data(SUBTITLE_ROLE) or "")
        if not subtitle:
            return
        painter.setFont(self._subtitle_font)
        sub_metrics = QFontMetrics(self._subtitle_font)
        painter.setPen(QColor(TOKENS["txt_muted"]))
        painter.drawText(
            QRect(left, top + TITLE_HEIGHT + 2, width, SUBTITLE_HEIGHT),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            sub_metrics.elidedText(subtitle, Qt.TextElideMode.ElideRight, width),
        )

    # -- interaction --------------------------------------------------------

    def editorEvent(self, event, model, option, index):
        """Toggle the check state when the checkbox itself is clicked.

        Qt's own checkbox hit area does not apply here because the box is painted by
        hand, so the rect has to be tested explicitly. Clicks anywhere else fall
        through to normal selection handling.
        """
        from PyQt6.QtCore import QEvent

        if event.type() == QEvent.Type.MouseButtonRelease:
            if event.button() == Qt.MouseButton.LeftButton:
                card = QRect(option.rect).adjusted(0, 0, -GRID_GAP, -GRID_GAP)
                if self.check_rect(card).contains(event.pos()):
                    new_state = (
                        Qt.CheckState.Unchecked if is_checked(index)
                        else Qt.CheckState.Checked
                    )
                    model.setData(index, new_state, Qt.ItemDataRole.CheckStateRole)
                    return True
        return super().editorEvent(event, model, option, index)


# ---------------------------------------------------------------------------
# View configuration
# ---------------------------------------------------------------------------


class PlaylistGridView(QListWidget):
    """A QListWidget whose cover grid always divides the viewport exactly.

    Qt's IconMode lays items out on a fixed grid, so whatever width does not divide
    evenly is left as a dead column down the right-hand side. Recomputing the cell
    size on every resize spreads that remainder across the tiles instead, and the
    delegate scales each cover to whatever width it is given.

    It is a QListWidget subclass on purpose: the Playlists page has around thirty
    call sites reading items, check states and Qt.UserRole off this widget, and all
    of them keep working unchanged.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.card_delegate = PlaylistCardDelegate(self)
        self._retiling = False
        # Watch the viewport, not just the widget: when the vertical scrollbar appears
        # the viewport narrows without the widget itself being resized, and tiling
        # computed against the wider viewport then leaves a near-miss dead column.
        self.viewport().installEventFilter(self)

    def eventFilter(self, watched, event):
        if watched is self.viewport() and event.type() == QEvent.Type.Resize:
            self.retile()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.retile()

    def retile(self):
        if self._retiling or self.viewMode() != QListView.ViewMode.IconMode:
            return

        available = self.viewport().width() - GRID_EDGE_ALLOWANCE
        if available <= 0:
            return

        # Round to the nearest column count rather than flooring. Flooring keeps the
        # ideal width and dumps the remainder on the right, so a window 1.6 tiles wider
        # than a whole number of columns showed the same tiles with a bigger gap;
        # rounding up adds a column and lets every tile shrink a little to pay for it.
        target = CARD_WIDTH + GRID_GAP
        columns = max(1, round(available / target))

        # Adding a column must not push tiles below the readable minimum.
        columns = max(1, min(columns, available // (MIN_CARD_WIDTH + GRID_GAP)))

        cell_width = min(available // columns, MAX_CARD_WIDTH + GRID_GAP)
        card_width = max(1, cell_width - GRID_GAP)
        cover = card_width - CARD_PADDING * 2
        card_height = CARD_PADDING + cover + TEXT_GAP + TEXT_BLOCK + CARD_PADDING

        card_size = QSize(card_width, card_height)
        grid_size = QSize(cell_width, card_height + GRID_GAP)
        if grid_size == self.gridSize() and card_size == self.card_delegate.card_size:
            return

        # setGridSize() re-lays out, which can toggle the scrollbar and re-enter here.
        self._retiling = True
        try:
            self.card_delegate.card_size = card_size
            self.setGridSize(grid_size)
        finally:
            self._retiling = False


def apply_grid_mode(list_widget: QListWidget, delegate: PlaylistCardDelegate):
    """Switch an existing QListWidget to the cover wall."""
    list_widget.setViewMode(QListView.ViewMode.IconMode)
    list_widget.setResizeMode(QListView.ResizeMode.Adjust)
    list_widget.setMovement(QListView.Movement.Static)
    list_widget.setWrapping(True)
    list_widget.setUniformItemSizes(True)
    list_widget.setSpacing(0)  # the delegate reserves the gutter itself
    list_widget.setGridSize(QSize(CARD_WIDTH + GRID_GAP, CARD_HEIGHT + GRID_GAP))
    list_widget.setIconSize(QSize(COVER_SIZE, COVER_SIZE))
    list_widget.setItemDelegate(delegate)
    list_widget.setMouseTracking(True)
    list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    list_widget.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
    list_widget.setWordWrap(False)
    if hasattr(list_widget, "retile"):
        list_widget.retile()


def apply_list_mode(list_widget: QListWidget):
    """Restore the plain single-column list."""
    list_widget.setItemDelegate(QStyledItemDelegate(list_widget))
    list_widget.setViewMode(QListView.ViewMode.ListMode)
    list_widget.setMovement(QListView.Movement.Static)
    list_widget.setWrapping(False)
    list_widget.setUniformItemSizes(False)
    list_widget.setSpacing(SPACE_XS // 2)
    list_widget.setGridSize(QSize())
    list_widget.setIconSize(QSize(0, 0))
    list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    list_widget.setWordWrap(False)
