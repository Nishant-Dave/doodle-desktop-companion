"""Desktop window and shell components for Doodle."""

from doodle.desktop.companion_window import CompanionWindow
from doodle.desktop.positioning import (
    PositionManager,
    calculate_default_position,
    clamp_to_bounds,
    get_usable_screen_bounds,
)
from doodle.desktop.proximity import (
    DEFAULT_PROXIMITY_CHECK_INTERVAL_MS,
    DEFAULT_PROXIMITY_MARGIN,
    CursorProximityMonitor,
    CursorProximityTracker,
    compute_proximity_zone,
    is_point_in_proximity,
)
from doodle.desktop.tray import DoodleTrayIcon

__all__ = [
    "CompanionWindow",
    "CursorProximityMonitor",
    "CursorProximityTracker",
    "DEFAULT_PROXIMITY_CHECK_INTERVAL_MS",
    "DEFAULT_PROXIMITY_MARGIN",
    "DoodleTrayIcon",
    "PositionManager",
    "calculate_default_position",
    "clamp_to_bounds",
    "compute_proximity_zone",
    "get_usable_screen_bounds",
    "is_point_in_proximity",
]

