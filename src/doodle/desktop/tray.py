"""System tray icon integration for the Doodle desktop application."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from doodle.character.assets import DEFAULT_ASSETS_DIR

logger = logging.getLogger(__name__)


def create_default_tray_icon(assets_dir: Optional[Path] = None) -> QIcon:
    """Load or generate a suitable tray icon for Doodle."""
    base_dir = Path(assets_dir) if assets_dir is not None else DEFAULT_ASSETS_DIR
    icon_candidate = base_dir / "panda" / "idle" / "panda_idle.png"

    if icon_candidate.is_file():
        return QIcon(str(icon_candidate))

    # Procedural fallback icon if asset is unavailable
    pixmap = QPixmap(32, 32)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(35, 35, 40))
    painter.drawEllipse(2, 2, 28, 28)
    painter.end()
    return QIcon(pixmap)


class DoodleTrayIcon(QSystemTrayIcon):
    """System tray icon providing desktop controls for Doodle.

    The tray delegates actions (show, hide, exit) via Qt signals rather than
    owning application lifecycle logic directly.
    """

    # Signals requesting application/window action
    show_requested = Signal()
    hide_requested = Signal()
    exit_requested = Signal()

    def __init__(
        self,
        icon: Optional[QIcon] = None,
        parent: Optional[QObject] = None,
        assets_dir: Optional[Path] = None,
    ) -> None:
        tray_icon = icon or create_default_tray_icon(assets_dir=assets_dir)
        super().__init__(tray_icon, parent)

        self.setToolTip("Doodle — Desktop Companion")

        # Build context menu
        self._menu = QMenu()
        self._action_show = self._menu.addAction("Show Doodle")
        self._action_show.triggered.connect(self.show_requested.emit)

        self._action_hide = self._menu.addAction("Hide Doodle")
        self._action_hide.triggered.connect(self.hide_requested.emit)

        self._menu.addSeparator()

        self._action_exit = self._menu.addAction("Exit Doodle")
        self._action_exit.triggered.connect(self.exit_requested.emit)

        self.setContextMenu(self._menu)
        self.activated.connect(self._on_activated)

    @property
    def action_show(self):
        """Return the Show Doodle menu action."""
        return self._action_show

    @property
    def action_hide(self):
        """Return the Hide Doodle menu action."""
        return self._action_hide

    @property
    def action_exit(self):
        """Return the Exit Doodle menu action."""
        return self._action_exit

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle clicks on the system tray icon."""
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.show_requested.emit()

    def cleanup(self) -> None:
        """Clean up tray icon and menu during application shutdown."""
        self.hide()
        self.setContextMenu(None)
