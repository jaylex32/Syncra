"""Tests for the colour theme system.

Theming only works if *every* colour comes from the palette. The app used to carry
roughly 330 hardcoded colours -- 199 CSS declarations inside inline `setStyleSheet`
calls in the main module alone -- and each one is a spot that silently keeps its old
value when the theme changes. The regression guard at the bottom of this file fails if
a raw hex colour reappears in UI code.

Two failures worth remembering:

* A palette with a missing key is an invisible hole: nothing breaks until the one
  screen that uses that key is opened, so `test_every_theme_defines_every_key` checks
  all of them up front.
* The stylesheet is not the whole story. Anything Qt paints itself -- scroll-area
  viewports, message boxes, native dialogs -- reads the QPalette, and leaving that on
  the dark default made the light theme render black panels behind styled content.
"""

import os
import re
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from syncra.theme import styles
from syncra.theme.palettes import (
    DEFAULT_THEME,
    PALETTE_KEYS,
    THEMES,
    get_palette,
    tile_gradients,
)

HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")

PROJECT_UI_FILES = [
    "syncra/app/legacy_main.py",
    "syncra/ui/widgets/playlist_grid.py",
    "syncra/ui/widgets/track_picker.py",
    "syncra/ui/widgets/flow_layout.py",
    "syncra/ui/dialogs/export_files_dialog.py",
    "syncra/ui/dialogs/share_playlist_dialog.py",
]


class PaletteCompletenessTests(unittest.TestCase):
    def test_every_theme_defines_every_key(self):
        """A missing key only shows up on whichever screen happens to use it."""
        for name, palette in THEMES.items():
            missing = sorted(set(PALETTE_KEYS) - set(palette))
            with self.subTest(theme=name):
                self.assertEqual(missing, [], f"{name} is missing {missing}")

    def test_every_theme_has_a_name_and_description(self):
        for name, palette in THEMES.items():
            with self.subTest(theme=name):
                self.assertTrue(palette.get("name"))
                self.assertTrue(palette.get("description"))
                self.assertIn("dark", palette)

    def test_every_colour_value_is_a_hex_colour(self):
        for name, palette in THEMES.items():
            for key in PALETTE_KEYS:
                if key.startswith("tile_"):
                    continue
                with self.subTest(theme=name, key=key):
                    self.assertRegex(palette[key], r"^#[0-9a-fA-F]{6}$")

    def test_every_theme_supplies_eight_tile_gradients(self):
        for name, palette in THEMES.items():
            with self.subTest(theme=name):
                self.assertEqual(len(tile_gradients(palette)), 8)

    def test_at_least_one_light_and_several_dark_themes_exist(self):
        light = [n for n, p in THEMES.items() if not p["dark"]]
        dark = [n for n, p in THEMES.items() if p["dark"]]
        self.assertTrue(light, "no light theme")
        self.assertGreaterEqual(len(dark), 2)

    def test_an_unknown_theme_falls_back_to_the_default(self):
        self.assertEqual(get_palette("nonsense"), get_palette(DEFAULT_THEME))
        self.assertEqual(get_palette(None), get_palette(DEFAULT_THEME))


class ActiveThemeTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(styles.set_theme, DEFAULT_THEME)

    def test_switching_replaces_the_live_token_values(self):
        styles.set_theme("daylight")
        self.assertEqual(styles.TOKENS["bg_0"], THEMES["daylight"]["bg_0"])
        self.assertEqual(styles.current_theme(), "daylight")
        self.assertFalse(styles.is_dark())

    def test_tokens_is_mutated_in_place_not_rebound(self):
        """Modules that paint captured this dict at import; rebinding would strand them."""
        captured = styles.TOKENS
        styles.set_theme("carbon")
        self.assertIs(captured, styles.TOKENS)
        self.assertEqual(captured["bg_0"], THEMES["carbon"]["bg_0"])

    def test_an_unknown_name_keeps_a_usable_theme(self):
        styles.set_theme("does-not-exist")
        self.assertEqual(styles.current_theme(), DEFAULT_THEME)

    def test_the_stylesheet_follows_the_active_theme(self):
        light = styles.set_theme("daylight")
        self.assertIn(THEMES["daylight"]["bg_0"], light)
        self.assertNotIn(THEMES["midnight"]["sidebar"], light)

    def test_every_theme_renders_a_complete_stylesheet(self):
        for name in THEMES:
            with self.subTest(theme=name):
                sheet = styles.set_theme(name)
                self.assertGreater(len(sheet), 10000)
                self.assertIn("QMainWindow", sheet)
                self.assertIn('QLabel[status="ok"]', sheet)

    def test_no_stylesheet_leaks_another_theme_s_colours(self):
        for name, palette in THEMES.items():
            with self.subTest(theme=name):
                sheet = styles.set_theme(name)
                found = {c.lower() for c in HEX.findall(sheet)}
                allowed = {str(v).lower() for k, v in palette.items()
                           if isinstance(v, str) and v.startswith("#")}
                self.assertEqual(
                    found - allowed, set(),
                    "stylesheet contains colours not in this palette",
                )

    def test_tile_palette_follows_the_theme(self):
        styles.set_theme("daylight")
        self.assertEqual(styles.tile_palette(), tile_gradients(THEMES["daylight"]))


class QPaletteTests(unittest.TestCase):
    """The stylesheet does not reach widgets Qt paints itself."""

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.addCleanup(styles.set_theme, DEFAULT_THEME)

    def test_a_palette_is_produced_for_every_theme(self):
        from PyQt6.QtGui import QPalette
        for name in THEMES:
            with self.subTest(theme=name):
                styles.set_theme(name)
                self.assertIsInstance(styles.build_qpalette(), QPalette)

    def test_the_window_colour_matches_the_theme(self):
        from PyQt6.QtGui import QPalette
        styles.set_theme("daylight")
        palette = styles.build_qpalette()
        self.assertEqual(
            palette.color(QPalette.ColorRole.Window).name().lower(),
            THEMES["daylight"]["bg_0"].lower(),
        )

    def test_light_and_dark_palettes_actually_differ(self):
        from PyQt6.QtGui import QPalette
        styles.set_theme("midnight")
        dark = styles.build_qpalette().color(QPalette.ColorRole.Window).name()
        styles.set_theme("daylight")
        light = styles.build_qpalette().color(QPalette.ColorRole.Window).name()
        self.assertNotEqual(dark, light)

    def test_highlighted_text_uses_on_accent(self):
        """Text on an accent fill is not the canvas colour in a light theme."""
        from PyQt6.QtGui import QPalette
        styles.set_theme("daylight")
        palette = styles.build_qpalette()
        self.assertEqual(
            palette.color(QPalette.ColorRole.HighlightedText).name().lower(),
            THEMES["daylight"]["on_accent"].lower(),
        )


class NoHardcodedColoursTests(unittest.TestCase):
    """The regression guard: a raw hex in UI code is a spot the theme cannot reach."""

    # Brand marks stay fixed on purpose: Spotify green is Spotify green in any theme.
    ALLOWED = {"playlist_grid.py"}

    def _sources(self):
        import pathlib
        root = pathlib.Path(styles.__file__).resolve().parents[2]
        for relative in PROJECT_UI_FILES:
            path = root / relative
            if path.exists():
                yield path

    def test_no_raw_hex_colours_in_ui_code(self):
        offenders = []
        for path in self._sources():
            if path.name in self.ALLOWED:
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if HEX.search(line):
                    offenders.append(f"{path.name}:{number}: {line.strip()[:70]}")
        self.assertEqual(offenders, [], "hardcoded colours:\n" + "\n".join(offenders[:10]))

    def test_the_grid_only_hardcodes_brand_and_fallback_colours(self):
        """playlist_grid.py may hold fixed colours, but only in three named places."""
        import pathlib

        root = pathlib.Path(styles.__file__).resolve().parents[2]
        lines = (root / "syncra/ui/widgets/playlist_grid.py").read_text(
            encoding="utf-8"
        ).splitlines()

        # Line ranges of the constants allowed to carry literal colours.
        allowed = set()
        block = None
        for number, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("BADGE_TEXT"):
                allowed.add(number)
            elif stripped.startswith(("SERVICE_COLOURS = {", "PLACEHOLDER_GRADIENTS = (")):
                block = "}" if stripped.endswith("{") else ")"
                allowed.add(number)
            elif block is not None:
                allowed.add(number)
                if stripped.startswith(block):
                    block = None

        offenders = [
            f"line {number}: {line.strip()[:60]}"
            for number, line in enumerate(lines, 1)
            if HEX.search(line) and number not in allowed
        ]
        self.assertEqual(
            offenders, [],
            "colours outside SERVICE_COLOURS / PLACEHOLDER_GRADIENTS / BADGE_TEXT:" + chr(10) + chr(10).join(offenders),
        )


class ThemePersistenceTests(unittest.TestCase):
    """The chosen theme was not surviving a restart.

    Two separate faults. `save_config()` rebuilds the file from what is already on
    disk, so a value only ever written to an in-memory dict never reached it -- and
    the dict in question, `self.app_config`, did not exist at all, so the guarded
    write was skipped silently. The same pair of bugs also lost the grid/list choice.
    """

    @classmethod
    def setUpClass(cls):
        from PyQt6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        import json
        import tempfile
        from syncra.app import legacy_main
        from syncra.ui.widgets import playlist_grid as pg

        self.legacy_main = legacy_main
        self.addCleanup(styles.set_theme, DEFAULT_THEME)

        self._real_request = pg.CoverFetcher.request
        self._real_cached = pg.CoverFetcher.cached_bytes
        pg.CoverFetcher.request = lambda fetcher, url: False
        pg.CoverFetcher.cached_bytes = lambda fetcher, url: None
        self.addCleanup(setattr, pg.CoverFetcher, "request", self._real_request)
        self.addCleanup(setattr, pg.CoverFetcher, "cached_bytes", self._real_cached)

        self.tmp = tempfile.TemporaryDirectory(prefix="syncra-theme-cfg-")
        self.addCleanup(self.tmp.cleanup)
        self.config_path = os.path.join(self.tmp.name, "app_config.json")
        with open(self.config_path, "w", encoding="utf-8") as handle:
            json.dump({"server_ip": "127.0.0.1", "server_port": "32400"}, handle)

        self._real_config = legacy_main.CONFIG_FILE
        legacy_main.CONFIG_FILE = self.config_path
        self.addCleanup(setattr, legacy_main, "CONFIG_FILE", self._real_config)

    def _window(self):
        window = self.legacy_main.PlexPlaylistManager()
        self.addCleanup(window.close)
        return window

    def _stored(self):
        import json
        with open(self.config_path, encoding="utf-8") as handle:
            return json.load(handle)

    def test_choosing_a_theme_writes_it_to_the_config_file(self):
        window = self._window()
        window.apply_theme("daylight")
        self.assertEqual(self._stored().get("theme"), "daylight")

    def test_the_theme_comes_back_on_the_next_launch(self):
        first = self._window()
        first.apply_theme("carbon")
        first.close()

        styles.set_theme(DEFAULT_THEME)
        self._window()
        self.assertEqual(styles.current_theme(), "carbon")

    def test_the_view_mode_is_saved_too(self):
        window = self._window()
        window.set_playlist_view_mode("list")
        self.assertEqual(self._stored().get("playlist_view_mode"), "list")

    def test_the_view_mode_comes_back_even_though_the_page_is_built_first(self):
        """initUI() runs before load_config(), so it must be re-applied afterwards."""
        first = self._window()
        first.set_playlist_view_mode("list")
        first.close()

        second = self._window()
        self.assertEqual(second.playlist_view_mode, "list")

    def test_saving_preserves_unrelated_settings(self):
        window = self._window()
        window.apply_theme("slate")
        self.assertEqual(self._stored().get("server_ip"), "127.0.0.1")

    def test_applying_without_saving_leaves_the_file_alone(self):
        window = self._window()
        window.apply_theme("aurora", save=False)
        self.assertNotEqual(self._stored().get("theme"), "aurora")


if __name__ == "__main__":
    unittest.main()
