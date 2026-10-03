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

__all__ = [
    "AVAILABLE_ACTIONS",
    "DEFAULT_CAPTURE_HEIGHT",
    "DEFAULT_CAPTURE_WIDTH",
    "InteractionMenu",
    "QuickCaptureCard",
    "compute_menu_position",
]
