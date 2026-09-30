"""Composition root and main application controller for Doodle."""

from __future__ import annotations

import sys
from typing import Optional, Sequence

from PySide6.QtWidgets import QApplication

from doodle.app.lifecycle import AppLifecycle
from doodle.character.character import Character
from doodle.desktop.companion_window import CompanionWindow
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

        # Persistence and lifecycle
        self._settings_manager = settings_manager or SettingsManager()
        self._lifecycle = AppLifecycle()
        self._qapp.aboutToQuit.connect(self._lifecycle.shutdown)
        self._lifecycle.add_shutdown_hook(self._save_state)

        # Character and transparent desktop companion window
        self._character = Character(name="panda")
        self._window: CompanionWindow = CompanionWindow(
            character=self._character,
            settings_manager=self._settings_manager,
        )

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

    def _save_state(self) -> None:
        """Save application state during clean shutdown."""
        self._window.position_manager.save_position(self._window.pos())

    def run(self) -> int:
        """Start the application, show the window, and enter the Qt event loop."""
        self._lifecycle.startup()
        self._window.show()
        exit_code = self._qapp.exec()
        self._lifecycle.shutdown()
        return exit_code
