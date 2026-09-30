"""Desktop companion window for Doodle.

Provides a transparent, frameless, always-on-top top-level window.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
    QResizeEvent,
)
from PySide6.QtWidgets import QWidget

from doodle.desktop.positioning import (
    PositionManager,
    get_usable_screen_bounds,
)

if TYPE_CHECKING:
    from doodle.character.character import Character
    from doodle.persistence.settings import SettingsManager

DEFAULT_WINDOW_WIDTH: int = 160
DEFAULT_WINDOW_HEIGHT: int = 160
DEFAULT_SCREEN_MARGIN: int = 24
DEFAULT_DRAG_THRESHOLD: int = 5


class CompanionWindow(QWidget):
    """Top-level transparent and frameless desktop shell window."""

    # Signal emitted when window position changes due to dragging or positioning
    character_moved = Signal(QPoint)
    CHARACTER_MOVED = character_moved

    # Signal emitted when the companion window is clicked without dragging
    character_clicked = Signal()
    CHARACTER_CLICKED = character_clicked

    def __init__(
        self,
        character: Optional[Character] = None,
        position_manager: Optional[PositionManager] = None,
        settings_manager: Optional[SettingsManager] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._character: Optional[Character] = None
        self._is_dragging: bool = False
        self._drag_start_offset: QPoint = QPoint(0, 0)
        self._drag_start_pos: QPoint = QPoint(0, 0)
        self._drag_occurred: bool = False
        self._drag_threshold: int = DEFAULT_DRAG_THRESHOLD

        self.setWindowTitle("Doodle")
        self.resize(DEFAULT_WINDOW_WIDTH, DEFAULT_WINDOW_HEIGHT)

        # Configure frameless, always-on-top, transparent presentation
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        # Initialize positioning manager delegating screen boundary and persistence logic
        if position_manager is not None:
            self._position_manager = position_manager
            if settings_manager is not None:
                self._position_manager.set_settings_manager(settings_manager)
        else:
            self._position_manager = PositionManager(
                window_size=self.size(),
                screen_bounds_provider=self._get_screen_bounds,
                settings_manager=settings_manager,
            )

        # Restore persisted position or default to bottom-right
        self.restore_or_default_position()
        self.set_character(character)

    @property
    def character(self) -> Optional[Character]:
        """Return the attached character instance, if any."""
        return self._character

    @property
    def is_dragging(self) -> bool:
        """Return True if currently in a mouse press or active drag operation."""
        return self._is_dragging

    @property
    def drag_occurred(self) -> bool:
        """Return True if the current or most recent press exceeded drag threshold."""
        return self._drag_occurred

    @property
    def drag_threshold(self) -> int:
        """Return the distance threshold in pixels to differentiate click from drag."""
        return self._drag_threshold

    @drag_threshold.setter
    def drag_threshold(self, value: int) -> None:
        self._drag_threshold = max(1, value)

    @property
    def position_manager(self) -> PositionManager:
        """Return the position manager associated with this window."""
        return self._position_manager

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

    def _get_screen_bounds(self) -> QRect:
        """Query available screen bounds for this window."""
        return get_usable_screen_bounds()

    def restore_or_default_position(self) -> None:
        """Restore position from persistence or fall back to default position."""
        pos = self._position_manager.restore_position()
        self.move(pos)

    def set_default_position(self) -> None:
        """Position the window at the default location on the screen."""
        default_pos = self._position_manager.get_default_position()
        self._position_manager.set_position(default_pos)
        self.move(default_pos)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Synchronize window size updates with the position manager."""
        super().resizeEvent(event)
        self._position_manager.set_window_size(self.size())

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle left mouse click to initiate dragging or click detection."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self._drag_occurred = False
            self._drag_start_pos = event.globalPosition().toPoint()
            # Offset between the global pointer location and window top-left
            self._drag_start_offset = event.globalPosition().toPoint() - self.pos()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Handle mouse movement during dragging, clamped to screen bounds."""
        if self._is_dragging and (event.buttons() & Qt.MouseButton.LeftButton):
            current_pos = event.globalPosition().toPoint()
            delta = (current_pos - self._drag_start_pos).manhattanLength()
            if not self._drag_occurred:
                if delta >= self._drag_threshold:
                    self._drag_occurred = True
                else:
                    event.accept()
                    return

            target_pos = current_pos - self._drag_start_offset
            clamped_pos = self._position_manager.clamp_to_screen(target_pos)
            if clamped_pos != self.pos():
                self.move(clamped_pos)
                self.character_moved.emit(clamped_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """Handle mouse release to conclude dragging or emit click interaction."""
        if event.button() == Qt.MouseButton.LeftButton and self._is_dragging:
            self._is_dragging = False
            if self._drag_occurred:
                clamped_pos = self._position_manager.set_position(self.pos())
                if clamped_pos != self.pos():
                    self.move(clamped_pos)
                self._position_manager.save_position()
                self.character_moved.emit(self.pos())
            else:
                self.character_clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

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
