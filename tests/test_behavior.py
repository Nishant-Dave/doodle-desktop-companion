"""Automated unit and integration tests for Doodle deterministic behavior engine and rules."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

# Ensure Qt runs offscreen during automated test execution
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QSettings
from PySide6.QtWidgets import QApplication

from doodle.app.application import DoodleApplication
from doodle.behavior.engine import DEFAULT_IDLE_INTERVAL_MS, BehaviorEngine
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
from doodle.character.character import Character
from doodle.character.state import CharacterState
from doodle.persistence.settings import SettingsManager


class TestIdleBehaviorRules(unittest.TestCase):
    """Unit tests for IdleBehaviorRules pure decision logic."""

    def setUp(self) -> None:
        self.rules = IdleBehaviorRules()

    def test_idle_timeout_produces_expected_action(self) -> None:
        context = BehaviorContext(
            current_state=CharacterState.IDLE,
            is_visible=True,
            is_menu_open=False,
            is_dragging=False,
        )
        action = self.rules.evaluate(EVENT_IDLE_TIMEOUT, context)

        self.assertEqual(action.action_type, ACTION_CHANGE_STATE)
        self.assertEqual(action.state, CharacterState.STRETCH)
        self.assertFalse(action.loop)

    def test_deterministic_sequence_is_repeatable(self) -> None:
        context = BehaviorContext(current_state=CharacterState.IDLE)

        # 1st cycle: STRETCH
        action1 = self.rules.evaluate(EVENT_IDLE_TIMEOUT, context)
        self.assertEqual(action1.state, CharacterState.STRETCH)

        # 2nd cycle: SIT
        action2 = self.rules.evaluate(EVENT_IDLE_TIMEOUT, context)
        self.assertEqual(action2.state, CharacterState.SIT)

        # 3rd cycle: SLEEP
        action3 = self.rules.evaluate(EVENT_IDLE_TIMEOUT, context)
        self.assertEqual(action3.state, CharacterState.SLEEP)

        # 4th cycle: wraps around back to STRETCH
        action4 = self.rules.evaluate(EVENT_IDLE_TIMEOUT, context)
        self.assertEqual(action4.state, CharacterState.STRETCH)

        # Reset cycle index and verify repeatability
        self.rules.reset_cycle()
        action_reset = self.rules.evaluate(EVENT_IDLE_TIMEOUT, context)
        self.assertEqual(action_reset.state, CharacterState.STRETCH)

    def test_animation_completion_returns_toward_idle(self) -> None:
        # After any temporary idle behavior finishes, return to IDLE
        for state in (CharacterState.STRETCH, CharacterState.SIT, CharacterState.SLEEP):
            context = BehaviorContext(current_state=state)
            action = self.rules.evaluate(EVENT_ANIMATION_FINISHED, context)
            self.assertEqual(action.action_type, ACTION_CHANGE_STATE)
            self.assertEqual(action.state, CharacterState.IDLE)
            self.assertTrue(action.loop)

    def test_click_takes_priority_over_idle_behavior(self) -> None:
        # Clicking while stretching, sitting, or sleeping immediately transitions to ATTENTION
        for state in (CharacterState.IDLE, CharacterState.STRETCH, CharacterState.SIT, CharacterState.SLEEP):
            context = BehaviorContext(current_state=state)
            action = self.rules.evaluate(EVENT_CHARACTER_CLICKED, context)
            self.assertEqual(action.action_type, ACTION_CHANGE_STATE)
            self.assertEqual(action.state, CharacterState.ATTENTION)
            self.assertTrue(action.loop)

    def test_menu_dismissal_returns_to_idle(self) -> None:
        context = BehaviorContext(current_state=CharacterState.ATTENTION)
        action = self.rules.evaluate(EVENT_MENU_DISMISSED, context)
        self.assertEqual(action.action_type, ACTION_CHANGE_STATE)
        self.assertEqual(action.state, CharacterState.IDLE)

    def test_conditions_prevent_idle_timeout(self) -> None:
        # Hidden
        ctx_hidden = BehaviorContext(is_visible=False, current_state=CharacterState.IDLE)
        self.assertEqual(self.rules.evaluate(EVENT_IDLE_TIMEOUT, ctx_hidden).action_type, ACTION_NOOP)

        # Dragging
        ctx_dragging = BehaviorContext(is_dragging=True, current_state=CharacterState.IDLE)
        self.assertEqual(self.rules.evaluate(EVENT_IDLE_TIMEOUT, ctx_dragging).action_type, ACTION_NOOP)

        # Menu Open
        ctx_menu = BehaviorContext(is_menu_open=True, current_state=CharacterState.IDLE)
        self.assertEqual(self.rules.evaluate(EVENT_IDLE_TIMEOUT, ctx_menu).action_type, ACTION_NOOP)

        # Already in non-idle state (e.g. ATTENTION or STRETCH)
        ctx_attention = BehaviorContext(current_state=CharacterState.ATTENTION)
        self.assertEqual(self.rules.evaluate(EVENT_IDLE_TIMEOUT, ctx_attention).action_type, ACTION_NOOP)

    def test_unknown_and_unhandled_events_are_safely_ignored(self) -> None:
        context = BehaviorContext(current_state=CharacterState.IDLE)
        action = self.rules.evaluate("UNKNOWN_RANDOM_EVENT", context)
        self.assertEqual(action.action_type, ACTION_NOOP)


class TestBehaviorEngineUnit(unittest.TestCase):
    """Unit tests for BehaviorEngine controller, signals, and character coordination."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_behavior_engine"])

    def setUp(self) -> None:
        self.character = Character(name="panda")
        self.engine = BehaviorEngine(character=self.character, idle_interval_ms=1000)

    def tearDown(self) -> None:
        self.engine.cleanup()
        self.character.stop_animation()

    def test_behavior_engine_receives_idle_event(self) -> None:
        executed_actions: list[BehaviorAction] = []
        idle_timeouts: list[bool] = []

        self.engine.action_executed.connect(executed_actions.append)
        self.engine.idle_timeout.connect(lambda: idle_timeouts.append(True))

        # Manually trigger idle timeout without waiting
        action = self.engine.trigger_idle_timeout()

        self.assertEqual(len(idle_timeouts), 1)
        self.assertEqual(len(executed_actions), 1)
        self.assertEqual(action.action_type, ACTION_CHANGE_STATE)
        self.assertEqual(action.state, CharacterState.STRETCH)
        self.assertEqual(self.character.state, CharacterState.STRETCH)

    def test_behavior_does_not_directly_manipulate_widgets(self) -> None:
        # Ensure engine contains no widget references or widget manipulation APIs
        self.assertFalse(hasattr(self.engine, "window"))
        self.assertFalse(hasattr(self.engine, "menu"))
        self.assertFalse(hasattr(self.engine, "companion_window"))

        # Verify only Character layer receives high-level commands
        self.assertIs(self.engine.character, self.character)

    def test_hidden_state_does_not_trigger_idle_behavior(self) -> None:
        self.engine.start_idle_timer()
        self.assertTrue(self.engine.is_idle_timer_active)

        # Signal hide requested
        self.engine.on_hide_requested()
        self.assertFalse(self.engine.is_visible)
        self.assertFalse(self.engine.is_idle_timer_active)

        # Triggering idle timeout while hidden produces NOOP
        action = self.engine.trigger_idle_timeout()
        self.assertEqual(action.action_type, ACTION_NOOP)
        self.assertEqual(self.character.state, CharacterState.IDLE)

    def test_show_resumes_behavior_safely(self) -> None:
        self.engine.on_hide_requested()
        self.assertFalse(self.engine.is_idle_timer_active)

        self.engine.on_show_requested()
        self.assertTrue(self.engine.is_visible)
        self.assertTrue(self.engine.is_idle_timer_active)

        action = self.engine.trigger_idle_timeout()
        self.assertEqual(action.state, CharacterState.STRETCH)
        self.assertEqual(self.character.state, CharacterState.STRETCH)

    def test_click_priority_interrupts_idle_action(self) -> None:
        # Start idle action
        self.engine.trigger_idle_timeout()
        self.assertEqual(self.character.state, CharacterState.STRETCH)

        # User clicks panda
        self.engine.on_character_clicked()
        self.assertEqual(self.character.state, CharacterState.ATTENTION)

    def test_animation_finished_returns_to_idle(self) -> None:
        self.engine.trigger_idle_timeout()
        self.assertEqual(self.character.state, CharacterState.STRETCH)

        # Signal animation completed
        self.engine.on_animation_finished("stretch")
        self.assertEqual(self.character.state, CharacterState.IDLE)

    def test_menu_opened_and_dismissed_lifecycle(self) -> None:
        self.engine.start_idle_timer()
        self.assertTrue(self.engine.is_idle_timer_active)

        self.engine.on_menu_opened()
        self.assertTrue(self.engine.is_menu_open)
        self.assertFalse(self.engine.is_idle_timer_active)

        self.engine.on_menu_dismissed()
        self.assertFalse(self.engine.is_menu_open)
        self.assertTrue(self.engine.is_idle_timer_active)

    def test_drag_movement_resets_idle_timer(self) -> None:
        self.engine.start_idle_timer()
        self.assertTrue(self.engine.is_idle_timer_active)

        self.engine.on_drag_started()
        self.assertTrue(self.engine.is_dragging)
        self.assertFalse(self.engine.is_idle_timer_active)

        self.engine.on_character_moved(QPoint(100, 100))
        self.engine.on_drag_finished()
        self.assertFalse(self.engine.is_dragging)
        self.assertTrue(self.engine.is_idle_timer_active)


class TestBehaviorIntegration(unittest.TestCase):
    """Integration tests verifying full behavior engine wiring in DoodleApplication."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_behavior_integration"])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ini_path = Path(self.temp_dir.name) / "test_behavior.ini"
        self.qsettings = QSettings(str(self.ini_path), QSettings.Format.IniFormat)
        self.settings = SettingsManager(settings=self.qsettings)
        self.app = DoodleApplication(["test_app"], settings_manager=self.settings)

    def tearDown(self) -> None:
        self.app.behavior_engine.cleanup()
        self.app.dismiss_interaction_menu()
        self.app.window.close()
        self.qsettings.clear()
        self.qsettings.sync()
        del self.qsettings
        self.temp_dir.cleanup()

    def test_application_starts_with_behavior_engine(self) -> None:
        self.assertIsNotNone(self.app.behavior_engine)
        self.assertIsInstance(self.app.behavior_engine, BehaviorEngine)
        self.assertIs(self.app.behavior_engine.character, self.app.character)

    def test_idle_behavior_triggers_and_returns_to_idle(self) -> None:
        self.assertEqual(self.app.character.state, CharacterState.IDLE)

        # Trigger idle timeout
        self.app.behavior_engine.trigger_idle_timeout()
        self.assertEqual(self.app.character.state, CharacterState.STRETCH)

        # Simulate animation completion
        self.app.character.animation_finished.emit("stretch")
        self.assertEqual(self.app.character.state, CharacterState.IDLE)

    def test_click_remains_responsive_during_idle_behavior(self) -> None:
        # Trigger idle behavior
        self.app.behavior_engine.trigger_idle_timeout()
        self.assertEqual(self.app.character.state, CharacterState.STRETCH)

        # Click panda
        self.app.window.character_clicked.emit()
        self.assertEqual(self.app.character.state, CharacterState.ATTENTION)
        self.assertTrue(self.app.menu.isVisible())

        # Dismiss menu restores IDLE
        self.app.menu.dismiss()
        self.assertEqual(self.app.character.state, CharacterState.IDLE)

    def test_tray_hide_and_show_integration(self) -> None:
        self.app.behavior_engine.start_idle_timer()
        self.assertTrue(self.app.behavior_engine.is_idle_timer_active)

        # Hide via tray
        self.app.hide_companion()
        self.assertFalse(self.app.behavior_engine.is_visible)
        self.assertFalse(self.app.behavior_engine.is_idle_timer_active)

        # Show via tray
        self.app.show_companion()
        self.assertTrue(self.app.behavior_engine.is_visible)
        self.assertTrue(self.app.behavior_engine.is_idle_timer_active)

    def test_shutdown_remains_clean(self) -> None:
        self.app.lifecycle.startup()
        self.app.behavior_engine.start_idle_timer()
        self.assertTrue(self.app.behavior_engine.is_idle_timer_active)

        self.app.lifecycle.shutdown()
        self.assertFalse(self.app.behavior_engine.is_idle_timer_active)


if __name__ == "__main__":
    unittest.main()
