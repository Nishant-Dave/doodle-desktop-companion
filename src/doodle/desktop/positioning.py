"""Screen boundary and desktop positioning logic for Doodle."""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtGui import QGuiApplication, QScreen

DEFAULT_SCREEN_MARGIN: int = 24
FALLBACK_SCREEN_BOUNDS = QRect(0, 0, 1920, 1080)


def get_usable_screen_bounds(screen: Optional[QScreen] = None) -> QRect:
    """Retrieve the available screen geometry (accounting for taskbars/dock areas)."""
    target_screen = screen or QGuiApplication.primaryScreen()
    if target_screen is not None:
        geom = target_screen.availableGeometry()
        if geom.isValid() and not geom.isEmpty():
            return geom
    return QRect(FALLBACK_SCREEN_BOUNDS)


def clamp_to_bounds(position: QPoint, window_size: QSize, bounds: QRect) -> QPoint:
    """Clamp a top-left window position so the window remains within the given bounds.

    Handles left, right, top, and bottom screen boundaries safely, including oversized
    windows or invalid bounds.
    """
    if not bounds.isValid() or bounds.isEmpty():
        return QPoint(position)

    # Calculate horizontal limits
    min_x = bounds.x()
    max_x = bounds.x() + bounds.width() - window_size.width()
    if max_x < min_x:
        clamped_x = min_x
    else:
        clamped_x = max(min_x, min(position.x(), max_x))

    # Calculate vertical limits
    min_y = bounds.y()
    max_y = bounds.y() + bounds.height() - window_size.height()
    if max_y < min_y:
        clamped_y = min_y
    else:
        clamped_y = max(min_y, min(position.y(), max_y))

    return QPoint(clamped_x, clamped_y)


def calculate_default_position(
    window_size: QSize,
    bounds: QRect,
    margin: int = DEFAULT_SCREEN_MARGIN,
) -> QPoint:
    """Calculate the default position in the bottom-right corner with margin."""
    target_x = bounds.x() + bounds.width() - window_size.width() - margin
    target_y = bounds.y() + bounds.height() - window_size.height() - margin
    return clamp_to_bounds(QPoint(target_x, target_y), window_size, bounds)


class PositionManager:
    """Coordinates window positioning and screen-boundary clamping."""

    def __init__(
        self,
        window_size: QSize,
        initial_position: Optional[QPoint] = None,
        screen_bounds_provider: Optional[Callable[[], QRect]] = None,
    ) -> None:
        self._window_size = QSize(window_size)
        self._screen_bounds_provider = screen_bounds_provider
        self._position = (
            QPoint(initial_position) if initial_position is not None else QPoint(0, 0)
        )

    @property
    def window_size(self) -> QSize:
        """Return the tracked window size."""
        return self._window_size

    def set_window_size(self, size: QSize) -> None:
        """Update tracked window size."""
        self._window_size = QSize(size)

    def get_position(self) -> QPoint:
        """Return the current desktop position."""
        return QPoint(self._position)

    def set_position(self, position: QPoint) -> QPoint:
        """Set, clamp, and store the position, returning the clamped coordinate."""
        self._position = self.clamp_to_screen(position)
        return QPoint(self._position)

    def get_usable_bounds(self) -> QRect:
        """Return the current usable screen bounds."""
        if self._screen_bounds_provider is not None:
            return self._screen_bounds_provider()
        return get_usable_screen_bounds()

    def clamp_to_screen(self, position: QPoint) -> QPoint:
        """Clamp a position to the usable screen boundary."""
        bounds = self.get_usable_bounds()
        return clamp_to_bounds(position, self._window_size, bounds)

    def get_default_position(self, margin: int = DEFAULT_SCREEN_MARGIN) -> QPoint:
        """Compute the sensible initial default position on the screen."""
        bounds = self.get_usable_bounds()
        return calculate_default_position(self._window_size, bounds, margin=margin)
