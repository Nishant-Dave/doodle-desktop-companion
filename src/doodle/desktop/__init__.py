"""Desktop window and shell components for Doodle."""

from doodle.desktop.companion_window import CompanionWindow
from doodle.desktop.positioning import (
    PositionManager,
    calculate_default_position,
    clamp_to_bounds,
    get_usable_screen_bounds,
)
from doodle.desktop.tray import DoodleTrayIcon

__all__ = [
    "CompanionWindow",
    "DoodleTrayIcon",
    "PositionManager",
    "calculate_default_position",
    "clamp_to_bounds",
    "get_usable_screen_bounds",
]
