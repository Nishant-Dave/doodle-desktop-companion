"""Desktop companion window for Doodle.

Provides a transparent, frameless, always-on-top top-level window.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPaintEvent, QPen, QPixmap
from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from doodle.character.character import Character

DEFAULT_WINDOW_WIDTH: int = 160
DEFAULT_WINDOW_HEIGHT: int = 160
DEFAULT_SCREEN_MARGIN: int = 24


class CompanionWindow(QWidget):
    """Top-level transparent and frameless desktop shell window."""

    def __init__(
        self,
        character: Optional[Character] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._character: Optional[Character] = None

        self.setWindowTitle("Doodle")
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)

        # Configure frameless, always-on-top, transparent presentation
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.set_default_position()
        self.set_character(character)

    @property
    def character(self) -> Optional[Character]:
        """Return the attached character instance, if any."""
        return self._character

    def set_character(self, character: Optional[Character]) -> None:
        """Attach or update the character displayed in this window."""
        if self._character is not None:
            try:
                self._character.frame_changed.disconnect(self._on_frame_changed)
            except (RuntimeError, TypeError):
                pass

        self._character = character

        if self._character is not None:
            self._character.frame_changed.connect(self._on_frame_changed)

        self.update()

    def _on_frame_changed(self, _pixmap: QPixmap) -> None:
        """Slot invoked whenever the character's active animation frame advances."""
        self.update()

    def set_default_position(self) -> None:
        """Position the window at a sensible default location on the screen.

        Defaults to the bottom-right corner of the available primary screen area,
        leaving a small margin above the taskbar.
        """
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is not None:
            available_geom: QRect = screen.availableGeometry()
            if (
                available_geom.isValid()
                and available_geom.width() > self.width()
                and available_geom.height() > self.height()
            ):
                x = available_geom.right() - self.width() - DEFAULT_SCREEN_MARGIN
                y = available_geom.bottom() - self.height() - DEFAULT_SCREEN_MARGIN
                self.move(QPoint(x, y))
                return

        # Safe fallback position if screen geometry is unavailable
        self.move(QPoint(100, 100))

    def paintEvent(self, event: QPaintEvent) -> None:
        """Render character visual or temporary placeholder.

        Renders the attached character visual centered in the transparent window.
        If no character visual is available, renders a subtle placeholder.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pixmap = self._character.visual if self._character is not None else None
        if pixmap is not None and not pixmap.isNull():
            # Render character visual centered with smooth scaling to fit window
            scaled = pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)
            return

        # Subtly tinted rounded placeholder if no character visual is attached
        rect = self.rect().adjusted(4, 4, -4, -4)
        painter.setBrush(QColor(30, 30, 35, 200))
        painter.setPen(QPen(QColor(160, 160, 180, 220), 1.5))
        painter.drawRoundedRect(rect, 16, 16)

        painter.setPen(QColor(240, 240, 250, 240))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Doodle")
