"""Automated tests for the Doodle interaction menu and click/drag interaction boundary."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

# Ensure Qt runs offscreen during automated test execution
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QSettings, QSize, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication

from doodle.app.application import DoodleApplication
from doodle.character.state import CharacterState
from doodle.desktop.companion_window import CompanionWindow
from doodle.persistence.settings import SettingsManager
from doodle.ui.interaction_menu import (
    AVAILABLE_ACTIONS,
    DEFAULT_MENU_WIDTH,
    InteractionMenu,
    compute_menu_position,
)


class TestComputeMenuPosition(unittest.TestCase):
    """Deterministic mathematical tests for menu position calculation."""

    def setUp(self) -> None:
        self.screen = QRect(0, 0, 1920, 1080)
        self.menu_size = QSize(148, 200)

    def test_normal_placement_above_target(self) -> None:
        target = QRect(1000, 500, 160, 160)
        pos = compute_menu_position(target, self.menu_size, self.screen)

        # Expected center: 1000 + 80 = 1080; menu x = 1080 - 74 = 1006
        self.assertEqual(pos.x(), 1006)
        # Expected y: 500 - 200 - 8 = 292
        self.assertEqual(pos.y(), 292)

        # Confirm strictly inside screen bounds
        menu_rect = QRect(pos, self.menu_size)
        self.assertTrue(self.screen.contains(menu_rect))

    def test_top_edge_flips_below_target(self) -> None:
        # Target at top edge with insufficient space above
        target = QRect(500, 20, 160, 160)
        pos = compute_menu_position(target, self.menu_size, self.screen)

        # y should flip below target: 20 + 160 + 8 = 188
        self.assertEqual(pos.y(), 188)
        menu_rect = QRect(pos, self.menu_size)
        self.assertTrue(self.screen.contains(menu_rect))

    def test_bottom_right_edge_clamping(self) -> None:
        # Target near bottom-right screen corner (default Doodle location)
        target = QRect(1800, 900, 160, 160)
        pos = compute_menu_position(target, self.menu_size, self.screen)

        # Fits above target: 900 - 200 - 8 = 692
        self.assertEqual(pos.y(), 692)
        # Clamped horizontally so right edge doesn't exceed screen: 1920 - 148 = 1772
        self.assertEqual(pos.x(), 1920 - 148)

        menu_rect = QRect(pos, self.menu_size)
        self.assertTrue(self.screen.contains(menu_rect))

    def test_left_edge_clamping(self) -> None:
        target = QRect(10, 500, 160, 160)
        pos = compute_menu_position(target, self.menu_size, self.screen)

        # Target center x = 10 + 80 = 90; 90 - 74 = 16 >= 0
        self.assertEqual(pos.x(), 16)
        menu_rect = QRect(pos, self.menu_size)
        self.assertTrue(self.screen.contains(menu_rect))

    def test_out_of_bounds_target_clamping(self) -> None:
        # Target completely offscreen past top-left
        target = QRect(-200, -200, 160, 160)
        pos = compute_menu_position(target, self.menu_size, self.screen)

        self.assertGreaterEqual(pos.x(), self.screen.left())
        self.assertGreaterEqual(pos.y(), self.screen.top())
        self.assertLessEqual(pos.x() + self.menu_size.width(), self.screen.right() + 1)
        self.assertLessEqual(pos.y() + self.menu_size.height(), self.screen.bottom() + 1)


class TestInteractionMenu(unittest.TestCase):
    """Component tests for the InteractionMenu widget."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_interaction_menu"])

    def setUp(self) -> None:
        self.menu = InteractionMenu()

    def tearDown(self) -> None:
        if self.menu.isVisible():
            self.menu.dismiss()
        self.menu.deleteLater()

    def test_construction_and_flags(self) -> None:
        self.assertIsNotNone(self.menu)
        flags = self.menu.windowFlags()
        self.assertTrue(bool(flags & Qt.WindowType.Popup))
        self.assertTrue(bool(flags & Qt.WindowType.FramelessWindowHint))
        self.assertTrue(self.menu.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
        self.assertEqual(self.menu.width(), DEFAULT_MENU_WIDTH)

    def test_action_buttons_exist_and_disabled(self) -> None:
        expected_actions = ["journal", "mood", "idea", "remember", "settings"]
        for action_id in expected_actions:
            btn = self.menu.get_action_button(action_id)
            self.assertIsNotNone(btn, f"Action button for '{action_id}' must exist.")
            self.assertFalse(btn.isEnabled(), f"Action button for '{action_id}' must be disabled in M1.")
            self.assertFalse(self.menu.is_action_enabled(action_id))

    def test_dismiss_button_exists_and_enabled(self) -> None:
        dismiss_btn = self.menu.get_action_button("dismiss")
        self.assertIsNotNone(dismiss_btn, "Dismiss button must exist.")
        self.assertTrue(dismiss_btn.isEnabled(), "Dismiss button must be enabled.")

    def test_menu_visibility_and_open_behavior(self) -> None:
        self.assertFalse(self.menu.isVisible())

        target = QRect(400, 400, 160, 160)
        screen = QRect(0, 0, 1920, 1080)
        self.menu.show_near(target, screen_bounds=screen)

        self.assertTrue(self.menu.isVisible())
        self.assertGreater(self.menu.pos().x(), 0)
        self.assertGreater(self.menu.pos().y(), 0)

    def test_menu_dismissal(self) -> None:
        dismissed_events: list[bool] = []
        self.menu.dismissed.connect(lambda: dismissed_events.append(True))

        self.menu.show()
        self.assertTrue(self.menu.isVisible())

        self.menu.dismiss()
        self.assertFalse(self.menu.isVisible())
        self.assertEqual(len(dismissed_events), 1)

    def test_dismiss_button_click(self) -> None:
        dismissed_events: list[bool] = []
        self.menu.dismissed.connect(lambda: dismissed_events.append(True))

        self.menu.show()
        dismiss_btn = self.menu.get_action_button("dismiss")
        self.assertIsNotNone(dismiss_btn)
        dismiss_btn.click()

        self.assertFalse(self.menu.isVisible())
        self.assertEqual(len(dismissed_events), 1)

    def test_escape_key_dismissal(self) -> None:
        dismissed_events: list[bool] = []
        self.menu.dismissed.connect(lambda: dismissed_events.append(True))

        self.menu.show()
        esc_event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            Qt.Key.Key_Escape,
            Qt.KeyboardModifier.NoModifier,
        )
        self.menu.keyPressEvent(esc_event)

        self.assertFalse(self.menu.isVisible())
        self.assertEqual(len(dismissed_events), 1)

    def test_menu_action_requests(self) -> None:
        action_events: list[str] = []
        self.menu.action_requested.connect(action_events.append)

        self.menu.request_action("journal")
        self.assertEqual(action_events, ["journal"])

        self.menu.request_action("Mood")
        self.assertEqual(action_events, ["journal", "mood"])

        self.menu.request_action("SETTINGS")
        self.assertEqual(action_events, ["journal", "mood", "settings"])

    def test_menu_cleanup(self) -> None:
        self.menu.show()
        self.assertTrue(self.menu.isVisible())

        self.menu.cleanup()
        self.assertFalse(self.menu.isVisible())


class TestPandaClickAndDragIntegration(unittest.TestCase):
    """Tests verifying click vs drag discrimination and menu opening/closing."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_click_drag"])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ini_path = Path(self.temp_dir.name) / "test_interaction.ini"
        self.qsettings = QSettings(str(self.ini_path), QSettings.Format.IniFormat)
        self.settings = SettingsManager(settings=self.qsettings)
        self.app = DoodleApplication(["test_app"], settings_manager=self.settings)

    def tearDown(self) -> None:
        self.app.dismiss_interaction_menu()
        self.app.window.close()
        self.qsettings.clear()
        self.qsettings.sync()
        del self.qsettings
        self.temp_dir.cleanup()

    def test_click_produces_character_clicked_and_no_move(self) -> None:
        window = self.app.window
        clicked_events: list[bool] = []
        moved_events: list[QPoint] = []

        window.character_clicked.connect(lambda: clicked_events.append(True))
        window.character_moved.connect(moved_events.append)

        # Mouse press and release without movement
        press = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(40, 40),
            QPointF(140, 140),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        window.mousePressEvent(press)
        self.assertTrue(window.is_dragging)
        self.assertFalse(window.drag_occurred)

        release = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            QPointF(40, 40),
            QPointF(140, 140),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        window.mouseReleaseEvent(release)
        self.assertFalse(window.is_dragging)
        self.assertFalse(window.drag_occurred)

        # Click signal emitted, moved signal NOT emitted
        self.assertEqual(len(clicked_events), 1)
        self.assertEqual(len(moved_events), 0)

    def test_click_opens_menu_and_character_enters_attention(self) -> None:
        self.assertFalse(self.app.menu.isVisible())
        self.assertEqual(self.app.character.state, CharacterState.IDLE)

        # Emit click
        self.app.window.character_clicked.emit()

        self.assertTrue(self.app.menu.isVisible())
        self.assertEqual(self.app.character.state, CharacterState.ATTENTION)

        # Dismiss menu restores IDLE state
        self.app.menu.dismiss()
        self.assertFalse(self.app.menu.isVisible())
        self.assertEqual(self.app.character.state, CharacterState.IDLE)

    def test_drag_does_not_open_menu(self) -> None:
        window = self.app.window
        clicked_events: list[bool] = []
        moved_events: list[QPoint] = []

        window.character_clicked.connect(lambda: clicked_events.append(True))
        window.character_moved.connect(moved_events.append)

        # Mouse press
        press = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(20, 20),
            QPointF(120, 120),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        window.mousePressEvent(press)

        # Mouse move exceeding threshold
        move = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(70, 70),
            QPointF(170, 170),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        window.mouseMoveEvent(move)
        self.assertTrue(window.drag_occurred)
        self.assertGreater(len(moved_events), 0)

        # Mouse release
        release = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            QPointF(70, 70),
            QPointF(170, 170),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        window.mouseReleaseEvent(release)

        # character_clicked must NOT be emitted
        self.assertEqual(len(clicked_events), 0)
        # Menu must NOT be opened
        self.assertFalse(self.app.menu.isVisible())

    def test_drag_dismisses_existing_open_menu(self) -> None:
        # Open menu first
        self.app.show_interaction_menu()
        self.assertTrue(self.app.menu.isVisible())

        # Simulate movement
        self.app.window.character_moved.emit(QPoint(300, 300))

        # Menu should be dismissed
        self.assertFalse(self.app.menu.isVisible())
        self.assertEqual(self.app.character.state, CharacterState.IDLE)

    def test_duplicate_menu_creation_prevented(self) -> None:
        initial_menu = self.app.menu

        # Click multiple times
        self.app.window.character_clicked.emit()
        self.assertIs(self.app.menu, initial_menu)

        # Click again to toggle dismiss
        self.app.window.character_clicked.emit()
        self.assertFalse(self.app.menu.isVisible())
        self.assertIs(self.app.menu, initial_menu)

        # Click once more to open again
        self.app.window.character_clicked.emit()
        self.assertTrue(self.app.menu.isVisible())
        self.assertIs(self.app.menu, initial_menu)

    def test_hide_from_tray_dismisses_menu(self) -> None:
        self.app.show_interaction_menu()
        self.assertTrue(self.app.menu.isVisible())

        self.app.hide_companion()
        self.assertFalse(self.app.menu.isVisible())
        self.assertFalse(self.app.window.isVisible())

    def test_application_lifecycle_cleanup(self) -> None:
        self.app.lifecycle.startup()
        self.app.show_interaction_menu()
        self.assertTrue(self.app.menu.isVisible())

        self.app.lifecycle.shutdown()
        self.assertFalse(self.app.menu.isVisible())


if __name__ == "__main__":
    unittest.main()
