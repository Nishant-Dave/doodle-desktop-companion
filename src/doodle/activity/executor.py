"""Activity execution boundary for the Doodle companion.

Coordinates the lifecycle of companion activities (start, complete,
interrupt, cancel) as a pure execution boundary.

Per Architecture v2:
- Behavior/Decision decides WHAT Doodle wants to do.
- Activity represents WHAT Doodle is doing over time.
- ActivityExecutor manages whether and which Activity is actively executing.
- Future execution systems (Task 24+) will handle physical realization
  (animation clips, coordinate translation, transitions).

This module is strictly independent of PySide6, UI, and animation systems.
"""

from __future__ import annotations

import logging
from typing import Optional, Protocol, runtime_checkable

from doodle.activity.model import Activity
from doodle.activity.types import ActivityLifecycleState

logger = logging.getLogger(__name__)


class ActivityExecutionError(Exception):
    """Raised when an invalid or prohibited activity execution lifecycle operation occurs."""


@runtime_checkable
class ActivityExecutionTarget(Protocol):
    """Protocol for targets capable of physically realizing an Activity.

    Per Architecture v2:
    - ActivityExecutor manages lifecycle transitions.
    - ActivityExecutionTarget receives commands to physically begin,
      interrupt, or cancel realization of an Activity.
    - Natural completion is reported back toward the executor via the
      composition/integration boundary (e.g., Qt animation signals),
      not commanded downward to the target.
    """

    def perform_activity(self, activity: Activity) -> None:
        """Physically begin realizing the given activity."""
        ...

    def interrupt_activity(self, activity: Activity) -> None:
        """Physically abort the active activity and safely recover to a neutral state."""
        ...

    def cancel_activity(self, activity: Activity) -> None:
        """Physically abort the active activity immediately without graceful recovery."""
        ...


class ActivityExecutor:
    """Manages the execution lifecycle of a single active companion Activity.

    Core lifecycle rules:
    - Exactly one Activity may be active (executing) at a time.
    - Starting an Activity transitions its state to RUNNING and sets current_activity.
    - If another Activity is already executing:
        - If the active Activity is interruptible, it is automatically interrupted
          (state -> INTERRUPTED) and replaced by the new Activity.
        - If the active Activity is non-interruptible, replacement is rejected
          with an ActivityExecutionError, preserving the active activity.
    - Completing an active Activity transitions its state to COMPLETED and clears current_activity.
    - Interrupting an active Activity transitions its state to INTERRUPTED and clears current_activity.
    - Cancelling an active Activity transitions its state to CANCELLED and clears current_activity.
    - Attempting to complete, interrupt, or cancel when no Activity is executing raises ActivityExecutionError.
    """

    def __init__(self, target: Optional[ActivityExecutionTarget] = None) -> None:
        self._current_activity: Optional[Activity] = None
        self._target: Optional[ActivityExecutionTarget] = target

    @property
    def target(self) -> Optional[ActivityExecutionTarget]:
        """Return the attached activity execution target, if any."""
        return self._target

    @property
    def current_activity(self) -> Optional[Activity]:
        """Return the currently executing Activity, or None if idle."""
        return self._current_activity

    @property
    def is_executing(self) -> bool:
        """Return True if an Activity is currently executing."""
        return self._current_activity is not None

    def start(self, activity: Activity) -> Activity:
        """Start executing an Activity.

        If another Activity is active and interruptible, it is interrupted and replaced.
        If another Activity is active and non-interruptible, raises ActivityExecutionError.

        Args:
            activity: The Activity instance to start.

        Returns:
            The newly executing Activity with lifecycle_state set to RUNNING.

        Raises:
            TypeError: If activity is not an Activity instance.
            ActivityExecutionError: If activity is already executing, or in a terminal state,
                or if current activity is non-interruptible.
        """
        if not isinstance(activity, Activity):
            raise TypeError(f"Expected an Activity instance, got {type(activity).__name__}")

        if activity is self._current_activity:
            raise ActivityExecutionError(
                f"Activity '{activity.activity_id}' is already executing."
            )

        if activity.lifecycle_state in (
            ActivityLifecycleState.COMPLETED,
            ActivityLifecycleState.INTERRUPTED,
            ActivityLifecycleState.CANCELLED,
        ):
            raise ActivityExecutionError(
                f"Cannot start activity '{activity.activity_id}' in terminal state {activity.lifecycle_state.value}."
            )

        # Handle active activity replacement
        if self._current_activity is not None:
            if not self._current_activity.interruptible:
                raise ActivityExecutionError(
                    f"Cannot replace active non-interruptible activity '{self._current_activity.activity_id}'."
                )
            # Auto-interrupt the previous interruptible activity
            self.interrupt()

        activity.lifecycle_state = ActivityLifecycleState.RUNNING
        self._current_activity = activity
        if self._target is not None:
            self._target.perform_activity(activity)
        logger.debug("Started executing activity: %s", activity.activity_id)
        return activity

    def complete(self, activity: Optional[Activity] = None) -> Activity:
        """Complete the currently executing Activity.

        Args:
            activity: Optional expected Activity instance to verify before completing.

        Returns:
            The completed Activity with lifecycle_state set to COMPLETED.

        Raises:
            ActivityExecutionError: If no Activity is executing, or if activity does not match.
        """
        if self._current_activity is None:
            raise ActivityExecutionError("No active activity to complete.")

        if activity is not None and activity is not self._current_activity:
            raise ActivityExecutionError(
                f"Activity '{activity.activity_id}' is not currently executing."
            )

        completed = self._current_activity
        completed.lifecycle_state = ActivityLifecycleState.COMPLETED
        self._current_activity = None
        # Note: complete() does NOT call target; completion notification flows
        # from physical realization upward via the composition boundary.
        logger.debug("Completed activity: %s", completed.activity_id)
        return completed

    def interrupt(self, activity: Optional[Activity] = None) -> Activity:
        """Interrupt the currently executing Activity.

        Args:
            activity: Optional expected Activity instance to verify before interrupting.

        Returns:
            The interrupted Activity with lifecycle_state set to INTERRUPTED.

        Raises:
            ActivityExecutionError: If no Activity is executing, or activity does not match,
                or active activity is non-interruptible.
        """
        if self._current_activity is None:
            raise ActivityExecutionError("No active activity to interrupt.")

        if activity is not None and activity is not self._current_activity:
            raise ActivityExecutionError(
                f"Activity '{activity.activity_id}' is not currently executing."
            )

        if not self._current_activity.interruptible:
            raise ActivityExecutionError(
                f"Cannot interrupt non-interruptible activity '{self._current_activity.activity_id}'."
            )

        interrupted = self._current_activity
        interrupted.lifecycle_state = ActivityLifecycleState.INTERRUPTED
        self._current_activity = None
        if self._target is not None:
            self._target.interrupt_activity(interrupted)
        logger.debug("Interrupted activity: %s", interrupted.activity_id)
        return interrupted

    def cancel(self, activity: Optional[Activity] = None) -> Activity:
        """Cancel the currently executing Activity.

        Cancellation is an external abort operation and terminates the activity
        regardless of its interruptibility setting.

        Args:
            activity: Optional expected Activity instance to verify before cancelling.

        Returns:
            The cancelled Activity with lifecycle_state set to CANCELLED.

        Raises:
            ActivityExecutionError: If no Activity is executing, or activity does not match.
        """
        if self._current_activity is None:
            raise ActivityExecutionError("No active activity to cancel.")

        if activity is not None and activity is not self._current_activity:
            raise ActivityExecutionError(
                f"Activity '{activity.activity_id}' is not currently executing."
            )

        cancelled = self._current_activity
        cancelled.lifecycle_state = ActivityLifecycleState.CANCELLED
        self._current_activity = None
        if self._target is not None:
            self._target.cancel_activity(cancelled)
        logger.debug("Cancelled activity: %s", cancelled.activity_id)
        return cancelled

    def __repr__(self) -> str:
        current_id = self._current_activity.activity_id if self._current_activity else None
        return f"ActivityExecutor(current_activity={current_id!r}, is_executing={self.is_executing})"
