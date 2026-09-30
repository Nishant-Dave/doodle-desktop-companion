"""Composition root and main application controller for Doodle."""

from __future__ import annotations

import sys
from typing import Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from doodle.app.lifecycle import AppLifecycle


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

        # Minimal temporary window for Milestone 1 Task 1 foundation
        self._window: QWidget = self._create_initial_window()

    @property
    def lifecycle(self) -> AppLifecycle:
        """Return the application lifecycle manager."""
        return self._lifecycle

    @property
    def qapp(self) -> QApplication:
        """Return the underlying Qt application instance."""
        return self._qapp

    @property
    def window(self) -> QWidget:
        """Return the root window instance."""
        return self._window

    def _create_initial_window(self) -> QWidget:
        """Create a minimal foundation window for startup validation."""
        window = QWidget()
        window.setWindowTitle("Doodle")
        window.resize(240, 160)

        layout = QVBoxLayout(window)
        label = QLabel("Doodle Desktop Companion\n(Foundation)", window)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

        return window

    def run(self) -> int:
        """Start the application, show the window, and enter the Qt event loop."""
        self._lifecycle.startup()
        self._window.show()
        exit_code = self._qapp.exec()
        self._lifecycle.shutdown()
        return exit_code
