"""Deterministic 2D spatial movement calculation primitive for Doodle.

Provides step-driven vector interpolation, screen boundary clamping, and
completion/interruption tracking for physical companion relocation.

Per Architecture v2:
- Task 25 establishes physical movement mechanics only.
- MovementPrimitive is a pure spatial calculator, completely separate from
  Activity, ActivityExecutor, CharacterState, and Animation.
- Movement coordinates operate in Windows screen pixels (QPoint).
- Screen clamping reuses the existing positioning.py infrastructure.
- Autonomous movement is strictly independent of user-initiated mouse dragging.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Union

from PySide6.QtCore import QPoint, QRect, QSize

from doodle.desktop.positioning import clamp_to_bounds

logger = logging.getLogger(__name__)

DEFAULT_MOVEMENT_SPEED_PX_PER_S: float = 120.0


class MovementStatus(Enum):
    """Lifecycle states of the movement primitive."""

    IDLE = "IDLE"
    MOVING = "MOVING"
    REACHED = "REACHED"
    INTERRUPTED = "INTERRUPTED"


@dataclass(frozen=True)
class MovementDirection:
    """Normalized 2D direction vector."""

    dx: float = 0.0
    dy: float = 0.0

    @property
    def is_facing_left(self) -> bool:
        """Return True if direction has a significant leftward component."""
        return self.dx < -0.1

    @property
    def is_facing_right(self) -> bool:
        """Return True if direction has a significant rightward component."""
        return self.dx > 0.1


class MovementPrimitive:
    """Deterministic 2D spatial movement calculator.

    Maintains current, start, and target coordinates, and advances position
    along a straight-line vector with respect to elapsed delta time (dt).

    Internal coordinates are tracked as floats to prevent cumulative rounding
    drift during fractional sub-pixel stepping, while public positions are
    emitted as rounded QPoint coordinates.
    """

    def __init__(
        self,
        speed_px_per_s: float = DEFAULT_MOVEMENT_SPEED_PX_PER_S,
        bounds_provider: Optional[Union[Callable[[], QRect], QRect]] = None,
        window_size: Optional[QSize] = None,
        initial_position: Optional[QPoint] = None,
    ) -> None:
        """Initialize movement primitive.

        Args:
            speed_px_per_s: Movement speed in pixels per second. Must be positive.
            bounds_provider: Optional callable returning usable QRect bounds,
                or a static QRect instance, used to clamp targets and trajectory.
            window_size: Optional QSize of the companion window, used for clamping.
            initial_position: Optional initial QPoint position (default 0, 0).

        Raises:
            ValueError: If speed_px_per_s is non-positive.
        """
        if speed_px_per_s <= 0.0:
            raise ValueError(f"speed_px_per_s must be positive, got {speed_px_per_s}")

        self._speed_px_per_s: float = float(speed_px_per_s)
        self._bounds_provider: Optional[Callable[[], QRect]] = (
            (lambda: bounds_provider)
            if isinstance(bounds_provider, QRect)
            else bounds_provider
        )
        self._window_size: Optional[QSize] = (
            QSize(window_size) if window_size is not None else None
        )

        init_pos = initial_position or QPoint(0, 0)
        self._current_x: float = float(init_pos.x())
        self._current_y: float = float(init_pos.y())
        self._start_position: Optional[QPoint] = QPoint(init_pos)
        self._target_position: Optional[QPoint] = None
        self._status: MovementStatus = MovementStatus.IDLE
        self._direction: MovementDirection = MovementDirection(0.0, 0.0)
        self._remaining_distance: float = 0.0

    @property
    def speed_px_per_s(self) -> float:
        """Return the movement speed in pixels per second."""
        return self._speed_px_per_s

    @speed_px_per_s.setter
    def speed_px_per_s(self, value: float) -> None:
        """Update movement speed. Must be positive."""
        if value <= 0.0:
            raise ValueError(f"speed_px_per_s must be positive, got {value}")
        self._speed_px_per_s = float(value)

    @property
    def window_size(self) -> Optional[QSize]:
        """Return the window size used for clamping, if configured."""
        return QSize(self._window_size) if self._window_size is not None else None

    @window_size.setter
    def window_size(self, size: Optional[QSize]) -> None:
        self._window_size = QSize(size) if size is not None else None

    @property
    def current_position(self) -> QPoint:
        """Return the current desktop position as an integer QPoint."""
        return QPoint(round(self._current_x), round(self._current_y))

    @property
    def start_position(self) -> Optional[QPoint]:
        """Return the starting position of the current movement segment."""
        return QPoint(self._start_position) if self._start_position is not None else None

    @property
    def target_position(self) -> Optional[QPoint]:
        """Return the active target destination as an integer QPoint, if set."""
        return QPoint(self._target_position) if self._target_position is not None else None

    @property
    def status(self) -> MovementStatus:
        """Return the current movement status."""
        return self._status

    @property
    def is_moving(self) -> bool:
        """Return True if currently executing active movement toward target."""
        return self._status == MovementStatus.MOVING

    @property
    def has_reached_target(self) -> bool:
        """Return True if movement successfully arrived at the target position."""
        return self._status == MovementStatus.REACHED

    @property
    def is_interrupted(self) -> bool:
        """Return True if movement was halted prior to reaching the target."""
        return self._status == MovementStatus.INTERRUPTED

    @property
    def direction(self) -> MovementDirection:
        """Return the normalized movement direction vector."""
        return self._direction

    @property
    def remaining_distance(self) -> float:
        """Return Euclidean distance remaining to the active target."""
        return self._remaining_distance

    def _get_current_bounds(self) -> Optional[QRect]:
        """Query usable screen bounds if provider is configured."""
        if self._bounds_provider is not None:
            bounds = self._bounds_provider()
            if bounds is not None and bounds.isValid() and not bounds.isEmpty():
                return bounds
        return None

    def _clamp_point(self, point: QPoint) -> QPoint:
        """Clamp a point to screen bounds using existing positioning infrastructure."""
        bounds = self._get_current_bounds()
        if bounds is not None:
            win_size = self._window_size or QSize(0, 0)
            return clamp_to_bounds(point, win_size, bounds)
        return QPoint(point)

    def set_target(
        self,
        target: QPoint,
        start: Optional[QPoint] = None,
    ) -> None:
        """Set or replace movement target and begin trajectory calculation.

        If start is provided, sets current position to start. Otherwise continues
        from the current position.
        The target coordinate is clamped to usable screen bounds if configured.

        Args:
            target: The destination desktop coordinate (QPoint).
            start: Optional explicit starting coordinate (QPoint).
        """
        if start is not None:
            clamped_start = self._clamp_point(start)
            self._current_x = float(clamped_start.x())
            self._current_y = float(clamped_start.y())
            self._start_position = QPoint(clamped_start)
        else:
            self._start_position = self.current_position

        clamped_target = self._clamp_point(target)
        self._target_position = QPoint(clamped_target)

        dx = float(clamped_target.x()) - self._current_x
        dy = float(clamped_target.y()) - self._current_y
        distance = math.hypot(dx, dy)
        self._remaining_distance = distance

        if distance <= 1e-6:
            # Already at the target position
            self._direction = MovementDirection(0.0, 0.0)
            self._current_x = float(clamped_target.x())
            self._current_y = float(clamped_target.y())
            self._remaining_distance = 0.0
            self._status = MovementStatus.REACHED
        else:
            self._direction = MovementDirection(dx / distance, dy / distance)
            self._status = MovementStatus.MOVING

        logger.debug(
            "Movement target set: from (%s) to (%s), distance=%.2f, dir=(%.2f, %.2f)",
            self.current_position,
            self._target_position,
            self._remaining_distance,
            self._direction.dx,
            self._direction.dy,
        )

    def step(self, dt_s: float) -> QPoint:
        """Advance position toward the target by elapsed time dt_s seconds.

        If remaining distance <= step distance, arrives exactly at target and
        transitions status to REACHED.
        Does not overshoot.
        If status is not MOVING, position is preserved without modification.

        Args:
            dt_s: Elapsed delta time in seconds. Must be non-negative.

        Returns:
            The updated current position as a QPoint.

        Raises:
            ValueError: If dt_s is negative.
        """
        if dt_s < 0.0:
            raise ValueError(f"dt_s cannot be negative, got {dt_s}")

        if self._status != MovementStatus.MOVING or self._target_position is None:
            return self.current_position

        if dt_s == 0.0:
            return self.current_position

        step_distance = self._speed_px_per_s * dt_s

        if self._remaining_distance <= step_distance:
            # Arrival at target (no overshoot)
            self._current_x = float(self._target_position.x())
            self._current_y = float(self._target_position.y())
            self._remaining_distance = 0.0
            self._status = MovementStatus.REACHED
            logger.debug("Movement reached target: %s", self.current_position)
            return self.current_position

        # Advance along direction vector
        self._current_x += self._direction.dx * step_distance
        self._current_y += self._direction.dy * step_distance

        # Apply screen clamping during transit if configured
        bounds = self._get_current_bounds()
        if bounds is not None:
            clamped = clamp_to_bounds(
                self.current_position,
                self._window_size or QSize(0, 0),
                bounds,
            )
            self._current_x = float(clamped.x())
            self._current_y = float(clamped.y())

        # Recalculate remaining distance to target
        dx = float(self._target_position.x()) - self._current_x
        dy = float(self._target_position.y()) - self._current_y
        self._remaining_distance = math.hypot(dx, dy)

        if self._remaining_distance <= 1e-6:
            self._current_x = float(self._target_position.x())
            self._current_y = float(self._target_position.y())
            self._remaining_distance = 0.0
            self._status = MovementStatus.REACHED

        return self.current_position

    def interrupt(self) -> None:
        """Halt active movement immediately, preserving current position.

        Sets status to INTERRUPTED. No further movement occurs until a new
        target is set or reset() is called.
        """
        if self._status == MovementStatus.MOVING:
            self._status = MovementStatus.INTERRUPTED
            logger.debug("Movement interrupted at: %s", self.current_position)

    def reset(self, position: Optional[QPoint] = None) -> None:
        """Reset state to IDLE at current or specified coordinate.

        Args:
            position: Optional coordinate to establish as current position.
        """
        if position is not None:
            clamped = self._clamp_point(position)
            self._current_x = float(clamped.x())
            self._current_y = float(clamped.y())
            self._start_position = QPoint(clamped)
        else:
            self._start_position = self.current_position

        self._target_position = None
        self._remaining_distance = 0.0
        self._direction = MovementDirection(0.0, 0.0)
        self._status = MovementStatus.IDLE
        logger.debug("Movement reset to IDLE at: %s", self.current_position)

    def __repr__(self) -> str:
        return (
            f"MovementPrimitive(pos={self.current_position}, "
            f"target={self._target_position}, status={self._status.value}, "
            f"speed={self._speed_px_per_s})"
        )
