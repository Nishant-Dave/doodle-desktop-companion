"""Physical realization adapter for Doodle activities.

Translates semantic Activity domain objects into concrete Character and
AnimationController operations.

Per Architecture v2:
- Behavior chooses WHAT Doodle wants to do.
- Activity represents WHAT Doodle is doing over time.
- ActivityExecutor manages lifecycle transitions.
- CharacterActivityPerformer adapts Activity to existing physical Character capabilities.
- Character and AnimationController own physical state and animation rendering.

Crucial architectural rules:
- CharacterActivityPerformer conforms to ActivityExecutionTarget protocol.
- CharacterActivityPerformer does NOT hold or reference ActivityExecutor.
- Completion events are emitted by Character/AnimationController and routed
  via the composition boundary, NOT by this performer.
- CharacterState remains strictly a physical posture enum (IDLE, SIT, SLEEP,
  STRETCH, ATTENTION) and is not expanded with activity or cognitive values.
"""

from __future__ import annotations

import logging

from doodle.activity.executor import ActivityExecutionTarget
from doodle.activity.model import Activity
from doodle.activity.types import ActivityType
from doodle.character.character import Character
from doodle.character.state import CharacterState

logger = logging.getLogger(__name__)


class CharacterActivityPerformer(ActivityExecutionTarget):
    """Physical realization adapter translating Activity into Character actions.

    Conforms to the ActivityExecutionTarget protocol.
    """

    def __init__(self, character: Character) -> None:
        """Initialize performer with a Character instance.

        Args:
            character: The existing Character instance to command.

        Raises:
            TypeError: If character is not a Character instance.
        """
        if character is None or not isinstance(character, Character):
            raise TypeError(
                f"Expected a Character instance, got {type(character).__name__ if character is not None else 'None'}"
            )
        self._character: Character = character

    @property
    def character(self) -> Character:
        """Return the attached Character instance."""
        return self._character

    def perform_activity(self, activity: Activity) -> None:
        """Physically begin realizing the given activity on the Character.

        Maps semantic ActivityType values into existing Character capabilities:
        - REST: Deterministically maps to resting posture CharacterState.SIT and 'sit' animation.
        - WALK: MVP fallback to CharacterState.IDLE (no physical movement/walk animation).
        - LOOK_AROUND: Plays the existing 'look_around' animation.
        - STRETCH: Maps to CharacterState.STRETCH and plays 'stretch' animation.
        - SLEEP: Maps to CharacterState.SLEEP and plays 'sleep' animation.
        - PLAY: Plays the existing 'playful' animation as closest capability.

        Args:
            activity: The semantic Activity to physically realize.
        """
        activity_type = activity.activity_type

        logger.debug("Performing activity: %s (%s)", activity.activity_id, activity_type.value)

        if activity_type == ActivityType.REST:
            # Deterministic mapping to resting posture CharacterState.SIT and 'sit' animation.
            # Activity metadata cannot override physical CharacterState or animation selection.
            self._character.set_state(CharacterState.SIT)

        elif activity_type == ActivityType.WALK:
            # MVP Fallback: WALK currently has no physical movement/coordinate translation
            # or walking sprite assets. Fall back to neutral CharacterState.IDLE without
            # pretending to simulate movement.
            logger.info("Activity WALK has no physical movement assets; falling back to IDLE.")
            self._character.set_state(CharacterState.IDLE)

        elif activity_type == ActivityType.LOOK_AROUND:
            # Play existing 'look_around' animation.
            # Reset physical posture to IDLE if in a non-neutral posture (e.g. SIT/SLEEP).
            if self._character.state != CharacterState.IDLE:
                self._character.set_state(CharacterState.IDLE)
            self._character.play_animation("look_around")

        elif activity_type == ActivityType.STRETCH:
            # Map to CharacterState.STRETCH and play stretch animation
            self._character.set_state(CharacterState.STRETCH)

        elif activity_type == ActivityType.SLEEP:
            # Map to CharacterState.SLEEP and play sleep animation
            self._character.set_state(CharacterState.SLEEP)

        elif activity_type == ActivityType.PLAY:
            # Play existing 'playful' animation as the closest existing animation capability.
            # Reset physical posture to IDLE if in a non-neutral posture.
            if self._character.state != CharacterState.IDLE:
                self._character.set_state(CharacterState.IDLE)
            self._character.play_animation("playful")

        else:
            # Unsupported or unexpected activity type: safe fallback to neutral resting state
            logger.warning("Unsupported ActivityType '%s'; falling back to IDLE.", activity_type)
            self._character.set_state(CharacterState.IDLE)

    def interrupt_activity(self, activity: Activity) -> None:
        """Safely return the character to the neutral existing state upon interruption.

        Args:
            activity: The Activity instance being interrupted.
        """
        logger.debug("Interrupting activity physical realization: %s", activity.activity_id)
        self._character.set_state(CharacterState.IDLE)

    def cancel_activity(self, activity: Activity) -> None:
        """Safely return the character to the neutral existing state upon cancellation.

        Stops any ongoing animation and resets physical state to CharacterState.IDLE.

        Args:
            activity: The Activity instance being cancelled.
        """
        logger.debug("Cancelling activity physical realization: %s", activity.activity_id)
        self._character.stop_animation()
        self._character.set_state(CharacterState.IDLE)

    def __repr__(self) -> str:
        return f"CharacterActivityPerformer(character={self._character.name!r}, state={self._character.state.value})"
