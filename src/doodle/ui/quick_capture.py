"""Compact Quick Capture card overlay for Doodle companion."""

from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QEvent, QObject, QPoint, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QHideEvent, QKeyEvent, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from doodle.desktop.positioning import get_usable_screen_bounds
from doodle.persistence.capture_store import CaptureRecord, CaptureStore, CaptureType
from doodle.ui.interaction_menu import compute_menu_position

logger = logging.getLogger(__name__)

DEFAULT_CAPTURE_WIDTH: int = 220
DEFAULT_CAPTURE_HEIGHT: int = 110
DEFAULT_CAPTURE_MARGIN: int = 8


class QuickCaptureCard(QWidget):
    """Compact Quick Capture overlay card for rapid thought entry.

    Displays a capture type selector, a single-line text input field, and
    status/keyboard hints. Saves captures locally via CaptureStore and
    coordinates with Doodle to return cleanly to quiet behavior.
    """

    # Signal emitted when a capture is successfully persisted
    capture_saved = Signal(object)  # emits CaptureRecord

    # Signal emitted when capture is cancelled or dismissed without saving
    capture_cancelled = Signal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        capture_store: Optional[CaptureStore] = None,
        acknowledgment_delay_ms: int = 0,
    ) -> None:
        super().__init__(parent)
        self._capture_store = capture_store
        self._acknowledgment_delay_ms = acknowledgment_delay_ms
        self._is_saved = False
        self._is_cancelled = False

        self.setWindowTitle("Doodle Quick Capture")
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(DEFAULT_CAPTURE_WIDTH, DEFAULT_CAPTURE_HEIGHT)

        self._init_ui()

    @property
    def capture_store(self) -> Optional[CaptureStore]:
        """Return the attached CaptureStore instance."""
        return self._capture_store

    @capture_store.setter
    def capture_store(self, store: Optional[CaptureStore]) -> None:
        self._capture_store = store

    @property
    def input_field(self) -> QLineEdit:
        """Return the text input widget."""
        return self._input

    @property
    def type_selector(self) -> QComboBox:
        """Return the capture type dropdown widget."""
        return self._type_combo

    @property
    def hint_label(self) -> QLabel:
        """Return the hint/status label widget."""
        return self._hint_label

    def _init_ui(self) -> None:
        """Construct the compact card layout and styling."""
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        card = QFrame(self)
        card.setObjectName("captureCard")
        card.setFixedSize(DEFAULT_CAPTURE_WIDTH, DEFAULT_CAPTURE_HEIGHT)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setSpacing(5)

        # Header row: Type selector pill dropdown + close button
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        self._type_combo = QComboBox(card)
        self._type_combo.setObjectName("captureTypeSelector")
        self._type_combo.addItem("IDEA ▾", CaptureType.IDEA)
        self._type_combo.addItem("JOURNAL ▾", CaptureType.JOURNAL)
        self._type_combo.addItem("MOOD ▾", CaptureType.MOOD)
        self._type_combo.addItem("REMEMBER ▾", CaptureType.REMEMBER)
        self._type_combo.setToolTip("Select capture type")
        self._type_combo.activated.connect(self._on_type_selected)
        header_layout.addWidget(self._type_combo)

        header_layout.addStretch()

        close_btn = QPushButton("×", card)
        close_btn.setObjectName("closeButton")
        close_btn.setFixedSize(18, 18)
        close_btn.setToolTip("Dismiss (Esc)")
        close_btn.clicked.connect(self.cancel)
        header_layout.addWidget(close_btn)

        card_layout.addLayout(header_layout)

        # Middle row: Text input
        self._input = QLineEdit(card)
        self._input.setObjectName("captureInput")
        self._input.setPlaceholderText("What's on your mind?")
        self._input.setMaxLength(10000)
        self._input.installEventFilter(self)
        self._input.textChanged.connect(self._on_text_changed)
        card_layout.addWidget(self._input)

        # Bottom row: Subtle hint / inline error label
        self._hint_label = QLabel("Enter to save · Esc to dismiss", card)
        self._hint_label.setObjectName("hintLabel")
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(self._hint_label)

        outer_layout.addWidget(card)
        self._apply_styles()

    def _apply_styles(self) -> None:
        """Apply compact dark translucent stylesheet matching InteractionMenu."""
        self.setStyleSheet("""
            QFrame#captureCard {
                background-color: rgba(28, 30, 38, 245);
                border: 1px solid rgba(255, 255, 255, 35);
                border-radius: 12px;
            }
            QComboBox#captureTypeSelector {
                background-color: rgba(255, 255, 255, 14);
                color: #e2e4ee;
                border: 1px solid rgba(255, 255, 255, 24);
                border-radius: 6px;
                padding: 2px 6px;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 0.5px;
                min-width: 90px;
            }
            QComboBox#captureTypeSelector:hover {
                background-color: rgba(255, 255, 255, 24);
                border-color: rgba(255, 255, 255, 45);
            }
            QComboBox#captureTypeSelector::drop-down {
                border: none;
                width: 0px;
            }
            QComboBox#captureTypeSelector QAbstractItemView {
                background-color: rgb(28, 30, 38);
                color: #e2e4ee;
                border: 1px solid rgba(255, 255, 255, 35);
                border-radius: 6px;
                selection-background-color: rgba(255, 255, 255, 30);
                selection-color: #ffffff;
                outline: none;
                padding: 2px;
            }
            QPushButton#closeButton {
                background-color: transparent;
                color: rgba(255, 255, 255, 120);
                border: none;
                font-size: 14px;
                font-weight: bold;
                padding: 0;
            }
            QPushButton#closeButton:hover {
                color: #ffffff;
            }
            QLineEdit#captureInput {
                background-color: rgba(255, 255, 255, 12);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 22);
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 11px;
            }
            QLineEdit#captureInput:focus {
                border: 1px solid rgba(130, 160, 255, 180);
                background-color: rgba(255, 255, 255, 18);
            }
            QLabel#hintLabel {
                color: rgba(200, 205, 220, 140);
                font-size: 9px;
            }
            QLabel#hintLabel[state="error"] {
                color: rgba(255, 120, 120, 230);
                font-weight: bold;
            }
            QLabel#hintLabel[state="success"] {
                color: rgba(120, 230, 150, 230);
                font-weight: bold;
            }
        """)

    def selected_type(self) -> CaptureType:
        """Return the currently selected CaptureType enum value."""
        data = self._type_combo.currentData()
        if isinstance(data, CaptureType):
            return data
        if isinstance(data, str):
            try:
                return CaptureType(data)
            except ValueError:
                pass
        return CaptureType.IDEA

    def set_selected_type(self, capture_type: CaptureType) -> None:
        """Set the active selection in the capture type dropdown."""
        target_val = capture_type.value if isinstance(capture_type, CaptureType) else str(capture_type)
        for i in range(self._type_combo.count()):
            data = self._type_combo.itemData(i)
            if data == capture_type or (isinstance(data, CaptureType) and data.value == target_val) or data == target_val:
                self._type_combo.setCurrentIndex(i)
                return

    def showEvent(self, event: QShowEvent) -> None:
        """Reset state flags whenever the card is displayed."""
        super().showEvent(event)
        self._is_saved = False
        self._is_cancelled = False

    def _on_type_selected(self, index: int) -> None:
        """Refocus the text input after selecting a capture type."""
        self._input.setFocus()

    def _on_text_changed(self, text: str) -> None:
        """Reset hint label to normal state when user types."""
        if self._hint_label.property("state") != "normal":
            self._show_normal_hint()

    def _show_normal_hint(self) -> None:
        """Display default keyboard hint."""
        self._hint_label.setText("Enter to save · Esc to dismiss")
        self._hint_label.setProperty("state", "normal")
        self._hint_label.style().unpolish(self._hint_label)
        self._hint_label.style().polish(self._hint_label)

    def _show_error(self, message: str) -> None:
        """Display subtle inline error message."""
        self._hint_label.setText(message)
        self._hint_label.setProperty("state", "error")
        self._hint_label.style().unpolish(self._hint_label)
        self._hint_label.style().polish(self._hint_label)

    def _show_success(self, message: str) -> None:
        """Display subtle inline success message."""
        self._hint_label.setText(message)
        self._hint_label.setProperty("state", "success")
        self._hint_label.style().unpolish(self._hint_label)
        self._hint_label.style().polish(self._hint_label)

    def show_near(
        self,
        target_rect: QRect,
        screen_bounds: Optional[QRect] = None,
        initial_type: CaptureType = CaptureType.IDEA,
    ) -> None:
        """Position and show the card near the target window with pre-selected type.

        Args:
            target_rect: Geometry rectangle of companion target window.
            screen_bounds: Optional bounding rectangle of active desktop screen.
            initial_type: CaptureType to pre-select when opening.
        """
        if screen_bounds is None:
            screen_bounds = get_usable_screen_bounds()

        self._is_saved = False
        self._is_cancelled = False
        self.set_selected_type(initial_type)
        self._input.clear()
        self._show_normal_hint()

        pos = compute_menu_position(
            target_rect=target_rect,
            menu_size=self.size(),
            screen_bounds=screen_bounds,
            margin=DEFAULT_CAPTURE_MARGIN,
        )
        self.move(pos)
        self.show()
        self.raise_()
        self.activateWindow()
        self._input.setFocus()

    def submit(self) -> None:
        """Validate input and persist capture via CaptureStore."""
        text = self._input.text().strip()
        if not text:
            self._show_error("Please enter some text.")
            return

        capture_type = self.selected_type()

        if self._capture_store is not None:
            try:
                record = self._capture_store.save_capture(
                    capture_type=capture_type,
                    content=text,
                )
            except Exception as e:
                logger.error("Failed to save quick capture: %s", e)
                self._show_error("Could not save. Press Enter to retry.")
                return

            self._is_saved = True
            self._show_success("Saved!")
            self.capture_saved.emit(record)
            self._dismiss_after_save()
        else:
            logger.warning("QuickCaptureCard submitted without an attached CaptureStore.")
            self._is_saved = True
            self._dismiss_after_save()

    def _dismiss_after_save(self) -> None:
        """Dismiss card either immediately or after brief acknowledgment delay."""
        if self._acknowledgment_delay_ms > 0:
            QTimer.singleShot(self._acknowledgment_delay_ms, self.dismiss)
        else:
            self.dismiss()

    def cancel(self) -> None:
        """Cancel capture without saving and dismiss the card."""
        if not self._is_saved and not self._is_cancelled:
            self._is_cancelled = True
            self.capture_cancelled.emit()
        self.dismiss()

    def dismiss(self) -> None:
        """Dismiss (hide) the Quick Capture card."""
        if self.isVisible():
            self.hide()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Filter input events on child widgets to reliably handle Enter and Escape."""
        if watched is self._input and event.type() == QEvent.Type.KeyPress:
            key_event = event  # type: ignore[assignment]
            if key_event.key() == Qt.Key.Key_Escape:
                self.cancel()
                return True
            if key_event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.submit()
                return True
        return super().eventFilter(watched, event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle Escape or Enter at the card window level."""
        if event.key() == Qt.Key.Key_Escape:
            self.cancel()
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.submit()
            event.accept()
            return
        super().keyPressEvent(event)

    def hideEvent(self, event: QHideEvent) -> None:
        """Emit capture_cancelled if card is hidden without having saved."""
        super().hideEvent(event)
        if not self._is_saved and not self._is_cancelled:
            self._is_cancelled = True
            self.capture_cancelled.emit()

    def cleanup(self) -> None:
        """Clean up resources during application shutdown."""
        self.dismiss()
        self.close()
