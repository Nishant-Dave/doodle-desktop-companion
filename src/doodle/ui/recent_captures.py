"""Compact Recent Captures timeline panel overlay for Doodle companion."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Sequence

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QHideEvent, QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from doodle.desktop.positioning import get_usable_screen_bounds
from doodle.persistence.capture_store import CaptureRecord, CaptureType
from doodle.ui.interaction_menu import compute_menu_position

logger = logging.getLogger(__name__)

DEFAULT_TIMELINE_WIDTH: int = 300
DEFAULT_TIMELINE_HEIGHT: int = 320
DEFAULT_TIMELINE_MARGIN: int = 8
DEFAULT_RECENT_LIMIT: int = 10


def format_capture_type(capture_type: CaptureType | str) -> str:
    """Format CaptureType into human-friendly capitalized display label."""
    if isinstance(capture_type, CaptureType):
        val = capture_type.value
    else:
        val = str(capture_type)
    return val.capitalize()


def format_capture_timestamp(utc_iso_str: str, now: Optional[datetime] = None) -> str:
    """Convert UTC ISO 8601 string to user's local friendly timestamp.

    Examples:
        - Today · 11:42 PM
        - Yesterday · 8:15 PM
        - Oct 2 · 6:30 PM
        - Oct 2, 2025 · 6:30 PM (if different year)
    """
    clean_str = utc_iso_str.replace("Z", "+00:00")
    try:
        dt_utc = datetime.fromisoformat(clean_str)
    except Exception as exc:
        logger.warning("Failed to parse ISO timestamp %r: %s", utc_iso_str, exc)
        return utc_iso_str

    dt_local = dt_utc.astimezone()
    now_local = now if now is not None else datetime.now().astimezone()

    today = now_local.date()
    capture_date = dt_local.date()
    days_diff = (today - capture_date).days

    hour_val = dt_local.hour % 12
    if hour_val == 0:
        hour_val = 12
    am_pm = "AM" if dt_local.hour < 12 else "PM"
    time_str = f"{hour_val}:{dt_local.minute:02d} {am_pm}"

    if days_diff == 0:
        return f"Today · {time_str}"
    elif days_diff == 1:
        return f"Yesterday · {time_str}"
    elif dt_local.year == now_local.year:
        return f"{dt_local.strftime('%b')} {dt_local.day} · {time_str}"
    else:
        return f"{dt_local.strftime('%b')} {dt_local.day}, {dt_local.year} · {time_str}"


class RecentCapturesPanel(QWidget):
    """Compact desktop overlay panel displaying recent Quick Captures chronologically."""

    # Signal emitted when panel is dismissed or closed
    dismissed = Signal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        recent_limit: int = DEFAULT_RECENT_LIMIT,
    ) -> None:
        super().__init__(parent)
        self._recent_limit = max(1, recent_limit)
        self._records: list[CaptureRecord] = []
        self._rendered_items: list[QWidget] = []
        self._empty_label: Optional[QLabel] = None
        self._close_button: Optional[QPushButton] = None

        self.setWindowTitle("Recent Captures")
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(DEFAULT_TIMELINE_WIDTH, DEFAULT_TIMELINE_HEIGHT)

        self._init_ui()

    @property
    def recent_limit(self) -> int:
        """Return the maximum number of recent captures to display."""
        return self._recent_limit

    @recent_limit.setter
    def recent_limit(self, value: int) -> None:
        self._recent_limit = max(1, int(value))

    @property
    def records(self) -> list[CaptureRecord]:
        """Return the list of currently displayed CaptureRecords."""
        return list(self._records)

    @property
    def rendered_items(self) -> list[QWidget]:
        """Return list of rendered item container widgets."""
        return list(self._rendered_items)

    @property
    def empty_label(self) -> Optional[QLabel]:
        """Return the empty state title label, or None if not currently shown."""
        return self._empty_label

    @property
    def close_button(self) -> QPushButton:
        """Return the header close button."""
        assert self._close_button is not None
        return self._close_button

    def _init_ui(self) -> None:
        """Construct the timeline card frame, scroll area, and styling."""
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        card = QFrame(self)
        card.setObjectName("recentCapturesCard")
        card.setFixedSize(DEFAULT_TIMELINE_WIDTH, DEFAULT_TIMELINE_HEIGHT)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)
        card_layout.setSpacing(6)

        # Header: Title + Close Button
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        title_label = QLabel("RECENT CAPTURES", card)
        title_label.setObjectName("headerTitle")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        self._close_button = QPushButton("×", card)
        self._close_button.setObjectName("closeButton")
        self._close_button.setFixedSize(18, 18)
        self._close_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._close_button.setToolTip("Close (Esc)")
        self._close_button.clicked.connect(self.dismiss)
        header_layout.addWidget(self._close_button)

        card_layout.addLayout(header_layout)

        # Scroll Area for timeline items
        self._scroll_area = QScrollArea(card)
        self._scroll_area.setObjectName("timelineScrollArea")
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        self._scroll_widget = QWidget()
        self._scroll_widget.setObjectName("scrollWidget")
        self._items_layout = QVBoxLayout(self._scroll_widget)
        self._items_layout.setContentsMargins(0, 2, 4, 2)
        self._items_layout.setSpacing(6)

        self._scroll_area.setWidget(self._scroll_widget)
        card_layout.addWidget(self._scroll_area)

        outer_layout.addWidget(card)
        self._apply_styles()

    def _apply_styles(self) -> None:
        """Apply compact dark translucent stylesheet matching Doodle UI."""
        self.setStyleSheet("""
            QFrame#recentCapturesCard {
                background-color: rgba(28, 30, 38, 245);
                border: 1px solid rgba(255, 255, 255, 35);
                border-radius: 12px;
            }
            QLabel#headerTitle {
                color: #e2e4ee;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 0.5px;
            }
            QPushButton#closeButton {
                background-color: transparent;
                color: rgba(210, 210, 225, 120);
                border: none;
                border-radius: 4px;
                font-size: 14px;
                font-weight: bold;
                padding: 0;
            }
            QPushButton#closeButton:hover {
                background-color: rgba(255, 255, 255, 20);
                color: #ffffff;
            }
            QScrollArea#timelineScrollArea {
                background-color: transparent;
                border: none;
            }
            QWidget#scrollWidget {
                background-color: transparent;
            }
            QScrollBar:vertical {
                background-color: transparent;
                width: 4px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background-color: rgba(255, 255, 255, 30);
                border-radius: 2px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: rgba(255, 255, 255, 60);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QLabel#itemType {
                color: #8c9bf0;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }
            QLabel#itemContent {
                color: #e8e9f2;
                font-size: 11px;
                line-height: 1.3;
            }
            QLabel#itemTimestamp {
                color: rgba(170, 175, 195, 140);
                font-size: 9px;
            }
            QFrame#itemDivider {
                background-color: rgba(255, 255, 255, 15);
                max-height: 1px;
                border: none;
            }
            QLabel#emptyTitle {
                color: #d0d2e0;
                font-size: 12px;
                font-weight: 600;
            }
            QLabel#emptySubtitle {
                color: rgba(180, 185, 205, 150);
                font-size: 10px;
                line-height: 1.4;
            }
        """)

    def set_captures(self, records: Sequence[CaptureRecord]) -> None:
        """Populate the timeline with the provided capture records.

        Args:
            records: CaptureRecord instances ordered newest first.
        """
        # Clear existing items in layout
        while self._items_layout.count() > 0:
            item = self._items_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        self._rendered_items.clear()
        self._empty_label = None
        self._records = list(records[: self._recent_limit])

        if not self._records:
            self._render_empty_state()
            return

        for index, record in enumerate(self._records):
            item_widget = self._create_item_widget(record)
            self._rendered_items.append(item_widget)
            self._items_layout.addWidget(item_widget)

            # Divider line between items (except after the last item)
            if index < len(self._records) - 1:
                divider = QFrame()
                divider.setObjectName("itemDivider")
                divider.setFrameShape(QFrame.Shape.HLine)
                self._items_layout.addWidget(divider)

        self._items_layout.addStretch()

    def _create_item_widget(self, record: CaptureRecord) -> QWidget:
        """Create a compact, read-only item widget for a single capture."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        # 1. Capture type
        type_label = QLabel(format_capture_type(record.capture_type), container)
        type_label.setObjectName("itemType")
        layout.addWidget(type_label)

        # 2. Content
        content_label = QLabel(record.content, container)
        content_label.setObjectName("itemContent")
        content_label.setWordWrap(True)
        layout.addWidget(content_label)

        # 3. Localized timestamp
        time_label = QLabel(format_capture_timestamp(record.created_at), container)
        time_label.setObjectName("itemTimestamp")
        layout.addWidget(time_label)

        return container

    def _render_empty_state(self) -> None:
        """Display calm empty state message when no captures exist."""
        empty_container = QWidget()
        layout = QVBoxLayout(empty_container)
        layout.setContentsMargins(10, 40, 10, 20)
        layout.setSpacing(6)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("No captures yet.", empty_container)
        title.setObjectName("emptyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label = title
        layout.addWidget(title)

        subtitle = QLabel("Capture an idea, journal entry, mood, or memory with Doodle.", empty_container)
        subtitle.setObjectName("emptySubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self._items_layout.addWidget(empty_container)
        self._items_layout.addStretch()

    def show_near(
        self,
        target_rect: QRect,
        screen_bounds: Optional[QRect] = None,
    ) -> None:
        """Position and display the panel near the companion target window."""
        if screen_bounds is None:
            screen_bounds = get_usable_screen_bounds()

        pos = compute_menu_position(
            target_rect=target_rect,
            menu_size=self.size(),
            screen_bounds=screen_bounds,
            margin=DEFAULT_TIMELINE_MARGIN,
        )
        self.move(pos)
        self.show()
        self.raise_()
        self.activateWindow()

    def show_captures(
        self,
        records: Sequence[CaptureRecord],
        target_rect: Optional[QRect] = None,
        screen_bounds: Optional[QRect] = None,
    ) -> None:
        """Populate captures and display the panel near the companion window.

        Args:
            records: CaptureRecord instances to display.
            target_rect: Optional geometry rectangle of companion target window.
            screen_bounds: Optional usable screen bounds.
        """
        self.set_captures(records)
        if target_rect is not None:
            self.show_near(target_rect, screen_bounds=screen_bounds)
        else:
            self.show()
            self.raise_()
            self.activateWindow()

    def dismiss(self) -> None:
        """Dismiss (hide) the Recent Captures panel."""
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
        """Emit dismissed signal when the panel is hidden."""
        super().hideEvent(event)
        self.dismissed.emit()

    def cleanup(self) -> None:
        """Clean up panel resources during application shutdown."""
        self.dismiss()
        self.close()
