"""Tests for application identity and resource resolution.

A window created without an explicit title inherits QCoreApplication.applicationName(),
which defaults to the executable basename -- so the deletion progress dialog was
titled "python" from source, and would carry the exe name in a build. Resources were
also resolved relative to the working directory, and the icon was never bundled.
"""

import os
import pathlib
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QCoreApplication
from PyQt6.QtWidgets import QApplication, QProgressDialog

from syncra.app import legacy_main

PROJECT_ROOT = pathlib.Path(legacy_main.__file__).resolve().parents[2]


class ResourcePathTests(unittest.TestCase):
    def test_resolves_relative_to_the_project_not_the_working_directory(self):
        original = os.getcwd()
        try:
            os.chdir(pathlib.Path(original).anchor)
            resolved = legacy_main.resource_path(legacy_main.APP_ICON_FILE)
            self.assertTrue(
                os.path.exists(resolved),
                "resources must resolve however the app was launched",
            )
        finally:
            os.chdir(original)

    def test_prefers_the_pyinstaller_bundle_directory(self):
        saved = getattr(sys, "_MEIPASS", None)
        sys._MEIPASS = os.path.join("some", "bundle")
        try:
            resolved = legacy_main.resource_path("thing.txt")
            self.assertEqual(resolved, os.path.join("some", "bundle", "thing.txt"))
        finally:
            if saved is None:
                del sys._MEIPASS
            else:
                sys._MEIPASS = saved

    def test_missing_resource_still_returns_a_path(self):
        self.assertTrue(legacy_main.resource_path("definitely-not-here.dat"))


class AppIconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_icon_loads_and_has_real_sizes(self):
        icon = legacy_main.get_app_icon()
        self.assertFalse(icon.isNull(), "the window icon should load in development")
        self.assertTrue(icon.availableSizes())

    def test_icon_file_is_present_at_the_expected_name(self):
        self.assertTrue((PROJECT_ROOT / legacy_main.APP_ICON_FILE).exists())


class WindowTitleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_untitled_windows_inherit_the_application_name(self):
        saved = QCoreApplication.applicationName()
        try:
            QCoreApplication.setApplicationName(legacy_main.APP_NAME)
            dialog = QProgressDialog("working", "Cancel", 0, 10)
            try:
                # Qt reports an empty title and paints applicationName() instead.
                shown = dialog.windowTitle() or QCoreApplication.applicationName()
                self.assertEqual(shown, "Syncra")
                self.assertNotIn("python", shown.lower())
            finally:
                dialog.deleteLater()
        finally:
            QCoreApplication.setApplicationName(saved)

    def test_app_name_constant_is_not_an_executable_name(self):
        self.assertEqual(legacy_main.APP_NAME, "Syncra")


class PackagingTests(unittest.TestCase):
    """The icon has to be in datas, not just set as the exe's file icon."""

    def test_spec_bundles_the_icon_as_data(self):
        spec = (PROJECT_ROOT / "Syncra-Windows.spec").read_text(encoding="utf-8")
        self.assertIn("('Syncra Icon.ico', '.')", spec,
                      "icon must be in datas so QIcon can load it at runtime")

    def test_workflows_bundle_the_icon(self):
        for name in ("build-multiplatform.yml", "release.yml"):
            workflow = (PROJECT_ROOT / ".github" / "workflows" / name).read_text(
                encoding="utf-8"
            )
            self.assertIn("Syncra Icon.ico;.", workflow, f"{name}: windows build")
            self.assertIn("Syncra Icon.ico:.", workflow, f"{name}: unix build")


if __name__ == "__main__":
    unittest.main()
