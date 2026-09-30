"""Deterministic behavior engine coordinating events, rules, and character actions."""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QObject, QPoint, QTimer, Signal

from doodle.behavior.rules import (
    ACTION_CHANGE_STATE,
    ACTION_NOOP,
    ACTION_PLAY_ANIMATION,
    EVENT_ANIMATION_FINISHED,
    EVENT_CHARACTER_CLICKED,
    EVENT_IDLE_TIMEOUT,
    EVENT_MENU_DISMISSED,
    EVENT_MENU_OPENED,
    BehaviorAction,
    BehaviorContext,
    IdleBehaviorRules,
)
from doodle.character.character import Character
from doodle.character.state import CharacterState

logger = logging.getLogger(__name__)

# Default idle interval: 30 seconds between calm idle behaviors
DEFAULT_IDLE_INTERVAL_MS: int = 30000


class BehaviorEngine(QObject):
    """Coordinates events, evaluates deterministic behavior rules, and commands the character.

    Maintains strict boundaries:
        Event -> Behavior Engine -> Character Action -> Character -> Animation Controller

    Never directly manipulates Qt widgets, animation frames, or Windows APIs.
    """

    # Signals
    action_executed = Signal(object)  # Emits BehaviorAction
    idle_timeout = Signal()            # Emitted whenever idle interval expires

    def __init__(
        self,
        character: Optional[Character] = None,
        rules: Optional[IdleBehaviorRules] = None,
        idle_interval_ms: int = DEFAULT_IDLE_INTERVAL_MS,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._character: Optional[Character] = character
        self._rules: IdleBehaviorRules = rules or IdleBehaviorRules()
        self._idle_interval_ms: int = max(1, idle_interval_ms)

        # Context state tracking
        self._is_visible: bool = True
        self._is_menu_open: bool = False
        self._is_dragging: bool = False

        # Internal idle timer
        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(self.on_idle_timeout)

    @property
    def rules(self) -> IdleBehaviorRules:
        """Return the active rule set evaluator."""
        return self._rules

    @property
    def character(self) -> Optional[Character]:
        """Return the attached character instance, if any."""
        return self._character

    def attach_character(self, character: Optional[Character]) -> None:
        """Attach or update the character controlled by this engine."""
        self._character = character

    @property
    def idle_interval_ms(self) -> int:
        """Return the idle timeout interval in milliseconds."""
        return self._idle_interval_ms

    @idle_interval_ms.setter
    def idle_interval_ms(self, value: int) -> None:
        self._idle_interval_ms = max(1, value)
        if self._idle_timer.isActive():
            self._idle_timer.setInterval(self._idle_interval_ms)

    @property
    def is_idle_timer_active(self) -> bool:
        """Return True if the idle timer is currently running."""
        return self._idle_timer.isActive()

    @property
    def is_visible(self) -> bool:
        """Return True if companion window is currently visible."""
        return self._is_visible

    @property
    def is_menu_open(self) -> bool:
        """Return True if interaction menu is open."""
        return self._is_menu_open

    @property
    def is_dragging(self) -> bool:
        """Return True if window is being dragged."""
        return self._is_dragging

    @property
    def is_idle_eligible(self) -> bool:
        """Return True if conditions allow idle behavior timer to run."""
        return self._is_visible and not self._is_menu_open and not self._is_dragging

    def get_current_context(self) -> BehaviorContext:
        """Assemble current environmental context for rule evaluation."""
        current_state = (
            self._character.state if self._character is not None else CharacterState.IDLE
        )
        return BehaviorContext(
            current_state=current_state,
            is_visible=self._is_visible,
            is_menu_open=self._is_menu_open,
            is_dragging=self._is_dragging,
        )

    def handle_event(self, event: str, **kwargs) -> BehaviorAction:
        """Evaluate an incoming event against deterministic rules and execute the action."""
        context = self.get_current_context()
        action = self._rules.evaluate(event, context, **kwargs)

        if action.action_type != ACTION_NOOP:
            self._apply_action(action)
            self.action_executed.emit(action)

            # Manage idle timer lifecycle based on resulting state
            if action.action_type == ACTION_CHANGE_STATE and action.state is not None:
                if action.state == CharacterState.IDLE:
                    self.reset_idle_timer()
                else:
                    # Non-IDLE state (e.g. stretch, sit, sleep, attention): stop timer during action
                    self.stop_idle_timer()

        return action

    def _apply_action(self, action: BehaviorAction) -> None:
        """Send high-level action toward the Character layer."""
        if self._character is None:
            return

        if action.action_type == ACTION_CHANGE_STATE and action.state is not None:
            self._character.set_state(action.state, loop=action.loop)
        elif action.action_type == ACTION_PLAY_ANIMATION and action.animation_name is not None:
            self._character.play_animation(action.animation_name, loop=action.loop)

    def trigger_idle_timeout(self) -> BehaviorAction:
        """Manually trigger an idle timeout event (useful for tests and timers)."""
        self.idle_timeout.emit()
        return self.handle_event(EVENT_IDLE_TIMEOUT)

    def start_idle_timer(self) -> None:
        """Start the idle timer if current context permits."""
        if self.is_idle_eligible and not self._idle_timer.isActive():
            self._idle_timer.start(self._idle_interval_ms)

    def stop_idle_timer(self) -> None:
        """Stop the idle timer."""
        if self._idle_timer.isActive():
            self._idle_timer.stop()

    def reset_idle_timer(self) -> None:
        """Reset and restart the idle timer if eligible."""
        self.stop_idle_timer()
        self.start_idle_timer()

    def pause(self) -> None:
        """Pause idle behavior (e.g. when hidden in tray)."""
        self.stop_idle_timer()

    def resume(self) -> None:
        """Resume idle behavior (e.g. when shown from tray)."""
        self.reset_idle_timer()

    # Qt Slots for external lifecycle and window events

    def on_idle_timeout(self) -> None:
        """Slot invoked when internal idle timer fires."""
        self.trigger_idle_timeout()

    def on_character_clicked(self) -> None:
        """Slot invoked when companion character is clicked."""
        self.stop_idle_timer()
        self.handle_event(EVENT_CHARACTER_CLICKED)

    def on_animation_finished(self, animation_name: str) -> None:
        """Slot invoked when an animation finishes playing."""
        self.handle_event(EVENT_ANIMATION_FINISHED, animation_name=animation_name)

    def on_menu_opened(self) -> None:
        """Slot invoked when interaction menu opens."""
        self._is_menu_open = True
        self.stop_idle_timer()
        self.handle_event(EVENT_MENU_OPENED)

    def on_menu_dismissed(self) -> None:
        """Slot invoked when interaction menu is dismissed."""
        self._is_menu_open = False
        self.handle_event(EVENT_MENU_DISMISSED)
        self.start_idle_timer()

    def on_character_moved(self, _pos: Optional[QPoint] = None) -> None:
        """Slot invoked when character moves during drag."""
        self.reset_idle_timer()

    def on_drag_started(self) -> None:
        """Slot invoked when drag begins."""
        self._is_dragging = True
        self.stop_idle_timer()

    def on_drag_finished(self) -> None:
        """Slot invoked when drag ends."""
        self._is_dragging = False
        self.reset_idle_timer()

    def on_show_requested(self) -> None:
        """Slot invoked when application is shown from tray."""
        self._is_visible = True
        self.resume()

    def on_hide_requested(self) -> None:
        """Slot invoked when application is hidden in tray."""
        self._is_visible = False
        self.pause()

    def cleanup(self) -> None:
        """Clean up behavior engine resources during application shutdown."""
        self.stop_idle_timer()
