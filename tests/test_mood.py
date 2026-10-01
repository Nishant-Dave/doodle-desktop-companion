"""Automated tests for Milestone 2 Task 14: Basic Mood Foundation.

Verifies:
1. Mood Model:
   - Initial mood is NEUTRAL
   - Valid mood transitions work
   - Invalid transitions are prevented (validation)
   - Mood representation is deterministic
   - Mood is NOT CharacterState
2. Event -> Mood:
   - Cursor proximity produces CURIOUS
   - Drag interaction produces PLAYFUL
   - Click interaction produces HAPPY
   - Extended idle produces SLEEPY
   - Recent interaction prevents immediate SLEEPY
3. Mood Decay:
   - Temporary moods (HAPPY, PLAYFUL, CURIOUS) eventually return to NEUTRAL
   - Decay is deterministic
   - Mood does not oscillate unexpectedly
   - Mood does not remain permanently stuck
4. Mood -> Behavior Influence:
   - NEUTRAL uses normal idle candidates
   - CURIOUS prefers curious-compatible behavior
   - PLAYFUL prefers playful behavior
   - HAPPY prefers light/playful behavior
   - SLEEPY prefers relaxed behavior
   - Fallback when preferred behavior is on cooldown or unavailable
5. Interaction Priority:
   - Mood does not interrupt dragging
   - Mood does not override click / ATTENTION reaction
   - Mood does not interfere with interaction menu
   - Existing Task 11, 12, 13 behaviors remain authoritative
6. Application Integration:
   - Application starts with initial mood NEUTRAL
   - Application and Character mood sync
   - Full event-driven mood flow works cleanly
   - Clean shutdown without persistence of mood
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
from doodle.behavior.engine import BehaviorEngine
from doodle.behavior.rules import (
    ACTION_CHANGE_STATE,
    ACTION_NOOP,
    ACTION_PLAY_ANIMATION,
    EVENT_CHARACTER_CLICKED,
    EVENT_CURSOR_ENTERED_PROXIMITY,
    EVENT_DRAG_RELEASED,
    EVENT_DRAG_STARTED,
    EVENT_IDLE_TIMEOUT,
    EVENT_MENU_DISMISSED,
    EVENT_MENU_OPENED,
    BehaviorAction,
    BehaviorContext,
    IdleBehavior,
    IdleBehaviorRules,
    IdleSelectionPolicy,
    MOOD_PREFERRED_BEHAVIORS,
)
from doodle.character.character import Character
from doodle.character.mood import (
    DEFAULT_MOOD_DECAY_S,
    DEFAULT_SLEEPY_THRESHOLD_S,
    Mood,
    MoodManager,
)
from doodle.character.state import CharacterState
from doodle.persistence.settings import SettingsManager


class TestMoodModel(unittest.TestCase):
    """Unit tests for the Mood enum and MoodManager model."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_mood"])

    def test_initial_mood_is_neutral(self) -> None:
        manager = MoodManager()
        self.assertEqual(manager.current_mood, Mood.NEUTRAL)
        self.assertEqual(manager.raw_mood, Mood.NEUTRAL)

    def test_valid_mood_transitions(self) -> None:
        manager = MoodManager()
        self.assertEqual(manager.set_mood(Mood.HAPPY), Mood.HAPPY)
        self.assertEqual(manager.set_mood(Mood.PLAYFUL), Mood.PLAYFUL)
        self.assertEqual(manager.set_mood(Mood.CURIOUS), Mood.CURIOUS)
        self.assertEqual(manager.set_mood(Mood.SLEEPY), Mood.SLEEPY)
        self.assertEqual(manager.set_mood(Mood.NEUTRAL), Mood.NEUTRAL)

    def test_string_conversion_and_validation(self) -> None:
        manager = MoodManager()
        self.assertEqual(manager.set_mood("happy"), Mood.HAPPY)
        self.assertEqual(manager.set_mood("PLAYFUL"), Mood.PLAYFUL)

        # Invalid mood values must raise ValueError
        with self.assertRaises(ValueError):
            manager.set_mood("ANGRY")

        with self.assertRaises(ValueError):
            manager.set_mood("EXCITED")

        # Invalid types must raise TypeError
        with self.assertRaises(TypeError):
            manager.set_mood(12345)  # type: ignore

    def test_mood_representation_is_deterministic(self) -> None:
        self.assertEqual(str(Mood.NEUTRAL), "NEUTRAL")
        self.assertEqual(str(Mood.HAPPY), "HAPPY")
        self.assertEqual(str(Mood.SLEEPY), "SLEEPY")
        self.assertEqual(str(Mood.CURIOUS), "CURIOUS")
        self.assertEqual(str(Mood.PLAYFUL), "PLAYFUL")
        self.assertEqual(len(list(Mood)), 5)

    def test_mood_is_not_character_state(self) -> None:
        # Mood must be distinct from CharacterState
        char = Character()
        self.assertEqual(char.state, CharacterState.IDLE)
        self.assertEqual(char.mood, Mood.NEUTRAL)

        # Updating mood must not alter character state
        char.set_mood(Mood.SLEEPY)
        self.assertEqual(char.mood, Mood.SLEEPY)
        self.assertEqual(char.state, CharacterState.IDLE)


class TestEventToMood(unittest.TestCase):
    """Unit tests verifying event-driven deterministic mood transitions."""

    def setUp(self) -> None:
        self.current_time = 1000.0
        self.manager = MoodManager(
            decay_s=60.0,
            sleepy_threshold_s=180.0,
            time_provider=lambda: self.current_time,
        )

    def test_cursor_proximity_produces_curious(self) -> None:
        mood = self.manager.update_for_event(
            EVENT_CURSOR_ENTERED_PROXIMITY,
            current_time=self.current_time,
        )
        self.assertEqual(mood, Mood.CURIOUS)
        self.assertEqual(self.manager.current_mood, Mood.CURIOUS)

    def test_drag_started_produces_playful(self) -> None:
        mood = self.manager.update_for_event(
            EVENT_DRAG_STARTED,
            current_time=self.current_time,
        )
        self.assertEqual(mood, Mood.PLAYFUL)
        self.assertEqual(self.manager.current_mood, Mood.PLAYFUL)

    def test_drag_released_produces_playful(self) -> None:
        mood = self.manager.update_for_event(
            EVENT_DRAG_RELEASED,
            current_time=self.current_time,
        )
        self.assertEqual(mood, Mood.PLAYFUL)

    def test_click_interaction_produces_happy(self) -> None:
        mood = self.manager.update_for_event(
            EVENT_CHARACTER_CLICKED,
            current_time=self.current_time,
        )
        self.assertEqual(mood, Mood.HAPPY)
        self.assertEqual(self.manager.current_mood, Mood.HAPPY)

    def test_extended_idle_produces_sleepy(self) -> None:
        # Extended idle past sleepy threshold (180s)
        mood = self.manager.update_for_event(
            EVENT_IDLE_TIMEOUT,
            current_time=self.current_time,
            idle_duration_s=185.0,
        )
        self.assertEqual(mood, Mood.SLEEPY)
        self.assertEqual(self.manager.current_mood, Mood.SLEEPY)

    def test_short_idle_does_not_produce_sleepy(self) -> None:
        mood = self.manager.update_for_event(
            EVENT_IDLE_TIMEOUT,
            current_time=self.current_time,
            idle_duration_s=45.0,
        )
        self.assertEqual(mood, Mood.NEUTRAL)

    def test_recent_interaction_prevents_immediate_sleepy(self) -> None:
        # User plays with Doodle at t=1000.0
        self.manager.update_for_event(EVENT_DRAG_STARTED, current_time=1000.0)
        self.assertEqual(self.manager.current_mood, Mood.PLAYFUL)

        # 10s later, an idle timeout occurs with theoretical idle time
        # but because mood is PLAYFUL and decay (60s) has not elapsed, it remains PLAYFUL
        mood = self.manager.get_mood(current_time=1010.0, idle_duration_s=200.0)
        self.assertEqual(mood, Mood.PLAYFUL)


class TestMoodDecay(unittest.TestCase):
    """Unit tests for deterministic return of temporary moods toward NEUTRAL."""

    def setUp(self) -> None:
        self.sim_time = 500.0
        self.manager = MoodManager(
            decay_s=60.0,
            sleepy_threshold_s=180.0,
            time_provider=lambda: self.sim_time,
        )

    def test_happy_decays_to_neutral_after_inactivity(self) -> None:
        self.manager.set_mood(Mood.HAPPY, current_time=self.sim_time)
        self.assertEqual(self.manager.get_mood(current_time=self.sim_time + 30.0), Mood.HAPPY)

        # After 60s inactivity -> decays to NEUTRAL
        self.assertEqual(self.manager.get_mood(current_time=self.sim_time + 61.0), Mood.NEUTRAL)

    def test_playful_decays_to_neutral_after_inactivity(self) -> None:
        self.manager.set_mood(Mood.PLAYFUL, current_time=self.sim_time)
        self.assertEqual(self.manager.get_mood(current_time=self.sim_time + 61.0), Mood.NEUTRAL)

    def test_curious_decays_to_neutral_after_inactivity(self) -> None:
        self.manager.set_mood(Mood.CURIOUS, current_time=self.sim_time)
        self.assertEqual(self.manager.get_mood(current_time=self.sim_time + 61.0), Mood.NEUTRAL)

    def test_decay_is_deterministic(self) -> None:
        self.manager.set_mood(Mood.HAPPY, current_time=100.0)
        self.assertEqual(self.manager.get_mood(current_time=150.0), Mood.HAPPY)
        self.assertEqual(self.manager.get_mood(current_time=160.0), Mood.NEUTRAL)
        self.assertEqual(self.manager.get_mood(current_time=160.0), Mood.NEUTRAL)

    def test_mood_does_not_oscillate_unexpectedly(self) -> None:
        self.manager.set_mood(Mood.PLAYFUL, current_time=100.0)
        self.manager.get_mood(current_time=170.0)  # Decayed to NEUTRAL

        # Continued inactivity remains NEUTRAL
        for offset in (180.0, 190.0, 200.0):
            self.assertEqual(self.manager.get_mood(current_time=offset, idle_duration_s=10.0), Mood.NEUTRAL)

    def test_sleepy_mood_exits_on_user_interaction(self) -> None:
        # Transition to SLEEPY via long idle
        self.manager.set_mood(Mood.SLEEPY, current_time=100.0)
        self.assertEqual(self.manager.raw_mood, Mood.SLEEPY)

        # User clicks Doodle: immediately leaves SLEEPY -> HAPPY
        mood = self.manager.update_for_event(EVENT_CHARACTER_CLICKED, current_time=105.0)
        self.assertEqual(mood, Mood.HAPPY)

    def test_reset_clears_mood_to_neutral(self) -> None:
        self.manager.set_mood(Mood.PLAYFUL)
        self.assertEqual(self.manager.raw_mood, Mood.PLAYFUL)

        self.manager.reset()
        self.assertEqual(self.manager.raw_mood, Mood.NEUTRAL)


class TestMoodBehaviorInfluence(unittest.TestCase):
    """Unit tests verifying mood influence on IdleSelectionPolicy behavior candidate selection."""

    def setUp(self) -> None:
        self.current_time = 200.0
        self.policy = IdleSelectionPolicy(
            cooldown_s=30.0,
            short_idle_threshold_s=60.0,
            long_idle_threshold_s=180.0,
            time_provider=lambda: self.current_time,
        )

    def test_neutral_mood_uses_normal_tier_candidates(self) -> None:
        # In short idle tier, candidates are TIER_SHORT_IDLE_BEHAVIORS (STRETCH, CURIOUS, LOOK_AROUND)
        selected = self.policy.select(idle_time_s=10.0, mood=Mood.NEUTRAL)
        self.assertEqual(selected, IdleBehavior.STRETCH)

    def test_curious_mood_prefers_curious_behavior(self) -> None:
        selected = self.policy.select(idle_time_s=10.0, mood=Mood.CURIOUS)
        self.assertEqual(selected, IdleBehavior.CURIOUS)

    def test_playful_mood_prefers_playful_behavior(self) -> None:
        selected = self.policy.select(idle_time_s=10.0, mood=Mood.PLAYFUL)
        self.assertEqual(selected, IdleBehavior.PLAYFUL_DANCE)

    def test_happy_mood_prefers_light_and_playful_behavior(self) -> None:
        # Happy prefers STRETCH, PLAYFUL_DANCE, CURIOUS
        selected = self.policy.select(idle_time_s=10.0, mood=Mood.HAPPY)
        self.assertIn(selected, (IdleBehavior.STRETCH, IdleBehavior.PLAYFUL_DANCE, IdleBehavior.CURIOUS))

    def test_sleepy_mood_prefers_relaxed_behavior(self) -> None:
        # Sleepy prefers NAP, YAWN, STRETCH
        selected = self.policy.select(idle_time_s=10.0, mood=Mood.SLEEPY)
        self.assertEqual(selected, IdleBehavior.NAP)

    def test_fallback_when_preferred_behavior_on_cooldown(self) -> None:
        # 1. Curious selects CURIOUS
        selected1 = self.policy.select(idle_time_s=10.0, current_time=200.0, mood=Mood.CURIOUS)
        self.assertEqual(selected1, IdleBehavior.CURIOUS)

        # 2. While CURIOUS is on cooldown (cooldown=30s), another selection occurs at t=210.0
        # Preferred candidates (CURIOUS, LOOK_AROUND) have no eligible behavior (LOOK_AROUND unavailable, CURIOUS on cooldown)
        # Policy must fall back gracefully to normal tier candidates without error
        selected2 = self.policy.select(idle_time_s=10.0, current_time=210.0, mood=Mood.CURIOUS)
        self.assertIsNotNone(selected2)
        self.assertNotEqual(selected2, IdleBehavior.CURIOUS)
        self.assertEqual(selected2, IdleBehavior.STRETCH)

    def test_mood_behavior_selection_is_deterministic(self) -> None:
        # Identical parameters produce identical selection
        policy1 = IdleSelectionPolicy(time_provider=lambda: 100.0)
        policy2 = IdleSelectionPolicy(time_provider=lambda: 100.0)

        sel1 = policy1.select(idle_time_s=10.0, current_time=100.0, mood=Mood.PLAYFUL)
        sel2 = policy2.select(idle_time_s=10.0, current_time=100.0, mood=Mood.PLAYFUL)
        self.assertEqual(sel1, sel2)


class TestMoodInteractionPriority(unittest.TestCase):
    """Unit tests verifying that mood never causes autonomous behavior to fight user interactions."""

    def setUp(self) -> None:
        self.rules = IdleBehaviorRules(policy=IdleSelectionPolicy())

    def test_mood_does_not_interrupt_dragging(self) -> None:
        ctx = BehaviorContext(
            current_state=CharacterState.IDLE,
            is_visible=True,
            is_dragging=True,
            mood=Mood.PLAYFUL,
        )
        action = self.rules.evaluate(EVENT_IDLE_TIMEOUT, ctx)
        self.assertEqual(action.action_type, ACTION_NOOP)

    def test_mood_does_not_interrupt_click_or_attention(self) -> None:
        ctx = BehaviorContext(
            current_state=CharacterState.ATTENTION,
            is_visible=True,
            mood=Mood.HAPPY,
        )
        action = self.rules.evaluate(EVENT_IDLE_TIMEOUT, ctx)
        self.assertEqual(action.action_type, ACTION_NOOP)

    def test_mood_does_not_interrupt_menu(self) -> None:
        ctx = BehaviorContext(
            current_state=CharacterState.IDLE,
            is_visible=True,
            is_menu_open=True,
            mood=Mood.CURIOUS,
        )
        action = self.rules.evaluate(EVENT_IDLE_TIMEOUT, ctx)
        self.assertEqual(action.action_type, ACTION_NOOP)

    def test_mood_does_not_interrupt_quiet_period(self) -> None:
        ctx = BehaviorContext(
            current_state=CharacterState.IDLE,
            is_visible=True,
            is_in_quiet_period=True,
            mood=Mood.HAPPY,
        )
        action = self.rules.evaluate(EVENT_IDLE_TIMEOUT, ctx)
        self.assertEqual(action.action_type, ACTION_NOOP)


class TestMoodApplicationIntegration(unittest.TestCase):
    """Integration tests verifying full application wiring of the mood foundation."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_mood_app"])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.settings_path = Path(self.temp_dir.name) / "test_settings.ini"
        self.settings = QSettings(str(self.settings_path), QSettings.Format.IniFormat)
        self.settings_manager = SettingsManager(settings=self.settings)

        self.sim_time = 1000.0
        self.app = DoodleApplication(
            settings_manager=self.settings_manager,
            use_rich_idle=True,
        )
        self.app.behavior_engine.time_provider = lambda: self.sim_time
        self.app.behavior_engine.rules._time_provider = lambda: self.sim_time
        self.app.behavior_engine.mood_manager.time_provider = lambda: self.sim_time

    def tearDown(self) -> None:
        self.app.quit()
        self.temp_dir.cleanup()

    def test_application_initial_mood_is_neutral(self) -> None:
        self.assertEqual(self.app.mood, Mood.NEUTRAL)
        self.assertEqual(self.app.character.mood, Mood.NEUTRAL)
        self.assertEqual(self.app.behavior_engine.mood, Mood.NEUTRAL)

    def test_cursor_proximity_updates_mood_to_curious(self) -> None:
        self.app.companion_window.cursor_entered_proximity.emit()
        self.assertEqual(self.app.mood, Mood.CURIOUS)
        self.assertEqual(self.app.character.mood, Mood.CURIOUS)

    def test_click_updates_mood_to_happy(self) -> None:
        self.app._on_character_clicked()
        self.assertEqual(self.app.mood, Mood.HAPPY)
        self.assertEqual(self.app.character.mood, Mood.HAPPY)

    def test_drag_updates_mood_to_playful(self) -> None:
        self.app.companion_window.drag_started.emit()
        self.assertEqual(self.app.mood, Mood.PLAYFUL)
        self.assertEqual(self.app.character.mood, Mood.PLAYFUL)

        self.app.companion_window.drag_finished.emit()
        self.assertEqual(self.app.mood, Mood.PLAYFUL)

    def test_extended_idle_transitions_mood_to_sleepy(self) -> None:
        # Move simulated clock forward past sleepy threshold (180s)
        self.sim_time += 190.0

        # Trigger idle check
        self.app.behavior_engine.trigger_idle_timeout()
        self.assertEqual(self.app.mood, Mood.SLEEPY)
        self.assertEqual(self.app.character.mood, Mood.SLEEPY)

    def test_mood_resets_to_neutral_on_app_restart_without_persistence(self) -> None:
        # Set mood in first app
        self.app.behavior_engine.mood_manager.set_mood(Mood.PLAYFUL)
        self.assertEqual(self.app.mood, Mood.PLAYFUL)

        # Quit first app
        self.app.quit()

        # Launch fresh app instance with same settings
        fresh_app = DoodleApplication(
            settings_manager=self.settings_manager,
            use_rich_idle=True,
        )
        self.assertEqual(fresh_app.mood, Mood.NEUTRAL)
        self.assertEqual(fresh_app.character.mood, Mood.NEUTRAL)
        fresh_app.quit()
