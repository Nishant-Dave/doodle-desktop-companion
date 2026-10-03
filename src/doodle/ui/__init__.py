"""User interface package for Doodle desktop companion."""

from doodle.ui.interaction_menu import (
    AVAILABLE_ACTIONS,
    InteractionMenu,
    compute_menu_position,
)
from doodle.ui.quick_capture import (
    DEFAULT_CAPTURE_HEIGHT,
    DEFAULT_CAPTURE_WIDTH,
    QuickCaptureCard,
)
from doodle.ui.recent_captures import (
    DEFAULT_RECENT_LIMIT,
    DEFAULT_TIMELINE_HEIGHT,
    DEFAULT_TIMELINE_WIDTH,
    RecentCapturesPanel,
    format_capture_timestamp,
    format_capture_type,
)

__all__ = [
    "AVAILABLE_ACTIONS",
    "DEFAULT_CAPTURE_HEIGHT",
    "DEFAULT_CAPTURE_WIDTH",
    "DEFAULT_RECENT_LIMIT",
    "DEFAULT_TIMELINE_HEIGHT",
    "DEFAULT_TIMELINE_WIDTH",
    "InteractionMenu",
    "QuickCaptureCard",
    "RecentCapturesPanel",
    "compute_menu_position",
    "format_capture_timestamp",
    "format_capture_type",
]
