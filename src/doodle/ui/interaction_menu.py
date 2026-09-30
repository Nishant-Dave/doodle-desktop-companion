"""Compact interaction menu popup for Doodle desktop companion."""

from __future__ import annotations

import logging
from typing import Optional, Sequence

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QHideEvent, QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from doodle.desktop.positioning import get_usable_screen_bounds

logger = logging.getLogger(__name__)

# Proposed interaction actions (establishing UI boundary without backends)
AVAILABLE_ACTIONS: Sequence[tuple[str, str]] = (
    ("journal", "Journal"),
    ("mood", "Mood"),
    ("idea", "Idea"),
    ("remember", "Remember"),
    ("settings", "Settings"),
)

DEFAULT_MENU_WIDTH: int = 148
DEFAULT_MENU_MARGIN: int = 8


def compute_menu_position(
    target_rect: QRect,
    menu_size: QSize,
    screen_bounds: QRect,
    margin: int = DEFAULT_MENU_MARGIN,
) -> QPoint:
    """Calculate deterministic coordinates for the interaction menu near a target window.

    Positions the menu centered horizontally relative to the target window,
    preferring to display above the companion window. If there is insufficient vertical
    space above the target, it flips the menu below. Clamps all coordinates to remain
    strictly within the provided usable screen bounds.

    Args:
        target_rect: Geometry rect of the companion target window.
        menu_size: Dimensions of the interaction menu.
        screen_bounds: Usable bounding rectangle of the active desktop screen.
        margin: Pixel spacing between the target window and menu.

    Returns:
        QPoint with clamped top-left coordinates for the interaction menu.
    """
    # Center horizontally with respect to target window
    target_center_x = target_rect.x() + target_rect.width() // 2
    preferred_x = target_center_x - menu_size.width() // 2

    # Prefer positioning above target window
    preferred_y = target_rect.y() - menu_size.height() - margin

    # If insufficient vertical space above, flip below target window
    if preferred_y < screen_bounds.top():
        preferred_y = target_rect.y() + target_rect.height() + margin

    # Clamp horizontally to screen bounds
    max_x = screen_bounds.x() + screen_bounds.width() - menu_size.width()
    if max_x < screen_bounds.left():
        clamped_x = screen_bounds.left()
    else:
        clamped_x = max(screen_bounds.left(), min(preferred_x, max_x))

    # Clamp vertically to screen bounds
    max_y = screen_bounds.y() + screen_bounds.height() - menu_size.height()
    if max_y < screen_bounds.top():
        clamped_y = screen_bounds.top()
    else:
        clamped_y = max(screen_bounds.top(), min(preferred_y, max_y))

    return QPoint(clamped_x, clamped_y)


class InteractionMenu(QWidget):
    """Compact interaction menu popup associated with the companion window.

    Presents future action entry points in an unavailable/disabled state for Milestone 1,
    establishing the clean interaction boundary and action request routing without
    implementing actual backends.
    """

    # Signal emitted when a menu action is requested (boundary for future features)
    action_requested = Signal(str)

    # Signal emitted when the menu is dismissed or closed
    dismissed = Signal()
    dismiss_requested = dismissed

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        actions: Optional[Sequence[tuple[str, str]]] = None,
    ) -> None:
        super().__init__(parent)
        self._action_definitions = list(actions or AVAILABLE_ACTIONS)
        self._buttons: dict[str, QPushButton] = {}

        self.setWindowTitle("Doodle Menu")
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(DEFAULT_MENU_WIDTH)

        self._init_ui()

    def _init_ui(self) -> None:
        """Construct the menu card layout and styling."""
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        card = QFrame(self)
        card.setObjectName("menuCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.setSpacing(5)

        # Header title
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(2, 0, 2, 2)
        title_label = QLabel("Doodle", card)
        title_label.setObjectName("headerTitle")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        card_layout.addLayout(header_layout)

        # Action buttons (disabled in Milestone 1 to avoid fake functionality)
        for action_id, label in self._action_definitions:
            btn = QPushButton(label, card)
            btn.setObjectName(f"action_{action_id.lower()}")
            btn.setEnabled(False)
            btn.setToolTip(f"{label} (Not available in Milestone 1)")
            btn.clicked.connect(lambda _, a=action_id: self.request_action(a))
            card_layout.addWidget(btn)
            self._buttons[action_id.lower()] = btn

        # Separator spacing before dismiss button
        card_layout.addSpacing(4)

        # Dismiss button (enabled)
        dismiss_btn = QPushButton("Dismiss", card)
        dismiss_btn.setObjectName("dismissButton")
        dismiss_btn.setToolTip("Close interaction menu")
        dismiss_btn.clicked.connect(self.dismiss)
        card_layout.addWidget(dismiss_btn)
        self._buttons["dismiss"] = dismiss_btn

        outer_layout.addWidget(card)
        self._apply_styles()

    def _apply_styles(self) -> None:
        """Apply compact dark translucent stylesheet."""
        self.setStyleSheet("""
            QFrame#menuCard {
                background-color: rgba(28, 30, 38, 240);
                border: 1px solid rgba(255, 255, 255, 35);
                border-radius: 12px;
            }
            QLabel#headerTitle {
                color: #e2e4ee;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 0.5px;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 12);
                color: #e2e2ea;
                border: 1px solid rgba(255, 255, 255, 18);
                border-radius: 6px;
                padding: 5px 10px;
                font-size: 11px;
                text-align: left;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 25);
                border-color: rgba(255, 255, 255, 45);
            }
            QPushButton:disabled {
                background-color: rgba(255, 255, 255, 5);
                color: rgba(160, 160, 180, 100);
                border-color: rgba(255, 255, 255, 10);
            }
            QPushButton#dismissButton {
                background-color: rgba(255, 255, 255, 10);
                color: rgba(210, 210, 225, 180);
                border: 1px solid rgba(255, 255, 255, 20);
                border-radius: 6px;
                padding: 4px 10px;
                font-size: 11px;
                text-align: center;
            }
            QPushButton#dismissButton:hover {
                background-color: rgba(220, 70, 70, 60);
                color: #ffffff;
                border-color: rgba(220, 70, 70, 100);
            }
        """)

    def request_action(self, action_id: str) -> None:
        """Emit action_requested signal for the given action id."""
        normalized_id = action_id.lower()
        logger.info("Interaction menu action requested: %s", normalized_id)
        self.action_requested.emit(normalized_id)

    def get_action_button(self, action_id: str) -> Optional[QPushButton]:
        """Return the QPushButton widget associated with action id, if found."""
        return self._buttons.get(action_id.lower())

    def is_action_enabled(self, action_id: str) -> bool:
        """Return True if the specified action is enabled."""
        btn = self.get_action_button(action_id)
        return btn.isEnabled() if btn is not None else False

    def show_near(
        self,
        target_rect: QRect,
        screen_bounds: Optional[QRect] = None,
    ) -> None:
        """Position the menu deterministically near the target rect and display it.

        Args:
            target_rect: Geometry rect of the companion window to associate with.
            screen_bounds: Optional usable screen bounds. Defaults to primary screen bounds.
        """
        if screen_bounds is None:
            screen_bounds = get_usable_screen_bounds()

        self.adjustSize()
        pos = compute_menu_position(
            target_rect=target_rect,
            menu_size=self.size(),
            screen_bounds=screen_bounds,
        )
        self.move(pos)
        self.show()
        self.raise_()
        self.activateWindow()

    def dismiss(self) -> None:
        """Dismiss (hide) the interaction menu."""
        if self.isVisible():
            self.hide()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Dismiss on Escape key press."""
        if event.key() == Qt.Key.Key_Escape:
            self.dismiss()
            event.accept()
            return
        super().keyPressEvent(event)

    def hideEvent(self, event: QHideEvent) -> None:
        """Emit dismissed signal when the menu transitions from visible to hidden."""
        super().hideEvent(event)
        self.dismissed.emit()

    def cleanup(self) -> None:
        """Clean up menu resources during application shutdown."""
        self.dismiss()
        self.close()
