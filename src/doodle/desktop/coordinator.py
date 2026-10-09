"""Runtime execution coordinator driving continuous physical Activity execution.

Coordinates between ActivityExecutor and DesktopActivityPerformer:
- Owns a single on-demand QTimer (~20 ms / 50 Hz).
- Runs the timer ONLY while continuous physical progression is required.
- Calculates measured elapsed delta time (dt_s) via QElapsedTimer clamped to MAX_DELTA_TIME_S.
- Drives DesktopActivityPerformer.tick(dt_s).
- Propagates natural arrival completion upward to ActivityExecutor.complete().
- Stops timer immediately on completion, interruption, cancellation, or shutdown.
- Provides a deterministic step(dt_s) method for testing without QTimer or wall-clock dependencies.
- Keeps ActivityExecutor pure Python (zero Qt imports).
- Keeps DesktopActivityPerformer.tick(dt_s) deterministic.
- Remains independent of specific ActivityTypes (no hard-coded WALK/REST/SLEEP rules).
"""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QElapsedTimer, QObject, QPoint, QTimer, Signal

from doodle.activity.executor import ActivityExecutor
from doodle.activity.model import Activity
from doodle.desktop.performer import DesktopActivityPerformer

logger = logging.getLogger(__name__)

DEFAULT_TICK_INTERVAL_MS: int = 20  # ~50 Hz update rate
MAX_DELTA_TIME_S: float = 0.1       # 100 ms maximum clamp per step


class ActivityExecutionCoordinator(QObject):
    """Runtime coordinator driving continuous physical Activity progression.

    Bridges the pure-Python ActivityExecutor lifecycle with the Qt-based
    DesktopActivityPerformer, owning a single QTimer that ticks only while continuous
    physical movement is actively executing.
    """

    activity_completed = Signal(Activity)
    activity_interrupted = Signal(Activity)
    activity_cancelled = Signal(Activity)
    ticked = Signal(QPoint)
    progression_started = Signal()
    progression_stopped = Signal()

    def __init__(
        self,
        executor: ActivityExecutor,
        performer: DesktopActivityPerformer,
        tick_interval_ms: int = DEFAULT_TICK_INTERVAL_MS,
        max_delta_time_s: float = MAX_DELTA_TIME_S,
        parent: Optional[QObject] = None,
        clock: Optional[QElapsedTimer] = None,
    ) -> None:
        """Initialize the execution coordinator with an executor and performer.

        Args:
            executor: Lifecycle manager for Activities.
            performer: Physical realization coordinator at desktop layer.
            tick_interval_ms: Timer tick interval in milliseconds (~20 ms for ~50 Hz).
            max_delta_time_s: Maximum delta time clamped per step (default 0.1s).
            parent: Optional Qt parent object.
            clock: Optional QElapsedTimer instance for elapsed time calculation.

        Raises:
            TypeError: If executor or performer is None.
            ValueError: If tick_interval_ms or max_delta_time_s is not positive.
        """
        super().__init__(parent)

        if executor is None:
            raise TypeError("executor must not be None")
        if performer is None:
            raise TypeError("performer must not be None")
        if tick_interval_ms <= 0:
            raise ValueError(f"tick_interval_ms must be positive, got {tick_interval_ms}")
        if max_delta_time_s <= 0.0:
            raise ValueError(f"max_delta_time_s must be positive, got {max_delta_time_s}")

        self._executor: ActivityExecutor = executor
        self._performer: DesktopActivityPerformer = performer
        self._interval_ms: int = tick_interval_ms
        self._max_dt_s: float = float(max_delta_time_s)

        # Single runtime execution timer (inactive until continuous execution starts)
        self._timer: QTimer = QTimer(self)
        self._timer.setInterval(self._interval_ms)
        self._timer.timeout.connect(self._on_timeout)

        # Elapsed time measurement clock
        self._clock: QElapsedTimer = clock if clock is not None else QElapsedTimer()

        # Connect performer upward completion signals
        self._performer.activity_completed.connect(self._on_activity_completed)
        self._performer.activity_interrupted.connect(self._on_activity_interrupted)
        self._performer.activity_cancelled.connect(self._on_activity_cancelled)

    @property
    def executor(self) -> ActivityExecutor:
        """Return the attached ActivityExecutor."""
        return self._executor

    @property
    def performer(self) -> DesktopActivityPerformer:
        """Return the attached DesktopActivityPerformer."""
        return self._performer

    @property
    def is_running(self) -> bool:
        """Return True if the runtime execution timer is currently active."""
        return self._timer.isActive()

    @property
    def tick_interval_ms(self) -> int:
        """Return the timer tick interval in milliseconds."""
        return self._interval_ms

    @property
    def max_delta_time_s(self) -> float:
        """Return the maximum clamped delta time in seconds."""
        return self._max_dt_s

    @property
    def is_progression_required(self) -> bool:
        """Return True if continuous physical progression is currently required.

        Generic eligibility check that inspects target progression state without
        hard-coding specific ActivityTypes.
        """
        if hasattr(self._performer, "is_progression_active"):
            return bool(self._performer.is_progression_active)
        if hasattr(self._performer, "is_walking"):
            return bool(self._performer.is_walking)
        return False

    def start_activity(self, activity: Activity) -> Activity:
        """Start an activity via the executor and initiate runtime progression if needed.

        Args:
            activity: The Activity instance to start.

        Returns:
            The newly executing Activity.
        """
        started = self._executor.start(activity)
        self.sync_progression()
        return started

    def sync_progression(self) -> bool:
        """Synchronize timer state with current performer execution requirements.

        Returns:
            True if continuous progression is active and running, False otherwise.
        """
        if self.is_progression_required:
            self.start()
            return True
        else:
            self.stop()
            return False

    def start(self) -> None:
        """Start continuous runtime timer ticking if progression is required."""
        if not self._timer.isActive() and self.is_progression_required:
            self._clock.restart()
            self._timer.start(self._interval_ms)
            logger.debug("ActivityExecutionCoordinator timer started (%d ms).", self._interval_ms)
            self.progression_started.emit()

    def stop(self) -> None:
        """Stop continuous runtime timer ticking."""
        if self._timer.isActive():
            self._timer.stop()
            logger.debug("ActivityExecutionCoordinator timer stopped.")
            self.progression_stopped.emit()

    def cleanup(self) -> None:
        """Stop ticking and clean up resources on application shutdown."""
        self.stop()

    def step(self, dt_s: float, clamp: bool = False) -> Optional[QPoint]:
        """Advance physical execution by explicit dt_s seconds.

        Deterministic progression method for unit testing and timer dispatch.
        Does not depend on real-time delays.

        Args:
            dt_s: Time step in seconds. Must be non-negative.
            clamp: If True, clamps dt_s to max_delta_time_s. Defaults to False
                for deterministic unit testing.

        Returns:
            Updated coordinate from performer, or None if no progression occurred.

        Raises:
            ValueError: If dt_s is negative.
        """
        if dt_s < 0.0:
            raise ValueError(f"dt_s cannot be negative, got {dt_s}")

        effective_dt_s = min(dt_s, self._max_dt_s) if clamp else dt_s
        pos = self._performer.tick(effective_dt_s)
        if pos is not None:
            self.ticked.emit(pos)
        return pos

    def _on_timeout(self) -> None:
        """Handle runtime timer tick using measured elapsed time."""
        if not self.is_progression_required:
            self.stop()
            return

        if not self._clock.isValid():
            self._clock.restart()
            return

        elapsed_ns = self._clock.nsecsElapsed()
        self._clock.restart()

        dt_s = min(elapsed_ns / 1_000_000_000.0, self._max_dt_s)
        self.step(dt_s)

    def _on_activity_completed(self, activity: Activity) -> None:
        """Slot invoked when performer signals completion."""
        self.stop()
        if self._executor.is_executing and self._executor.current_activity is activity:
            try:
                self._executor.complete(activity)
            except Exception as exc:
                logger.warning(
                    "Error completing activity '%s' in executor: %s",
                    activity.activity_id,
                    exc,
                )
        self.activity_completed.emit(activity)

    def _on_activity_interrupted(self, activity: Activity) -> None:
        """Slot invoked when performer signals interruption."""
        self.stop()
        self.activity_interrupted.emit(activity)

    def _on_activity_cancelled(self, activity: Activity) -> None:
        """Slot invoked when performer signals cancellation."""
        self.stop()
        self.activity_cancelled.emit(activity)

    def __repr__(self) -> str:
        return (
            f"ActivityExecutionCoordinator(running={self.is_running}, "
            f"interval_ms={self._interval_ms}, "
            f"progression_required={self.is_progression_required})"
        )
