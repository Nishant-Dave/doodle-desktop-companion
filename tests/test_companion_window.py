"""Automated tests for the transparent companion window shell, positioning, and dragging."""

import os
import unittest

# Ensure Qt runs offscreen during automated test execution
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from doodle.character.character import Character
from doodle.desktop.companion_window import (
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    CompanionWindow,
)


class TestCompanionWindow(unittest.TestCase):
    """Tests verifying window configuration, desktop shell properties, and dragging."""

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
        self.assertFalse(self.window.is_dragging)

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
        self.window.set_default_position()
        pos = self.window.pos()
        self.assertIsNotNone(pos)

    def test_show_and_close(self) -> None:
        self.window.show()
        self.assertTrue(self.window.isVisible())
        self.window.close()
        self.assertFalse(self.window.isVisible())

    def test_mouse_drag_lifecycle_and_clamping(self) -> None:
        # Provide fixed bounds for deterministic testing
        test_bounds = QRect(0, 0, 1000, 800)
        self.window.position_manager._screen_bounds_provider = lambda: test_bounds
        self.window.move(QPoint(100, 100))

        moved_signals: list[QPoint] = []
        self.window.character_moved.connect(moved_signals.append)

        # 1. Mouse press initiates dragging without jumping
        press_event = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(20, 20),
            QPointF(120, 120),  # Global position: 100 + 20
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.window.mousePressEvent(press_event)
        self.assertTrue(self.window.is_dragging)
        self.assertEqual(self.window.pos(), QPoint(100, 100))

        # 2. Mouse move updates position preserving offset
        move_event = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(20, 20),
            QPointF(220, 220),  # Moved by (100, 100)
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.window.mouseMoveEvent(move_event)
        self.assertEqual(self.window.pos(), QPoint(200, 200))
        self.assertEqual(moved_signals[-1], QPoint(200, 200))

        # 3. Mouse move out-of-bounds clamps to screen bounds
        move_out_event = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(20, 20),
            QPointF(-200, -200),  # Drag far past top-left
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.window.mouseMoveEvent(move_out_event)
        # Position clamped to left/top boundary
        self.assertEqual(self.window.pos(), QPoint(0, 0))

        # 4. Mouse release ends dragging
        release_event = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            QPointF(20, 20),
            QPointF(20, 20),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.window.mouseReleaseEvent(release_event)
        self.assertFalse(self.window.is_dragging)

    def test_character_rendering_preserved(self) -> None:
        char = Character(name="panda")
        self.window.set_character(char)
        self.assertIs(self.window.character, char)
        self.window.show()
        # Force a repaint to verify rendering works alongside positioning
        self.window.repaint()
        self.window.close()


if __name__ == "__main__":
    unittest.main()
