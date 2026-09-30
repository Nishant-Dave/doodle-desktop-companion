"""Composition root and main application controller for Doodle."""

from __future__ import annotations

import sys
from typing import Sequence

from PySide6.QtWidgets import QApplication

from doodle.app.lifecycle import AppLifecycle
from doodle.character.character import Character
from doodle.desktop.companion_window import CompanionWindow


class DoodleApplication:
    """Composition root for Doodle.

    Initializes the Qt application, coordinates lifecycle events, and
    assembles the root application components.
    """

    def __init__(self, argv: Sequence[str] | None = None) -> None:
        self._argv = list(argv) if argv is not None else sys.argv

        existing_qapp = QApplication.instance()
        if existing_qapp is None:
            self._qapp = QApplication(self._argv)
        else:
            self._qapp = existing_qapp

        self._qapp.setApplicationName("Doodle")
        self._qapp.setOrganizationName("Doodle")

        self._lifecycle = AppLifecycle()
        self._qapp.aboutToQuit.connect(self._lifecycle.shutdown)

        # Character and transparent desktop companion window
        self._character = Character(name="panda")
        self._window: CompanionWindow = CompanionWindow(character=self._character)

    @property
    def lifecycle(self) -> AppLifecycle:
        """Return the application lifecycle manager."""
        return self._lifecycle

    @property
    def qapp(self) -> QApplication:
        """Return the underlying Qt application instance."""
        return self._qapp

    @property
    def character(self) -> Character:
        """Return the root character instance."""
        return self._character

    @property
    def window(self) -> CompanionWindow:
        """Return the root companion window instance."""
        return self._window

    def run(self) -> int:
        """Start the application, show the window, and enter the Qt event loop."""
        self._lifecycle.startup()
        self._window.show()
        exit_code = self._qapp.exec()
        self._lifecycle.shutdown()
        return exit_code
