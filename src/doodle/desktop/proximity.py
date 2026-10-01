"""Cursor proximity detection and monitoring for Doodle companion window."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Optional

from PySide6.QtCore import QObject, QPoint, QRect, QTimer, Signal
from PySide6.QtGui import QCursor

if TYPE_CHECKING:
    from doodle.desktop.companion_window import CompanionWindow

logger = logging.getLogger(__name__)

DEFAULT_PROXIMITY_MARGIN: int = 50
DEFAULT_PROXIMITY_CHECK_INTERVAL_MS: int = 100


def compute_proximity_zone(
    target_rect: QRect,
    margin: int = DEFAULT_PROXIMITY_MARGIN,
) -> QRect:
    """Calculate the expanded bounding box representing the proximity zone around target_rect.

    Args:
        target_rect: Geometry rect of the target window.
        margin: Padding distance in pixels in all four directions.

    Returns:
        Expanded QRect defining the proximity boundary.
    """
    m = max(0, int(margin))
    return target_rect.adjusted(-m, -m, m, m)


def is_point_in_proximity(
    point: QPoint,
    target_rect: QRect,
    margin: int = DEFAULT_PROXIMITY_MARGIN,
) -> bool:
    """Return True if point falls within or on the boundary of the proximity zone.

    Args:
        point: Cursor position in screen coordinates.
        target_rect: Target window rectangle in screen coordinates.
        margin: Proximity padding distance in pixels.

    Returns:
        True if point is contained within the expanded proximity zone.
    """
    zone = compute_proximity_zone(target_rect, margin)
    return zone.contains(point)


class CursorProximityTracker:
    """Pure edge-triggered transition tracker for cursor proximity events."""

    def __init__(self, margin: int = DEFAULT_PROXIMITY_MARGIN) -> None:
        self._margin: int = max(0, int(margin))
        self._is_inside: bool = False

    @property
    def margin(self) -> int:
        """Return the proximity margin in pixels."""
        return self._margin

    @margin.setter
    def margin(self, value: int) -> None:
        self._margin = max(0, int(value))

    @property
    def is_inside(self) -> bool:
        """Return True if cursor was inside the proximity zone during the last update."""
        return self._is_inside

    def reset(self, initial_inside: bool = False) -> None:
        """Reset the internal tracking state.

        Args:
            initial_inside: Initial inside state. Set to True on show if cursor is
                            already inside to avoid false edge-triggering.
        """
        self._is_inside = bool(initial_inside)

    def update(self, cursor_pos: QPoint, target_rect: QRect) -> bool:
        """Update tracker with the current cursor position and target window geometry.

        Edge-triggered logic:
            outside -> inside: returns True (transition occurred)
            inside -> inside: returns False (no repeated event)
            inside -> outside: returns False (state reset)
            outside -> outside: returns False

        Args:
            cursor_pos: Current cursor position in screen coordinates.
            target_rect: Target window rectangle in screen coordinates.

        Returns:
            True if the cursor transitioned from outside into proximity; False otherwise.
        """
        in_zone = is_point_in_proximity(cursor_pos, target_rect, self._margin)

        if in_zone:
            if not self._is_inside:
                self._is_inside = True
                return True
        else:
            self._is_inside = False

        return False


class CursorProximityMonitor(QObject):
    """Monitors mouse cursor proximity to a CompanionWindow using an event-driven Qt timer.

    Emits `proximity_entered` only when the cursor crosses into the proximity zone.
    Pauses processing when the target window is hidden, closed, or being dragged.
    """

    proximity_entered = Signal()

    def __init__(
        self,
        window: CompanionWindow,
        margin: int = DEFAULT_PROXIMITY_MARGIN,
        interval_ms: int = DEFAULT_PROXIMITY_CHECK_INTERVAL_MS,
        cursor_provider: Optional[Callable[[], QPoint]] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent or window)
        self._window: CompanionWindow = window
        self._tracker = CursorProximityTracker(margin=margin)
        self._cursor_provider: Callable[[], QPoint] = cursor_provider or QCursor.pos
        self._is_enabled: bool = True

        self._timer = QTimer(self)
        self._timer.setInterval(max(10, int(interval_ms)))
        self._timer.timeout.connect(self.check_proximity)

    @property
    def margin(self) -> int:
        """Return proximity margin in pixels."""
        return self._tracker.margin

    @margin.setter
    def margin(self, value: int) -> None:
        self._tracker.margin = value

    @property
    def tracker(self) -> CursorProximityTracker:
        """Return the internal transition tracker."""
        return self._tracker

    @property
    def is_enabled(self) -> bool:
        """Return True if proximity monitoring is enabled."""
        return self._is_enabled

    @is_enabled.setter
    def is_enabled(self, value: bool) -> None:
        self._is_enabled = bool(value)
        if not self._is_enabled:
            self.stop()

    @property
    def is_active(self) -> bool:
        """Return True if the internal monitoring timer is currently active."""
        return self._timer.isActive()

    @property
    def cursor_provider(self) -> Callable[[], QPoint]:
        """Return the cursor coordinate provider function."""
        return self._cursor_provider

    @cursor_provider.setter
    def cursor_provider(self, provider: Callable[[], QPoint]) -> None:
        self._cursor_provider = provider

    def sync_inside_state(self) -> None:
        """Synchronize the tracker's inside state with current cursor location without emitting."""
        cursor_pos = self._cursor_provider()
        already_inside = is_point_in_proximity(
            cursor_pos,
            self._window.geometry(),
            self._tracker.margin,
        )
        self._tracker.reset(initial_inside=already_inside)

    def start(self) -> None:
        """Start monitoring. Primes the tracker so an already-nearby cursor doesn't trigger."""
        if not self._is_enabled:
            return

        self.sync_inside_state()

        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        """Stop proximity timer and reset state."""
        if self._timer.isActive():
            self._timer.stop()
        self._tracker.reset(initial_inside=False)

    def check_proximity(self) -> bool:
        """Sample cursor position and evaluate proximity transition.

        Returns:
            True if proximity entered event was detected and emitted; False otherwise.
        """
        if not self._is_enabled or not self._window.isVisible():
            return False

        # Suppress proximity tracking during active drag
        if getattr(self._window, "is_dragging", False):
            return False

        cursor_pos = self._cursor_provider()
        target_rect = self._window.geometry()

        entered = self._tracker.update(cursor_pos, target_rect)
        if entered:
            logger.debug("Cursor entered proximity of companion window at %s", cursor_pos)
            self.proximity_entered.emit()
            return True

        return False
