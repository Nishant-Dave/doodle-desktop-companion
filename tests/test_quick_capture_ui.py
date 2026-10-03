"""Comprehensive tests for Doodle Quick Capture UI and application wiring."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

# Ensure offscreen Qt platform for test execution
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QSettings, Qt
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import QApplication

from doodle.app.application import DoodleApplication
from doodle.behavior.engine import BehaviorEngine
from doodle.behavior.rules import (
    EVENT_CAPTURE_CANCELLED,
    EVENT_CAPTURE_REQUESTED,
    EVENT_CAPTURE_SAVED,
)
from doodle.character.state import CharacterState
from doodle.persistence.capture_store import CaptureRecord, CaptureStore, CaptureType
from doodle.persistence.settings import SettingsManager
from doodle.ui.interaction_menu import InteractionMenu
from doodle.ui.quick_capture import (
    DEFAULT_CAPTURE_HEIGHT,
    DEFAULT_CAPTURE_WIDTH,
    QuickCaptureCard,
)


class TestQuickCaptureCardUnit(unittest.TestCase):
    """Unit tests for QuickCaptureCard widget in isolation."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_quick_capture_ui"])

    def setUp(self) -> None:
        self.store = CaptureStore(":memory:")
        self.card = QuickCaptureCard(capture_store=self.store, acknowledgment_delay_ms=0)

    def tearDown(self) -> None:
        self.card.cleanup()
        self.store.close()

    def test_card_initial_properties(self) -> None:
        """Card has compact dimensions, frameless popup flags, and translucency."""
        self.assertEqual(self.card.width(), DEFAULT_CAPTURE_WIDTH)
        self.assertEqual(self.card.height(), DEFAULT_CAPTURE_HEIGHT)
        flags = self.card.windowFlags()
        self.assertTrue(bool(flags & Qt.WindowType.Popup))
        self.assertTrue(bool(flags & Qt.WindowType.FramelessWindowHint))
        self.assertTrue(self.card.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
        self.assertEqual(self.card.hint_label.text(), "Enter to save · Esc to dismiss")

    def test_type_selector_defaults_and_selection(self) -> None:
        """Type selector defaults to IDEA and correctly sets/gets types."""
        self.assertEqual(self.card.selected_type(), CaptureType.IDEA)

        for c_type in (CaptureType.JOURNAL, CaptureType.MOOD, CaptureType.REMEMBER, CaptureType.IDEA):
            self.card.set_selected_type(c_type)
            self.assertEqual(self.card.selected_type(), c_type)

    def test_show_near_positions_and_focuses_input(self) -> None:
        """show_near sets initial type, positions card, clears text, and focuses input."""
        target = QRect(500, 500, 160, 160)
        screen = QRect(0, 0, 1920, 1080)
        self.card.input_field.setText("old leftover text")

        self.card.show_near(target, screen_bounds=screen, initial_type=CaptureType.JOURNAL)

        self.assertTrue(self.card.isVisible())
        self.assertEqual(self.card.selected_type(), CaptureType.JOURNAL)
        self.assertEqual(self.card.input_field.text(), "")
        self.assertTrue(self.card.input_field.hasFocus())
        self.assertGreater(self.card.pos().x(), 0)
        self.assertGreater(self.card.pos().y(), 0)

    def test_enter_with_valid_content_saves_and_dismisses(self) -> None:
        """Valid submission persists record to CaptureStore, emits capture_saved, and dismisses."""
        saved_records: list[CaptureRecord] = []
        self.card.capture_saved.connect(saved_records.append)

        self.card.show()
        self.card.set_selected_type(CaptureType.IDEA)
        self.card.input_field.setText("Build lightweight capture overlay")

        self.card.submit()

        self.assertEqual(len(saved_records), 1)
        record = saved_records[0]
        self.assertEqual(record.capture_type, CaptureType.IDEA)
        self.assertEqual(record.content, "Build lightweight capture overlay")
        self.assertIsNotNone(record.id)

        # Verified in SQLite database
        self.assertEqual(self.store.count(), 1)
        db_record = self.store.get_capture(record.id)  # type: ignore[arg-type]
        self.assertIsNotNone(db_record)
        self.assertEqual(db_record.content, "Build lightweight capture overlay")

        # Card is dismissed
        self.assertFalse(self.card.isVisible())

    def test_empty_content_does_not_save_and_keeps_card_open(self) -> None:
        """Submitting empty string does not save, keeps card open, and shows inline error."""
        saved_records: list[CaptureRecord] = []
        self.card.capture_saved.connect(saved_records.append)

        self.card.show()
        self.card.input_field.setText("")
        self.card.submit()

        self.assertEqual(len(saved_records), 0)
        self.assertEqual(self.store.count(), 0)
        self.assertTrue(self.card.isVisible())
        self.assertIn("enter some text", self.card.hint_label.text().lower())
        self.assertEqual(self.card.hint_label.property("state"), "error")

    def test_whitespace_only_content_does_not_save(self) -> None:
        """Submitting whitespace-only text does not save, keeps card open, and shows inline error."""
        saved_records: list[CaptureRecord] = []
        self.card.capture_saved.connect(saved_records.append)

        self.card.show()
        self.card.input_field.setText("    \t  \n  ")
        self.card.submit()

        self.assertEqual(len(saved_records), 0)
        self.assertEqual(self.store.count(), 0)
        self.assertTrue(self.card.isVisible())
        self.assertIn("enter some text", self.card.hint_label.text().lower())

    def test_typing_clears_error_hint(self) -> None:
        """Typing text after an error resets the hint label back to normal."""
        self.card.show()
        self.card.input_field.setText("")
        self.card.submit()
        self.assertEqual(self.card.hint_label.property("state"), "error")

        self.card.input_field.setText("a")
        self.assertEqual(self.card.hint_label.text(), "Enter to save · Esc to dismiss")
        self.assertEqual(self.card.hint_label.property("state"), "normal")

    def test_escape_cancels_without_saving(self) -> None:
        """Escape cancels capture, emits capture_cancelled, dismisses, and saves nothing."""
        cancelled_events: list[bool] = []
        self.card.capture_cancelled.connect(lambda: cancelled_events.append(True))

        self.card.show()
        self.card.input_field.setText("Discarded thought")

        # Simulate Escape key press
        key_event = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Escape,
            Qt.KeyboardModifier.NoModifier,
        )
        self.card.keyPressEvent(key_event)

        self.assertEqual(len(cancelled_events), 1)
        self.assertFalse(self.card.isVisible())
        self.assertEqual(self.store.count(), 0)

    def test_event_filter_handles_input_enter_and_escape(self) -> None:
        """EventFilter on input_field handles Return to submit and Escape to cancel."""
        saved_records: list[CaptureRecord] = []
        cancelled_events: list[bool] = []
        self.card.capture_saved.connect(saved_records.append)
        self.card.capture_cancelled.connect(lambda: cancelled_events.append(True))

        self.card.show()
        self.card.input_field.setText("Test event filter submission")

        # Simulate Enter key on input_field
        enter_event = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Return,
            Qt.KeyboardModifier.NoModifier,
        )
        handled = self.card.eventFilter(self.card.input_field, enter_event)
        self.assertTrue(handled)
        self.assertEqual(len(saved_records), 1)
        self.assertFalse(self.card.isVisible())

        # Reset card and simulate Escape key on input_field
        self.card.show()
        self.card.input_field.setText("Will be cancelled")
        esc_event = QKeyEvent(
            QEvent.Type.KeyPress,
            Qt.Key.Key_Escape,
            Qt.KeyboardModifier.NoModifier,
        )
        handled = self.card.eventFilter(self.card.input_field, esc_event)
        self.assertTrue(handled)
        self.assertEqual(len(cancelled_events), 1)
        self.assertFalse(self.card.isVisible())

    def test_close_button_cancels_without_saving(self) -> None:
        """Clicking the close '×' button dismisses and cancels without saving."""
        cancelled_events: list[bool] = []
        self.card.capture_cancelled.connect(lambda: cancelled_events.append(True))

        self.card.show()
        self.card.input_field.setText("Unsaved thought")
        self.card.cancel()

        self.assertEqual(len(cancelled_events), 1)
        self.assertFalse(self.card.isVisible())
        self.assertEqual(self.store.count(), 0)

    def test_save_failure_keeps_input_intact_and_card_open(self) -> None:
        """If CaptureStore fails, input text is preserved, card stays open, inline error shown."""
        failing_store = MagicMock(spec=CaptureStore)
        failing_store.save_capture.side_effect = RuntimeError("Disk I/O failure")
        self.card.capture_store = failing_store

        self.card.show()
        self.card.input_field.setText("Important thoughts that must not be lost")
        self.card.submit()

        self.assertTrue(self.card.isVisible())
        self.assertEqual(self.card.input_field.text(), "Important thoughts that must not be lost")
        self.assertIn("could not save", self.card.hint_label.text().lower())
        self.assertEqual(self.card.hint_label.property("state"), "error")

        # Now fix the store and retry
        self.card.capture_store = self.store
        self.card.submit()

        self.assertFalse(self.card.isVisible())
        self.assertEqual(self.store.count(), 1)


class TestQuickCaptureAppIntegration(unittest.TestCase):
    """Integration tests verifying Quick Capture wiring in DoodleApplication."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_quick_capture_app"])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ini_path = Path(self.temp_dir.name) / "test_app_settings.ini"
        self.qsettings = QSettings(str(self.ini_path), QSettings.Format.IniFormat)
        self.settings = SettingsManager(settings=self.qsettings)
        self.store = CaptureStore(":memory:")
        self.app = DoodleApplication(
            ["test_app"],
            settings_manager=self.settings,
            capture_store=self.store,
            enable_quick_capture=True,
        )
        # Ensure synchronous card dismissal for deterministic tests
        if self.app.quick_capture_card is not None:
            self.app.quick_capture_card._acknowledgment_delay_ms = 0

    def tearDown(self) -> None:
        if hasattr(self, "app") and self.app is not None:
            self.app.dismiss_quick_capture()
            self.app.dismiss_interaction_menu()
            self.app.window.close()
            self.app.lifecycle.shutdown()
        self.store.close()
        self.qsettings.clear()
        self.qsettings.sync()
        del self.qsettings
        self.temp_dir.cleanup()

    def test_capture_actions_enabled_when_quick_capture_active(self) -> None:
        """When quick capture is enabled, idea, journal, mood, remember are enabled on menu."""
        for action_id in ("idea", "journal", "mood", "remember"):
            self.assertTrue(
                self.app.menu.is_action_enabled(action_id),
                f"Action '{action_id}' should be enabled when quick capture is active.",
            )
        # Settings remains disabled
        self.assertFalse(self.app.menu.is_action_enabled("settings"))

    def test_menu_action_idea_opens_quick_capture_with_idea_type(self) -> None:
        """Selecting 'idea' closes menu and opens QuickCaptureCard with CaptureType.IDEA."""
        self.app.show_interaction_menu()
        self.assertTrue(self.app.menu.isVisible())
        self.assertEqual(self.app.character.state, CharacterState.ATTENTION)

        # Trigger Idea action
        self.app.menu.request_action("idea")

        self.assertFalse(self.app.menu.isVisible())
        self.assertIsNotNone(self.app.quick_capture_card)
        self.assertTrue(self.app.quick_capture_card.isVisible())
        self.assertEqual(self.app.quick_capture_card.selected_type(), CaptureType.IDEA)
        self.assertTrue(self.app.quick_capture_card.input_field.hasFocus())
        self.assertEqual(self.app.character.state, CharacterState.ATTENTION)

    def test_menu_actions_open_corresponding_types(self) -> None:
        """Each menu action opens the card with the corresponding CaptureType pre-selected."""
        action_map = {
            "journal": CaptureType.JOURNAL,
            "mood": CaptureType.MOOD,
            "remember": CaptureType.REMEMBER,
            "idea": CaptureType.IDEA,
        }
        for action_id, expected_type in action_map.items():
            self.app.show_interaction_menu()
            self.app.menu.request_action(action_id)

            card = self.app.quick_capture_card
            self.assertIsNotNone(card)
            self.assertTrue(card.isVisible())
            self.assertEqual(card.selected_type(), expected_type)
            card.dismiss()

    def test_full_save_flow_returns_doodle_to_calm_idle(self) -> None:
        """Typing and saving persists record, dismisses card, and returns Doodle to IDLE quiet period."""
        self.app.show_interaction_menu()
        self.app.menu.request_action("idea")
        card = self.app.quick_capture_card
        self.assertIsNotNone(card)

        card.input_field.setText("Refactor behavior rules for clarity")
        card.submit()

        self.assertFalse(card.isVisible())
        self.assertEqual(self.store.count(), 1)
        self.assertEqual(self.app.character.state, CharacterState.IDLE)
        self.assertTrue(self.app.behavior_engine.is_in_quiet_period)

    def test_full_cancel_flow_returns_doodle_to_calm_idle(self) -> None:
        """Cancelling via Escape dismisses card and returns Doodle to calm IDLE without saving."""
        self.app.show_interaction_menu()
        self.app.menu.request_action("mood")
        card = self.app.quick_capture_card
        self.assertIsNotNone(card)

        card.input_field.setText("Feeling slightly distracted")
        card.cancel()

        self.assertFalse(card.isVisible())
        self.assertEqual(self.store.count(), 0)
        self.assertEqual(self.app.character.state, CharacterState.IDLE)

    def test_character_click_toggles_card_dismissal(self) -> None:
        """Clicking character while QuickCaptureCard is open dismisses it."""
        self.app.show_quick_capture(CaptureType.IDEA)
        card = self.app.quick_capture_card
        self.assertIsNotNone(card)
        self.assertTrue(card.isVisible())

        # Click character
        self.app.window.character_clicked.emit()

        self.assertFalse(card.isVisible())
        self.assertFalse(self.app.menu.isVisible())
        self.assertEqual(self.app.character.state, CharacterState.IDLE)

    def test_character_moved_dismisses_quick_capture_card(self) -> None:
        """Moving companion during drag dismisses QuickCaptureCard."""
        self.app.show_quick_capture(CaptureType.JOURNAL)
        card = self.app.quick_capture_card
        self.assertIsNotNone(card)
        self.assertTrue(card.isVisible())

        # Window moves
        self.app.window.character_moved.emit(QPoint(350, 350))

        self.assertFalse(card.isVisible())

    def test_hide_companion_dismisses_quick_capture_card(self) -> None:
        """Hiding companion from tray dismisses open QuickCaptureCard."""
        self.app.show_quick_capture(CaptureType.MOOD)
        card = self.app.quick_capture_card
        self.assertIsNotNone(card)
        self.assertTrue(card.isVisible())

        self.app.hide_companion()

        self.assertFalse(card.isVisible())
        self.assertFalse(self.app.window.isVisible())

    def test_close_button_no_focus_and_tab_order(self) -> None:
        """Close button has NoFocus so Tab navigates directly between input and type combo."""
        card = self.app.quick_capture_card
        self.assertIsNotNone(card)
        self.assertEqual(card._close_btn.focusPolicy(), Qt.FocusPolicy.NoFocus)

    def test_type_selector_delegate_clean_display(self) -> None:
        """TypeSelectorDelegate renders clean names in the popup view without down chevrons."""
        card = self.app.quick_capture_card
        self.assertIsNotNone(card)
        delegate = card.type_selector.itemDelegate()
        self.assertIsNotNone(delegate)
        for val in ("IDEA ▾", "JOURNAL ▾", "MOOD ▾", "REMEMBER ▾"):
            display = delegate.displayText(val, None)
            self.assertNotIn("▾", display)
            self.assertEqual(display, val.replace(" ▾", "").strip())

    def test_edge_positioning_and_clamping(self) -> None:
        """Card stays completely within screen bounds across all 4 screen edges/corners."""
        card = self.app.quick_capture_card
        self.assertIsNotNone(card)
        screen = QRect(0, 0, 1920, 1080)

        # Top-left corner
        card.show_near(QRect(0, 0, 160, 160), screen_bounds=screen)
        card_rect = QRect(card.pos(), card.size())
        self.assertTrue(screen.contains(card_rect), f"Card {card_rect} should be within {screen}")

        # Top-right corner
        card.show_near(QRect(1760, 0, 160, 160), screen_bounds=screen)
        card_rect = QRect(card.pos(), card.size())
        self.assertTrue(screen.contains(card_rect), f"Card {card_rect} should be within {screen}")

        # Bottom-left corner
        card.show_near(QRect(0, 920, 160, 160), screen_bounds=screen)
        card_rect = QRect(card.pos(), card.size())
        self.assertTrue(screen.contains(card_rect), f"Card {card_rect} should be within {screen}")

        # Bottom-right corner
        card.show_near(QRect(1760, 920, 160, 160), screen_bounds=screen)
        card_rect = QRect(card.pos(), card.size())
        self.assertTrue(screen.contains(card_rect), f"Card {card_rect} should be within {screen}")

    def test_drag_repositioning_flow(self) -> None:
        """Dragging companion window updates position for subsequent Quick Capture opens."""
        # 1. Open at initial position
        self.app.show_quick_capture(CaptureType.IDEA)
        card = self.app.quick_capture_card
        self.assertIsNotNone(card)
        initial_pos = card.pos()
        card.dismiss()

        # 2. Simulate dragging companion to a new position
        new_window_pos = QPoint(700, 700)
        self.app.window.move(new_window_pos)

        # 3. Open Quick Capture again
        self.app.show_quick_capture(CaptureType.IDEA)
        new_card_pos = card.pos()
        self.assertNotEqual(initial_pos, new_card_pos)
        self.assertGreater(new_card_pos.x(), 500)

    def test_outside_click_dismissal(self) -> None:
        """Clicking outside or dismissing the card cancels cleanly without saving."""
        self.app.show_quick_capture(CaptureType.JOURNAL)
        card = self.app.quick_capture_card
        self.assertIsNotNone(card)
        self.assertTrue(card.isVisible())

        # Simulate outside dismissal (hiding without saving)
        card.dismiss()

        self.assertFalse(card.isVisible())
        self.assertEqual(self.store.count(), 0)
        self.assertEqual(self.app.character.state, CharacterState.IDLE)


if __name__ == "__main__":
    unittest.main()
