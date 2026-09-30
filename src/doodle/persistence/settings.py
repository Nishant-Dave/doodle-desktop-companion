"""Lightweight desktop settings persistence for Doodle using QSettings."""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QPoint, QSettings

logger = logging.getLogger(__name__)

KEY_WINDOW_POSITION: str = "window/position"
KEY_WINDOW_POSITION_X: str = "window/position/x"
KEY_WINDOW_POSITION_Y: str = "window/position/y"


class SettingsManager:
    """Manages reading and writing application preferences via QSettings."""

    def __init__(self, settings: Optional[QSettings] = None) -> None:
        if settings is not None:
            self._settings = settings
        else:
            self._settings = QSettings("Doodle", "Doodle")

    @property
    def settings(self) -> QSettings:
        """Return the underlying QSettings instance."""
        return self._settings

    def load_window_position(self) -> Optional[QPoint]:
        """Load the saved window position, or None if not saved or invalid."""
        # 1. Check primary key: window/position
        if self._settings.contains(KEY_WINDOW_POSITION):
            raw_val = self._settings.value(KEY_WINDOW_POSITION)
            if isinstance(raw_val, QPoint):
                return QPoint(raw_val)
            if isinstance(raw_val, (list, tuple)) and len(raw_val) >= 2:
                try:
                    return QPoint(int(raw_val[0]), int(raw_val[1]))
                except (ValueError, TypeError):
                    pass
            if isinstance(raw_val, str):
                import re
                nums = re.findall(r"-?\d+", raw_val)
                if len(nums) >= 2:
                    try:
                        return QPoint(int(nums[0]), int(nums[1]))
                    except (ValueError, TypeError):
                        pass

        # 2. Check coordinate keys: window/position/x and window/position/y
        has_x = self._settings.contains(KEY_WINDOW_POSITION_X)
        has_y = self._settings.contains(KEY_WINDOW_POSITION_Y)

        if has_x and has_y:
            raw_x = self._settings.value(KEY_WINDOW_POSITION_X)
            raw_y = self._settings.value(KEY_WINDOW_POSITION_Y)
            try:
                return QPoint(int(raw_x), int(raw_y))
            except (ValueError, TypeError):
                return None
        elif has_x or has_y:
            # Missing one coordinate -> invalid / corrupted
            logger.warning("Incomplete window coordinates in settings.")
            return None

        return None

    def save_window_position(self, position: QPoint) -> None:
        """Save the window position coordinates."""
        self._settings.setValue(KEY_WINDOW_POSITION, QPoint(position))
        self._settings.setValue(KEY_WINDOW_POSITION_X, position.x())
        self._settings.setValue(KEY_WINDOW_POSITION_Y, position.y())
        self._settings.sync()

    def clear(self) -> None:
        """Clear all stored settings."""
        self._settings.clear()
        self._settings.sync()
