"""Unit and integration tests for Milestone 2 Task 12: Rich Idle Personality.

Verifies:
1. Conceptual idle behavior vocabulary and asset availability mapping.
2. Deterministic candidate selection policy across idle tiers.
3. Cooldown behavior preventing immediate repetition.
4. Quiet period suppressing autonomous behavior after meaningful user interaction.
5. Safe behavior pause and quiet resumption around hidden/shown state.
6. User interaction priority and clean interruption of autonomous animations.
7. Return to IDLE upon animation completion without premature triggers.
8. Clean integration within DoodleApplication.
"""

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
from doodle.behavior.engine import (
    DEFAULT_IDLE_INTERVAL_MS,
    BehaviorEngine,
)
from doodle.behavior.rules import (
    ACTION_CHANGE_STATE,
    ACTION_NOOP,
    ACTION_PLAY_ANIMATION,
    DEFAULT_BEHAVIOR_COOLDOWN_S,
    DEFAULT_QUIET_PERIOD_MS,
    DEFAULT_QUIET_PERIOD_S,
    EVENT_ANIMATION_FINISHED,
    EVENT_CHARACTER_CLICKED,
    EVENT_DRAG_RELEASED,
    EVENT_DRAG_STARTED,
    EVENT_IDLE_TIMEOUT,
    EVENT_MENU_DISMISSED,
    EVENT_MENU_OPENED,
    LONG_IDLE_THRESHOLD_S,
    SHORT_IDLE_THRESHOLD_S,
    TIER_LONG_IDLE_BEHAVIORS,
    TIER_SHORT_IDLE_BEHAVIORS,
    TIER_VERY_LONG_IDLE_BEHAVIORS,
    BehaviorAction,
    BehaviorContext,
    IdleBehavior,
    IdleBehaviorRules,
    IdleSelectionPolicy,
    action_for_idle_behavior,
    get_available_behaviors,
    is_behavior_available,
)
from doodle.character.character import Character
from doodle.character.state import CharacterState
from doodle.persistence.settings import SettingsManager


class SimulatedClock:
    """Controllable clock for deterministic, non-flaky timing tests."""

    def __init__(self, initial_time: float = 1000.0) -> None:
        self._current_time: float = initial_time

    def __call__(self) -> float:
        return self._current_time

    def advance(self, seconds: float) -> None:
        self._current_time += seconds

    def set(self, time_val: float) -> None:
        self._current_time = time_val


class TestIdleBehaviorVocabularyAndAvailability(unittest.TestCase):
    """1. Vocabulary & Availability tests."""

    def test_vocabulary_contains_all_eight_conceptual_behaviors(self) -> None:
        expected = {
            "YAWN",
            "LOOK_AROUND",
            "STRETCH",
            "NAP",
            "WAKE_UP",
            "PLAYFUL_DANCE",
            "CURIOUS",
            "SELF_AMUSEMENT",
        }
        actual = {b.value for b in IdleBehavior}
        self.assertEqual(actual, expected)

    def test_available_behaviors_detected_from_project_assets(self) -> None:
        # Default project-owned animations present in assets/panda
        available = get_available_behaviors()
        self.assertIn(IdleBehavior.STRETCH, available)
        self.assertIn(IdleBehavior.NAP, available)
        self.assertIn(IdleBehavior.CURIOUS, available)
        self.assertIn(IdleBehavior.PLAYFUL_DANCE, available)

    def test_unavailable_behaviors_are_excluded(self) -> None:
        # Animations without assets in assets/panda
        self.assertFalse(is_behavior_available(IdleBehavior.YAWN))
        self.assertFalse(is_behavior_available(IdleBehavior.LOOK_AROUND))
        self.assertFalse(is_behavior_available(IdleBehavior.WAKE_UP))
        self.assertFalse(is_behavior_available(IdleBehavior.SELF_AMUSEMENT))

        available = get_available_behaviors()
        self.assertNotIn(IdleBehavior.YAWN, available)
        self.assertNotIn(IdleBehavior.LOOK_AROUND, available)
        self.assertNotIn(IdleBehavior.WAKE_UP, available)
        self.assertNotIn(IdleBehavior.SELF_AMUSEMENT, available)

    def test_dynamic_availability_when_animations_provided(self) -> None:
        custom_anims = {"look_around", "curious"}
        self.assertTrue(is_behavior_available(IdleBehavior.LOOK_AROUND, custom_anims))
        self.assertTrue(is_behavior_available(IdleBehavior.CURIOUS, custom_anims))
        self.assertFalse(is_behavior_available(IdleBehavior.STRETCH, custom_anims))
        self.assertFalse(is_behavior_available(IdleBehavior.NAP, custom_anims))

    def test_action_for_idle_behavior_mapping(self) -> None:
        # STRETCH maps to state STRETCH
        act_stretch = action_for_idle_behavior(IdleBehavior.STRETCH)
        self.assertEqual(act_stretch.action_type, ACTION_CHANGE_STATE)
        self.assertEqual(act_stretch.state, CharacterState.STRETCH)
        self.assertFalse(act_stretch.loop)

        # NAP maps to state SLEEP
        act_nap = action_for_idle_behavior(IdleBehavior.NAP)
        self.assertEqual(act_nap.action_type, ACTION_CHANGE_STATE)
        self.assertEqual(act_nap.state, CharacterState.SLEEP)
        self.assertFalse(act_nap.loop)

        # CURIOUS maps to transient animation curious
        act_curious = action_for_idle_behavior(IdleBehavior.CURIOUS)
        self.assertEqual(act_curious.action_type, ACTION_PLAY_ANIMATION)
        self.assertEqual(act_curious.animation_name, "curious")
        self.assertFalse(act_curious.loop)

        # PLAYFUL_DANCE maps to transient animation playful
        act_playful = action_for_idle_behavior(IdleBehavior.PLAYFUL_DANCE)
        self.assertEqual(act_playful.action_type, ACTION_PLAY_ANIMATION)
        self.assertEqual(act_playful.animation_name, "playful")
        self.assertFalse(act_playful.loop)


class TestIdleBehaviorSelection(unittest.TestCase):
    """2. Deterministic selection policy tests."""

    def setUp(self) -> None:
        self.clock = SimulatedClock(100.0)
        self.policy = IdleSelectionPolicy(
            cooldown_s=30.0,
            short_idle_threshold_s=60.0,
            long_idle_threshold_s=180.0,
            time_provider=self.clock,
        )

    def test_idle_behavior_selection_is_deterministic(self) -> None:
        # Repeating the same scenario produces the exact same selection
        p1 = IdleSelectionPolicy(cooldown_s=30.0, time_provider=self.clock)
        p2 = IdleSelectionPolicy(cooldown_s=30.0, time_provider=self.clock)

        res1_a = p1.select(idle_time_s=10.0)
        res2_a = p2.select(idle_time_s=10.0)
        self.assertEqual(res1_a, res2_a)
        self.assertEqual(res1_a, IdleBehavior.STRETCH)

        self.clock.advance(35.0)
        res1_b = p1.select(idle_time_s=45.0)
        res2_b = p2.select(idle_time_s=45.0)
        self.assertEqual(res1_b, res2_b)

    def test_unavailable_behaviors_are_excluded_from_selection(self) -> None:
        # In short idle: candidates are STRETCH, CURIOUS, LOOK_AROUND.
        # Since LOOK_AROUND is unavailable, it must never be selected.
        selected_set: set[IdleBehavior] = set()
        for _ in range(5):
            self.clock.advance(35.0)
            sel = self.policy.select(idle_time_s=10.0)
            if sel is not None:
                selected_set.add(sel)

        self.assertNotIn(IdleBehavior.LOOK_AROUND, selected_set)
        self.assertIn(IdleBehavior.STRETCH, selected_set)
        self.assertIn(IdleBehavior.CURIOUS, selected_set)

    def test_recently_used_behavior_is_excluded(self) -> None:
        # First selection at short idle
        first = self.policy.select(idle_time_s=10.0)
        self.assertEqual(first, IdleBehavior.STRETCH)
        self.assertEqual(self.policy.most_recent_behavior, IdleBehavior.STRETCH)

        # Immediate next attempt before cooldown: STRETCH is excluded because it was just used
        second = self.policy.select(idle_time_s=12.0)
        self.assertNotEqual(second, IdleBehavior.STRETCH)
        self.assertEqual(second, IdleBehavior.CURIOUS)

    def test_selection_changes_appropriately_after_enough_idle_time(self) -> None:
        # 1. Short idle (< 60s) selects lightweight behaviors
        sel_short = self.policy.select(idle_time_s=20.0)
        self.assertIn(sel_short, (IdleBehavior.STRETCH, IdleBehavior.CURIOUS))

        # Advance time and policy cooldown
        self.clock.advance(40.0)

        # 2. Longer idle (60s - 180s) selects relaxed/sleepy behaviors (NAP)
        sel_longer = self.policy.select(idle_time_s=90.0)
        self.assertEqual(sel_longer, IdleBehavior.NAP)

        self.clock.advance(40.0)

        # 3. Very long idle (>= 180s) selects playful/relaxed behaviors (PLAYFUL_DANCE)
        sel_vlong = self.policy.select(idle_time_s=200.0)
        self.assertEqual(sel_vlong, IdleBehavior.PLAYFUL_DANCE)


class TestIdleCooldowns(unittest.TestCase):
    """3. Cooldown tests."""

    def setUp(self) -> None:
        self.clock = SimulatedClock(500.0)
        self.policy = IdleSelectionPolicy(
            cooldown_s=60.0,
            time_provider=self.clock,
        )

    def test_recently_used_behavior_is_not_immediately_repeated(self) -> None:
        b1 = self.policy.select(idle_time_s=10.0)
        self.assertIsNotNone(b1)
        self.assertTrue(self.policy.is_on_cooldown(b1))

        # Second selection cannot be b1
        b2 = self.policy.select(idle_time_s=15.0)
        self.assertNotEqual(b1, b2)

    def test_cooldown_eventually_expires(self) -> None:
        b1 = self.policy.select(idle_time_s=10.0)
        self.assertTrue(self.policy.is_on_cooldown(b1))

        # Advance clock by 30s (< 60s cooldown)
        self.clock.advance(30.0)
        self.assertTrue(self.policy.is_on_cooldown(b1))

        # Advance clock past 60s
        self.clock.advance(35.0)  # total 65s
        self.assertFalse(self.policy.is_on_cooldown(b1))

    def test_cooldown_logic_is_deterministic(self) -> None:
        # Perform b1, then b2
        b1 = self.policy.select(idle_time_s=10.0)
        b2 = self.policy.select(idle_time_s=15.0)

        # While both are on cooldown and no other behaviors are available in short tier
        # (candidates: STRETCH, CURIOUS, LOOK_AROUND where LOOK_AROUND is unavailable)
        b3 = self.policy.select(idle_time_s=20.0)
        self.assertIsNone(b3)  # All eligible behaviors on cooldown -> stay quiet

        # Advance past b1's cooldown
        self.clock.advance(62.0)
        self.assertFalse(self.policy.is_on_cooldown(b1))
        # Now b1 is eligible again
        b4 = self.policy.select(idle_time_s=25.0)
        self.assertEqual(b4, b1)


class TestQuietPeriod(unittest.TestCase):
    """4. Quiet period tests."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_quiet_period"])

    def setUp(self) -> None:
        self.clock = SimulatedClock(1000.0)
        self.char = Character(name="panda")
        self.policy = IdleSelectionPolicy(time_provider=self.clock)
        self.engine = BehaviorEngine(
            character=self.char,
            policy=self.policy,
            quiet_period_ms=15000,
            idle_interval_ms=1000,
            time_provider=self.clock,
        )

    def tearDown(self) -> None:
        self.engine.cleanup()
        self.char.stop_animation()

    def test_user_interaction_starts_quiet_period(self) -> None:
        self.assertFalse(self.engine.is_in_quiet_period)

        # User clicks character
        self.engine.on_character_clicked()
        self.assertTrue(self.engine.is_in_quiet_period)
        self.assertEqual(self.engine.quiet_period_s, 15.0)

    def test_autonomous_behavior_does_not_trigger_during_quiet_period(self) -> None:
        # User interacts
        self.engine.on_character_clicked()
        self.char.set_state(CharacterState.IDLE)
        self.assertTrue(self.engine.is_in_quiet_period)

        # Trigger idle timeout during quiet period (5s in)
        self.clock.advance(5.0)
        action = self.engine.trigger_idle_timeout()

        self.assertEqual(action.action_type, ACTION_NOOP)
        self.assertEqual(self.char.state, CharacterState.IDLE)

    def test_behavior_resumes_after_quiet_period(self) -> None:
        self.engine.on_character_clicked()
        self.char.set_state(CharacterState.IDLE)

        # Advance past 15s quiet period
        self.clock.advance(16.0)
        self.assertFalse(self.engine.is_in_quiet_period)

        action = self.engine.trigger_idle_timeout()
        self.assertNotEqual(action.action_type, ACTION_NOOP)
        self.assertEqual(action.state, CharacterState.STRETCH)
        self.assertEqual(self.char.state, CharacterState.STRETCH)

    def test_all_user_interactions_initiate_quiet_period(self) -> None:
        interactions = [
            lambda: self.engine.on_character_clicked(),
            lambda: self.engine.on_drag_started(),
            lambda: self.engine.on_dragging(QPoint(10, 10)),
            lambda: self.engine.on_drag_released(),
            lambda: self.engine.on_menu_opened(),
            lambda: self.engine.on_menu_dismissed(),
            lambda: self.engine.on_character_moved(QPoint(50, 50)),
            lambda: self.engine.on_show_requested(),
        ]
        for trigger in interactions:
            self.clock.advance(20.0)  # Let any previous quiet period expire
            self.assertFalse(self.engine.is_in_quiet_period)
            trigger()
            self.assertTrue(self.engine.is_in_quiet_period)


class TestHiddenState(unittest.TestCase):
    """5. Hidden state behavior tests."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_hidden_state"])

    def setUp(self) -> None:
        self.clock = SimulatedClock(2000.0)
        self.char = Character(name="panda")
        self.policy = IdleSelectionPolicy(time_provider=self.clock)
        self.engine = BehaviorEngine(
            character=self.char,
            policy=self.policy,
            quiet_period_ms=15000,
            time_provider=self.clock,
        )

    def tearDown(self) -> None:
        self.engine.cleanup()
        self.char.stop_animation()

    def test_hidden_doodle_does_not_select_idle_behavior(self) -> None:
        self.engine.on_hide_requested()
        self.assertFalse(self.engine.is_visible)
        self.assertFalse(self.engine.is_idle_timer_active)

        action = self.engine.trigger_idle_timeout()
        self.assertEqual(action.action_type, ACTION_NOOP)
        self.assertEqual(self.char.state, CharacterState.IDLE)

    def test_showing_doodle_does_not_immediately_trigger_behavior(self) -> None:
        self.engine.on_hide_requested()
        self.clock.advance(60.0)

        # Show from tray
        self.engine.on_show_requested()
        self.assertTrue(self.engine.is_visible)
        self.assertTrue(self.engine.is_in_quiet_period)

        # Idle timeout right after show produces NOOP due to quiet period
        action = self.engine.trigger_idle_timeout()
        self.assertEqual(action.action_type, ACTION_NOOP)

    def test_idle_behavior_resumes_safely_after_quiet_period_post_show(self) -> None:
        self.engine.on_hide_requested()
        self.engine.on_show_requested()

        # Advance past quiet period
        self.clock.advance(16.0)
        self.assertFalse(self.engine.is_in_quiet_period)

        action = self.engine.trigger_idle_timeout()
        self.assertNotEqual(action.action_type, ACTION_NOOP)
        self.assertEqual(action.state, CharacterState.STRETCH)


class TestInteractionPriority(unittest.TestCase):
    """6. Interaction priority and interruption tests."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_priority"])

    def setUp(self) -> None:
        self.clock = SimulatedClock(3000.0)
        self.char = Character(name="panda")
        self.policy = IdleSelectionPolicy(time_provider=self.clock)
        self.engine = BehaviorEngine(
            character=self.char,
            policy=self.policy,
            quiet_period_ms=10000,
            time_provider=self.clock,
        )

    def tearDown(self) -> None:
        self.engine.cleanup()
        self.char.stop_animation()

    def test_drag_interrupts_autonomous_behavior(self) -> None:
        # Start autonomous idle behavior (STRETCH)
        self.engine.trigger_idle_timeout()
        self.assertEqual(self.char.state, CharacterState.STRETCH)

        # User begins dragging window
        action = self.engine.handle_event(EVENT_DRAG_STARTED)
        self.assertEqual(action.action_type, ACTION_PLAY_ANIMATION)
        self.assertEqual(action.animation_name, "surprised")
        self.assertEqual(self.char.current_animation_name, "surprised")

        # Conclude drag: dizzy -> recover -> IDLE
        self.engine.handle_event(EVENT_DRAG_RELEASED)
        self.assertEqual(self.char.current_animation_name, "dizzy")
        self.engine.handle_event(EVENT_ANIMATION_FINISHED, animation_name="dizzy")
        self.assertEqual(self.char.current_animation_name, "recover")
        self.engine.handle_event(EVENT_ANIMATION_FINISHED, animation_name="recover")

        self.assertEqual(self.char.state, CharacterState.IDLE)
        self.assertEqual(self.char.current_animation_name, "idle")

    def test_click_interrupts_autonomous_behavior(self) -> None:
        # Start autonomous idle behavior
        self.engine.trigger_idle_timeout()
        self.assertEqual(self.char.state, CharacterState.STRETCH)

        # User clicks
        action = self.engine.handle_event(EVENT_CHARACTER_CLICKED)
        self.assertEqual(action.action_type, ACTION_CHANGE_STATE)
        self.assertEqual(action.state, CharacterState.ATTENTION)
        self.assertEqual(self.char.state, CharacterState.ATTENTION)

        # Dismiss menu returns to IDLE
        self.engine.handle_event(EVENT_MENU_DISMISSED)
        self.assertEqual(self.char.state, CharacterState.IDLE)

    def test_doodle_never_left_stuck_in_non_idle_behavior(self) -> None:
        # Interrupt during CURIOUS animation
        self.char.play_animation("curious", loop=False)
        self.assertEqual(self.char.current_animation_name, "curious")

        self.engine.on_drag_started()
        self.assertEqual(self.char.current_animation_name, "surprised")

        self.engine.on_drag_released()
        self.engine.on_animation_finished("dizzy")
        self.engine.on_animation_finished("recover")

        self.assertEqual(self.char.state, CharacterState.IDLE)
        self.assertEqual(self.char.current_animation_name, "idle")


class TestAnimationCompletion(unittest.TestCase):
    """7. Animation completion and safe recovery tests."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_anim_completion"])

    def setUp(self) -> None:
        self.clock = SimulatedClock(4000.0)
        self.char = Character(name="panda")
        self.policy = IdleSelectionPolicy(time_provider=self.clock)
        self.engine = BehaviorEngine(
            character=self.char,
            policy=self.policy,
            quiet_period_ms=10000,
            idle_interval_ms=30000,
            time_provider=self.clock,
        )

    def tearDown(self) -> None:
        self.engine.cleanup()
        self.char.stop_animation()

    def test_all_idle_animations_return_to_idle_on_completion(self) -> None:
        idle_anims = ["stretch", "sleep", "curious", "playful"]
        for anim in idle_anims:
            # Put character into the action
            self.char.play_animation(anim, loop=False)
            self.engine.on_animation_finished(anim)
            self.assertEqual(self.char.state, CharacterState.IDLE)
            self.assertEqual(self.char.current_animation_name, "idle")

    def test_next_autonomous_behavior_not_triggered_prematurely(self) -> None:
        # Trigger STRETCH
        self.engine.trigger_idle_timeout()
        self.assertEqual(self.char.state, CharacterState.STRETCH)

        # Animation finishes
        self.engine.on_animation_finished("stretch")
        self.assertEqual(self.char.state, CharacterState.IDLE)

        # Idle timer was reset to 30,000ms, not firing prematurely
        self.assertTrue(self.engine.is_idle_timer_active)
        self.assertEqual(self.engine.idle_interval_ms, 30000)


class TestRichIdlePersonalityIntegration(unittest.TestCase):
    """8. Full DoodleApplication integration with rich idle personality."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_rich_app"])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ini_path = Path(self.temp_dir.name) / "test_rich.ini"
        self.qsettings = QSettings(str(self.ini_path), QSettings.Format.IniFormat)
        self.settings = SettingsManager(settings=self.qsettings)
        self.clock = SimulatedClock(5000.0)
        self.policy = IdleSelectionPolicy(
            cooldown_s=30.0,
            short_idle_threshold_s=60.0,
            long_idle_threshold_s=180.0,
            time_provider=self.clock,
        )
        self.app = DoodleApplication(
            ["test_rich_app"],
            settings_manager=self.settings,
            selection_policy=self.policy,
            use_rich_idle=True,
        )
        self.app.behavior_engine.time_provider = self.clock

    def tearDown(self) -> None:
        self.app.behavior_engine.cleanup()
        self.app.dismiss_interaction_menu()
        self.app.window.close()
        self.app.lifecycle.shutdown()
        self.qsettings.clear()
        self.qsettings.sync()
        del self.qsettings
        self.temp_dir.cleanup()

    def test_application_initializes_with_rich_idle_policy(self) -> None:
        self.assertIsNotNone(self.app.behavior_engine.policy)
        self.assertIs(self.app.behavior_engine.policy, self.policy)

    def test_idle_selection_varies_over_time_without_immediate_repetition(self) -> None:
        # First autonomous action (short idle)
        act1 = self.app.behavior_engine.trigger_idle_timeout()
        self.assertEqual(act1.state, CharacterState.STRETCH)
        self.app.character.animation_finished.emit("stretch")
        self.assertEqual(self.app.character.state, CharacterState.IDLE)

        # Advance clock by 35s (> cooldown, still short idle tier)
        self.clock.advance(35.0)
        act2 = self.app.behavior_engine.trigger_idle_timeout()
        # STRETCH was most recent, so next in tier is CURIOUS
        self.assertEqual(act2.action_type, ACTION_PLAY_ANIMATION)
        self.assertEqual(act2.animation_name, "curious")
        self.app.character.animation_finished.emit("curious")
        self.assertEqual(self.app.character.state, CharacterState.IDLE)

        # Advance clock to longer idle tier (100s idle)
        self.clock.advance(35.0)
        act3 = self.app.behavior_engine.trigger_idle_timeout()
        self.assertEqual(act3.state, CharacterState.SLEEP)
        self.app.character.animation_finished.emit("sleep")
        self.assertEqual(self.app.character.state, CharacterState.IDLE)

    def test_interaction_triggers_quiet_period_and_preserves_responsiveness(self) -> None:
        # Click opens menu and triggers ATTENTION
        self.app.window.character_clicked.emit()
        self.assertEqual(self.app.character.state, CharacterState.ATTENTION)
        self.assertTrue(self.app.menu.isVisible())

        # Dismiss menu
        self.app.menu.dismiss()
        self.assertEqual(self.app.character.state, CharacterState.IDLE)

        # During quiet period, idle trigger produces NOOP
        act = self.app.behavior_engine.trigger_idle_timeout()
        self.assertEqual(act.action_type, ACTION_NOOP)

        # Once quiet period expires, behavior triggers
        self.clock.advance(20.0)
        act_resumed = self.app.behavior_engine.trigger_idle_timeout()
        self.assertNotEqual(act_resumed.action_type, ACTION_NOOP)


if __name__ == "__main__":
    unittest.main()
