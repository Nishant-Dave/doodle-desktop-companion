"""Deterministic rules and action decisions for Doodle companion behavior."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Sequence, Set, Union

from doodle.character.mood import Mood
from doodle.character.state import CharacterState

logger = logging.getLogger(__name__)

# Core behavior events
EVENT_IDLE_TIMEOUT: str = "IDLE_TIMEOUT"
EVENT_ANIMATION_FINISHED: str = "ANIMATION_FINISHED"
EVENT_CHARACTER_CLICKED: str = "CHARACTER_CLICKED"
EVENT_MENU_OPENED: str = "MENU_OPENED"
EVENT_MENU_DISMISSED: str = "MENU_DISMISSED"
EVENT_CHARACTER_MOVED: str = "CHARACTER_MOVED"
EVENT_SHOW_REQUESTED: str = "SHOW_REQUESTED"
EVENT_HIDE_REQUESTED: str = "HIDE_REQUESTED"
EVENT_DRAG_STARTED: str = "DRAG_STARTED"
EVENT_DRAGGING: str = "DRAGGING"
EVENT_DRAG_RELEASED: str = "DRAG_RELEASED"
EVENT_DRAG_FINISHED: str = "DRAG_RELEASED"
EVENT_CURSOR_ENTERED_PROXIMITY: str = "CURSOR_ENTERED_PROXIMITY"

# Action type representations
ACTION_CHANGE_STATE: str = "CHANGE_STATE"
ACTION_PLAY_ANIMATION: str = "PLAY_ANIMATION"
ACTION_NOOP: str = "NOOP"

# Default deterministic sequence of idle states (Milestone 1 compatibility)
DEFAULT_IDLE_CYCLE: Sequence[CharacterState] = (
    CharacterState.STRETCH,
    CharacterState.SIT,
    CharacterState.SLEEP,
)

# Centralized timing configuration defaults
DEFAULT_QUIET_PERIOD_S: float = 15.0
DEFAULT_QUIET_PERIOD_MS: int = 15000
DEFAULT_BEHAVIOR_COOLDOWN_S: float = 60.0
DEFAULT_PROXIMITY_COOLDOWN_S: float = 30.0

SHORT_IDLE_THRESHOLD_S: float = 60.0
LONG_IDLE_THRESHOLD_S: float = 180.0


class IdleBehavior(str, Enum):
    """Vocabulary of supported conceptual idle behaviors."""

    YAWN = "YAWN"
    LOOK_AROUND = "LOOK_AROUND"
    STRETCH = "STRETCH"
    NAP = "NAP"
    WAKE_UP = "WAKE_UP"
    PLAYFUL_DANCE = "PLAYFUL_DANCE"
    CURIOUS = "CURIOUS"
    SELF_AMUSEMENT = "SELF_AMUSEMENT"

    def __str__(self) -> str:
        return self.value


# Mapping of conceptual idle behavior to animation name
IDLE_BEHAVIOR_ANIMATIONS: dict[IdleBehavior, str] = {
    IdleBehavior.YAWN: "yawn",
    IdleBehavior.LOOK_AROUND: "look_around",
    IdleBehavior.STRETCH: "stretch",
    IdleBehavior.NAP: "sleep",
    IdleBehavior.WAKE_UP: "wake_up",
    IdleBehavior.PLAYFUL_DANCE: "playful",
    IdleBehavior.CURIOUS: "curious",
    IdleBehavior.SELF_AMUSEMENT: "self_amusement",
}

# Mapping of conceptual idle behavior to permanent character state if applicable
IDLE_BEHAVIOR_STATES: dict[IdleBehavior, CharacterState] = {
    IdleBehavior.STRETCH: CharacterState.STRETCH,
    IdleBehavior.NAP: CharacterState.SLEEP,
}

# Idle tier candidate preferences
TIER_SHORT_IDLE_BEHAVIORS: tuple[IdleBehavior, ...] = (
    IdleBehavior.STRETCH,
    IdleBehavior.CURIOUS,
    IdleBehavior.LOOK_AROUND,
)

TIER_LONG_IDLE_BEHAVIORS: tuple[IdleBehavior, ...] = (
    IdleBehavior.NAP,
    IdleBehavior.STRETCH,
    IdleBehavior.CURIOUS,
    IdleBehavior.YAWN,
)

TIER_VERY_LONG_IDLE_BEHAVIORS: tuple[IdleBehavior, ...] = (
    IdleBehavior.PLAYFUL_DANCE,
    IdleBehavior.NAP,
    IdleBehavior.SELF_AMUSEMENT,
    IdleBehavior.WAKE_UP,
)

# Preferred idle behaviors for each companion mood
MOOD_PREFERRED_BEHAVIORS: dict[Mood, tuple[IdleBehavior, ...]] = {
    Mood.NEUTRAL: (),
    Mood.CURIOUS: (
        IdleBehavior.CURIOUS,
        IdleBehavior.LOOK_AROUND,
    ),
    Mood.PLAYFUL: (
        IdleBehavior.PLAYFUL_DANCE,
        IdleBehavior.SELF_AMUSEMENT,
    ),
    Mood.HAPPY: (
        IdleBehavior.STRETCH,
        IdleBehavior.PLAYFUL_DANCE,
        IdleBehavior.CURIOUS,
    ),
    Mood.SLEEPY: (
        IdleBehavior.NAP,
        IdleBehavior.YAWN,
    ),
}


def is_behavior_available(
    behavior: Union[IdleBehavior, str],
    available_animations: Optional[Union[Sequence[str], Set[str]]] = None,
) -> bool:
    """Return True if an animation asset exists for the conceptual idle behavior.

    If available_animations is provided, checks membership in that set.
    Otherwise, checks against default project-owned animations known to exist in assets/panda.
    """
    if isinstance(behavior, str):
        try:
            behavior = IdleBehavior(behavior.upper())
        except ValueError:
            return False

    anim_name = IDLE_BEHAVIOR_ANIMATIONS.get(behavior)
    if anim_name is None:
        return False

    if available_animations is not None:
        return anim_name.lower() in {a.lower() for a in available_animations}

    # Project-owned animations known to exist in assets/panda
    return anim_name.lower() in ("stretch", "sleep", "curious", "playful")


def get_available_behaviors(
    available_animations: Optional[Union[Sequence[str], Set[str]]] = None,
) -> list[IdleBehavior]:
    """Return a list of IdleBehavior values that are currently available."""
    return [
        b for b in IdleBehavior
        if is_behavior_available(b, available_animations=available_animations)
    ]


def action_for_idle_behavior(behavior: IdleBehavior) -> BehaviorAction:
    """Construct the high-level BehaviorAction for an IdleBehavior."""
    if behavior in IDLE_BEHAVIOR_STATES:
        state = IDLE_BEHAVIOR_STATES[behavior]
        return BehaviorAction.change_state(state, loop=False)

    anim_name = IDLE_BEHAVIOR_ANIMATIONS.get(behavior)
    if anim_name:
        return BehaviorAction.play_animation(anim_name, loop=False)

    return BehaviorAction.noop()


class IdleSelectionPolicy:
    """Deterministic selection policy governing rich autonomous idle behaviors."""

    def __init__(
        self,
        cooldown_s: float = DEFAULT_BEHAVIOR_COOLDOWN_S,
        short_idle_threshold_s: float = SHORT_IDLE_THRESHOLD_S,
        long_idle_threshold_s: float = LONG_IDLE_THRESHOLD_S,
        time_provider: Optional[Callable[[], float]] = None,
        available_animations: Optional[Union[Sequence[str], Set[str]]] = None,
    ) -> None:
        self._cooldown_s = max(0.0, float(cooldown_s))
        self._short_idle_threshold_s = short_idle_threshold_s
        self._long_idle_threshold_s = long_idle_threshold_s
        self._time_provider = time_provider or time.monotonic
        self._available_animations = (
            set(available_animations) if available_animations is not None else None
        )

        self._last_performed_at: dict[IdleBehavior, float] = {}
        self._most_recent_behavior: Optional[IdleBehavior] = None
        self._rotation_indices: dict[str, int] = {
            "short": 0,
            "long": 0,
            "very_long": 0,
        }
        self._mood_rotation_indices: dict[Mood, int] = {m: 0 for m in Mood}

    @property
    def cooldown_s(self) -> float:
        """Return behavior cooldown duration in seconds."""
        return self._cooldown_s

    @property
    def most_recent_behavior(self) -> Optional[IdleBehavior]:
        """Return the most recently performed autonomous idle behavior."""
        return self._most_recent_behavior

    @property
    def rotation_index(self) -> int:
        """Return the aggregate deterministic rotation index."""
        return sum(self._rotation_indices.values())

    def reset(self) -> None:
        """Reset policy history, cooldowns, and rotation indices."""
        self._last_performed_at.clear()
        self._most_recent_behavior = None
        self._rotation_indices = {"short": 0, "long": 0, "very_long": 0}
        self._mood_rotation_indices = {m: 0 for m in Mood}

    def is_available(self, behavior: IdleBehavior) -> bool:
        """Check if behavior has an animation asset available."""
        return is_behavior_available(behavior, self._available_animations)

    def is_on_cooldown(self, behavior: IdleBehavior, current_time: Optional[float] = None) -> bool:
        """Return True if the specified behavior is currently on cooldown."""
        now = current_time if current_time is not None else self._time_provider()
        last_time = self._last_performed_at.get(behavior)
        if last_time is None:
            return False
        return (now - last_time) < self._cooldown_s

    def record_behavior(self, behavior: IdleBehavior, current_time: Optional[float] = None) -> None:
        """Record that a behavior was performed to track cooldowns and recency."""
        now = current_time if current_time is not None else self._time_provider()
        self._last_performed_at[behavior] = now
        self._most_recent_behavior = behavior

    def get_tier_key(self, idle_time_s: float) -> str:
        """Return the tier identifier for a given idle duration."""
        if idle_time_s < self._short_idle_threshold_s:
            return "short"
        elif idle_time_s < self._long_idle_threshold_s:
            return "long"
        else:
            return "very_long"

    def get_tier_candidates(self, idle_time_s: float) -> tuple[IdleBehavior, ...]:
        """Return the candidate behaviors appropriate for a given idle duration."""
        tier_key = self.get_tier_key(idle_time_s)
        if tier_key == "short":
            return TIER_SHORT_IDLE_BEHAVIORS
        elif tier_key == "long":
            return TIER_LONG_IDLE_BEHAVIORS
        else:
            return TIER_VERY_LONG_IDLE_BEHAVIORS

    def select(
        self,
        idle_time_s: float = 0.0,
        current_time: Optional[float] = None,
        available_behaviors: Optional[Sequence[IdleBehavior]] = None,
        mood: Optional[Mood] = None,
    ) -> Optional[IdleBehavior]:
        """Deterministically select the next appropriate idle behavior.

        Evaluation pipeline:
        1. If companion has an active non-neutral mood with preferred behaviors,
           evaluate mood candidates first.
        2. Filter out unavailable behaviors and behaviors on cooldown.
        3. Deterministically rotate through eligible candidates.
        4. Fall back to normal tier candidate selection if mood has no eligible behaviors.
        """
        now = current_time if current_time is not None else self._time_provider()
        tier_key = self.get_tier_key(idle_time_s)
        tier_candidates = self.get_tier_candidates(idle_time_s)

        # 1. Evaluate mood-preferred candidates if mood is active and non-neutral
        if mood is not None and mood in MOOD_PREFERRED_BEHAVIORS and MOOD_PREFERRED_BEHAVIORS[mood]:
            mood_candidates = MOOD_PREFERRED_BEHAVIORS[mood]
            if available_behaviors is not None:
                avail_set = set(available_behaviors)
                mood_filtered = [b for b in mood_candidates if b in avail_set]
            else:
                mood_filtered = [b for b in mood_candidates if self.is_available(b)]

            eligible_mood = [
                b for b in mood_filtered
                if b != self._most_recent_behavior and not self.is_on_cooldown(b, now)
            ]

            if eligible_mood:
                rot_index = self._mood_rotation_indices.get(mood, 0)
                selected = eligible_mood[rot_index % len(eligible_mood)]
                self._mood_rotation_indices[mood] = rot_index + 1
                self.record_behavior(selected, now)
                return selected

        # 2. Standard tier candidate selection (fallback or neutral mood)
        if available_behaviors is not None:
            available_set = set(available_behaviors)
            candidates = [b for b in tier_candidates if b in available_set]
        else:
            candidates = [b for b in tier_candidates if self.is_available(b)]

        eligible: list[IdleBehavior] = []
        for b in candidates:
            if b == self._most_recent_behavior:
                continue
            if self.is_on_cooldown(b, now):
                continue
            eligible.append(b)

        if not eligible:
            return None

        # Select deterministically using per-tier rotation index
        rot_index = self._rotation_indices.get(tier_key, 0)
        selected = eligible[rot_index % len(eligible)]
        self._rotation_indices[tier_key] = rot_index + 1
        self.record_behavior(selected, now)
        return selected



@dataclass(frozen=True)
class BehaviorAction:
    """Represents a high-level action decided by the behavior engine."""

    action_type: str
    state: Optional[CharacterState] = None
    animation_name: Optional[str] = None
    loop: Optional[bool] = None

    @classmethod
    def change_state(
        cls,
        state: CharacterState,
        loop: Optional[bool] = None,
    ) -> BehaviorAction:
        """Create a state transition action for the character."""
        return cls(action_type=ACTION_CHANGE_STATE, state=state, loop=loop)

    @classmethod
    def play_animation(
        cls,
        animation_name: str,
        loop: Optional[bool] = None,
    ) -> BehaviorAction:
        """Create an animation playback action for the character."""
        return cls(action_type=ACTION_PLAY_ANIMATION, animation_name=animation_name, loop=loop)

    @classmethod
    def noop(cls) -> BehaviorAction:
        """Create a no-operation action."""
        return cls(action_type=ACTION_NOOP)

    def __str__(self) -> str:
        if self.action_type == ACTION_CHANGE_STATE and self.state is not None:
            loop_suffix = f", loop={self.loop}" if self.loop is not None else ""
            return f"CHANGE_STATE({self.state.value}{loop_suffix})"
        if self.action_type == ACTION_PLAY_ANIMATION and self.animation_name is not None:
            loop_suffix = f", loop={self.loop}" if self.loop is not None else ""
            return f"PLAY_ANIMATION({self.animation_name}{loop_suffix})"
        return "NOOP"


@dataclass
class BehaviorContext:
    """Current environmental context and character conditions evaluated by rules."""

    current_state: CharacterState = CharacterState.IDLE
    is_visible: bool = True
    is_menu_open: bool = False
    is_dragging: bool = False
    current_animation: Optional[str] = None
    idle_duration_s: float = 0.0
    time_since_last_interaction_s: float = 0.0
    quiet_period_s: float = DEFAULT_QUIET_PERIOD_S
    is_in_quiet_period: bool = False
    current_time_s: Optional[float] = None
    available_behaviors: Optional[Sequence[IdleBehavior]] = None
    policy: Optional[IdleSelectionPolicy] = None
    mood: Mood = Mood.NEUTRAL


class IdleBehaviorRules:
    """Deterministic rule evaluator governing idle behavior and interaction priority."""

    def __init__(
        self,
        idle_cycle: Optional[Sequence[CharacterState]] = None,
        policy: Optional[IdleSelectionPolicy] = None,
        proximity_cooldown_s: float = DEFAULT_PROXIMITY_COOLDOWN_S,
        time_provider: Optional[Callable[[], float]] = None,
    ) -> None:
        self._idle_cycle = tuple(idle_cycle or DEFAULT_IDLE_CYCLE)
        self._cycle_index: int = 0
        self._policy: Optional[IdleSelectionPolicy] = policy
        self._proximity_cooldown_s: float = max(0.0, float(proximity_cooldown_s))
        self._time_provider: Callable[[], float] = time_provider or time.monotonic
        self._last_proximity_time: float = float("-inf")

    @property
    def idle_cycle(self) -> tuple[CharacterState, ...]:
        """Return the configured sequence of idle states."""
        return self._idle_cycle

    @property
    def cycle_index(self) -> int:
        """Return the current cycle pointer index."""
        return self._cycle_index

    @property
    def policy(self) -> Optional[IdleSelectionPolicy]:
        """Return the attached deterministic idle selection policy, if any."""
        return self._policy

    @policy.setter
    def policy(self, value: Optional[IdleSelectionPolicy]) -> None:
        self._policy = value

    @property
    def proximity_cooldown_s(self) -> float:
        """Return the proximity reaction cooldown in seconds."""
        return self._proximity_cooldown_s

    @proximity_cooldown_s.setter
    def proximity_cooldown_s(self, value: float) -> None:
        self._proximity_cooldown_s = max(0.0, float(value))

    @property
    def last_proximity_time(self) -> float:
        """Return the timestamp of the last executed proximity reaction."""
        return self._last_proximity_time

    @last_proximity_time.setter
    def last_proximity_time(self, value: float) -> None:
        self._last_proximity_time = float(value)

    def is_proximity_on_cooldown(self, current_time: Optional[float] = None) -> bool:
        """Return True if proximity reaction is currently on cooldown."""
        now = current_time if current_time is not None else self._time_provider()
        return (now - self._last_proximity_time) < self._proximity_cooldown_s

    def reset_proximity_cooldown(self) -> None:
        """Reset proximity cooldown timer to allow immediate reaction."""
        self._last_proximity_time = float("-inf")

    def reset_cycle(self) -> None:
        """Reset the deterministic cycle index, policy history, and proximity cooldown."""
        self._cycle_index = 0
        self._last_proximity_time = float("-inf")
        if self._policy is not None:
            self._policy.reset()

    def evaluate(
        self,
        event: str,
        context: BehaviorContext,
        **kwargs,
    ) -> BehaviorAction:
        """Evaluate an incoming event against the current context to decide an action.

        Follows:
            EVENT -> STATE / CONTEXT -> DECISION -> ACTION
        """
        normalized_event = event.upper().strip()

        # 1. User interaction priority: click always transitions to ATTENTION
        if normalized_event == EVENT_CHARACTER_CLICKED:
            return BehaviorAction.change_state(CharacterState.ATTENTION, loop=True)

        # 2. Drag interaction lifecycle:
        # Drag started: enter surprised/held pose, interrupt idle behavior
        if normalized_event == EVENT_DRAG_STARTED:
            return BehaviorAction.play_animation("surprised", loop=True)

        # During dragging: remain visually stable while following pointer
        if normalized_event == EVENT_DRAGGING:
            return BehaviorAction.noop()

        # Drag released: perform short deterministic reaction (dizzy) before recovering to IDLE
        if normalized_event in (EVENT_DRAG_RELEASED, "DRAG_FINISHED"):
            return BehaviorAction.play_animation("dizzy", loop=False)

        # 3. Animation finished transitions:
        if normalized_event == EVENT_ANIMATION_FINISHED:
            anim_name = kwargs.get("animation_name")
            if anim_name == "dizzy":
                return BehaviorAction.play_animation("recover", loop=False)
            if anim_name in (
                "recover",
                "curious",
                "playful",
                "stretch",
                "sleep",
                "yawn",
                "look_around",
                "wake_up",
                "self_amusement",
                "attention",
            ):
                return BehaviorAction.change_state(CharacterState.IDLE, loop=True)

            if context.current_state in (
                CharacterState.STRETCH,
                CharacterState.SIT,
                CharacterState.SLEEP,
            ):
                return BehaviorAction.change_state(CharacterState.IDLE, loop=True)
            return BehaviorAction.noop()

        # 4. Menu dismissed returns to IDLE if character was in ATTENTION
        if normalized_event == EVENT_MENU_DISMISSED:
            if context.current_state == CharacterState.ATTENTION:
                return BehaviorAction.change_state(CharacterState.IDLE, loop=True)
            return BehaviorAction.noop()

        # 5. Idle timeout triggers next deterministic idle action
        if normalized_event == EVENT_IDLE_TIMEOUT:
            # Idle action is only valid when character is IDLE, visible, not dragging, not in menu,
            # and not playing a transient expressive animation
            if (
                context.is_visible
                and not context.is_dragging
                and not context.is_menu_open
                and context.current_state == CharacterState.IDLE
                and context.current_animation in (None, "idle")
            ):
                # If a deterministic selection policy is active, select next behavior
                active_policy = self._policy or context.policy
                if active_policy is not None:
                    # Suppress autonomous behavior during quiet period after interaction
                    if context.is_in_quiet_period:
                        return BehaviorAction.noop()

                    selected = active_policy.select(
                        idle_time_s=context.idle_duration_s,
                        current_time=context.current_time_s,
                        available_behaviors=context.available_behaviors,
                        mood=context.mood,
                    )
                    if selected is not None:
                        return action_for_idle_behavior(selected)
                    return BehaviorAction.noop()

                # Fallback to deterministic cycle
                if not self._idle_cycle:
                    return BehaviorAction.noop()
                next_state = self._idle_cycle[self._cycle_index]
                self._cycle_index = (self._cycle_index + 1) % len(self._idle_cycle)
                return BehaviorAction.change_state(next_state, loop=False)

            return BehaviorAction.noop()

        # 6. Proximity awareness: subtle reaction when cursor crosses into proximity zone
        if normalized_event == EVENT_CURSOR_ENTERED_PROXIMITY:
            now = (
                context.current_time_s
                if context.current_time_s is not None
                else self._time_provider()
            )
            if (
                context.is_visible
                and not context.is_dragging
                and not context.is_menu_open
                and context.current_state == CharacterState.IDLE
                and context.current_animation in (None, "idle")
                and not self.is_proximity_on_cooldown(now)
            ):
                self._last_proximity_time = now
                return BehaviorAction.play_animation("curious", loop=False)
            return BehaviorAction.noop()

        # 7. All other, unhandled, or unknown events are safely ignored
        logger.debug("Unhandled or ignored behavior event: %s", normalized_event)
        return BehaviorAction.noop()

