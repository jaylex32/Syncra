"""Tests for the playlist cover wall.

The Playlists page was a QListWidget of "Title (N tracks)" strings and is now a grid
of cover cards. The whole point of the approach is that it stays the same QListWidget
holding the same items -- roughly thirty existing call sites read checkState() and
Qt.UserRole off those items -- so a good chunk of what is tested here is that the
compatibility contract did not quietly break.

Two bugs these tests pin down, both of which rendered as "nothing visible":

* `index.data(CheckStateRole)` returns a plain int through the model even though
  `item.checkState()` returns a Qt.CheckState, so comparing the raw value against the
  enum never matched and the tile checkbox was never painted.
* The theme styles `QCheckBox::indicator` but nothing for item views. Once a
  stylesheet is active Qt stops drawing the native checkmark, so a ticked row in list
  mode looked exactly like an unticked one.
"""

import os
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QEvent, QPoint, QPointF, QRect, Qt
from PyQt6.QtGui import QMouseEvent, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QListView,
    QListWidget,
    QListWidgetItem,
    QStyleOptionViewItem,
)

from syncra.app import legacy_main
from syncra.services.cover_cache import CoverCache, cache_key
from syncra.theme.styles import MAIN_STYLESHEET
from syncra.ui.widgets import playlist_grid as pg


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakePlaylist:
    def __init__(self, title, rating_key=1, leaf_count=None, duration=None,
                 thumb="/library/metadata/1/composite/1700000000"):
        self.title = title
        self.ratingKey = rating_key
        self.playlistType = "audio"
        if leaf_count is not None:
            self.leafCount = leaf_count
        if duration is not None:
            self.duration = duration
        self.thumb = thumb


class FakeServer:
    def url(self, path, includeToken=False):
        token = "&X-Plex-Token=secret" if includeToken else ""
        return f"http://plex.local{path}{token}"


# ---------------------------------------------------------------------------
# Disk cache
# ---------------------------------------------------------------------------


class CoverCacheTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="syncra-covers-")
        self.cache = CoverCache(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_round_trips_bytes(self):
        self.cache.put("abc", b"image-data")
        self.assertEqual(self.cache.get("abc"), b"image-data")

    def test_missing_entry_is_none_not_an_error(self):
        self.assertIsNone(self.cache.get("nope"))

    def test_empty_payload_is_not_cached(self):
        self.assertFalse(self.cache.put("abc", b""))
        self.assertIsNone(self.cache.get("abc"))

    def test_key_ignores_the_plex_token(self):
        """The token changes on every re-login; hashing it would void the cache."""
        base = "http://plex.local/photo/:/transcode?width=336&url=%2Fthumb"
        self.assertEqual(
            cache_key(f"{base}&X-Plex-Token=aaaa"),
            cache_key(f"{base}&X-Plex-Token=bbbb"),
        )

    def test_key_still_separates_different_images(self):
        self.assertNotEqual(cache_key("http://a/one"), cache_key("http://a/two"))

    def test_prune_enforces_the_entry_ceiling(self):
        cache = CoverCache(self._tmp.name, max_entries=3, max_bytes=10 ** 9)
        for i in range(8):
            cache.put(f"key{i}", b"x" * 100)
        self.assertLessEqual(cache.stats()["entries"], 3)

    def test_prune_enforces_the_byte_ceiling(self):
        cache = CoverCache(self._tmp.name, max_entries=1000, max_bytes=500)
        for i in range(10):
            cache.put(f"key{i}", b"x" * 100)
        self.assertLessEqual(cache.stats()["bytes"], 500)

    def test_clear_empties_the_directory(self):
        for i in range(4):
            self.cache.put(f"key{i}", b"data")
        self.assertEqual(self.cache.clear(), 4)
        self.assertEqual(self.cache.stats()["entries"], 0)

    def test_an_unwritable_directory_does_not_raise(self):
        cache = CoverCache(os.path.join(self._tmp.name, "no", "such", "dir"))
        self.assertFalse(cache.put("abc", b"data"))
        self.assertIsNone(cache.get("abc"))
        self.assertEqual(cache.stats(), {"entries": 0, "bytes": 0})


# ---------------------------------------------------------------------------
# Formatting and generated art
# ---------------------------------------------------------------------------


class FormatSpanTests(unittest.TestCase):
    def test_sub_minute(self):
        self.assertEqual(pg.format_span(45_000), "45s")

    def test_minutes(self):
        self.assertEqual(pg.format_span(2_742_000), "45m")

    def test_hours_and_minutes(self):
        self.assertEqual(pg.format_span(32_844_000), "9h 7m")

    def test_whole_hours_drop_the_minutes(self):
        self.assertEqual(pg.format_span(3_600_000), "1h")

    def test_none_and_zero_are_safe(self):
        self.assertEqual(pg.format_span(None), "0s")
        self.assertEqual(pg.format_span(0), "0s")

    def test_negative_does_not_produce_a_negative_span(self):
        self.assertEqual(pg.format_span(-5000), "0s")


class InitialsTests(unittest.TestCase):
    def test_two_words_give_one_letter_each(self):
        self.assertEqual(pg._initials("Late Night Drive"), "LN")

    def test_single_word_uses_its_first_two_characters(self):
        self.assertEqual(pg._initials("Workout"), "WO")

    def test_digits_count(self):
        self.assertEqual(pg._initials("90s Throwback"), "9T")

    def test_punctuation_is_skipped(self):
        self.assertEqual(pg._initials("*** Party"), "PA")

    def test_empty_title_falls_back(self):
        self.assertEqual(pg._initials(""), "?")
        self.assertEqual(pg._initials("   "), "?")

    def test_emoji_only_title_does_not_crash(self):
        self.assertTrue(pg._initials("❤️"))


class GeneratedCoverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_placeholder_is_square_and_the_requested_size(self):
        cover = pg.placeholder_cover("Road Trip", 120)
        self.assertEqual(cover.width(), 120)
        self.assertEqual(cover.height(), 120)

    def test_placeholder_colours_are_stable_for_a_title(self):
        """A playlist must not change colour between launches."""
        first = pg.placeholder_cover("Road Trip", 64).toImage()
        second = pg.placeholder_cover("Road Trip", 64).toImage()
        self.assertEqual(first, second)

    def test_different_titles_generally_differ(self):
        a = pg.placeholder_cover("Alpha", 64).toImage()
        b = pg.placeholder_cover("Zulu Nine", 64).toImage()
        self.assertNotEqual(a, b)

    def test_rounded_cover_crops_a_wide_image_to_a_square(self):
        wide = QPixmap(400, 100)
        wide.fill(Qt.GlobalColor.red)
        out = pg.rounded_cover(wide, 80)
        self.assertEqual((out.width(), out.height()), (80, 80))

    def test_rounded_cover_has_transparent_corners(self):
        source = QPixmap(200, 200)
        source.fill(Qt.GlobalColor.red)
        image = pg.rounded_cover(source, 100).toImage()
        self.assertEqual(image.pixelColor(0, 0).alpha(), 0, "corner should be rounded off")
        self.assertGreater(image.pixelColor(50, 50).alpha(), 0, "centre should be opaque")


# ---------------------------------------------------------------------------
# Delegate
# ---------------------------------------------------------------------------


class CheckStateReadingTests(unittest.TestCase):
    """The bug: model reads return int, item reads return the enum."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.widget = QListWidget()
        self.item = QListWidgetItem("x")
        self.item.setFlags(self.item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        self.item.setCheckState(Qt.CheckState.Unchecked)
        self.widget.addItem(self.item)
        self.index = self.widget.indexFromItem(self.item)

    def tearDown(self):
        self.widget.deleteLater()

    def test_unchecked_reads_false(self):
        self.assertFalse(pg.is_checked(self.index))

    def test_checked_reads_true_through_the_model(self):
        self.item.setCheckState(Qt.CheckState.Checked)
        self.assertTrue(pg.is_checked(self.index))

    def test_raw_int_from_the_model_is_accepted(self):
        raw = self.index.data(Qt.ItemDataRole.CheckStateRole)
        self.item.setCheckState(Qt.CheckState.Checked)
        raw_checked = self.index.data(Qt.ItemDataRole.CheckStateRole)
        # Guard the assumption the helper exists for: these come back as ints.
        self.assertNotIsInstance(raw, Qt.CheckState)
        self.assertEqual(int(raw_checked), Qt.CheckState.Checked.value)
        self.assertTrue(pg.is_checked(self.index))

    def test_absent_check_state_is_false(self):
        plain = QListWidgetItem("no checkbox")
        self.widget.addItem(plain)
        self.assertFalse(pg.is_checked(self.widget.indexFromItem(plain)))


class DelegateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.widget = QListWidget()
        self.delegate = pg.PlaylistCardDelegate(self.widget)
        pg.apply_grid_mode(self.widget, self.delegate)
        self.item = QListWidgetItem()
        self.item.setFlags(self.item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        self.item.setCheckState(Qt.CheckState.Unchecked)
        self.item.setData(pg.TITLE_ROLE, "Road Trip")
        self.item.setData(pg.SUBTITLE_ROLE, "56 tracks · 3h 9m")
        self.item.setText("Road Trip")
        self.widget.addItem(self.item)
        self.index = self.widget.indexFromItem(self.item)

    def tearDown(self):
        self.widget.deleteLater()

    def test_size_hint_is_the_card(self):
        hint = self.delegate.sizeHint(QStyleOptionViewItem(), self.index)
        self.assertEqual(hint.width(), pg.CARD_WIDTH)
        self.assertEqual(hint.height(), pg.CARD_HEIGHT)

    def test_checkbox_sits_inside_the_cover(self):
        card = QRect(0, 0, pg.CARD_WIDTH, pg.CARD_HEIGHT)
        self.assertTrue(self.delegate.cover_rect(card).contains(self.delegate.check_rect(card)))

    def _click(self, point):
        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, pg.CARD_WIDTH + pg.GRID_GAP, pg.CARD_HEIGHT + pg.GRID_GAP)
        event = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            QPointF(point),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        return self.delegate.editorEvent(event, self.widget.model(), option, self.index)

    def test_clicking_the_checkbox_ticks_the_item(self):
        card = QRect(0, 0, pg.CARD_WIDTH, pg.CARD_HEIGHT)
        handled = self._click(self.delegate.check_rect(card).center())
        self.assertTrue(handled)
        self.assertEqual(self.item.checkState(), Qt.CheckState.Checked)

    def test_clicking_it_again_unticks(self):
        card = QRect(0, 0, pg.CARD_WIDTH, pg.CARD_HEIGHT)
        self._click(self.delegate.check_rect(card).center())
        self._click(self.delegate.check_rect(card).center())
        self.assertEqual(self.item.checkState(), Qt.CheckState.Unchecked)

    def test_clicking_the_artwork_does_not_tick(self):
        """Selection must stay separate from the checkbox, or drag-select is unusable."""
        self._click(QPoint(pg.CARD_WIDTH // 2, pg.CARD_HEIGHT // 2))
        self.assertEqual(self.item.checkState(), Qt.CheckState.Unchecked)

    def test_painting_a_tile_without_a_cover_does_not_raise(self):
        canvas = QPixmap(pg.CARD_WIDTH + pg.GRID_GAP, pg.CARD_HEIGHT + pg.GRID_GAP)
        canvas.fill(Qt.GlobalColor.black)
        from PyQt6.QtGui import QPainter

        option = QStyleOptionViewItem()
        option.rect = QRect(0, 0, pg.CARD_WIDTH + pg.GRID_GAP, pg.CARD_HEIGHT + pg.GRID_GAP)
        painter = QPainter(canvas)
        try:
            self.delegate.paint(painter, option, self.index)
        finally:
            painter.end()


class ViewModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.widget = QListWidget()
        self.delegate = pg.PlaylistCardDelegate(self.widget)

    def tearDown(self):
        self.widget.deleteLater()

    def test_grid_mode_wraps_icons(self):
        pg.apply_grid_mode(self.widget, self.delegate)
        self.assertEqual(self.widget.viewMode(), QListView.ViewMode.IconMode)
        self.assertTrue(self.widget.isWrapping())
        self.assertIs(self.widget.itemDelegate(), self.delegate)

    def test_grid_never_scrolls_sideways(self):
        pg.apply_grid_mode(self.widget, self.delegate)
        self.assertEqual(
            self.widget.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

    def test_list_mode_restores_a_plain_column(self):
        pg.apply_grid_mode(self.widget, self.delegate)
        pg.apply_list_mode(self.widget)
        self.assertEqual(self.widget.viewMode(), QListView.ViewMode.ListMode)
        self.assertFalse(self.widget.isWrapping())
        self.assertIsNot(self.widget.itemDelegate(), self.delegate)


class RetileTests(unittest.TestCase):
    """Qt's IconMode leaves whatever does not divide evenly as a dead right column."""

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _view(self, width, items=24):
        view = pg.PlaylistGridView()
        pg.apply_grid_mode(view, view.card_delegate)
        for i in range(items):
            item = QListWidgetItem()
            item.setData(pg.TITLE_ROLE, f"Playlist {i}")
            item.setText(f"Playlist {i}")
            view.addItem(item)
        view.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        view.resize(width, 700)
        view.show()
        view.retile()
        # Let the pending item layout run, or visualItemRect reports stale geometry.
        self.app.processEvents()
        view.doItemsLayout()
        self.addCleanup(view.deleteLater)
        return view

    def _first_row_slack(self, view):
        rects = [view.visualItemRect(view.item(i)) for i in range(view.count())]
        top = rects[0].y()
        right_edge = max(r.right() for r in rects if r.y() == top)
        return view.viewport().width() - right_edge

    def test_no_whole_extra_column_fits_beside_the_first_row(self):
        """The regression: 6 tiles fitted but only 5 were laid out."""
        for width in (760, 980, 1200, 1322, 1600):
            with self.subTest(width=width):
                view = self._view(width)
                slack = self._first_row_slack(view)
                self.assertLess(
                    slack,
                    view.gridSize().width(),
                    f"{slack}px free at {width}px wide -- another column fits",
                )

    def _columns(self, view):
        rects = [view.visualItemRect(view.item(i)) for i in range(view.count())]
        top = rects[0].y()
        return sum(1 for r in rects if r.y() == top)

    def test_cells_absorb_the_leftover_width(self):
        """Tiles stretch to divide the viewport, rather than sitting at a fixed size."""
        for width in (760, 980, 1200, 1322, 1600):
            with self.subTest(width=width):
                view = self._view(width)
                cell = view.gridSize().width()
                if cell >= pg.MAX_CARD_WIDTH + pg.GRID_GAP:
                    continue  # capped, so leftover is expected
                available = view.viewport().width() - pg.GRID_EDGE_ALLOWANCE
                columns = self._columns(view)
                leftover = available - columns * cell
                self.assertLess(leftover, cell, "another whole column would fit")
                self.assertGreaterEqual(leftover, 0)

    def test_narrowing_shrinks_the_tiles_instead_of_dropping_columns(self):
        """A small window should show more, smaller covers -- not two fat ones."""
        narrow = self._view(620)
        self.assertGreaterEqual(
            self._columns(narrow), 3,
            "a 620px wall should fit at least three covers",
        )

    def test_widening_never_reduces_the_column_count(self):
        previous = 0
        for width in (400, 620, 800, 1000, 1200, 1500, 1800):
            with self.subTest(width=width):
                columns = self._columns(self._view(width))
                self.assertGreaterEqual(columns, previous)
                previous = columns

    def test_tiles_never_shrink_below_the_readable_minimum(self):
        for width in (620, 800, 1000, 1400, 1900):
            with self.subTest(width=width):
                view = self._view(width)
                self.assertGreaterEqual(
                    view.card_delegate.card_size.width(), pg.MIN_CARD_WIDTH
                )

    def test_cards_never_exceed_the_cap(self):
        view = self._view(400)
        self.assertLessEqual(view.card_delegate.card_size.width(), pg.MAX_CARD_WIDTH)

    def test_cards_stay_square_plus_the_text_block(self):
        view = self._view(1322)
        size = view.card_delegate.card_size
        cover = size.width() - pg.CARD_PADDING * 2
        expected = pg.CARD_PADDING + cover + pg.TEXT_GAP + pg.TEXT_BLOCK + pg.CARD_PADDING
        self.assertEqual(size.height(), expected)

    def test_a_very_narrow_viewport_still_lays_out_one_column(self):
        view = self._view(220, items=3)
        self.assertEqual(self._columns(view), 1)
        self.assertGreater(view.card_delegate.card_size.width(), 0)

    def test_list_mode_is_not_retiled(self):
        view = self._view(1200)
        pg.apply_list_mode(view)
        before = view.gridSize()
        view.retile()
        self.assertEqual(view.gridSize(), before)


class IndicatorStylesheetTests(unittest.TestCase):
    """A ticked row in list mode was invisible; the theme must cover item views."""

    def test_theme_styles_item_view_indicators(self):
        self.assertIn("QListWidget::indicator", MAIN_STYLESHEET)
        self.assertIn("QListWidget::indicator:checked", MAIN_STYLESHEET)


# ---------------------------------------------------------------------------
# Main window integration
# ---------------------------------------------------------------------------


class PlaylistsPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        # FakeServer hands out URLs for a host that does not exist. Left alone, every
        # populated tile would queue a real HTTP request and every close() would then
        # block waiting for the pool to drain.
        self._real_request = pg.CoverFetcher.request
        self._real_cached = pg.CoverFetcher.cached_bytes
        pg.CoverFetcher.request = lambda fetcher, url: False
        pg.CoverFetcher.cached_bytes = lambda fetcher, url: None

        original = legacy_main.PlexPlaylistManager.load_config
        legacy_main.PlexPlaylistManager.load_config = lambda self: None
        try:
            self.window = legacy_main.PlexPlaylistManager()
        finally:
            legacy_main.PlexPlaylistManager.load_config = original
        self.window.plex_server = FakeServer()

    def tearDown(self):
        try:
            self.window.close()
        finally:
            pg.CoverFetcher.request = self._real_request
            pg.CoverFetcher.cached_bytes = self._real_cached

    def _populate(self, playlists):
        self.window.playlists = list(playlists)
        self.window.playlist_data = [(p, None) for p in playlists]
        self.window.update_playlist_listwidget()

    # -- subtitles ----------------------------------------------------------

    def test_leaf_count_and_duration_come_from_the_playlist_itself(self):
        """Both ship with the playlists() response, so no extra request is needed."""
        playlist = FakePlaylist("Road Trip", leaf_count=138, duration=32_844_000)
        self.assertEqual(
            self.window._playlist_subtitle(playlist), "138 tracks · 9h 7m"
        )

    def test_thousands_are_grouped(self):
        playlist = FakePlaylist("All Music", leaf_count=57857, duration=None)
        self.assertEqual(self.window._playlist_subtitle(playlist), "57,857 tracks")

    def test_one_track_is_singular(self):
        self.assertEqual(
            self.window._playlist_subtitle(FakePlaylist("Solo", leaf_count=1)), "1 track"
        )

    def test_an_explicit_count_wins_over_leaf_count(self):
        playlist = FakePlaylist("Road Trip", leaf_count=138)
        self.assertTrue(
            self.window._playlist_subtitle(playlist, 140).startswith("140 tracks")
        )

    def test_unknown_count_falls_back_to_the_old_prompt(self):
        self.assertEqual(
            self.window._playlist_subtitle(FakePlaylist("Mystery")),
            "click to load tracks...",
        )

    # -- compatibility with the pre-existing call sites ---------------------

    def test_the_playlist_object_is_still_on_user_role(self):
        playlist = FakePlaylist("Road Trip", leaf_count=10)
        self._populate([playlist])
        item = self.window.playlist_listwidget.item(0)
        self.assertIs(item.data(Qt.ItemDataRole.UserRole), playlist)

    def test_items_are_still_checkable_and_start_unchecked(self):
        self._populate([FakePlaylist("Road Trip", leaf_count=10)])
        item = self.window.playlist_listwidget.item(0)
        self.assertTrue(bool(item.flags() & Qt.ItemFlag.ItemIsUserCheckable))
        self.assertEqual(item.checkState(), Qt.CheckState.Unchecked)

    def test_select_all_and_get_selected_still_work(self):
        self._populate([FakePlaylist(f"P{i}", i, leaf_count=5) for i in range(4)])
        self.window.select_all_playlists(Qt.CheckState.Checked)
        self.assertEqual(len(self.window.get_selected_playlists()), 4)

    def test_display_text_still_splits_back_to_the_title(self):
        """Two call sites recover the name with text().split(' (')[0]."""
        self._populate([FakePlaylist("Road Trip", leaf_count=138, duration=32_844_000)])
        item = self.window.playlist_listwidget.item(0)
        self.assertEqual(item.text().split(" (")[0], "Road Trip")

        self.window.set_playlist_view_mode("list")
        self.assertEqual(item.text().split(" (")[0], "Road Trip")

    def test_count_update_keeps_the_title_clean(self):
        playlist = FakePlaylist("Road Trip", rating_key=7, leaf_count=1)
        self._populate([playlist])
        self.window.update_playlist_item_count("7", 138)
        item = self.window.playlist_listwidget.item(0)
        self.assertEqual(item.data(pg.TITLE_ROLE), "Road Trip")
        self.assertIn("138 tracks", item.data(pg.SUBTITLE_ROLE))

    def test_loading_and_error_states_reach_the_subtitle(self):
        playlist = FakePlaylist("Road Trip", rating_key=7, leaf_count=1)
        self._populate([playlist])
        item = self.window.playlist_listwidget.item(0)

        self.window.update_playlist_item_loading("7")
        self.assertEqual(item.data(pg.SUBTITLE_ROLE), "loading...")

        self.window.update_playlist_item_error("7")
        self.assertEqual(item.data(pg.SUBTITLE_ROLE), "error loading tracks")

    # -- view mode ----------------------------------------------------------

    def test_grid_is_the_default(self):
        self.assertEqual(self.window.playlist_view_mode, "grid")

    def test_grid_mode_shows_only_the_title(self):
        self._populate([FakePlaylist("Road Trip", leaf_count=138)])
        self.assertEqual(self.window.playlist_listwidget.item(0).text(), "Road Trip")

    def test_list_mode_folds_the_subtitle_into_the_text(self):
        self._populate([FakePlaylist("Road Trip", leaf_count=138)])
        self.window.set_playlist_view_mode("list")
        self.assertEqual(
            self.window.playlist_listwidget.item(0).text(), "Road Trip (138 tracks)"
        )

    def test_switching_back_to_grid_strips_it_again(self):
        self._populate([FakePlaylist("Road Trip", leaf_count=138)])
        self.window.set_playlist_view_mode("list")
        self.window.set_playlist_view_mode("grid")
        self.assertEqual(self.window.playlist_listwidget.item(0).text(), "Road Trip")

    def test_the_toggle_buttons_track_the_mode(self):
        self.window.set_playlist_view_mode("list")
        self.assertFalse(self.window.playlist_grid_view_button.isChecked())
        self.assertTrue(self.window.playlist_list_view_button.isChecked())

    def test_an_unknown_mode_falls_back_to_grid(self):
        self.window.set_playlist_view_mode("carousel")
        self.assertEqual(self.window.playlist_view_mode, "grid")

    def test_switching_the_mode_persists_it(self):
        """Round-tripping through the config file is covered in test_themes.py.

        This asserts the trigger: changing the mode must reach save_config(). It used
        to write to a `self.app_config` dict that never existed, so nothing was saved.
        """
        from unittest import mock

        with mock.patch.object(self.window, "save_config") as saved:
            self.window.set_playlist_view_mode("list")
        self.assertTrue(saved.called, "changing the view must persist it")
        self.assertEqual(self.window.playlist_view_mode, "list")

    # -- filtering ----------------------------------------------------------

    def test_filter_hides_non_matching_playlists(self):
        self._populate([FakePlaylist("Road Trip", 1, 5), FakePlaylist("Jazz Hits", 2, 5)])
        self.window.filter_playlist_items("jazz")
        self.assertTrue(self.window.playlist_listwidget.item(0).isHidden())
        self.assertFalse(self.window.playlist_listwidget.item(1).isHidden())

    def test_clearing_the_filter_shows_everything(self):
        self._populate([FakePlaylist("Road Trip", 1, 5), FakePlaylist("Jazz Hits", 2, 5)])
        self.window.filter_playlist_items("jazz")
        self.window.filter_playlist_items("")
        self.assertFalse(self.window.playlist_listwidget.item(0).isHidden())

    def test_the_filter_survives_a_refresh(self):
        playlists = [FakePlaylist("Road Trip", 1, 5), FakePlaylist("Jazz Hits", 2, 5)]
        self._populate(playlists)
        self.window.playlist_filter_input.setText("jazz")
        self.window.update_playlist_listwidget()
        self.assertTrue(self.window.playlist_listwidget.item(0).isHidden())

    def test_the_count_label_reports_the_filtered_total(self):
        self._populate([FakePlaylist("Road Trip", 1, 5), FakePlaylist("Jazz Hits", 2, 5)])
        self.assertEqual(self.window.playlist_count_label.text(), "2 playlists")
        self.window.filter_playlist_items("jazz")
        self.assertEqual(self.window.playlist_count_label.text(), "1 of 2 playlists")

    # -- cover URLs ---------------------------------------------------------

    def test_cover_url_uses_the_transcoder_at_tile_size(self):
        url = self.window._playlist_cover_url(FakePlaylist("Road Trip"))
        self.assertIn("/photo/:/transcode", url)
        self.assertIn(f"width={pg.COVER_SIZE * 2}", url)
        self.assertIn("X-Plex-Token=", url)

    def test_a_playlist_without_art_has_no_url(self):
        self.assertEqual(
            self.window._playlist_cover_url(FakePlaylist("Bare", thumb=None)), ""
        )

    def test_an_absolute_url_is_passed_through(self):
        playlist = FakePlaylist("Remote", thumb="https://cdn.example/art.jpg")
        self.assertEqual(
            self.window._playlist_cover_url(playlist), "https://cdn.example/art.jpg"
        )

    def test_no_server_means_no_url_rather_than_an_exception(self):
        self.window.plex_server = None
        self.assertEqual(self.window._playlist_cover_url(FakePlaylist("Road Trip")), "")

    def test_a_cover_url_is_recorded_on_each_tile(self):
        self._populate([FakePlaylist("Road Trip", leaf_count=5)])
        item = self.window.playlist_listwidget.item(0)
        self.assertTrue(item.data(pg.COVER_URL_ROLE))

    def test_list_mode_does_not_fetch_cover_art(self):
        """No point paying for posters nobody is going to see."""
        self.window.set_playlist_view_mode("list")
        self._populate([FakePlaylist("Road Trip", leaf_count=5)])
        item = self.window.playlist_listwidget.item(0)
        self.assertIsNone(item.data(pg.COVER_URL_ROLE))

    def test_delivered_bytes_land_on_the_matching_tile(self):
        self._populate([FakePlaylist("Road Trip", leaf_count=5)])
        item = self.window.playlist_listwidget.item(0)
        url = item.data(pg.COVER_URL_ROLE)

        source = QPixmap(300, 300)
        source.fill(Qt.GlobalColor.blue)
        buffer = source.toImage()
        from PyQt6.QtCore import QBuffer, QByteArray

        store = QByteArray()
        device = QBuffer(store)
        device.open(QBuffer.OpenModeFlag.WriteOnly)
        buffer.save(device, "PNG")
        device.close()

        self.window._on_playlist_cover_ready(url, bytes(store))
        self.assertEqual(item.data(pg.COVER_STATE_ROLE), "ready")
        self.assertIsInstance(item.data(pg.COVER_ROLE), QPixmap)

    def test_a_failed_fetch_leaves_the_tile_alone(self):
        self._populate([FakePlaylist("Road Trip", leaf_count=5)])
        item = self.window.playlist_listwidget.item(0)
        self.window._on_playlist_cover_ready(item.data(pg.COVER_URL_ROLE), b"")
        self.assertNotEqual(item.data(pg.COVER_STATE_ROLE), "ready")

    def test_garbage_bytes_do_not_raise(self):
        self._populate([FakePlaylist("Road Trip", leaf_count=5)])
        item = self.window.playlist_listwidget.item(0)
        self.window._on_playlist_cover_ready(item.data(pg.COVER_URL_ROLE), b"not-an-image")
        self.assertNotEqual(item.data(pg.COVER_STATE_ROLE), "ready")


if __name__ == "__main__":
    unittest.main()
