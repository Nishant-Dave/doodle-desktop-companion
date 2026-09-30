"""Automated tests for the transparent companion window shell."""

import os
import unittest

# Ensure Qt runs offscreen during automated test execution
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from doodle.desktop.companion_window import (
    CompanionWindow,
    DEFAULT_WINDOW_WIDTH,
    DEFAULT_WINDOW_HEIGHT,
)


class TestCompanionWindow(unittest.TestCase):
    """Tests verifying window configuration and desktop shell properties."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_window"])

    def setUp(self) -> None:
        self.window = CompanionWindow()

    def tearDown(self) -> None:
        if self.window.isVisible():
            self.window.close()
        self.window.deleteLater()

    def test_construction_and_geometry(self) -> None:
        self.assertIsNotNone(self.window)
        self.assertEqual(self.window.windowTitle(), "Doodle")
        self.assertEqual(self.window.width(), DEFAULT_WINDOW_WIDTH)
        self.assertEqual(self.window.height(), DEFAULT_WINDOW_HEIGHT)

    def test_frameless_configuration(self) -> None:
        flags = self.window.windowFlags()
        self.assertTrue(
            bool(flags & Qt.WindowType.FramelessWindowHint),
            "CompanionWindow must have FramelessWindowHint flag set.",
        )

    def test_always_on_top_configuration(self) -> None:
        flags = self.window.windowFlags()
        self.assertTrue(
            bool(flags & Qt.WindowType.WindowStaysOnTopHint),
            "CompanionWindow must have WindowStaysOnTopHint flag set.",
        )

    def test_transparent_background_configuration(self) -> None:
        self.assertTrue(
            self.window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground),
            "CompanionWindow must have WA_TranslucentBackground attribute enabled.",
        )

    def test_positioning_fallback_and_execution(self) -> None:
        # Verify set_default_position executes cleanly regardless of screen resolution
        self.window.set_default_position()
        pos = self.window.pos()
        self.assertIsNotNone(pos)

    def test_show_and_close(self) -> None:
        self.window.show()
        self.assertTrue(self.window.isVisible())
        self.window.close()
        self.assertFalse(self.window.isVisible())


if __name__ == "__main__":
    unittest.main()
