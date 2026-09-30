"""Composition root and main application controller for Doodle."""

from __future__ import annotations

import logging
import sys
from typing import Optional, Sequence

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from doodle.app.lifecycle import AppLifecycle
from doodle.behavior.engine import BehaviorEngine
from doodle.character.character import Character
from doodle.character.state import CharacterState
from doodle.desktop.companion_window import CompanionWindow
from doodle.desktop.tray import DoodleTrayIcon
from doodle.persistence.settings import SettingsManager
from doodle.ui.interaction_menu import InteractionMenu

logger = logging.getLogger(__name__)


class DoodleApplication:
    """Composition root for Doodle.

    Initializes the Qt application, coordinates lifecycle events, and
    assembles the root application components.
    """

    def __init__(
        self,
        argv: Sequence[str] | None = None,
        settings_manager: Optional[SettingsManager] = None,
        behavior_engine: Optional[BehaviorEngine] = None,
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

        # Behavior engine
        if behavior_engine is not None:
            self._behavior_engine = behavior_engine
            if self._behavior_engine.character is None:
                self._behavior_engine.attach_character(self._character)
        else:
            self._behavior_engine = BehaviorEngine(
                character=self._character,
                parent=self._window,
            )

        # Wire animation completion to behavior engine
        self._character.animation_finished.connect(
            self._behavior_engine.on_animation_finished
        )

        # Interaction menu (single managed instance to prevent duplicates)
        self._menu: InteractionMenu = InteractionMenu(parent=self._window)
        self._menu.action_requested.connect(self._on_menu_action_requested)
        self._menu.dismissed.connect(self._on_menu_dismissed)

        # Wire companion window interactions
        self._window.character_clicked.connect(self._on_character_clicked)
        self._window.character_moved.connect(self._on_character_moved)
        self._window.drag_started.connect(self._behavior_engine.on_drag_started)
        self._window.drag_finished.connect(self._behavior_engine.on_drag_finished)

        # System tray integration
        self._tray = DoodleTrayIcon(parent=self._window)
        self._tray.show_requested.connect(self.show_companion)
        self._tray.hide_requested.connect(self.hide_companion)
        self._tray.exit_requested.connect(self._lifecycle.request_exit)

        # Wire lifecycle exit request to application termination
        self._lifecycle.exit_requested.connect(self.quit)
        self._qapp.aboutToQuit.connect(self._lifecycle.shutdown)

        # Register shutdown cleanup hooks in order
        self._lifecycle.add_shutdown_hook(self._behavior_engine.cleanup)
        self._lifecycle.add_shutdown_hook(self._menu.cleanup)
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

    @property
    def menu(self) -> InteractionMenu:
        """Return the managed interaction menu component."""
        return self._menu

    @property
    def behavior_engine(self) -> BehaviorEngine:
        """Return the managed behavior engine component."""
        return self._behavior_engine

    def show_companion(self) -> None:
        """Make the companion window visible and bring it to front."""
        self._behavior_engine.on_show_requested()
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def hide_companion(self) -> None:
        """Hide the companion window while keeping the application running in the tray."""
        self._behavior_engine.on_hide_requested()
        if self._menu.isVisible():
            self._menu.dismiss()
        self._window.hide()

    def show_interaction_menu(self) -> None:
        """Open the interaction menu adjacent to the companion window."""
        self._behavior_engine.on_menu_opened()
        self._character.set_state(CharacterState.ATTENTION)
        bounds = self._window.position_manager.get_usable_screen_bounds()
        self._menu.show_near(
            target_rect=self._window.geometry(),
            screen_bounds=bounds,
        )

    def dismiss_interaction_menu(self) -> None:
        """Dismiss the interaction menu if visible."""
        self._menu.dismiss()

    def _on_character_clicked(self) -> None:
        """Slot invoked when user clicks the companion character."""
        self._behavior_engine.on_character_clicked()
        if self._menu.isVisible():
            self._menu.dismiss()
        else:
            self.show_interaction_menu()

    def _on_character_moved(self, pos: QPoint) -> None:
        """Slot invoked when companion window moves during dragging."""
        self._behavior_engine.on_character_moved(pos)
        if self._menu.isVisible():
            self._menu.dismiss()

    def _on_menu_dismissed(self) -> None:
        """Slot invoked when interaction menu is dismissed."""
        self._behavior_engine.on_menu_dismissed()
        if self._character.state == CharacterState.ATTENTION:
            self._character.set_state(CharacterState.IDLE)

    def _on_menu_action_requested(self, action_id: str) -> None:
        """Slot invoked when a menu action is requested (action boundary)."""
        logger.info("Menu action requested: %s", action_id)

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
        self._behavior_engine.start_idle_timer()
        self._tray.show()
        self._window.show()
        exit_code = self._qapp.exec()
        self._lifecycle.shutdown()
        return exit_code
