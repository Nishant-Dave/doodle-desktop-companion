"""Automated tests for Milestone 2 Task 17: Living Companion Behavior Rhythm.

Verifies:
1. Behavioral Tiers:
   - Tier 1: Micro-life (idle, blink, breathing)
   - Tier 2: Awareness (look_around, curious)
   - Tier 3: Major idle behavior (yawn, stretch, sleep/nap, playful)
   - Micro-life does not count as major autonomous behavior
2. Behavior Chaining Prevention & Quiet Period:
   - Major behavior is followed by centralized quiet period (15s)
   - Major behaviors do not chain immediately
   - Autonomous completion does not reset continuous idle progression
3. Mood Influence on Rhythm:
   - NEUTRAL uses normal candidates
   - CURIOUS favors awareness behaviors
   - PLAYFUL favors playful behavior
   - HAPPY favors light behavior
   - SLEEPY favors relaxed behavior (NAP, YAWN)
   - SLEEPY makes Doodle quieter (NOOP), not busier, when relaxed behaviors are on cooldown
4. Idle Tiers Progression:
   - Short idle (<60s) has lightweight behavior
   - Medium idle (60s-180s) allows awareness behavior
   - Long idle (>180s) allows sleepy/relaxed behavior
   - Inactivity does not increase behavior frequency
5. Interaction Suppression:
   - Click starts suppression/quiet period
   - Drag start/release starts suppression
   - Menu open/dismiss starts suppression
   - Cursor proximity reaction starts quiet period and suppresses subsequent triggers
6. Autonomous Eligibility Blocking:
   - Hidden window
   - User interacting (click, drag, menu)
   - Animation already playing
   - Quiet period active
   - Candidate on cooldown
   - Recent user interaction
   - Incompatible mood
   - Unavailable asset
   - Valid outcome is NO ACTION (quietness)
7. Determinism:
   - 100% deterministic selection without random.choice
   - Cooldowns expire deterministically
   - Previous behavior influences eligibility
8. Recovery:
   - Animation completion returns cleanly to IDLE
   - Completion does not immediately launch another animation
"""

from __future__ import annotations

import os
import unittest
from typing import Optional

# Ensure Qt runs offscreen during automated test execution
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from doodle.behavior.engine import DEFAULT_IDLE_INTERVAL_MS, BehaviorEngine
from doodle.behavior.rules import (
    ACTION_CHANGE_STATE,
    ACTION_NOOP,
    ACTION_PLAY_ANIMATION,
    DEFAULT_BEHAVIOR_COOLDOWN_S,
    DEFAULT_QUIET_PERIOD_S,
    EVENT_ANIMATION_FINISHED,
    EVENT_CHARACTER_CLICKED,
    EVENT_CURSOR_ENTERED_PROXIMITY,
    EVENT_DRAG_RELEASED,
    EVENT_DRAG_STARTED,
    EVENT_IDLE_TIMEOUT,
    EVENT_MENU_DISMISSED,
    EVENT_MENU_OPENED,
    TIER_1_MICRO_LIFE,
    TIER_2_AWARENESS,
    TIER_3_MAJOR,
    TIER_LONG_IDLE_BEHAVIORS,
    TIER_SHORT_IDLE_BEHAVIORS,
    TIER_VERY_LONG_IDLE_BEHAVIORS,
    BehaviorAction,
    BehaviorContext,
    IdleBehavior,
    IdleBehaviorRules,
    IdleSelectionPolicy,
    check_autonomous_eligibility,
    get_behavior_tier,
    is_awareness_behavior,
    is_major_behavior,
    is_micro_life,
)
from doodle.character.character import Character
from doodle.character.mood import Mood, MoodManager
from doodle.character.state import CharacterState


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


class TestBehavioralTiers(unittest.TestCase):
    """1. Conceptual behavioral tiers classification tests."""

    def test_tier_1_micro_life_classification(self) -> None:
        for name in ("blink", "breathing", "idle"):
            self.assertEqual(get_behavior_tier(name), 1)
            self.assertTrue(is_micro_life(name))
            self.assertFalse(is_awareness_behavior(name))
            self.assertFalse(is_major_behavior(name))

    def test_tier_2_awareness_classification(self) -> None:
        for behavior in (IdleBehavior.LOOK_AROUND, IdleBehavior.CURIOUS):
            self.assertEqual(get_behavior_tier(behavior), 2)
            self.assertEqual(get_behavior_tier(behavior.value.lower()), 2)
            self.assertTrue(is_awareness_behavior(behavior))
            self.assertFalse(is_micro_life(behavior))
            self.assertFalse(is_major_behavior(behavior))

    def test_tier_3_major_classification(self) -> None:
        major_behaviors = (
            IdleBehavior.YAWN,
            IdleBehavior.STRETCH,
            IdleBehavior.NAP,
            IdleBehavior.WAKE_UP,
            IdleBehavior.PLAYFUL_DANCE,
            IdleBehavior.SELF_AMUSEMENT,
        )
        for behavior in major_behaviors:
            self.assertEqual(get_behavior_tier(behavior), 3)
            self.assertEqual(get_behavior_tier(behavior.value.lower()), 3)
            self.assertTrue(is_major_behavior(behavior))
            self.assertFalse(is_micro_life(behavior))
            self.assertFalse(is_awareness_behavior(behavior))

    def test_micro_life_does_not_count_as_major_autonomous_behavior(self) -> None:
        clock = SimulatedClock(100.0)
        char = Character(name="panda")
        policy = IdleSelectionPolicy(time_provider=clock)
        engine = BehaviorEngine(
            character=char,
            policy=policy,
            quiet_period_ms=15000,
            time_provider=clock,
        )

        # Looping micro-life frames or blink completion must not trigger quiet periods
        engine.on_animation_finished("idle")
        self.assertFalse(engine.is_in_quiet_period)
        self.assertEqual(engine.last_autonomous_action_time, float("-inf"))

        engine.on_animation_finished("blink")
        self.assertFalse(engine.is_in_quiet_period)
        self.assertEqual(engine.last_autonomous_action_time, float("-inf"))

        engine.cleanup()
        char.stop_animation()


class TestBehaviorChainingAndQuietPeriod(unittest.TestCase):
    """2. Behavior chaining prevention & centralized quiet period tests."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_rhythm"])

    def setUp(self) -> None:
        self.clock = SimulatedClock(500.0)
        self.char = Character(name="panda")
        self.policy = IdleSelectionPolicy(
            cooldown_s=60.0,
            time_provider=self.clock,
        )
        self.engine = BehaviorEngine(
            character=self.char,
            policy=self.policy,
            quiet_period_ms=15000,  # 15s quiet period
            time_provider=self.clock,
        )

    def tearDown(self) -> None:
        self.engine.cleanup()
        self.char.stop_animation()

    def test_major_behavior_is_followed_by_quiet_period(self) -> None:
        # Initial state: not in quiet period
        self.assertFalse(self.engine.is_in_quiet_period)

        # Trigger autonomous behavior (STRETCH)
        action = self.engine.trigger_idle_timeout()
        self.assertEqual(action.state, CharacterState.STRETCH)

        # Animation finishes playing 3 seconds later
        self.clock.advance(3.0)
        self.engine.on_animation_finished("stretch")

        # Returns to IDLE and enters centralized quiet period
        self.assertEqual(self.char.state, CharacterState.IDLE)
        self.assertTrue(self.engine.is_in_quiet_period)
        self.assertEqual(self.engine.last_autonomous_action_time, 503.0)

    def test_major_behaviors_do_not_chain_immediately(self) -> None:
        # Perform STRETCH
        self.engine.trigger_idle_timeout()
        self.clock.advance(2.5)
        self.engine.on_animation_finished("stretch")
        self.assertEqual(self.char.state, CharacterState.IDLE)

        # Immediately trigger idle timeout (e.g. 1 second after stretch finishes)
        self.clock.advance(1.0)
        chained_action = self.engine.trigger_idle_timeout()

        # Must return NOOP to prevent behavior chaining
        self.assertEqual(chained_action.action_type, ACTION_NOOP)
        self.assertEqual(self.char.state, CharacterState.IDLE)

    def test_quiet_period_expires_and_allows_next_behavior(self) -> None:
        # Complete stretch
        self.engine.trigger_idle_timeout()
        self.clock.advance(3.0)
        self.engine.on_animation_finished("stretch")
        self.assertTrue(self.engine.is_in_quiet_period)

        # Halfway through quiet period (8s in): still blocked
        self.clock.advance(8.0)
        self.assertTrue(self.engine.is_in_quiet_period)
        act_blocked = self.engine.trigger_idle_timeout()
        self.assertEqual(act_blocked.action_type, ACTION_NOOP)

        # Past quiet period (16s after stretch finished, at t=519.0): quiet period expires
        self.clock.advance(8.0)  # total 16s since completion
        self.assertFalse(self.engine.is_in_quiet_period)

        # Next idle behavior is allowed and is not STRETCH (cooldown active)
        act_resumed = self.engine.trigger_idle_timeout()
        self.assertNotEqual(act_resumed.action_type, ACTION_NOOP)
        self.assertNotEqual(act_resumed.state, CharacterState.STRETCH)

    def test_autonomous_action_completion_preserves_idle_duration_progression(self) -> None:
        # Advance idle time to 100 seconds (medium idle)
        self.clock.advance(100.0)
        self.assertEqual(self.engine.get_current_context().idle_duration_s, 100.0)

        # Autonomous behavior plays and completes
        self.engine.trigger_idle_timeout()
        self.clock.advance(3.0)
        self.engine.on_animation_finished("stretch")

        # Idle duration must continue progressing (103.0s), NOT reset to 0!
        # Resetting to 0 would prevent Doodle from ever reaching long idle / sleepy state.
        self.assertEqual(self.engine.get_current_context().idle_duration_s, 103.0)


class TestMoodInfluenceOnRhythm(unittest.TestCase):
    """3. Deterministic mood influence on behavior candidate selection."""

    def setUp(self) -> None:
        self.clock = SimulatedClock(1000.0)
        self.policy = IdleSelectionPolicy(
            cooldown_s=60.0,
            short_idle_threshold_s=60.0,
            long_idle_threshold_s=180.0,
            time_provider=self.clock,
        )

    def test_neutral_mood_uses_normal_candidates(self) -> None:
        sel = self.policy.select(idle_time_s=10.0, mood=Mood.NEUTRAL)
        self.assertEqual(sel, IdleBehavior.STRETCH)

    def test_curious_mood_favors_awareness_behaviors(self) -> None:
        sel = self.policy.select(idle_time_s=10.0, mood=Mood.CURIOUS)
        self.assertIn(sel, (IdleBehavior.CURIOUS, IdleBehavior.LOOK_AROUND))

    def test_playful_mood_favors_playful_behavior(self) -> None:
        sel = self.policy.select(idle_time_s=10.0, mood=Mood.PLAYFUL)
        self.assertIn(sel, (IdleBehavior.PLAYFUL_DANCE, IdleBehavior.SELF_AMUSEMENT))

    def test_happy_mood_favors_light_behavior(self) -> None:
        sel = self.policy.select(idle_time_s=10.0, mood=Mood.HAPPY)
        self.assertIn(sel, (IdleBehavior.STRETCH, IdleBehavior.PLAYFUL_DANCE, IdleBehavior.CURIOUS))

    def test_sleepy_mood_favors_relaxed_behavior(self) -> None:
        sel = self.policy.select(idle_time_s=10.0, mood=Mood.SLEEPY)
        self.assertIn(sel, (IdleBehavior.NAP, IdleBehavior.YAWN))

    def test_sleepy_mood_makes_doodle_quieter_not_busier(self) -> None:
        # 1. First selection selects relaxed behavior (NAP)
        sel1 = self.policy.select(idle_time_s=200.0, current_time=1000.0, mood=Mood.SLEEPY)
        self.assertEqual(sel1, IdleBehavior.NAP)

        # 2. NAP is now most recent. If YAWN is also exhausted/unavailable, SLEEPY must return None
        # Mocking available behaviors without YAWN
        custom_avail = [IdleBehavior.NAP, IdleBehavior.STRETCH, IdleBehavior.PLAYFUL_DANCE]
        sel2 = self.policy.select(
            idle_time_s=210.0,
            current_time=1010.0,
            available_behaviors=custom_avail,
            mood=Mood.SLEEPY,
        )
        # Sleepiness must NOT fall back to STRETCH or PLAYFUL_DANCE!
        self.assertIsNone(sel2)


class TestIdleTiersProgression(unittest.TestCase):
    """4. Idle tiers and progression over time."""

    def setUp(self) -> None:
        self.clock = SimulatedClock(2000.0)
        self.policy = IdleSelectionPolicy(
            short_idle_threshold_s=60.0,
            long_idle_threshold_s=180.0,
            time_provider=self.clock,
        )

    def test_short_idle_candidates(self) -> None:
        candidates = self.policy.get_tier_candidates(idle_time_s=30.0)
        self.assertEqual(candidates, TIER_SHORT_IDLE_BEHAVIORS)

    def test_medium_idle_candidates(self) -> None:
        candidates = self.policy.get_tier_candidates(idle_time_s=100.0)
        self.assertEqual(candidates, TIER_LONG_IDLE_BEHAVIORS)

    def test_long_idle_candidates(self) -> None:
        candidates = self.policy.get_tier_candidates(idle_time_s=250.0)
        self.assertEqual(candidates, TIER_VERY_LONG_IDLE_BEHAVIORS)

    def test_idle_progression_does_not_increase_behavior_frequency(self) -> None:
        char = Character(name="panda")
        engine = BehaviorEngine(
            character=char,
            policy=self.policy,
            idle_interval_ms=30000,
            time_provider=self.clock,
        )

        # Idle interval is fixed at 30,000ms and does not shrink as idle duration increases
        self.assertEqual(engine.idle_interval_ms, 30000)
        self.clock.advance(1000.0)
        self.assertEqual(engine.idle_interval_ms, 30000)

        engine.cleanup()
        char.stop_animation()


class TestInteractionSuppression(unittest.TestCase):
    """5. User interaction suppression and quiet period tests."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_suppression"])

    def setUp(self) -> None:
        self.clock = SimulatedClock(3000.0)
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

    def test_click_starts_suppression(self) -> None:
        self.engine.on_character_clicked()
        self.assertTrue(self.engine.is_in_quiet_period)
        self.assertEqual(self.char.state, CharacterState.ATTENTION)

        # Idle timeout during suppression yields NOOP
        act = self.engine.trigger_idle_timeout()
        self.assertEqual(act.action_type, ACTION_NOOP)

    def test_drag_starts_suppression(self) -> None:
        self.engine.on_drag_started()
        self.assertTrue(self.engine.is_in_quiet_period)
        self.assertTrue(self.engine.is_dragging)

        act = self.engine.trigger_idle_timeout()
        self.assertEqual(act.action_type, ACTION_NOOP)

    def test_drag_release_starts_suppression(self) -> None:
        self.engine.on_drag_started()
        self.engine.on_drag_released()
        self.assertTrue(self.engine.is_in_quiet_period)

        # Conclude recovery
        self.engine.on_animation_finished("dizzy")
        self.engine.on_animation_finished("recover")
        self.assertEqual(self.char.state, CharacterState.IDLE)
        self.assertTrue(self.engine.is_in_quiet_period)

        # Timeout during quiet period
        act = self.engine.trigger_idle_timeout()
        self.assertEqual(act.action_type, ACTION_NOOP)

    def test_menu_interaction_starts_suppression(self) -> None:
        self.engine.on_menu_opened()
        self.assertTrue(self.engine.is_in_quiet_period)

        self.engine.on_menu_dismissed()
        self.assertTrue(self.engine.is_in_quiet_period)
        self.assertEqual(self.char.state, CharacterState.IDLE)

        act = self.engine.trigger_idle_timeout()
        self.assertEqual(act.action_type, ACTION_NOOP)

    def test_cursor_proximity_reaction_initiates_quiet_period(self) -> None:
        # Cursor enters proximity: triggers curious reaction
        action = self.engine.on_cursor_entered_proximity()
        self.assertEqual(action.action_type, ACTION_PLAY_ANIMATION)
        self.assertEqual(action.animation_name, "curious")

        # Must record user interaction and enter quiet period
        self.assertTrue(self.engine.is_in_quiet_period)

        # Repeated proximity while inside/cooldown yields NOOP
        action_repeat = self.engine.on_cursor_entered_proximity()
        self.assertEqual(action_repeat.action_type, ACTION_NOOP)

        # Idle timeout during quiet period yields NOOP
        act_idle = self.engine.trigger_idle_timeout()
        self.assertEqual(act_idle.action_type, ACTION_NOOP)


class TestAutonomousEligibilityBlocking(unittest.TestCase):
    """6. Comprehensive testing of every autonomous behavior blocking condition."""

    def setUp(self) -> None:
        self.clock = SimulatedClock(4000.0)
        self.policy = IdleSelectionPolicy(
            cooldown_s=60.0,
            time_provider=self.clock,
        )

    def test_blocking_when_hidden(self) -> None:
        ctx = BehaviorContext(is_visible=False, policy=self.policy)
        eligible, reason = check_autonomous_eligibility(ctx)
        self.assertFalse(eligible)
        self.assertEqual(reason, "hidden")

    def test_blocking_when_dragging(self) -> None:
        ctx = BehaviorContext(is_dragging=True, policy=self.policy)
        eligible, reason = check_autonomous_eligibility(ctx)
        self.assertFalse(eligible)
        self.assertEqual(reason, "dragging")

    def test_blocking_when_menu_open(self) -> None:
        ctx = BehaviorContext(is_menu_open=True, policy=self.policy)
        eligible, reason = check_autonomous_eligibility(ctx)
        self.assertFalse(eligible)
        self.assertEqual(reason, "menu_open")

    def test_blocking_when_in_attention_state(self) -> None:
        ctx = BehaviorContext(current_state=CharacterState.ATTENTION, policy=self.policy)
        eligible, reason = check_autonomous_eligibility(ctx)
        self.assertFalse(eligible)
        self.assertEqual(reason, "user_attention")

    def test_blocking_when_animation_already_playing(self) -> None:
        ctx = BehaviorContext(current_animation="curious", policy=self.policy)
        eligible, reason = check_autonomous_eligibility(ctx)
        self.assertFalse(eligible)
        self.assertEqual(reason, "animation_playing_curious")

    def test_blocking_when_quiet_period_active(self) -> None:
        ctx = BehaviorContext(is_in_quiet_period=True, policy=self.policy)
        eligible, reason = check_autonomous_eligibility(ctx)
        self.assertFalse(eligible)
        self.assertEqual(reason, "in_quiet_period")

    def test_blocking_when_recent_user_interaction(self) -> None:
        ctx = BehaviorContext(
            time_since_last_interaction_s=5.0,
            quiet_period_s=15.0,
            policy=self.policy,
        )
        eligible, reason = check_autonomous_eligibility(ctx)
        self.assertFalse(eligible)
        self.assertEqual(reason, "recent_user_interaction")

    def test_blocking_when_candidate_on_cooldown(self) -> None:
        self.policy.record_behavior(IdleBehavior.STRETCH, current_time=4000.0)
        ctx = BehaviorContext(
            current_time_s=4010.0,
            policy=self.policy,
        )
        eligible, reason = check_autonomous_eligibility(ctx, behavior=IdleBehavior.STRETCH)
        self.assertFalse(eligible)
        self.assertEqual(reason, "cooldown_STRETCH")

    def test_blocking_when_mood_incompatible(self) -> None:
        ctx = BehaviorContext(mood=Mood.SLEEPY, policy=self.policy)
        eligible, reason = check_autonomous_eligibility(ctx, behavior=IdleBehavior.PLAYFUL_DANCE)
        self.assertFalse(eligible)
        self.assertEqual(reason, "incompatible_mood_SLEEPY")

    def test_blocking_when_asset_unavailable(self) -> None:
        # Custom animations where yawn is unavailable
        ctx = BehaviorContext(
            available_behaviors=[IdleBehavior.STRETCH, IdleBehavior.CURIOUS],
            policy=self.policy,
        )
        eligible, reason = check_autonomous_eligibility(ctx, behavior=IdleBehavior.YAWN)
        self.assertFalse(eligible)
        self.assertEqual(reason, "asset_unavailable_YAWN")

    def test_eligible_when_all_conditions_satisfied(self) -> None:
        ctx = BehaviorContext(
            is_visible=True,
            is_dragging=False,
            is_menu_open=False,
            current_state=CharacterState.IDLE,
            current_animation=None,
            is_in_quiet_period=False,
            time_since_last_interaction_s=100.0,
            quiet_period_s=15.0,
            policy=self.policy,
            available_behaviors=[IdleBehavior.STRETCH],
        )
        eligible, reason = check_autonomous_eligibility(ctx, behavior=IdleBehavior.STRETCH)
        self.assertTrue(eligible)
        self.assertEqual(reason, "eligible")


class TestDeterminismAndRepeatability(unittest.TestCase):
    """7. Deterministic candidate rotation and cooldown expiration."""

    def test_selection_is_fully_deterministic(self) -> None:
        clock1 = SimulatedClock(100.0)
        clock2 = SimulatedClock(100.0)
        policy1 = IdleSelectionPolicy(time_provider=clock1)
        policy2 = IdleSelectionPolicy(time_provider=clock2)

        sel1 = policy1.select(idle_time_s=30.0, mood=Mood.NEUTRAL)
        sel2 = policy2.select(idle_time_s=30.0, mood=Mood.NEUTRAL)
        self.assertEqual(sel1, sel2)

    def test_cooldown_expires_deterministically(self) -> None:
        clock = SimulatedClock(1000.0)
        policy = IdleSelectionPolicy(cooldown_s=60.0, time_provider=clock)

        policy.record_behavior(IdleBehavior.STRETCH, 1000.0)
        self.assertTrue(policy.is_on_cooldown(IdleBehavior.STRETCH, 1030.0))
        self.assertTrue(policy.is_on_cooldown(IdleBehavior.STRETCH, 1059.9))
        self.assertFalse(policy.is_on_cooldown(IdleBehavior.STRETCH, 1060.1))


class TestRecoveryAndReturnToQuiet(unittest.TestCase):
    """8. Animation completion returns to IDLE without launching immediate animations."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_recovery"])

    def setUp(self) -> None:
        self.clock = SimulatedClock(5000.0)
        self.char = Character(name="panda")
        self.policy = IdleSelectionPolicy(time_provider=self.clock)
        self.engine = BehaviorEngine(
            character=self.char,
            policy=self.policy,
            time_provider=self.clock,
        )

    def tearDown(self) -> None:
        self.engine.cleanup()
        self.char.stop_animation()

    def test_all_expressive_animations_return_to_idle_state(self) -> None:
        anims = ("yawn", "stretch", "look_around", "curious", "playful", "recover")
        for anim in anims:
            self.char.play_animation(anim, loop=False)
            self.engine.on_animation_finished(anim)
            self.assertEqual(self.char.state, CharacterState.IDLE)
            self.assertEqual(self.char.current_animation_name, "idle")

    def test_completion_does_not_launch_another_animation(self) -> None:
        executed_actions: list[BehaviorAction] = []
        self.engine.action_executed.connect(executed_actions.append)

        # Stretch finishes
        self.engine.on_animation_finished("stretch")

        # The executed action was CHANGE_STATE to IDLE, not another PLAY_ANIMATION
        self.assertEqual(len(executed_actions), 1)
        self.assertEqual(executed_actions[0].action_type, ACTION_CHANGE_STATE)
        self.assertEqual(executed_actions[0].state, CharacterState.IDLE)


if __name__ == "__main__":
    unittest.main()
