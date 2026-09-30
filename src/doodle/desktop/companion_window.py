"""Desktop companion window for Doodle.

Provides a transparent, frameless, always-on-top top-level window.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

DEFAULT_WINDOW_WIDTH: int = 160
DEFAULT_WINDOW_HEIGHT: int = 160
DEFAULT_SCREEN_MARGIN: int = 24


class CompanionWindow(QWidget):
    """Top-level transparent and frameless desktop shell window."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

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
        """Render temporary placeholder visual.

        This placeholder confirms the transparent window boundary and will be
        replaced by the Character rendering layer in subsequent milestones.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Subtly tinted rounded placeholder to visually demonstrate transparency
        rect = self.rect().adjusted(4, 4, -4, -4)
        painter.setBrush(QColor(30, 30, 35, 200))
        painter.setPen(QPen(QColor(160, 160, 180, 220), 1.5))
        painter.drawRoundedRect(rect, 16, 16)

        painter.setPen(QColor(240, 240, 250, 240))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Doodle")
