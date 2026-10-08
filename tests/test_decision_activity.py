"""Focused unit and boundary tests for Task 22: Decision → Activity Integration.

Verifies:
1. A deterministic behavior decision can produce an Activity.
2. The ActivityType corresponds to the semantic decision vocabulary:
   - REST        → ActivityType.REST
   - WALK        → ActivityType.WALK
   - LOOK_AROUND → ActivityType.LOOK_AROUND
   - STRETCH     → ActivityType.STRETCH
   - SLEEP       → ActivityType.SLEEP
   - PLAY        → ActivityType.PLAY
3. Existing behavior rules remain deterministic and repeatable.
4. Existing behavior tests continue to pass with legacy execution intact.
5. Activity remains declarative and independent of execution/presentation.
6. No animation/frame/timer logic enters the decision layer.
7. Unmapped/presentation-specific actions intentionally do not produce Activities.
8. Compatibility bridge (action_for_activity) translates Activity to BehaviorAction.
9. BehaviorEngine decision boundary produces Activity without triggering execution.
"""

from __future__ import annotations

import os
import unittest
from typing import Optional

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from doodle.activity import Activity, ActivityLifecycleState, ActivityType
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
    BehaviorAction,
    BehaviorContext,
    IdleBehavior,
    IdleBehaviorRules,
    IdleSelectionPolicy,
    action_for_activity,
    action_for_idle_behavior,
    activity_type_for_behavior,
    create_activity_for_behavior,
)
from doodle.character.character import Character
from doodle.character.state import CharacterState


class TestSemanticActivityMapping(unittest.TestCase):
    """Test pure semantic mapping from behaviors and states to ActivityType vocabulary."""

    def test_vocabulary_mapping_rest(self) -> None:
        self.assertEqual(activity_type_for_behavior("REST"), ActivityType.REST)
        self.assertEqual(activity_type_for_behavior(CharacterState.SIT), ActivityType.REST)
        act = create_activity_for_behavior(CharacterState.SIT)
        self.assertIsNotNone(act)
        assert act is not None
        self.assertEqual(act.activity_type, ActivityType.REST)

    def test_vocabulary_mapping_walk(self) -> None:
        self.assertEqual(activity_type_for_behavior("WALK"), ActivityType.WALK)
        act = create_activity_for_behavior("WALK")
        self.assertIsNotNone(act)
        assert act is not None
        self.assertEqual(act.activity_type, ActivityType.WALK)

    def test_vocabulary_mapping_look_around(self) -> None:
        self.assertEqual(activity_type_for_behavior("LOOK_AROUND"), ActivityType.LOOK_AROUND)
        self.assertEqual(activity_type_for_behavior(IdleBehavior.LOOK_AROUND), ActivityType.LOOK_AROUND)
        act = create_activity_for_behavior(IdleBehavior.LOOK_AROUND)
        self.assertIsNotNone(act)
        assert act is not None
        self.assertEqual(act.activity_type, ActivityType.LOOK_AROUND)

    def test_vocabulary_mapping_stretch(self) -> None:
        self.assertEqual(activity_type_for_behavior("STRETCH"), ActivityType.STRETCH)
        self.assertEqual(activity_type_for_behavior(IdleBehavior.STRETCH), ActivityType.STRETCH)
        self.assertEqual(activity_type_for_behavior(CharacterState.STRETCH), ActivityType.STRETCH)
        act = create_activity_for_behavior(IdleBehavior.STRETCH)
        self.assertIsNotNone(act)
        assert act is not None
        self.assertEqual(act.activity_type, ActivityType.STRETCH)

    def test_vocabulary_mapping_sleep(self) -> None:
        self.assertEqual(activity_type_for_behavior("SLEEP"), ActivityType.SLEEP)
        self.assertEqual(activity_type_for_behavior(IdleBehavior.NAP), ActivityType.SLEEP)
        self.assertEqual(activity_type_for_behavior(CharacterState.SLEEP), ActivityType.SLEEP)
        act = create_activity_for_behavior(IdleBehavior.NAP)
        self.assertIsNotNone(act)
        assert act is not None
        self.assertEqual(act.activity_type, ActivityType.SLEEP)

    def test_vocabulary_mapping_play(self) -> None:
        self.assertEqual(activity_type_for_behavior("PLAY"), ActivityType.PLAY)
        self.assertEqual(activity_type_for_behavior(IdleBehavior.PLAYFUL_DANCE), ActivityType.PLAY)
        self.assertEqual(activity_type_for_behavior(IdleBehavior.SELF_AMUSEMENT), ActivityType.PLAY)
        act = create_activity_for_behavior(IdleBehavior.PLAYFUL_DANCE)
        self.assertIsNotNone(act)
        assert act is not None
        self.assertEqual(act.activity_type, ActivityType.PLAY)

    def test_presentation_specific_behaviors_not_mapped(self) -> None:
        """Behaviors that are presentation-specific micro-gestures or reactions do NOT map to Activity."""
        self.assertIsNone(activity_type_for_behavior(IdleBehavior.YAWN))
        self.assertIsNone(activity_type_for_behavior(IdleBehavior.CURIOUS))
        self.assertIsNone(activity_type_for_behavior(IdleBehavior.WAKE_UP))
        self.assertIsNone(activity_type_for_behavior(CharacterState.ATTENTION))
        self.assertIsNone(activity_type_for_behavior("dizzy"))
        self.assertIsNone(activity_type_for_behavior("surprised"))
        self.assertIsNone(activity_type_for_behavior("recover"))

        self.assertIsNone(create_activity_for_behavior(IdleBehavior.YAWN))
        self.assertIsNone(create_activity_for_behavior(IdleBehavior.CURIOUS))


class TestRulesDecisionActivity(unittest.TestCase):
    """Test that IdleBehaviorRules produces Activity alongside BehaviorAction."""

    def setUp(self) -> None:
        self.rules = IdleBehaviorRules()

    def test_deterministic_idle_cycle_produces_activities(self) -> None:
        context = BehaviorContext(current_state=CharacterState.IDLE)

        # 1st: STRETCH -> Activity(ActivityType.STRETCH)
        action1 = self.rules.evaluate(EVENT_IDLE_TIMEOUT, context)
        self.assertEqual(action1.state, CharacterState.STRETCH)
        self.assertIsNotNone(action1.activity)
        assert action1.activity is not None
        self.assertEqual(action1.activity.activity_type, ActivityType.STRETCH)
        self.assertEqual(action1.activity.lifecycle_state, ActivityLifecycleState.PENDING)

        # 2nd: SIT -> Activity(ActivityType.REST)
        action2 = self.rules.evaluate(EVENT_IDLE_TIMEOUT, context)
        self.assertEqual(action2.state, CharacterState.SIT)
        self.assertIsNotNone(action2.activity)
        assert action2.activity is not None
        self.assertEqual(action2.activity.activity_type, ActivityType.REST)

        # 3rd: SLEEP -> Activity(ActivityType.SLEEP)
        action3 = self.rules.evaluate(EVENT_IDLE_TIMEOUT, context)
        self.assertEqual(action3.state, CharacterState.SLEEP)
        self.assertIsNotNone(action3.activity)
        assert action3.activity is not None
        self.assertEqual(action3.activity.activity_type, ActivityType.SLEEP)

        # 4th: cycle wraps back to STRETCH
        action4 = self.rules.evaluate(EVENT_IDLE_TIMEOUT, context)
        self.assertEqual(action4.state, CharacterState.STRETCH)
        self.assertIsNotNone(action4.activity)
        assert action4.activity is not None
        self.assertEqual(action4.activity.activity_type, ActivityType.STRETCH)

    def test_decide_activity_pure_query_without_execution(self) -> None:
        """Verify decide_activity on rules yields Activity directly."""
        context = BehaviorContext(current_state=CharacterState.IDLE)
        activity = self.rules.decide_activity(EVENT_IDLE_TIMEOUT, context)
        self.assertIsNotNone(activity)
        assert activity is not None
        self.assertEqual(activity.activity_type, ActivityType.STRETCH)

    def test_presentation_events_do_not_produce_activity(self) -> None:
        context = BehaviorContext(current_state=CharacterState.IDLE)

        # Click -> CharacterState.ATTENTION (UI focus, not companion activity)
        act_click = self.rules.evaluate(EVENT_CHARACTER_CLICKED, context)
        self.assertIsNone(act_click.activity)
        self.assertIsNone(self.rules.decide_activity(EVENT_CHARACTER_CLICKED, context))

        # Drag started -> surprised animation (physical gesture)
        act_drag_start = self.rules.evaluate(EVENT_DRAG_STARTED, context)
        self.assertIsNone(act_drag_start.activity)

        # Drag released -> dizzy animation (physical recovery)
        act_drag_rel = self.rules.evaluate(EVENT_DRAG_RELEASED, context)
        self.assertIsNone(act_drag_rel.activity)

        # Cursor proximity -> curious micro-reaction
        act_prox = self.rules.evaluate(EVENT_CURSOR_ENTERED_PROXIMITY, context)
        self.assertIsNone(act_prox.activity)

    def test_rich_idle_selection_policy_produces_activity(self) -> None:
        """When rich policy selects an IdleBehavior, Activity reflects that semantic choice."""
        policy = IdleSelectionPolicy(
            available_animations=["stretch", "sleep", "curious", "playful"]
        )
        self.rules.policy = policy
        context = BehaviorContext(
            current_state=CharacterState.IDLE,
            policy=policy,
            available_behaviors=[IdleBehavior.STRETCH, IdleBehavior.NAP],
            time_since_last_interaction_s=100.0,
            quiet_period_s=15.0,
        )

        action = self.rules.evaluate(EVENT_IDLE_TIMEOUT, context)
        self.assertIsNotNone(action.activity)
        assert action.activity is not None
        self.assertIn(action.activity.activity_type, (ActivityType.STRETCH, ActivityType.SLEEP))


class TestCompatibilityBridge(unittest.TestCase):
    """Test action_for_activity compatibility bridge."""

    def test_action_for_activity_mappings(self) -> None:
        act_rest = Activity(ActivityType.REST)
        action_rest = action_for_activity(act_rest)
        self.assertEqual(action_rest.action_type, ACTION_CHANGE_STATE)
        self.assertEqual(action_rest.state, CharacterState.SIT)
        self.assertEqual(action_rest.activity, act_rest)

        act_stretch = Activity(ActivityType.STRETCH)
        action_stretch = action_for_activity(act_stretch)
        self.assertEqual(action_stretch.action_type, ACTION_CHANGE_STATE)
        self.assertEqual(action_stretch.state, CharacterState.STRETCH)
        self.assertEqual(action_stretch.activity, act_stretch)

        act_sleep = Activity(ActivityType.SLEEP)
        action_sleep = action_for_activity(act_sleep)
        self.assertEqual(action_sleep.action_type, ACTION_CHANGE_STATE)
        self.assertEqual(action_sleep.state, CharacterState.SLEEP)
        self.assertEqual(action_sleep.activity, act_sleep)

        act_look = Activity(ActivityType.LOOK_AROUND)
        action_look = action_for_activity(act_look)
        self.assertEqual(action_look.action_type, ACTION_PLAY_ANIMATION)
        self.assertEqual(action_look.animation_name, "look_around")
        self.assertEqual(action_look.activity, act_look)

        act_play = Activity(ActivityType.PLAY)
        action_play = action_for_activity(act_play)
        self.assertEqual(action_play.action_type, ACTION_PLAY_ANIMATION)
        self.assertEqual(action_play.animation_name, "playful")
        self.assertEqual(action_play.activity, act_play)

        act_walk = Activity(ActivityType.WALK)
        action_walk = action_for_activity(act_walk)
        self.assertEqual(action_walk.action_type, ACTION_CHANGE_STATE)
        self.assertEqual(action_walk.state, CharacterState.IDLE)
        self.assertEqual(action_walk.activity, act_walk)


class TestBehaviorEngineDecisionBoundary(unittest.TestCase):
    """Test BehaviorEngine decision producing Activity without executing."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_decision_activity"])

    def setUp(self) -> None:
        self.character = Character(name="panda")
        self.engine = BehaviorEngine(character=self.character, idle_interval_ms=1000)

    def tearDown(self) -> None:
        self.engine.cleanup()
        self.character.stop_animation()

    def test_decide_activity_does_not_execute_character(self) -> None:
        """decide_activity returns Activity without changing physical character state."""
        self.assertEqual(self.character.state, CharacterState.IDLE)
        self.assertEqual(self.character.current_animation_name, "idle")

        decided_activities: list[Activity] = []
        executed_actions: list[BehaviorAction] = []
        self.engine.activity_decided.connect(decided_activities.append)
        self.engine.action_executed.connect(executed_actions.append)

        # Call decide_activity
        activity = self.engine.decide_activity(EVENT_IDLE_TIMEOUT)

        self.assertIsNotNone(activity)
        assert activity is not None
        self.assertEqual(activity.activity_type, ActivityType.STRETCH)

        # Character remains IDLE with "idle" animation - NO execution occurred!
        self.assertEqual(self.character.state, CharacterState.IDLE)
        self.assertEqual(self.character.current_animation_name, "idle")

        # activity_decided signal fired, action_executed signal did NOT fire
        self.assertEqual(len(decided_activities), 1)
        self.assertEqual(decided_activities[0].activity_type, ActivityType.STRETCH)
        self.assertEqual(len(executed_actions), 0)

        # last_activity is recorded
        self.assertEqual(self.engine.last_activity, activity)

    def test_handle_event_emits_both_signals(self) -> None:
        """handle_event emits activity_decided AND executes legacy action for compatibility."""
        decided_activities: list[Activity] = []
        executed_actions: list[BehaviorAction] = []
        self.engine.activity_decided.connect(decided_activities.append)
        self.engine.action_executed.connect(executed_actions.append)

        action = self.engine.trigger_idle_timeout()

        # Both signals emitted
        self.assertEqual(len(decided_activities), 1)
        self.assertEqual(decided_activities[0].activity_type, ActivityType.STRETCH)
        self.assertEqual(len(executed_actions), 1)
        self.assertEqual(executed_actions[0].action_type, ACTION_CHANGE_STATE)

        # Legacy execution path executed character state
        self.assertEqual(self.character.state, CharacterState.STRETCH)
        self.assertEqual(self.engine.last_activity, decided_activities[0])


class TestArchitecturalBoundaries(unittest.TestCase):
    """Verify architectural boundaries between Decision, Activity, and Presentation."""

    def test_activity_does_not_know_about_character_or_animation(self) -> None:
        """Verify Activity does not reference CharacterState, CharacterAction, or AnimationController."""
        act = Activity(ActivityType.REST)
        self.assertFalse(hasattr(act, "state"))
        self.assertFalse(hasattr(act, "animation_name"))
        self.assertFalse(hasattr(act, "character"))
        self.assertFalse(hasattr(act, "action_type"))

    def test_activity_has_no_execution_methods(self) -> None:
        """Verify Activity does not contain execution hooks."""
        forbidden = [
            "start", "tick", "finish", "interrupt", "cancel",
            "on_start", "on_tick", "on_interrupt", "on_finish", "on_cancel",
            "progress", "elapsed_time_s",
        ]
        for attr in forbidden:
            self.assertFalse(hasattr(Activity, attr), f"Activity illegally has {attr}")

    def test_decided_activity_remains_pure_declarative(self) -> None:
        """Decided activities hold semantic information, not frame/widget/timing details."""
        rules = IdleBehaviorRules()
        context = BehaviorContext(current_state=CharacterState.IDLE)
        activity = rules.decide_activity(EVENT_IDLE_TIMEOUT, context)
        self.assertIsNotNone(activity)
        assert activity is not None
        self.assertIsInstance(activity.activity_type, ActivityType)
        self.assertIsInstance(activity.metadata, dict)
        self.assertEqual(activity.lifecycle_state, ActivityLifecycleState.PENDING)


if __name__ == "__main__":
    unittest.main()
