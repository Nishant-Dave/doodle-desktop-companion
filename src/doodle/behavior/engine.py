"""Deterministic behavior engine coordinating events, rules, and character actions."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Callable, Optional

from PySide6.QtCore import QObject, QPoint, QTimer, Signal

from doodle.activity import Activity
from doodle.behavior.rules import (
    ACTION_CHANGE_STATE,
    ACTION_NOOP,
    ACTION_PLAY_ANIMATION,
    DEFAULT_PROXIMITY_COOLDOWN_S,
    DEFAULT_QUIET_PERIOD_MS,
    DEFAULT_QUIET_PERIOD_S,
    EVENT_ANIMATION_FINISHED,
    EVENT_CAPTURE_CANCELLED,
    EVENT_CAPTURE_REQUESTED,
    EVENT_CAPTURE_SAVED,
    EVENT_CHARACTER_CLICKED,
    EVENT_CONTEXT_CHANGED,
    EVENT_CURSOR_ENTERED_PROXIMITY,
    EVENT_DRAG_RELEASED,
    EVENT_DRAG_STARTED,
    EVENT_DRAGGING,
    EVENT_IDLE_TIMEOUT,
    EVENT_MENU_DISMISSED,
    EVENT_MENU_OPENED,
    BehaviorAction,
    BehaviorContext,
    IdleBehavior,
    IdleBehaviorRules,
    IdleSelectionPolicy,
    is_behavior_available,
)
from doodle.character.character import Character
from doodle.character.mood import Mood, MoodManager
from doodle.character.state import CharacterState

if TYPE_CHECKING:
    from doodle.context.model import DesktopContext
    from doodle.context.sampler import ContextSampler

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
    activity_decided = Signal(object) # Emits Activity when an Activity is decided

    def __init__(
        self,
        character: Optional[Character] = None,
        rules: Optional[IdleBehaviorRules] = None,
        idle_interval_ms: int = DEFAULT_IDLE_INTERVAL_MS,
        quiet_period_ms: int = DEFAULT_QUIET_PERIOD_MS,
        policy: Optional[IdleSelectionPolicy] = None,
        mood_manager: Optional[MoodManager] = None,
        context_sampler: Optional[ContextSampler] = None,
        time_provider: Optional[Callable[[], float]] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._character: Optional[Character] = character
        self._rules: IdleBehaviorRules = rules or IdleBehaviorRules()
        self._idle_interval_ms: int = max(1, idle_interval_ms)
        self._quiet_period_ms: int = max(0, quiet_period_ms)
        self._context_sampler: Optional[ContextSampler] = context_sampler
        self._time_provider: Callable[[], float] = time_provider or time.monotonic
        self._last_activity: Optional[Activity] = None

        # Initialize mood manager and sync initial character mood
        self._mood_manager: MoodManager = (
            mood_manager or MoodManager(time_provider=self._time_provider)
        )
        if self._character is not None:
            self._character.set_mood(self._mood_manager.raw_mood)

        # Attach or sync policy with rules evaluator
        self._policy: Optional[IdleSelectionPolicy] = policy or self._rules.policy
        if self._policy is not None and self._rules.policy is None:
            self._rules.policy = self._policy

        # Context state tracking
        self._is_visible: bool = True
        self._is_menu_open: bool = False
        self._is_dragging: bool = False

        # Quiet period and idle timing tracking
        self._start_time: float = self._time_provider()
        self._last_interaction_time: float = float("-inf")
        self._last_autonomous_action_time: float = float("-inf")
        self._idle_start_time: float = self._start_time

        # Internal idle timer
        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(self.on_idle_timeout)

    @property
    def mood_manager(self) -> MoodManager:
        """Return the managed mood state tracker."""
        return self._mood_manager

    @property
    def mood(self) -> Mood:
        """Return the current evaluated companion mood."""
        now = self._time_provider()
        idle_duration_s = max(0.0, now - self._idle_start_time)
        return self._mood_manager.get_mood(now, idle_duration_s=idle_duration_s)

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
        if self._character is not None:
            self._character.set_mood(self.mood)

    @property
    def policy(self) -> Optional[IdleSelectionPolicy]:
        """Return the attached deterministic idle selection policy, if any."""
        return self._policy

    @policy.setter
    def policy(self, value: Optional[IdleSelectionPolicy]) -> None:
        self._policy = value
        self._rules.policy = value

    @property
    def context_sampler(self) -> Optional[ContextSampler]:
        """Return the attached context sampler coordinator, if any."""
        return self._context_sampler

    @context_sampler.setter
    def context_sampler(self, value: Optional[ContextSampler]) -> None:
        self._context_sampler = value

    @property
    def time_provider(self) -> Callable[[], float]:
        """Return the current time provider function."""
        return self._time_provider

    @time_provider.setter
    def time_provider(self, provider: Callable[[], float]) -> None:
        self._time_provider = provider
        self._mood_manager.time_provider = provider
        now = self._time_provider()
        self._start_time = now
        self._idle_start_time = now


    @property
    def quiet_period_ms(self) -> int:
        """Return the quiet period duration in milliseconds."""
        return self._quiet_period_ms

    @quiet_period_ms.setter
    def quiet_period_ms(self, value: int) -> None:
        self._quiet_period_ms = max(0, value)

    @property
    def quiet_period_s(self) -> float:
        """Return the quiet period duration in seconds."""
        return self._quiet_period_ms / 1000.0

    @property
    def is_in_quiet_period(self) -> bool:
        """Return True if currently within the quiet period following user interaction or autonomous action."""
        now = self._time_provider()
        if self._last_interaction_time != float("-inf"):
            if (now - self._last_interaction_time) * 1000.0 < self._quiet_period_ms:
                return True
        if self._last_autonomous_action_time != float("-inf"):
            if (now - self._last_autonomous_action_time) * 1000.0 < self._quiet_period_ms:
                return True
        return False

    @property
    def last_autonomous_action_time(self) -> float:
        """Return timestamp of the most recent autonomous action completion."""
        return self._last_autonomous_action_time

    def record_autonomous_action(self, timestamp: Optional[float] = None) -> None:
        """Record autonomous action completion and initiate quiet period without resetting idle progression."""
        now = timestamp if timestamp is not None else self._time_provider()
        self._last_autonomous_action_time = now

    def record_user_interaction(self, timestamp: Optional[float] = None) -> None:
        """Record meaningful user interaction and initiate quiet period."""
        now = timestamp if timestamp is not None else self._time_provider()
        self._last_interaction_time = now
        self._idle_start_time = now

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
        state_is_idle = (
            self._character is None or self._character.state == CharacterState.IDLE
        )
        return (
            self._is_visible
            and not self._is_menu_open
            and not self._is_dragging
            and state_is_idle
        )

    @property
    def last_activity(self) -> Optional[Activity]:
        """Return the most recently decided semantic Activity, if any."""
        return self._last_activity

    def decide_activity(self, event: str, **kwargs) -> Optional[Activity]:
        """Evaluate an incoming event against deterministic rules and return the semantic Activity, if any.

        This represents the pure Decision -> Activity boundary without executing the activity.
        """
        now = self._time_provider()
        idle_duration_s = max(0.0, now - self._idle_start_time)

        # 1. Update companion mood for the incoming event
        updated_mood = self._mood_manager.update_for_event(
            event,
            current_time=now,
            idle_duration_s=idle_duration_s,
            **kwargs,
        )
        if self._character is not None:
            self._character.set_mood(updated_mood)

        # 2. Assemble context and evaluate rules
        context = self.get_current_context()
        activity = self._rules.decide_activity(event, context, **kwargs)

        if activity is not None:
            self._last_activity = activity
            self.activity_decided.emit(activity)

        return activity

    def get_current_context(self) -> BehaviorContext:
        """Assemble current environmental context for rule evaluation."""
        now = self._time_provider()
        current_state = (
            self._character.state if self._character is not None else CharacterState.IDLE
        )
        current_animation = (
            self._character.current_animation_name if self._character is not None else None
        )
        idle_duration_s = max(0.0, now - self._idle_start_time)
        time_since_interaction_s = (
            max(0.0, now - self._last_interaction_time)
            if self._last_interaction_time != float("-inf")
            else float("inf")
        )
        in_quiet = self.is_in_quiet_period
        current_mood = self._mood_manager.get_mood(now, idle_duration_s=idle_duration_s)
        if self._character is not None:
            self._character.set_mood(current_mood)

        available_behaviors = None
        if self._character is not None and hasattr(self._character, "animation_controller"):
            anims = list(self._character.animation_controller._animations.keys())
            available_behaviors = [
                b for b in IdleBehavior
                if is_behavior_available(b, anims)
            ]

        desktop_ctx = (
            self._context_sampler.current_context
            if self._context_sampler is not None
            else None
        )

        return BehaviorContext(
            current_state=current_state,
            is_visible=self._is_visible,
            is_menu_open=self._is_menu_open,
            is_dragging=self._is_dragging,
            current_animation=current_animation,
            idle_duration_s=idle_duration_s,
            time_since_last_interaction_s=time_since_interaction_s,
            quiet_period_s=self._quiet_period_ms / 1000.0,
            is_in_quiet_period=in_quiet,
            current_time_s=now,
            available_behaviors=available_behaviors,
            policy=self._policy,
            mood=current_mood,
            desktop_context=desktop_ctx,
        )

    def handle_event(self, event: str, **kwargs) -> BehaviorAction:
        """Evaluate an incoming event against deterministic rules and execute the action."""
        now = self._time_provider()
        idle_duration_s = max(0.0, now - self._idle_start_time)

        # 1. Update companion mood for the incoming event
        updated_mood = self._mood_manager.update_for_event(
            event,
            current_time=now,
            idle_duration_s=idle_duration_s,
            **kwargs,
        )
        if self._character is not None:
            self._character.set_mood(updated_mood)

        # 2. Assemble context and evaluate rules
        context = self.get_current_context()
        action = self._rules.evaluate(event, context, **kwargs)

        # 3. Decision -> Activity boundary: record and emit semantic Activity if decided
        if action.activity is not None:
            self._last_activity = action.activity
            self.activity_decided.emit(action.activity)

        # 4. Compatibility execution bridge: apply action through legacy path
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
            # If character was in a non-idle state (e.g. stretch/sleep), reset state to IDLE
            if self._character.state != CharacterState.IDLE and action.animation_name in (
                "surprised", "dizzy", "curious", "playful"
            ):
                self._character.set_state(CharacterState.IDLE)
            success = self._character.play_animation(action.animation_name, loop=action.loop)
            if not success and action.animation_name in ("dizzy", "recover", "surprised", "curious"):
                self._character.set_state(CharacterState.IDLE)

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
        self.record_user_interaction()
        self.stop_idle_timer()
        self.handle_event(EVENT_CHARACTER_CLICKED)

    def on_animation_finished(self, animation_name: str) -> None:
        """Slot invoked when an animation finishes playing."""
        now = self._time_provider()
        self.handle_event(EVENT_ANIMATION_FINISHED, animation_name=animation_name)
        # Meaningful autonomous behaviors enter a minimum quiet period upon completion
        if self._policy is not None and animation_name in (
            "yawn",
            "stretch",
            "look_around",
            "curious",
            "playful",
            "sleep",
            "wake_up",
            "self_amusement",
            "recover",
        ):
            self.record_autonomous_action(now)

    def on_menu_opened(self) -> None:
        """Slot invoked when interaction menu opens."""
        self.record_user_interaction()
        self._is_menu_open = True
        self.stop_idle_timer()
        self.handle_event(EVENT_MENU_OPENED)

    def on_menu_dismissed(self) -> None:
        """Slot invoked when interaction menu is dismissed."""
        self.record_user_interaction()
        self._is_menu_open = False
        self.handle_event(EVENT_MENU_DISMISSED)
        self.start_idle_timer()

    def on_capture_requested(self) -> None:
        """Slot invoked when quick capture is requested."""
        self.record_user_interaction()
        self.stop_idle_timer()
        self.handle_event(EVENT_CAPTURE_REQUESTED)

    def on_capture_saved(self) -> None:
        """Slot invoked when quick capture is successfully saved."""
        self.record_user_interaction()
        self.handle_event(EVENT_CAPTURE_SAVED)
        self.start_idle_timer()

    def on_capture_cancelled(self) -> None:
        """Slot invoked when quick capture is dismissed without saving."""
        self.record_user_interaction()
        self.handle_event(EVENT_CAPTURE_CANCELLED)
        self.start_idle_timer()

    def on_character_moved(self, pos: Optional[QPoint] = None) -> None:
        """Slot invoked when character moves during drag or positioning."""
        if self._is_dragging:
            self.on_dragging(pos)
        else:
            self.record_user_interaction()
            self.reset_idle_timer()

    def on_drag_started(self) -> None:
        """Slot invoked when drag begins."""
        self.record_user_interaction()
        self._is_dragging = True
        self.stop_idle_timer()
        self.handle_event(EVENT_DRAG_STARTED)

    def on_dragging(self, pos: Optional[QPoint] = None) -> None:
        """Slot invoked during active dragging."""
        self.record_user_interaction()
        self.handle_event(EVENT_DRAGGING, pos=pos)

    def on_drag_released(self) -> None:
        """Slot invoked when drag concludes."""
        self.record_user_interaction()
        self._is_dragging = False
        self.handle_event(EVENT_DRAG_RELEASED)
        self.reset_idle_timer()

    on_drag_finished = on_drag_released

    def on_show_requested(self) -> None:
        """Slot invoked when application is shown from tray."""
        self._is_visible = True
        if self._policy is not None:
            self.record_user_interaction()
        self.resume()


    def on_hide_requested(self) -> None:
        """Slot invoked when application is hidden in tray."""
        self._is_visible = False
        self.pause()

    def on_cursor_entered_proximity(self) -> BehaviorAction:
        """Slot invoked when cursor crosses into window proximity zone."""
        action = self.handle_event(EVENT_CURSOR_ENTERED_PROXIMITY)
        if action.action_type != ACTION_NOOP:
            # Meaningful reaction to user cursor proximity counts as user interaction
            self.record_user_interaction()
        return action

    def on_context_changed(self, context: DesktopContext) -> BehaviorAction:
        """Slot invoked when meaningful desktop context transition occurs."""
        return self.handle_event(EVENT_CONTEXT_CHANGED, desktop_context=context)

    def cleanup(self) -> None:
        """Clean up behavior engine resources during application shutdown."""
        self.stop_idle_timer()

