"""Tests for Milestone 2 Task 11: Expressive Animations and Physical Interaction Foundation.

Validates:
1. Drag lifecycle events (DRAG_STARTED, DRAGGING, DRAG_RELEASED)
2. Expressive animation vocabulary (surprised, dizzy, recover, curious, playful)
3. Physical interaction reactions and priority over idle behavior
4. Full integration with CompanionWindow and DoodleApplication
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

# Ensure Qt runs offscreen during test execution
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QSettings, QSize, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from doodle.app.application import DoodleApplication
from doodle.behavior.engine import BehaviorEngine
from doodle.behavior.rules import (
    ACTION_CHANGE_STATE,
    ACTION_NOOP,
    ACTION_PLAY_ANIMATION,
    EVENT_ANIMATION_FINISHED,
    EVENT_CHARACTER_CLICKED,
    EVENT_DRAG_FINISHED,
    EVENT_DRAG_RELEASED,
    EVENT_DRAG_STARTED,
    EVENT_DRAGGING,
    EVENT_IDLE_TIMEOUT,
    EVENT_MENU_DISMISSED,
    BehaviorAction,
    BehaviorContext,
    IdleBehaviorRules,
)
from doodle.character.character import KNOWN_ANIMATION_NAMES, Character
from doodle.character.state import CharacterState
from doodle.desktop.companion_window import CompanionWindow
from doodle.persistence.settings import SettingsManager


class TestDragLifecycleEvents(unittest.TestCase):
    """Unit tests for drag lifecycle event definitions and window emissions."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_drag_lifecycle"])

    def setUp(self) -> None:
        self.char = Character(name="panda")
        self.win = CompanionWindow(character=self.char)

    def tearDown(self) -> None:
        self.win.close()
        self.char.stop_animation()

    def test_drag_event_constants_are_stable(self) -> None:
        self.assertEqual(EVENT_DRAG_STARTED, "DRAG_STARTED")
        self.assertEqual(EVENT_DRAGGING, "DRAGGING")
        self.assertEqual(EVENT_DRAG_RELEASED, "DRAG_RELEASED")
        self.assertEqual(EVENT_DRAG_FINISHED, "DRAG_RELEASED")

    def test_window_emits_drag_lifecycle_signals(self) -> None:
        drag_started_emitted = False
        drag_released_emitted = False
        drag_finished_emitted = False
        dragged_points: list[QPoint] = []

        self.win.drag_started.connect(lambda: nonlocal_set("started"))
        self.win.drag_released.connect(lambda: nonlocal_set("released"))
        self.win.drag_finished.connect(lambda: nonlocal_set("finished"))
        self.win.dragging.connect(dragged_points.append)

        def nonlocal_set(kind: str) -> None:
            nonlocal drag_started_emitted, drag_released_emitted, drag_finished_emitted
            if kind == "started":
                drag_started_emitted = True
            elif kind == "released":
                drag_released_emitted = True
            elif kind == "finished":
                drag_finished_emitted = True

        start_x, start_y = self.win.pos().x(), self.win.pos().y()

        # Press
        press = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(10, 10),
            QPointF(start_x + 10, start_y + 10),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.win.mousePressEvent(press)
        self.assertFalse(drag_started_emitted)

        # Move exceeding threshold (25px)
        move = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(35, 35),
            QPointF(start_x + 35, start_y + 35),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.win.mouseMoveEvent(move)
        self.assertTrue(drag_started_emitted)
        self.assertGreaterEqual(len(dragged_points), 1)

        # Release
        release = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            QPointF(35, 35),
            QPointF(start_x + 35, start_y + 35),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        self.win.mouseReleaseEvent(release)
        self.assertTrue(drag_released_emitted)
        self.assertTrue(drag_finished_emitted)

    def test_small_movement_does_not_emit_drag_lifecycle(self) -> None:
        drag_started = False
        self.win.drag_started.connect(lambda: setattr(self, "_ds", True))

        start_x, start_y = self.win.pos().x(), self.win.pos().y()
        self.win.mousePressEvent(
            QMouseEvent(
                QEvent.Type.MouseButtonPress,
                QPointF(5, 5),
                QPointF(start_x + 5, start_y + 5),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
        )
        # Move only 2px
        self.win.mouseMoveEvent(
            QMouseEvent(
                QEvent.Type.MouseMove,
                QPointF(7, 7),
                QPointF(start_x + 7, start_y + 7),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
        )
        self.win.mouseReleaseEvent(
            QMouseEvent(
                QEvent.Type.MouseButtonRelease,
                QPointF(7, 7),
                QPointF(start_x + 7, start_y + 7),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
            )
        )
        self.assertFalse(self.win.drag_occurred)


class TestExpressiveAnimations(unittest.TestCase):
    """Unit tests for the expanded expressive animation vocabulary."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_expressive_animations"])

    def setUp(self) -> None:
        self.char = Character(name="panda")

    def tearDown(self) -> None:
        self.char.stop_animation()

    def test_all_expressive_animations_registered(self) -> None:
        controller = self.char.animation_controller
        # Existing animations
        self.assertTrue(controller.has_animation("idle"))
        self.assertTrue(controller.has_animation("sit"))
        self.assertTrue(controller.has_animation("sleep"))
        self.assertTrue(controller.has_animation("stretch"))
        self.assertTrue(controller.has_animation("attention"))

        # New expressive animations
        self.assertTrue(controller.has_animation("surprised"))
        self.assertTrue(controller.has_animation("dizzy"))
        self.assertTrue(controller.has_animation("recover"))
        self.assertTrue(controller.has_animation("curious"))
        self.assertTrue(controller.has_animation("playful"))

    def test_expressive_animation_playback_and_finished_signal(self) -> None:
        finished_anims: list[str] = []
        self.char.animation_finished.connect(finished_anims.append)

        # Play dizzy non-looping
        played = self.char.play_animation("dizzy", loop=False)
        self.assertTrue(played)
        self.assertEqual(self.char.current_animation_name, "dizzy")
        self.assertTrue(self.char.animation_controller.is_playing)

        # Advance frames to complete 2-frame animation
        self.char.animation_controller.advance_frame()
        self.char.animation_controller.advance_frame()
        self.assertEqual(finished_anims, ["dizzy"])
        self.assertFalse(self.char.animation_controller.is_playing)


class TestPhysicalInteractionBehavior(unittest.TestCase):
    """Tests for physical interaction reaction rules and deterministic transitions."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_physical_behavior"])

    def setUp(self) -> None:
        self.char = Character(name="panda")
        self.engine = BehaviorEngine(character=self.char, idle_interval_ms=1000)

    def tearDown(self) -> None:
        self.engine.cleanup()
        self.char.stop_animation()

    def test_drag_started_interrupts_idle_and_plays_surprised(self) -> None:
        self.engine.start_idle_timer()
        # Put into idle state STRETCH
        self.engine.trigger_idle_timeout()
        self.assertEqual(self.char.state, CharacterState.STRETCH)

        # User begins drag
        action = self.engine.handle_event(EVENT_DRAG_STARTED)
        self.assertEqual(action.action_type, ACTION_PLAY_ANIMATION)
        self.assertEqual(action.animation_name, "surprised")
        self.assertTrue(action.loop)
        self.assertEqual(self.char.current_animation_name, "surprised")
        self.assertFalse(self.engine.is_idle_timer_active)

    def test_dragging_is_visually_stable(self) -> None:
        self.engine.on_drag_started()
        self.assertEqual(self.char.current_animation_name, "surprised")

        # Movement events produce NOOP and do not restart animation
        action = self.engine.handle_event(EVENT_DRAGGING, pos=QPoint(200, 200))
        self.assertEqual(action.action_type, ACTION_NOOP)
        self.assertEqual(self.char.current_animation_name, "surprised")

    def test_drag_released_executes_dizzy_recover_idle_chain(self) -> None:
        self.engine.on_drag_started()
        self.assertEqual(self.char.current_animation_name, "surprised")

        # 1. Release drag -> triggers dizzy
        action_release = self.engine.handle_event(EVENT_DRAG_RELEASED)
        self.assertEqual(action_release.action_type, ACTION_PLAY_ANIMATION)
        self.assertEqual(action_release.animation_name, "dizzy")
        self.assertFalse(action_release.loop)
        self.assertEqual(self.char.current_animation_name, "dizzy")

        # 2. Dizzy finishes -> triggers recover
        action_dizzy_done = self.engine.handle_event(
            EVENT_ANIMATION_FINISHED, animation_name="dizzy"
        )
        self.assertEqual(action_dizzy_done.action_type, ACTION_PLAY_ANIMATION)
        self.assertEqual(action_dizzy_done.animation_name, "recover")
        self.assertFalse(action_dizzy_done.loop)
        self.assertEqual(self.char.current_animation_name, "recover")

        # 3. Recover finishes -> returns to IDLE
        action_recover_done = self.engine.handle_event(
            EVENT_ANIMATION_FINISHED, animation_name="recover"
        )
        self.assertEqual(action_recover_done.action_type, ACTION_CHANGE_STATE)
        self.assertEqual(action_recover_done.state, CharacterState.IDLE)
        self.assertEqual(self.char.state, CharacterState.IDLE)
        self.assertEqual(self.char.current_animation_name, "idle")

    def test_user_click_has_priority_over_dizzy_reaction(self) -> None:
        # Start reaction chain
        self.engine.handle_event(EVENT_DRAG_RELEASED)
        self.assertEqual(self.char.current_animation_name, "dizzy")

        # User clicks during dizzy
        action = self.engine.handle_event(EVENT_CHARACTER_CLICKED)
        self.assertEqual(action.action_type, ACTION_CHANGE_STATE)
        self.assertEqual(action.state, CharacterState.ATTENTION)
        self.assertEqual(self.char.state, CharacterState.ATTENTION)

    def test_new_drag_interrupts_dizzy_reaction(self) -> None:
        self.engine.handle_event(EVENT_DRAG_RELEASED)
        self.assertEqual(self.char.current_animation_name, "dizzy")

        # User starts dragging again immediately
        action = self.engine.handle_event(EVENT_DRAG_STARTED)
        self.assertEqual(action.action_type, ACTION_PLAY_ANIMATION)
        self.assertEqual(action.animation_name, "surprised")
        self.assertEqual(self.char.current_animation_name, "surprised")

    def test_idle_timeout_does_not_fight_transient_reactions(self) -> None:
        self.engine.handle_event(EVENT_DRAG_RELEASED)
        self.assertEqual(self.char.current_animation_name, "dizzy")

        # Idle timeout attempted while dizzy
        action = self.engine.trigger_idle_timeout()
        self.assertEqual(action.action_type, ACTION_NOOP)
        self.assertEqual(self.char.current_animation_name, "dizzy")

    def test_repeated_drag_cycles_stability(self) -> None:
        for _ in range(10):
            # Drag
            self.engine.on_drag_started()
            self.engine.on_dragging(QPoint(150, 150))
            self.engine.on_drag_released()
            # Advance reactions to completion
            self.engine.on_animation_finished("dizzy")
            self.engine.on_animation_finished("recover")

        self.assertEqual(self.char.state, CharacterState.IDLE)
        self.assertEqual(self.char.current_animation_name, "idle")
        self.assertTrue(self.engine.is_idle_eligible)


class TestPhysicalInteractionIntegration(unittest.TestCase):
    """Integration tests verifying physical interaction within DoodleApplication."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_physical_integration"])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ini_path = Path(self.temp_dir.name) / "test_m2.ini"
        self.qsettings = QSettings(str(self.ini_path), QSettings.Format.IniFormat)
        self.settings = SettingsManager(settings=self.qsettings)
        self.app = DoodleApplication(["test_app"], settings_manager=self.settings)

    def tearDown(self) -> None:
        self.app.window.close()
        self.app.lifecycle.shutdown()
        self.qsettings.clear()
        self.qsettings.sync()
        del self.qsettings
        self.temp_dir.cleanup()

    def test_full_drag_release_reaction_cycle(self) -> None:
        win = self.app.window
        start_pos = win.pos()

        # 1. Press and drag window
        win.mousePressEvent(
            QMouseEvent(
                QEvent.Type.MouseButtonPress,
                QPointF(10, 10),
                QPointF(start_pos.x() + 10, start_pos.y() + 10),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
        )
        win.mouseMoveEvent(
            QMouseEvent(
                QEvent.Type.MouseMove,
                QPointF(35, 35),
                QPointF(start_pos.x() + 35, start_pos.y() + 35),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
        )
        # In surprised pose while moving
        self.assertEqual(self.app.character.current_animation_name, "surprised")
        self.assertFalse(self.app.menu.isVisible())

        # 2. Release drag
        win.mouseReleaseEvent(
            QMouseEvent(
                QEvent.Type.MouseButtonRelease,
                QPointF(35, 35),
                QPointF(start_pos.x() + 35, start_pos.y() + 35),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
            )
        )
        # Enters dizzy reaction
        self.assertEqual(self.app.character.current_animation_name, "dizzy")
        self.assertFalse(self.app.menu.isVisible())

        # 3. Simulate animation completions: dizzy -> recover -> idle
        self.app.character.animation_finished.emit("dizzy")
        self.assertEqual(self.app.character.current_animation_name, "recover")

        self.app.character.animation_finished.emit("recover")
        self.assertEqual(self.app.character.state, CharacterState.IDLE)
        self.assertEqual(self.app.character.current_animation_name, "idle")

    def test_click_still_opens_menu_normally(self) -> None:
        self.app.window.character_clicked.emit()
        self.assertEqual(self.app.character.state, CharacterState.ATTENTION)
        self.assertTrue(self.app.menu.isVisible())

        self.app.menu.dismiss()
        self.assertEqual(self.app.character.state, CharacterState.IDLE)
        self.assertFalse(self.app.menu.isVisible())


if __name__ == "__main__":
    unittest.main()
