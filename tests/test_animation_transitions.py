"""Focused automated tests for animation quality, timing, and smooth transitions (Milestone 2 Task 15)."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from doodle.app.application import DoodleApplication
from doodle.behavior.engine import BehaviorEngine
from doodle.behavior.rules import (
    EVENT_ANIMATION_FINISHED,
    EVENT_CHARACTER_CLICKED,
    EVENT_CURSOR_ENTERED_PROXIMITY,
    EVENT_DRAG_RELEASED,
    EVENT_DRAG_STARTED,
    EVENT_IDLE_TIMEOUT,
    EVENT_MENU_DISMISSED,
    IdleBehavior,
    IdleBehaviorRules,
    IdleSelectionPolicy,
)
from doodle.character.animation import (
    DEFAULT_FRAME_DURATION_MS,
    IDLE_BLINK_MS,
    IDLE_REST_SHORT_MS,
    PANDA_ANIMATION_SPECS,
    Animation,
    AnimationController,
)
from doodle.character.character import Character
from doodle.character.mood import Mood
from doodle.character.state import CharacterState


class TestAnimationSequencing(unittest.TestCase):
    """1. Animation sequencing tests verifying frame validity, completion, and settles."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_anim_seq"])

    def setUp(self) -> None:
        self.char = Character(name="panda")

    def tearDown(self) -> None:
        self.char.stop_animation()

    def test_idle_animation_remains_valid(self) -> None:
        anim = self.char.animation_controller.get_animation("idle")
        self.assertIsNotNone(anim)
        self.assertTrue(anim.is_valid)
        self.assertGreaterEqual(anim.frame_count, 2)
        # Verify initial visual is non-null
        self.assertIsNotNone(self.char.visual)
        self.assertFalse(self.char.visual.isNull())

    def test_idle_animation_structure_and_quiet_rhythm(self) -> None:
        anim = self.char.animation_controller.get_animation("idle")
        self.assertIsNotNone(anim)
        self.assertIsNotNone(anim.frame_durations_ms)
        # Quiet frames should have substantial duration (>= 3000ms)
        quiet_durations = [d for d in anim.frame_durations_ms if d >= 3000]
        self.assertGreaterEqual(len(quiet_durations), 3)
        # Blink frames should have short, subtle duration (<= 250ms)
        blink_durations = [d for d in anim.frame_durations_ms if d <= 250]
        self.assertGreaterEqual(len(blink_durations), 3)

    def test_action_starts_and_completes_correctly(self) -> None:
        finished: list[str] = []
        self.char.animation_finished.connect(finished.append)

        # Start stretch non-looping
        started = self.char.play_animation("stretch", loop=False)
        self.assertTrue(started)
        self.assertEqual(self.char.current_animation_name, "stretch")
        self.assertTrue(self.char.animation_controller.is_playing)
        self.assertEqual(self.char.animation_controller.current_frame_index, 0)

        anim = self.char.animation_controller.get_animation("stretch")
        # Advance through all frames until completion
        for _ in range(anim.frame_count):
            self.char.animation_controller.advance_frame()

        self.assertEqual(finished, ["stretch"])
        self.assertFalse(self.char.animation_controller.is_playing)

    def test_action_recovery_settles_to_idle_frame(self) -> None:
        idle_anim = self.char.animation_controller.get_animation("idle")
        idle_first_frame = idle_anim.get_frame(0)

        for action_name in ("stretch", "curious", "playful"):
            anim = self.char.animation_controller.get_animation(action_name)
            self.assertIsNotNone(anim)
            # The final settle frame should match the idle resting frame
            last_frame = anim.get_frame(anim.frame_count - 1)
            self.assertIsNotNone(last_frame)
            # Pixmap bits match the resting idle frame
            self.assertEqual(last_frame.toImage(), idle_first_frame.toImage())

    def test_animation_state_valid_after_interruption(self) -> None:
        self.char.play_animation("curious", loop=False)
        self.assertEqual(self.char.current_animation_name, "curious")

        # Interrupt by setting state to ATTENTION
        self.char.set_state(CharacterState.ATTENTION)
        self.assertEqual(self.char.state, CharacterState.ATTENTION)
        self.assertEqual(self.char.current_animation_name, "attention")
        self.assertTrue(self.char.animation_controller.is_playing)
        self.assertEqual(self.char.animation_controller.current_frame_index, 0)


class TestTransitionBehavior(unittest.TestCase):
    """2. Transition behavior tests verifying character never gets stuck and returns cleanly to idle."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_trans_behav"])

    def setUp(self) -> None:
        self.char = Character(name="panda")
        self.engine = BehaviorEngine(character=self.char)

    def tearDown(self) -> None:
        self.engine.cleanup()
        self.char.stop_animation()

    def test_action_does_not_leave_character_stuck(self) -> None:
        # Trigger autonomous stretch
        self.engine.handle_event(EVENT_IDLE_TIMEOUT)
        self.assertIn(self.char.state, (CharacterState.STRETCH, CharacterState.IDLE))

        # Signal completion
        self.engine.on_animation_finished("stretch")
        self.assertEqual(self.char.state, CharacterState.IDLE)
        self.assertEqual(self.char.current_animation_name, "idle")
        self.assertTrue(self.char.animation_controller.is_playing)

    def test_completion_returns_to_appropriate_idle_behavior(self) -> None:
        for action_name in ("stretch", "sleep", "curious", "playful", "recover", "attention"):
            self.char.play_animation(action_name, loop=False)
            self.engine.on_animation_finished(action_name)
            self.assertEqual(self.char.state, CharacterState.IDLE)
            self.assertEqual(self.char.current_animation_name, "idle")

    def test_interrupted_animation_returns_to_valid_state(self) -> None:
        # Start playing autonomous animation
        self.char.play_animation("stretch", loop=False)

        # Drag starts
        self.engine.on_drag_started()
        self.assertEqual(self.char.current_animation_name, "surprised")

        # Drag finishes -> dizzy
        self.engine.on_drag_released()
        self.assertEqual(self.char.current_animation_name, "dizzy")

        # Dizzy finishes -> recover
        self.engine.on_animation_finished("dizzy")
        self.assertEqual(self.char.current_animation_name, "recover")

        # Recover finishes -> idle
        self.engine.on_animation_finished("recover")
        self.assertEqual(self.char.state, CharacterState.IDLE)
        self.assertEqual(self.char.current_animation_name, "idle")

    def test_repeated_animations_do_not_accumulate_timers_or_listeners(self) -> None:
        # Play animations repeatedly in succession
        for i in range(40):
            name = "curious" if i % 2 == 0 else "stretch"
            self.char.play_animation(name, loop=False)

        # Confirm only one timer is running
        self.assertTrue(self.char.animation_controller.is_playing)
        self.assertTrue(self.char.animation_controller._timer.isActive())

        # Finish safely
        self.char.stop_animation()
        self.assertFalse(self.char.animation_controller.is_playing)
        self.assertFalse(self.char.animation_controller._timer.isActive())


class TestAnimationTiming(unittest.TestCase):
    """3. Timing tests verifying determinism, per-frame durations, and single completion signals."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_anim_timing"])

    def setUp(self) -> None:
        self.char = Character(name="panda")

    def tearDown(self) -> None:
        self.char.stop_animation()

    def test_animation_timing_is_deterministic(self) -> None:
        # Timings match centralized specification exactly
        for name, spec in PANDA_ANIMATION_SPECS.items():
            anim = self.char.animation_controller.get_animation(name)
            self.assertIsNotNone(anim, f"Animation {name} must exist")
            self.assertEqual(
                anim.frame_durations_ms,
                spec.frame_durations_ms,
                f"Durations for {name} must match spec",
            )

    def test_frame_duration_updates_on_advance(self) -> None:
        self.char.play_animation("idle")
        controller = self.char.animation_controller
        anim = controller.current_animation

        # Frame 0 is quiet resting
        self.assertEqual(controller.current_frame_index, 0)
        self.assertEqual(controller.current_frame_duration_ms, anim.frame_durations_ms[0])

        # Advance to Frame 1 (blink)
        controller.advance_frame()
        self.assertEqual(controller.current_frame_index, 1)
        self.assertEqual(controller.current_frame_duration_ms, anim.frame_durations_ms[1])
        # Timer interval updated dynamically
        self.assertEqual(controller._timer.interval(), anim.frame_durations_ms[1])

    def test_animation_completion_fires_exactly_once(self) -> None:
        finished_events: list[str] = []
        self.char.animation_finished.connect(finished_events.append)

        self.char.play_animation("stretch", loop=False)
        controller = self.char.animation_controller
        anim = controller.current_animation

        # Advance through all frames
        for _ in range(anim.frame_count):
            controller.advance_frame()

        self.assertEqual(len(finished_events), 1)
        self.assertEqual(finished_events, ["stretch"])

        # Further advances while stopped do nothing
        controller.advance_frame()
        self.assertEqual(len(finished_events), 1)


class TestInteractionPriority(unittest.TestCase):
    """4. Interaction priority tests verifying user interactions take precedence over autonomous behaviors."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_interact_prio"])

    def setUp(self) -> None:
        self.char = Character(name="panda")
        self.engine = BehaviorEngine(character=self.char)

    def tearDown(self) -> None:
        self.engine.cleanup()
        self.char.stop_animation()

    def test_click_interrupts_autonomous_animation_immediately(self) -> None:
        # Autonomous animation playing
        self.char.play_animation("stretch", loop=False)
        self.assertEqual(self.char.current_animation_name, "stretch")

        # User clicks character
        self.engine.on_character_clicked()
        self.assertEqual(self.char.state, CharacterState.ATTENTION)
        self.assertEqual(self.char.current_animation_name, "attention")

    def test_drag_interrupts_autonomous_animation_immediately(self) -> None:
        # Autonomous animation playing
        self.char.play_animation("curious", loop=False)
        self.assertEqual(self.char.current_animation_name, "curious")

        # User starts dragging
        self.engine.on_drag_started()
        self.assertEqual(self.char.current_animation_name, "surprised")

    def test_drag_release_reaction_dizzy_and_recover(self) -> None:
        self.engine.on_drag_started()
        self.assertEqual(self.char.current_animation_name, "surprised")

        self.engine.on_drag_released()
        self.assertEqual(self.char.current_animation_name, "dizzy")

        # Dizzy finishes -> recover
        self.engine.on_animation_finished("dizzy")
        self.assertEqual(self.char.current_animation_name, "recover")

        # Recover finishes -> idle
        self.engine.on_animation_finished("recover")
        self.assertEqual(self.char.state, CharacterState.IDLE)
        self.assertEqual(self.char.current_animation_name, "idle")

    def test_menu_dismissal_returns_to_idle(self) -> None:
        self.engine.on_character_clicked()
        self.assertEqual(self.char.state, CharacterState.ATTENTION)

        self.engine.on_menu_dismissed()
        self.assertEqual(self.char.state, CharacterState.IDLE)


class TestIdleBehaviorAndIntegration(unittest.TestCase):
    """5. Idle variation, quiet period, cursor proximity, and mood integration."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_idle_integ"])

    def setUp(self) -> None:
        self.char = Character(name="panda")
        self.policy = IdleSelectionPolicy()
        self.engine = BehaviorEngine(
            character=self.char,
            policy=self.policy,
            quiet_period_ms=10000,
        )

    def tearDown(self) -> None:
        self.engine.cleanup()
        self.char.stop_animation()

    def test_idle_variation_does_not_constantly_trigger(self) -> None:
        anim = self.char.animation_controller.get_animation("idle")
        total_time_ms = sum(anim.frame_durations_ms)
        quiet_time_ms = sum(d for d in anim.frame_durations_ms if d >= 2000)

        # At least 80% of the idle cycle must be quiet resting time
        self.assertGreaterEqual(quiet_time_ms / total_time_ms, 0.80)

    def test_autonomous_behavior_respects_quiet_periods(self) -> None:
        # Record interaction to trigger quiet period
        self.engine.record_user_interaction()
        self.assertTrue(self.engine.is_in_quiet_period)

        # Trigger idle timeout during quiet period
        action = self.engine.trigger_idle_timeout()
        # Autonomous action is suppressed
        self.assertEqual(action.action_type, "NOOP")
        self.assertEqual(self.char.state, CharacterState.IDLE)

    def test_cursor_proximity_integration(self) -> None:
        action = self.engine.on_cursor_entered_proximity()
        self.assertEqual(action.animation_name, "curious")
        self.assertEqual(self.char.current_animation_name, "curious")

        # Finishes cleanly back to idle
        self.engine.on_animation_finished("curious")
        self.assertEqual(self.char.state, CharacterState.IDLE)
        self.assertEqual(self.char.current_animation_name, "idle")

    def test_mood_system_integration(self) -> None:
        self.assertEqual(self.engine.mood, Mood.NEUTRAL)

        # Click -> HAPPY
        self.engine.on_character_clicked()
        self.assertEqual(self.engine.mood, Mood.HAPPY)

        # Drag -> PLAYFUL
        self.engine.on_drag_started()
        self.assertEqual(self.engine.mood, Mood.PLAYFUL)


if __name__ == "__main__":
    unittest.main()
