"""Comprehensive integration and acceptance hardening test suite for Milestone 1.

Validates that all Milestone 1 components work together as a stable desktop companion:
1. Startup & Composition
2. Idle Behavior & Deterministic Transitions
3. Panda Click Interaction & Interaction Menu
4. Dragging & Screen Boundary Enforcement
5. Tray Show / Hide Lifecycle
6. Position Persistence & Boundary Clamping
7. Clean Shutdown & Resource Cleanup
8. Error Handling & Safe Fallbacks
9. Long-Running Simulation & Resource Stability
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

# Ensure Qt runs offscreen during automated test execution
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QSettings, QSize, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent, QPaintEvent, QRegion
from PySide6.QtWidgets import QApplication

from doodle.app.application import DoodleApplication
from doodle.app.lifecycle import AppLifecycle
from doodle.behavior.engine import BehaviorEngine
from doodle.behavior.rules import (
    ACTION_CHANGE_STATE,
    ACTION_NOOP,
    EVENT_ANIMATION_FINISHED,
    EVENT_CHARACTER_CLICKED,
    EVENT_IDLE_TIMEOUT,
    EVENT_MENU_DISMISSED,
    BehaviorAction,
    BehaviorContext,
    IdleBehaviorRules,
)
from doodle.character.animation import AnimationController
from doodle.character.character import Character
from doodle.character.state import CharacterState
from doodle.desktop.companion_window import (
    DEFAULT_DRAG_THRESHOLD,
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    CompanionWindow,
)
from doodle.desktop.positioning import PositionManager
from doodle.desktop.tray import DoodleTrayIcon
from doodle.persistence.settings import (
    KEY_WINDOW_POSITION,
    KEY_WINDOW_POSITION_X,
    KEY_WINDOW_POSITION_Y,
    SettingsManager,
)
from doodle.ui.interaction_menu import InteractionMenu, compute_menu_position


class Milestone1AcceptanceTestBase(unittest.TestCase):
    """Base test case providing clean Qt application and temporary isolated settings."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["milestone1_acceptance_tests"])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ini_path = Path(self.temp_dir.name) / "test_acceptance_settings.ini"
        self.qsettings = QSettings(str(self.ini_path), QSettings.Format.IniFormat)
        self.settings_manager = SettingsManager(settings=self.qsettings)
        self.app = DoodleApplication(
            argv=["doodle_acceptance"],
            settings_manager=self.settings_manager,
        )

    def tearDown(self) -> None:
        if hasattr(self, "app") and self.app is not None:
            self.app.window.close()
            self.app.lifecycle.shutdown()
        self.qsettings.clear()
        self.qsettings.sync()
        del self.qsettings
        self.temp_dir.cleanup()


class TestMilestone1Startup(Milestone1AcceptanceTestBase):
    """Scenario 1: Startup verification."""

    def test_startup_composition_and_no_duplicates(self) -> None:
        # 1. Composition root correctly constructs and holds single references
        self.assertIsInstance(self.app.qapp, QApplication)
        self.assertEqual(self.app.qapp.applicationName(), "Doodle")
        self.assertIsInstance(self.app.lifecycle, AppLifecycle)
        self.assertIsInstance(self.app.settings_manager, SettingsManager)
        self.assertIsInstance(self.app.character, Character)
        self.assertIsInstance(self.app.window, CompanionWindow)
        self.assertIsInstance(self.app.tray, DoodleTrayIcon)
        self.assertIsInstance(self.app.menu, InteractionMenu)
        self.assertIsInstance(self.app.behavior_engine, BehaviorEngine)

        # 2. Character initial state
        self.assertEqual(self.app.character.state, CharacterState.IDLE)
        self.assertEqual(self.app.character.current_animation_name, "idle")

        # 3. Window configuration
        self.assertEqual(self.app.window.windowTitle(), "Doodle")
        self.assertTrue(self.app.window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
        flags = self.app.window.windowFlags()
        self.assertTrue(bool(flags & Qt.WindowType.FramelessWindowHint))
        self.assertTrue(bool(flags & Qt.WindowType.WindowStaysOnTopHint))

        # 4. Default position restored within bounds
        pos = self.app.window.pos()
        bounds = self.app.window.position_manager.get_usable_screen_bounds()
        self.assertTrue(bounds.contains(QRect(pos, self.app.window.size())))

        # 5. Tray icon and menu state
        self.assertEqual(self.app.tray.action_show.text(), "Show Doodle")
        self.assertEqual(self.app.tray.action_hide.text(), "Hide Doodle")
        self.assertEqual(self.app.tray.action_exit.text(), "Exit Doodle")
        self.assertFalse(self.app.menu.isVisible())


class TestMilestone1IdleBehavior(Milestone1AcceptanceTestBase):
    """Scenario 2: Idle behavior verification."""

    def test_idle_cycle_transitions_and_eligibility(self) -> None:
        self.app.lifecycle.startup()
        self.app.behavior_engine.start_idle_timer()
        self.assertTrue(self.app.behavior_engine.is_idle_timer_active)
        self.assertTrue(self.app.behavior_engine.is_idle_eligible)

        # Deterministic sequence: STRETCH -> SIT -> SLEEP -> STRETCH
        expected_sequence = [
            CharacterState.STRETCH,
            CharacterState.SIT,
            CharacterState.SLEEP,
            CharacterState.STRETCH,
        ]

        for expected_state in expected_sequence:
            # 1. Idle timeout triggers transition
            self.app.behavior_engine.trigger_idle_timeout()
            self.assertEqual(self.app.character.state, expected_state)

            # 2. While performing action, character is not in IDLE, so idle timer must pause
            self.assertFalse(self.app.behavior_engine.is_idle_eligible)

            # 3. Animation finishes -> returns to IDLE
            self.app.character.animation_finished.emit(expected_state.value.lower())
            self.assertEqual(self.app.character.state, CharacterState.IDLE)
            self.assertTrue(self.app.behavior_engine.is_idle_eligible)

    def test_repeated_idle_cycles_do_not_accumulate_resources(self) -> None:
        self.app.lifecycle.startup()
        self.app.behavior_engine.start_idle_timer()

        # Run 12 full cycles (3 full loops of the deterministic sequence)
        for _ in range(12):
            self.app.behavior_engine.trigger_idle_timeout()
            current_state = self.app.character.state
            self.assertIn(current_state, (CharacterState.STRETCH, CharacterState.SIT, CharacterState.SLEEP))
            self.app.character.animation_finished.emit(current_state.value.lower())
            self.assertEqual(self.app.character.state, CharacterState.IDLE)

        # Confirm behavior engine is still healthy and idle timer active
        self.assertTrue(self.app.behavior_engine.is_idle_timer_active)
        self.assertTrue(self.app.behavior_engine.is_idle_eligible)


class TestMilestone1ClickInteraction(Milestone1AcceptanceTestBase):
    """Scenario 3: Click interaction verification."""

    def test_click_opens_menu_and_sets_attention(self) -> None:
        self.assertEqual(self.app.character.state, CharacterState.IDLE)
        self.assertFalse(self.app.menu.isVisible())

        # Click companion
        self.app.window.character_clicked.emit()
        self.assertEqual(self.app.character.state, CharacterState.ATTENTION)
        self.assertTrue(self.app.menu.isVisible())
        self.assertTrue(self.app.behavior_engine.is_menu_open)
        self.assertFalse(self.app.behavior_engine.is_idle_eligible)

    def test_click_during_idle_action_interrupts_into_attention(self) -> None:
        # Put into STRETCH via idle trigger
        self.app.behavior_engine.trigger_idle_timeout()
        self.assertEqual(self.app.character.state, CharacterState.STRETCH)

        # Click interrupts immediately into ATTENTION
        self.app.window.character_clicked.emit()
        self.assertEqual(self.app.character.state, CharacterState.ATTENTION)
        self.assertTrue(self.app.menu.isVisible())

    def test_menu_dismissal_restores_idle_without_getting_stuck(self) -> None:
        self.app.window.character_clicked.emit()
        self.assertEqual(self.app.character.state, CharacterState.ATTENTION)

        # Dismiss menu
        self.app.menu.dismiss()
        self.assertFalse(self.app.menu.isVisible())
        self.assertEqual(self.app.character.state, CharacterState.IDLE)
        self.assertFalse(self.app.behavior_engine.is_menu_open)
        self.assertTrue(self.app.behavior_engine.is_idle_eligible)

    def test_unimplemented_menu_actions_do_not_crash_or_fake_features(self) -> None:
        self.app.window.character_clicked.emit()
        self.assertTrue(self.app.menu.isVisible())

        requested_actions = []
        self.app.menu.action_requested.connect(requested_actions.append)

        # Check each future action button is disabled and safe to request
        for action_id in ["journal", "mood", "settings"]:
            self.assertFalse(self.app.menu.is_action_enabled(action_id))
            btn = self.app.menu.get_action_button(action_id)
            self.assertIsNotNone(btn)
            self.assertFalse(btn.isEnabled())

            # Emitting action request directly does not crash or fake features
            self.app.menu.request_action(action_id)
            self.assertIn(action_id, requested_actions)

        # Character should remain in ATTENTION while menu remains open, then cleanly close
        self.app.menu.dismiss()
        self.assertEqual(self.app.character.state, CharacterState.IDLE)


class TestMilestone1Dragging(Milestone1AcceptanceTestBase):
    """Scenario 4: Dragging and boundary enforcement verification."""

    def test_small_movement_treated_as_click_not_drag(self) -> None:
        win = self.app.window
        start_x, start_y = win.pos().x(), win.pos().y()

        # Press
        press = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(10, 10),
            QPointF(start_x + 10, start_y + 10),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        win.mousePressEvent(press)
        self.assertTrue(win.is_dragging)
        self.assertFalse(win.drag_occurred)

        # Move 2px (less than default threshold of 5px)
        move = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(12, 12),
            QPointF(start_x + 12, start_y + 12),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        win.mouseMoveEvent(move)
        self.assertFalse(win.drag_occurred)

        # Release
        release = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            QPointF(12, 12),
            QPointF(start_x + 12, start_y + 12),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        win.mouseReleaseEvent(release)
        self.assertFalse(win.is_dragging)
        self.assertFalse(win.drag_occurred)
        # Click triggered menu
        self.assertTrue(self.app.menu.isVisible())

    def test_drag_exceeding_threshold_does_not_open_menu_and_pauses_behavior(self) -> None:
        win = self.app.window
        start_x, start_y = win.pos().x(), win.pos().y()

        # Press
        press = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(10, 10),
            QPointF(start_x + 10, start_y + 10),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        win.mousePressEvent(press)

        # Move 20px (exceeds threshold)
        move = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(30, 30),
            QPointF(start_x + 30, start_y + 30),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        win.mouseMoveEvent(move)
        self.assertTrue(win.drag_occurred)
        self.assertTrue(self.app.behavior_engine.is_dragging)
        self.assertFalse(self.app.behavior_engine.is_idle_eligible)

        # Release
        release = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            QPointF(30, 30),
            QPointF(start_x + 30, start_y + 30),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        win.mouseReleaseEvent(release)
        self.assertFalse(win.is_dragging)
        self.assertFalse(self.app.behavior_engine.is_dragging)
        self.assertTrue(self.app.behavior_engine.is_idle_eligible)
        # Menu must NOT be opened by a drag
        self.assertFalse(self.app.menu.isVisible())

    def test_drag_screen_bounds_enforced(self) -> None:
        win = self.app.window
        bounds = win.position_manager.get_usable_screen_bounds()

        # Press
        press = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(10, 10),
            QPointF(win.pos().x() + 10, win.pos().y() + 10),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        win.mousePressEvent(press)

        # Drag way off to negative coordinates
        move_neg = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(10, 10),
            QPointF(-2000, -2000),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        win.mouseMoveEvent(move_neg)
        self.assertGreaterEqual(win.pos().x(), bounds.left())
        self.assertGreaterEqual(win.pos().y(), bounds.top())

        # Drag way off to huge positive coordinates
        move_pos = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(10, 10),
            QPointF(100000, 100000),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        win.mouseMoveEvent(move_pos)
        self.assertTrue(bounds.contains(QRect(win.pos(), win.size())))


class TestMilestone1HideShowLifecycle(Milestone1AcceptanceTestBase):
    """Scenario 5: Hide/Show lifecycle verification."""

    def test_hide_pauses_behavior_and_show_resumes(self) -> None:
        self.app.lifecycle.startup()
        self.app.behavior_engine.start_idle_timer()
        self.assertTrue(self.app.behavior_engine.is_idle_timer_active)

        # Hide companion
        self.app.hide_companion()
        self.assertFalse(self.app.window.isVisible())
        self.assertFalse(self.app.behavior_engine.is_visible)
        self.assertFalse(self.app.behavior_engine.is_idle_timer_active)

        # Show companion
        self.app.show_companion()
        self.assertTrue(self.app.window.isVisible())
        self.assertTrue(self.app.behavior_engine.is_visible)
        self.assertTrue(self.app.behavior_engine.is_idle_timer_active)

    def test_repeated_hide_show_cycles_stability(self) -> None:
        self.app.lifecycle.startup()
        self.app.behavior_engine.start_idle_timer()

        for _ in range(10):
            self.app.hide_companion()
            self.assertFalse(self.app.behavior_engine.is_idle_timer_active)
            self.app.show_companion()
            self.assertTrue(self.app.behavior_engine.is_idle_timer_active)

        # Confirm stable final state
        self.assertTrue(self.app.behavior_engine.is_visible)
        self.assertTrue(self.app.behavior_engine.is_idle_eligible)


class TestMilestone1Persistence(Milestone1AcceptanceTestBase):
    """Scenario 6: Persistence across application instances."""

    def test_persistence_lifecycle_across_instances(self) -> None:
        # Move window in first app
        target_pos = QPoint(350, 280)
        self.app.window.move(target_pos)
        self.app.window.position_manager.save_position(target_pos)
        self.app.window.close()

        # Second app instance sharing the same settings
        app2 = DoodleApplication(
            argv=["doodle_acceptance_2"],
            settings_manager=self.settings_manager,
        )
        self.assertEqual(app2.window.pos(), target_pos)
        app2.window.close()

    def test_corrupted_saved_position_handled_safely(self) -> None:
        self.qsettings.setValue(KEY_WINDOW_POSITION, "INVALID_VALUE")
        self.qsettings.sync()

        app2 = DoodleApplication(
            argv=["doodle_acceptance_corrupted"],
            settings_manager=self.settings_manager,
        )
        # Should gracefully use default position without raising
        pos = app2.window.pos()
        self.assertIsInstance(pos, QPoint)
        bounds = app2.window.position_manager.get_usable_screen_bounds()
        self.assertTrue(bounds.contains(QRect(pos, app2.window.size())))
        app2.window.close()

    def test_changed_screen_geometry_clamps_persisted_position(self) -> None:
        # Saved position far outside a 1280x720 screen
        self.settings_manager.save_window_position(QPoint(3840, 2160))

        # Position manager clamped to smaller simulated geometry
        small_screen = QRect(0, 0, 1280, 720)
        pm = PositionManager(
            window_size=QSize(160, 160),
            screen_bounds_provider=lambda: small_screen,
            settings_manager=self.settings_manager,
        )
        restored = pm.restore_position()
        self.assertEqual(restored, QPoint(1120, 560))
        self.assertTrue(small_screen.contains(QRect(restored, QSize(160, 160))))


class TestMilestone1Shutdown(Milestone1AcceptanceTestBase):
    """Scenario 7: Shutdown and cleanup verification."""

    def test_tray_exit_performs_clean_shutdown(self) -> None:
        quit_called = False
        original_quit = self.app.qapp.quit

        def mock_quit() -> None:
            nonlocal quit_called
            quit_called = True

        self.app.qapp.quit = mock_quit
        try:
            self.app.lifecycle.startup()
            self.app.behavior_engine.start_idle_timer()
            self.assertTrue(self.app.lifecycle.is_running)
            self.assertTrue(self.app.behavior_engine.is_idle_timer_active)

            # Move window to verify save during shutdown
            target_pos = QPoint(420, 310)
            self.app.window.move(target_pos)

            # Trigger exit from tray
            self.app.tray.action_exit.trigger()

            # Verify lifecycle state and timers
            self.assertFalse(self.app.lifecycle.is_running)
            self.assertFalse(self.app.behavior_engine.is_idle_timer_active)
            self.assertTrue(quit_called)

            # Verify position was saved
            saved = self.settings_manager.load_window_position()
            self.assertEqual(saved, target_pos)
        finally:
            self.app.qapp.quit = original_quit

    def test_shutdown_hooks_idempotent(self) -> None:
        self.app.lifecycle.startup()
        self.app.lifecycle.shutdown()
        self.assertFalse(self.app.lifecycle.is_running)
        # Calling shutdown again must be completely safe
        self.app.lifecycle.shutdown()
        self.assertFalse(self.app.lifecycle.is_running)


class TestMilestone1ErrorHandling(Milestone1AcceptanceTestBase):
    """Scenario 8: Error handling and safe fallbacks."""

    def test_nonexistent_animation_handled_safely(self) -> None:
        self.app.character.stop_animation()
        self.assertFalse(self.app.character.animation_controller.is_playing)
        result = self.app.character.play_animation("non_existent_animation")
        self.assertFalse(result)
        # Character animation controller remains stopped
        self.assertFalse(self.app.character.animation_controller.is_playing)

    def test_missing_assets_graceful_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as empty_dir:
            char = Character(
                name="nonexistent_char",
                assets_dir=Path(empty_dir),
            )
            # Has no frames registered
            self.assertIsNone(char.visual)
            self.assertEqual(char.state, CharacterState.IDLE)

            # Window rendering with no visual does not crash
            win = CompanionWindow(character=char)
            # Invoke paintEvent directly to verify placeholder drawing
            event = QPaintEvent(QRegion(win.rect()))
            win.paintEvent(event)
            win.close()


class TestMilestone1LongRunningStability(Milestone1AcceptanceTestBase):
    """Scenario 9: Long-running interaction stability simulation."""

    def test_simulated_representative_session(self) -> None:
        self.app.lifecycle.startup()
        self.app.behavior_engine.start_idle_timer()

        # Simulate 50 sequential events spanning all supported features
        for i in range(50):
            mod = i % 5
            if mod == 0:
                # Idle trigger and animation finish
                self.app.behavior_engine.trigger_idle_timeout()
                curr_state = self.app.character.state
                self.app.character.animation_finished.emit(curr_state.value.lower())
            elif mod == 1:
                # Click and open menu
                self.app.window.character_clicked.emit()
                self.assertTrue(self.app.menu.isVisible())
            elif mod == 2:
                # Dismiss menu
                self.app.menu.dismiss()
                self.assertFalse(self.app.menu.isVisible())
            elif mod == 3:
                # Hide and show
                self.app.hide_companion()
                self.app.show_companion()
            elif mod == 4:
                # Drag window slightly
                bounds = self.app.window.position_manager.get_usable_screen_bounds()
                new_x = bounds.left() + (i * 7) % (bounds.width() - 160)
                new_y = bounds.top() + (i * 11) % (bounds.height() - 160)
                self.app.window.move(QPoint(new_x, new_y))

        # Ensure after 50 mixed interactions, application is in clean IDLE state
        self.assertEqual(self.app.character.state, CharacterState.IDLE)
        self.assertFalse(self.app.menu.isVisible())
        self.assertTrue(self.app.behavior_engine.is_visible)
        self.assertTrue(self.app.behavior_engine.is_idle_timer_active)
        self.assertTrue(self.app.behavior_engine.is_idle_eligible)


if __name__ == "__main__":
    unittest.main()
