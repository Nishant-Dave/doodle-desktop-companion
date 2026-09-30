"""Application lifecycle management for Doodle.

Handles startup and clean shutdown sequences for the application.
"""

from __future__ import annotations

import logging
from typing import Callable, List

logger = logging.getLogger(__name__)


class AppLifecycle:
    """Manages the startup and shutdown phases of the application."""

    def __init__(self) -> None:
        self._is_running: bool = False
        self._shutdown_hooks: List[Callable[[], None]] = []

    @property
    def is_running(self) -> bool:
        """Return True if the application has started and has not yet shut down."""
        return self._is_running

    def add_shutdown_hook(self, hook: Callable[[], None]) -> None:
        """Register a callback to be called during application shutdown."""
        self._shutdown_hooks.append(hook)

    def startup(self) -> None:
        """Execute application startup sequence."""
        if self._is_running:
            return
        logger.info("Doodle application lifecycle starting up.")
        self._is_running = True

    def shutdown(self) -> None:
        """Execute clean application shutdown sequence."""
        if not self._is_running:
            return
        logger.info("Doodle application lifecycle shutting down.")
        for hook in reversed(self._shutdown_hooks):
            try:
                hook()
            except Exception:
                logger.exception("Error executing shutdown hook.")
        self._is_running = False
