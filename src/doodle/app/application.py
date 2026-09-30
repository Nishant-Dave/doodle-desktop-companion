"""Composition root and main application controller for Doodle."""

from __future__ import annotations

import sys
from typing import Optional, Sequence

from PySide6.QtWidgets import QApplication

from doodle.app.lifecycle import AppLifecycle
from doodle.character.character import Character
from doodle.desktop.companion_window import CompanionWindow
from doodle.desktop.tray import DoodleTrayIcon
from doodle.persistence.settings import SettingsManager


class DoodleApplication:
    """Composition root for Doodle.

    Initializes the Qt application, coordinates lifecycle events, and
    assembles the root application components.
    """

    def __init__(
        self,
        argv: Sequence[str] | None = None,
        settings_manager: Optional[SettingsManager] = None,
    ) -> None:
        self._argv = list(argv) if argv is not None else sys.argv

        existing_qapp = QApplication.instance()
        if existing_qapp is None:
            self._qapp = QApplication(self._argv)
        else:
            self._qapp = existing_qapp

        self._qapp.setApplicationName("Doodle")
        self._qapp.setOrganizationName("Doodle")
        # Ensure the application stays alive in the tray when the window is hidden
        self._qapp.setQuitOnLastWindowClosed(False)

        # Persistence and lifecycle
        self._settings_manager = settings_manager or SettingsManager()
        self._lifecycle = AppLifecycle()

        # Character and transparent desktop companion window
        self._character = Character(name="panda")
        self._window: CompanionWindow = CompanionWindow(
            character=self._character,
            settings_manager=self._settings_manager,
        )

        # System tray integration
        self._tray = DoodleTrayIcon(parent=self._window)
        self._tray.show_requested.connect(self.show_companion)
        self._tray.hide_requested.connect(self.hide_companion)
        self._tray.exit_requested.connect(self._lifecycle.request_exit)

        # Wire lifecycle exit request to application termination
        self._lifecycle.exit_requested.connect(self.quit)
        self._qapp.aboutToQuit.connect(self._lifecycle.shutdown)

        # Register shutdown cleanup hooks in order
        self._lifecycle.add_shutdown_hook(self._tray.cleanup)
        self._lifecycle.add_shutdown_hook(self._character.stop_animation)
        self._lifecycle.add_shutdown_hook(self._save_state)

    @property
    def lifecycle(self) -> AppLifecycle:
        """Return the application lifecycle manager."""
        return self._lifecycle

    @property
    def qapp(self) -> QApplication:
        """Return the underlying Qt application instance."""
        return self._qapp

    @property
    def settings_manager(self) -> SettingsManager:
        """Return the application settings manager."""
        return self._settings_manager

    @property
    def character(self) -> Character:
        """Return the root character instance."""
        return self._character

    @property
    def window(self) -> CompanionWindow:
        """Return the root companion window instance."""
        return self._window

    @property
    def tray(self) -> DoodleTrayIcon:
        """Return the system tray icon component."""
        return self._tray

    def show_companion(self) -> None:
        """Make the companion window visible and bring it to front."""
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def hide_companion(self) -> None:
        """Hide the companion window while keeping the application running in the tray."""
        self._window.hide()

    def quit(self) -> None:
        """Perform clean shutdown and terminate the Qt application event loop."""
        self._lifecycle.shutdown()
        self._qapp.quit()

    def _save_state(self) -> None:
        """Save application state during clean shutdown."""
        self._window.position_manager.save_position(self._window.pos())

    def run(self) -> int:
        """Start the application, show tray and window, and enter the Qt event loop."""
        self._lifecycle.startup()
        self._tray.show()
        self._window.show()
        exit_code = self._qapp.exec()
        self._lifecycle.shutdown()
        return exit_code
