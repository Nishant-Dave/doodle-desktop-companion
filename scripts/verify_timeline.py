"""Verification script for Milestone 3 Task 19: Quick Capture Timeline.

Executes all 7 manual verification scenarios defined in the Task 19 specification:
- Test 1: Empty timeline (With no captures -> menu -> Recent Captures -> "No captures yet.")
- Test 2: Create captures (Idea, Journal, Mood, Remember -> all 4 appear)
- Test 3: Ordering (Two captures created apart -> newest appears first)
- Test 4: Timestamp (Create capture -> confirm displayed time matches local system time)
- Test 5: Overflow (>10 captures -> panel remains compact, only 10 shown, newest first)
- Test 6: Close (Open timeline -> Esc -> closes cleanly)
- Test 7: Doodle behavior (Open and close timeline -> companion returns to calm IDLE)
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# Run Qt offscreen during automated script execution
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QPoint, QRect, QSettings, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QLabel

from doodle.app.application import DoodleApplication
from doodle.character.state import CharacterState
from doodle.persistence.capture_store import CaptureRecord, CaptureStore, CaptureType
from doodle.persistence.settings import SettingsManager
from doodle.ui.recent_captures import (
    DEFAULT_RECENT_LIMIT,
    DEFAULT_TIMELINE_HEIGHT,
    DEFAULT_TIMELINE_WIDTH,
    RecentCapturesPanel,
    format_capture_timestamp,
    format_capture_type,
)


def run_verification() -> int:
    print("=" * 70)
    print("Doodle Milestone 3 Task 19: Quick Capture Timeline Verification")
    print("=" * 70)

    qapp = QApplication.instance() or QApplication(["verify_timeline"])

    temp_dir = tempfile.TemporaryDirectory()
    ini_path = Path(temp_dir.name) / "verify_timeline_settings.ini"
    qsettings = QSettings(str(ini_path), QSettings.Format.IniFormat)
    settings = SettingsManager(settings=qsettings)
    store = CaptureStore(":memory:")

    app = DoodleApplication(
        ["verify_timeline"],
        settings_manager=settings,
        capture_store=store,
        enable_quick_capture=True,
    )

    app.lifecycle.startup()
    app.window.show()

    passed = 0
    total = 7

    try:
        # -------------------------------------------------------------
        # Test 1 — Empty timeline
        # -------------------------------------------------------------
        print("\n[Test 1] Empty timeline verification...")
        app.show_interaction_menu()
        assert app.menu.isVisible(), "Menu should be visible"
        btn = app.menu.get_action_button("recent_captures")
        assert btn is not None and btn.isEnabled(), "Recent Captures action must be enabled"

        # Click Recent Captures
        app.menu.action_requested.emit("recent_captures")
        assert not app.menu.isVisible(), "Menu must dismiss when Recent Captures requested"
        panel = app.recent_captures_panel
        assert panel is not None and panel.isVisible(), "RecentCapturesPanel must be visible"
        assert panel.empty_label is not None and panel.empty_label.isVisible(), "Empty label must be shown"
        assert "No captures yet." in panel.empty_label.text(), f"Expected 'No captures yet.', got {panel.empty_label.text()}"
        assert len(panel.rendered_items) == 0, "No item widgets should be rendered"
        panel.dismiss()
        print("[OK] Test 1 Passed: Empty state displays 'No captures yet.' calmly.")
        passed += 1

        # -------------------------------------------------------------
        # Test 2 — Create captures (Idea, Journal, Mood, Remember)
        # -------------------------------------------------------------
        print("\n[Test 2] Create 4 captures and verify all appear...")
        c_idea = store.save_capture(CaptureType.IDEA, "Explore SQLite WAL mode for companion storage")
        c_journal = store.save_capture(CaptureType.JOURNAL, "Refined animation transitions and quiet behavior today.")
        c_mood = store.save_capture(CaptureType.MOOD, "Feeling focused and content.")
        c_remember = store.save_capture(CaptureType.REMEMBER, "Review asset specs before releasing Milestone 3.")

        app.show_recent_captures()
        assert panel.isVisible(), "Timeline panel must be visible"
        assert panel.empty_label is None, "Empty label must be removed when captures exist"
        assert len(panel.rendered_items) == 4, f"Expected 4 items, got {len(panel.rendered_items)}"

        types_found = []
        for item in panel.rendered_items:
            for label in item.findChildren(QLabel):
                if label.objectName() == "itemType":
                    types_found.append(label.text())

        assert "Idea" in types_found, "Idea must appear in timeline"
        assert "Journal" in types_found, "Journal must appear in timeline"
        assert "Mood" in types_found, "Mood must appear in timeline"
        assert "Remember" in types_found, "Remember must appear in timeline"
        panel.dismiss()
        print("[OK] Test 2 Passed: All 4 capture types (Idea, Journal, Mood, Remember) displayed cleanly.")
        passed += 1

        # -------------------------------------------------------------
        # Test 3 — Ordering (Newest appears first)
        # -------------------------------------------------------------
        print("\n[Test 3] Ordering verification (newest first)...")
        # Most recently saved was c_remember
        app.show_recent_captures()
        first_item = panel.rendered_items[0]
        first_type = [w.text() for w in first_item.findChildren(QLabel) if w.objectName() == "itemType"][0]
        first_content = [w.text() for w in first_item.findChildren(QLabel) if w.objectName() == "itemContent"][0]

        assert first_type == "Remember", f"Expected first item to be 'Remember', got {first_type}"
        assert "Review asset specs" in first_content, f"Expected newest content, got {first_content}"

        last_item = panel.rendered_items[-1]
        last_type = [w.text() for w in last_item.findChildren(QLabel) if w.objectName() == "itemType"][0]
        assert last_type == "Idea", f"Expected oldest item to be 'Idea', got {last_type}"
        panel.dismiss()
        print("[OK] Test 3 Passed: Chronological ordering verified (newest captures at top).")
        passed += 1

        # -------------------------------------------------------------
        # Test 4 — Timestamp presentation
        # -------------------------------------------------------------
        print("\n[Test 4] Local timestamp presentation verification...")
        now_local = datetime.now().astimezone()
        now_utc = datetime.now(timezone.utc)
        test_rec = store.save_capture(CaptureType.IDEA, "Fresh local timestamp test", created_at=now_utc.isoformat().replace("+00:00", "Z"))
        app.show_recent_captures()

        newest_item = panel.rendered_items[0]
        time_label = [w.text() for w in newest_item.findChildren(QLabel) if w.objectName() == "itemTimestamp"][0]
        assert time_label.startswith("Today · "), f"Expected 'Today · ...', got {time_label}"
        # Check current hour representation (12-hour format with AM/PM)
        expected_hour = now_local.strftime("%I").lstrip("0")
        assert expected_hour in time_label, f"Expected hour {expected_hour} in {time_label}"
        panel.dismiss()
        print(f"[OK] Test 4 Passed: Displayed timestamp '{time_label}' correctly matches local time.")
        passed += 1

        # -------------------------------------------------------------
        # Test 5 — Overflow (>10 captures)
        # -------------------------------------------------------------
        print("\n[Test 5] Overflow behavior (>10 captures)...")
        # Add 10 more captures to exceed 10 total
        for i in range(10):
            store.save_capture(CaptureType.JOURNAL, f"Batch journal entry #{i+1}")

        app.show_recent_captures()
        assert panel.width() == DEFAULT_TIMELINE_WIDTH, f"Width should remain {DEFAULT_TIMELINE_WIDTH}px"
        assert panel.height() == DEFAULT_TIMELINE_HEIGHT, f"Height should remain {DEFAULT_TIMELINE_HEIGHT}px"
        assert len(panel.rendered_items) == DEFAULT_RECENT_LIMIT, (
            f"Expected max limit {DEFAULT_RECENT_LIMIT} items, got {len(panel.rendered_items)}"
        )
        # Top item should be the last created batch entry
        top_item_content = [w.text() for w in panel.rendered_items[0].findChildren(QLabel) if w.objectName() == "itemContent"][0]
        assert "Batch journal entry #10" in top_item_content, f"Expected newest batch item at top, got {top_item_content}"
        panel.dismiss()
        print("[OK] Test 5 Passed: Overflow capped at 10 items, compact dimensions preserved.")
        passed += 1

        # -------------------------------------------------------------
        # Test 6 — Close via Esc
        # -------------------------------------------------------------
        print("\n[Test 6] Dismissal via Escape key...")
        app.show_recent_captures()
        assert panel.isVisible(), "Panel must be visible before Esc"
        esc_event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            int(Qt.Key.Key_Escape),
            Qt.KeyboardModifier.NoModifier,
        )
        panel.keyPressEvent(esc_event)
        assert not panel.isVisible(), "Panel must be dismissed when Esc is pressed"
        print("[OK] Test 6 Passed: Timeline closes cleanly on Esc key.")
        passed += 1

        # -------------------------------------------------------------
        # Test 7 — Doodle companion behavior
        # -------------------------------------------------------------
        print("\n[Test 7] Doodle companion behavioral coherence...")
        # While timeline is open, character should be attentive
        app.show_recent_captures()
        assert app.character.state == CharacterState.ATTENTION, f"Expected ATTENTION while timeline open, got {app.character.state}"

        # After timeline is dismissed, character should return to calm IDLE
        panel.dismiss()
        assert app.character.state == CharacterState.IDLE, f"Expected IDLE after timeline dismissed, got {app.character.state}"
        assert not panel.isVisible(), "Timeline must be hidden"
        assert not app.menu.isVisible(), "Menu must remain hidden"
        assert app.behavior_engine.is_idle_eligible, "Companion must be eligible for idle behavior"
        print("[OK] Test 7 Passed: Character entered ATTENTION during view and returned to calm IDLE upon close.")
        passed += 1

    finally:
        app.lifecycle.shutdown()
        store.close()
        temp_dir.cleanup()

    print("\n" + "=" * 70)
    print(f"VERIFICATION RESULT: {passed}/{total} manual test scenarios PASSED.")
    print("=" * 70)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(run_verification())
