"""Deterministic rules and action decisions for Doodle companion behavior."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Sequence

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

# Action type representations
ACTION_CHANGE_STATE: str = "CHANGE_STATE"
ACTION_PLAY_ANIMATION: str = "PLAY_ANIMATION"
ACTION_NOOP: str = "NOOP"

# Default deterministic sequence of idle states
DEFAULT_IDLE_CYCLE: Sequence[CharacterState] = (
    CharacterState.STRETCH,
    CharacterState.SIT,
    CharacterState.SLEEP,
)


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


class IdleBehaviorRules:
    """Deterministic rule evaluator governing idle behavior and interaction priority."""

    def __init__(
        self,
        idle_cycle: Optional[Sequence[CharacterState]] = None,
    ) -> None:
        self._idle_cycle = tuple(idle_cycle or DEFAULT_IDLE_CYCLE)
        self._cycle_index: int = 0

    @property
    def idle_cycle(self) -> tuple[CharacterState, ...]:
        """Return the configured sequence of idle states."""
        return self._idle_cycle

    @property
    def cycle_index(self) -> int:
        """Return the current cycle pointer index."""
        return self._cycle_index

    def reset_cycle(self) -> None:
        """Reset the deterministic cycle index back to 0."""
        self._cycle_index = 0

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
            if anim_name in ("recover", "curious", "playful"):
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
                if not self._idle_cycle:
                    return BehaviorAction.noop()
                next_state = self._idle_cycle[self._cycle_index]
                self._cycle_index = (self._cycle_index + 1) % len(self._idle_cycle)
                # Play the idle action animation non-looping so animation_finished can return to IDLE
                return BehaviorAction.change_state(next_state, loop=False)
            return BehaviorAction.noop()

        # 6. All other, unhandled, or unknown events are safely ignored
        logger.debug("Unhandled or ignored behavior event: %s", normalized_event)
        return BehaviorAction.noop()
