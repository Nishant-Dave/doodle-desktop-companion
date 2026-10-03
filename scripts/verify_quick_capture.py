"""Verification script for Milestone 3 Task 18C: Quick Capture UI.

Executes all 6 manual test scenarios defined in the Task 18C specification:
- Test 1: Idea (Click Doodle -> Menu -> Idea -> Compact Card -> Focus -> Type -> Enter -> Saved -> Dismisssed -> Calm IDLE)
- Test 2: Journal (Repeat using Journal)
- Test 3: Mood (Repeat using Mood)
- Test 4: Remember (Repeat using Remember)
- Test 5: Cancel (Open -> Type -> Esc -> Not saved -> Dismissed -> Calm IDLE)
- Test 6: Empty input (Open -> Enter without text -> Remains open -> No record created)
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Run Qt offscreen during automated script execution
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QEvent, QRect, QSettings, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication

from doodle.app.application import DoodleApplication
from doodle.character.state import CharacterState
from doodle.persistence.capture_store import CaptureRecord, CaptureStore, CaptureType
from doodle.persistence.settings import SettingsManager


def run_verification() -> int:
    print("=" * 70)
    print("Doodle Milestone 3 Task 18C: Quick Capture UI Verification")
    print("=" * 70)

    qapp = QApplication.instance() or QApplication(["verify_quick_capture"])

    temp_dir = tempfile.TemporaryDirectory()
    ini_path = Path(temp_dir.name) / "verify_quick_capture_settings.ini"
    qsettings = QSettings(str(ini_path), QSettings.Format.IniFormat)
    settings = SettingsManager(settings=qsettings)
    store = CaptureStore(":memory:")

    app = DoodleApplication(
        ["verify_quick_capture"],
        settings_manager=settings,
        capture_store=store,
        enable_quick_capture=True,
    )
    if app.quick_capture_card is not None:
        app.quick_capture_card._acknowledgment_delay_ms = 0

    app.lifecycle.startup()
    app.window.show()

    passed = 0
    total = 6

    try:
        # -------------------------------------------------------------
        # Test 1 — Idea
        # -------------------------------------------------------------
        print("\n--- Test 1: Quick Capture 'Idea' ---")
        # 1. Click Doodle
        app.window.character_clicked.emit()
        assert app.menu.isVisible(), "Menu should be visible after clicking Doodle"
        assert app.character.state == CharacterState.ATTENTION, "Doodle should enter ATTENTION"
        print("  [OK] Step 1: Clicked Doodle -> Menu opened, Character in ATTENTION")

        # 2. Select Idea
        app.menu.request_action("idea")
        assert not app.menu.isVisible(), "Menu should close after selecting Idea"
        print("  [OK] Step 2: Selected Idea -> Menu closed")

        # 3. Confirm compact card appears near Doodle
        card = app.quick_capture_card
        assert card is not None and card.isVisible(), "Card should be visible"
        assert card.width() == 220 and card.height() == 110, f"Card should be compact (220x110), got {card.size()}"
        assert card.selected_type() == CaptureType.IDEA, "Type should be pre-selected to IDEA"
        print("  [OK] Step 3: Compact card appeared near Doodle with IDEA pre-selected")

        # 4. Confirm text field is focused
        assert card.input_field.hasFocus(), "Text input field should receive focus automatically"
        print("  [OK] Step 4: Text input is automatically focused")

        # 5. Type a short idea
        test_thought_1 = "Design lightweight timeline for Milestone 3"
        card.input_field.setText(test_thought_1)
        print(f"  [OK] Step 5: Typed thought: '{test_thought_1}'")

        # 6. Press Enter
        enter_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        card.eventFilter(card.input_field, enter_event)
        print("  [OK] Step 6: Pressed Enter")

        # 7. Confirm card disappears & record persisted
        assert not card.isVisible(), "Card should disappear after Enter"
        assert store.count() == 1, "Store should contain 1 record"
        rec = store.list_recent(1)[0]
        assert rec.capture_type == CaptureType.IDEA
        assert rec.content == test_thought_1
        print("  [OK] Step 7: Card disappeared and record persisted to CaptureStore")

        # 8. Confirm Doodle returns to normal behavior
        assert app.character.state == CharacterState.IDLE, "Doodle should return to IDLE"
        assert app.behavior_engine.is_in_quiet_period, "Doodle should enter quiet period"
        print("  [OK] Step 8: Doodle returned to calm IDLE behavior and quiet period")
        passed += 1

        # -------------------------------------------------------------
        # Test 2 — Journal
        # -------------------------------------------------------------
        print("\n--- Test 2: Quick Capture 'Journal' ---")
        app.window.character_clicked.emit()
        app.menu.request_action("journal")
        assert card.isVisible()
        assert card.selected_type() == CaptureType.JOURNAL
        assert card.input_field.hasFocus()
        test_thought_2 = "Completed Task 18C implementation cleanly."
        card.input_field.setText(test_thought_2)
        card.eventFilter(card.input_field, enter_event)
        assert not card.isVisible()
        assert store.count() == 2
        rec2 = store.list_recent(1)[0]
        assert rec2.capture_type == CaptureType.JOURNAL
        assert rec2.content == test_thought_2
        assert app.character.state == CharacterState.IDLE
        print("  [OK] Journal capture saved successfully and Doodle returned to IDLE")
        passed += 1

        # -------------------------------------------------------------
        # Test 3 — Mood
        # -------------------------------------------------------------
        print("\n--- Test 3: Quick Capture 'Mood' ---")
        app.window.character_clicked.emit()
        app.menu.request_action("mood")
        assert card.isVisible()
        assert card.selected_type() == CaptureType.MOOD
        assert card.input_field.hasFocus()
        test_thought_3 = "Focused and satisfied with test coverage."
        card.input_field.setText(test_thought_3)
        card.eventFilter(card.input_field, enter_event)
        assert not card.isVisible()
        assert store.count() == 3
        rec3 = store.list_recent(1)[0]
        assert rec3.capture_type == CaptureType.MOOD
        assert rec3.content == test_thought_3
        assert app.character.state == CharacterState.IDLE
        print("  [OK] Mood capture saved successfully and Doodle returned to IDLE")
        passed += 1

        # -------------------------------------------------------------
        # Test 4 — Remember
        # -------------------------------------------------------------
        print("\n--- Test 4: Quick Capture 'Remember' ---")
        app.window.character_clicked.emit()
        app.menu.request_action("remember")
        assert card.isVisible()
        assert card.selected_type() == CaptureType.REMEMBER
        assert card.input_field.hasFocus()
        test_thought_4 = "Check on SQLite schema versioning before milestone tag."
        card.input_field.setText(test_thought_4)
        card.eventFilter(card.input_field, enter_event)
        assert not card.isVisible()
        assert store.count() == 4
        rec4 = store.list_recent(1)[0]
        assert rec4.capture_type == CaptureType.REMEMBER
        assert rec4.content == test_thought_4
        assert app.character.state == CharacterState.IDLE
        print("  [OK] Remember capture saved successfully and Doodle returned to IDLE")
        passed += 1

        # -------------------------------------------------------------
        # Test 5 — Cancel
        # -------------------------------------------------------------
        print("\n--- Test 5: Quick Capture 'Cancel' (Esc) ---")
        # 1. Open any capture type
        app.window.character_clicked.emit()
        app.menu.request_action("idea")
        assert card.isVisible()
        # 2. Type text
        card.input_field.setText("This thought will be cancelled")
        # 3. Press Esc
        esc_event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        card.eventFilter(card.input_field, esc_event)
        # 4. Confirm nothing is saved
        assert store.count() == 4, "Store count should remain 4; nothing should be saved"
        assert not card.isVisible(), "Card should disappear after Esc"
        # 5. Confirm Doodle returns to normal behavior
        assert app.character.state == CharacterState.IDLE, "Doodle should return to IDLE"
        print("  [OK] Cancel dismissed card, saved nothing, and Doodle returned to IDLE")
        passed += 1

        # -------------------------------------------------------------
        # Test 6 — Empty input
        # -------------------------------------------------------------
        print("\n--- Test 6: Empty input rejected without saving ---")
        # 1. Open capture
        app.window.character_clicked.emit()
        app.menu.request_action("idea")
        assert card.isVisible()
        # 2. Press Enter without text
        card.input_field.setText("")
        card.eventFilter(card.input_field, enter_event)
        # 3. Confirm card remains open
        assert card.isVisible(), "Card must remain open upon empty submission"
        assert "enter some text" in card.hint_label.text().lower(), "Inline error must be displayed"
        # 4. Confirm no record is created
        assert store.count() == 4, "No record should be created in store"
        # Dismiss cleanly
        card.cancel()
        assert not card.isVisible()
        assert app.character.state == CharacterState.IDLE
        print("  [OK] Empty input was rejected, inline hint shown, card remained open, no record created")
        passed += 1

    finally:
        app.dismiss_quick_capture()
        app.dismiss_interaction_menu()
        app.window.close()
        app.lifecycle.shutdown()
        store.close()
        qsettings.clear()
        qsettings.sync()
        del qsettings
        temp_dir.cleanup()

    print("\n" + "=" * 70)
    print(f"VERIFICATION SUMMARY: {passed}/{total} scenarios PASSED.")
    print("=" * 70)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(run_verification())
