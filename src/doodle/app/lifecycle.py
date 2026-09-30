"""Application lifecycle management for Doodle.

Handles startup, shutdown hooks, and lifecycle state coordination for the application.
"""

from __future__ import annotations

import logging
from typing import Callable, List, Optional

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class AppLifecycle(QObject):
    """Manages the startup, shutdown phases, and exit requests for the application."""

    # Qt Signals for lifecycle events
    started = Signal()
    stopped = Signal()
    exit_requested = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._is_running: bool = False
        self._shutdown_hooks: List[Callable[[], None]] = []

    @property
    def is_running(self) -> bool:
        """Return True if the application has started and has not yet shut down."""
        return self._is_running

    def add_shutdown_hook(self, hook: Callable[[], None]) -> None:
        """Register a callback to be called during application shutdown."""
        self._shutdown_hooks.append(hook)

    def request_exit(self) -> None:
        """Request the application to initiate a clean exit."""
        logger.info("Application exit requested through lifecycle.")
        self.exit_requested.emit()

    def startup(self) -> None:
        """Execute application startup sequence."""
        if self._is_running:
            return
        logger.info("Doodle application lifecycle starting up.")
        self._is_running = True
        self.started.emit()

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
        self.stopped.emit()
