"""Unit and integration tests for Quick Capture Timeline (RecentCapturesPanel)."""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

# Ensure offscreen Qt platform for test execution
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect, QSettings, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QLabel

from doodle.app.application import DoodleApplication
from doodle.behavior.engine import BehaviorEngine
from doodle.character.state import CharacterState
from doodle.persistence.capture_store import CaptureRecord, CaptureStore, CaptureType
from doodle.persistence.settings import SettingsManager
from doodle.ui.interaction_menu import AVAILABLE_ACTIONS, InteractionMenu
from doodle.ui.recent_captures import (
    DEFAULT_RECENT_LIMIT,
    DEFAULT_TIMELINE_HEIGHT,
    DEFAULT_TIMELINE_WIDTH,
    RecentCapturesPanel,
    format_capture_timestamp,
    format_capture_type,
)


class TestTimestampAndTypeFormatting(unittest.TestCase):
    """Test pure functions for type and timestamp presentation."""

    def test_format_capture_type(self) -> None:
        """CaptureType enums and strings are formatted as capitalized labels."""
        self.assertEqual(format_capture_type(CaptureType.IDEA), "Idea")
        self.assertEqual(format_capture_type(CaptureType.JOURNAL), "Journal")
        self.assertEqual(format_capture_type(CaptureType.MOOD), "Mood")
        self.assertEqual(format_capture_type(CaptureType.REMEMBER), "Remember")
        self.assertEqual(format_capture_type("idea"), "Idea")
        self.assertEqual(format_capture_type("JOURNAL"), "Journal")

    def test_format_capture_timestamp_today(self) -> None:
        """Captures created today display as 'Today · <time>'."""
        # Fixed reference point in local timezone
        now_local = datetime(2026, 10, 4, 15, 30, 0).astimezone()
        # Same day, earlier time
        utc_dt = datetime(2026, 10, 4, 10, 15, 0, tzinfo=timezone.utc)
        # Convert utc_dt to match same date as now_local
        local_target = now_local.replace(hour=11, minute=42, second=0)
        utc_target = local_target.astimezone(timezone.utc)
        iso_str = utc_target.strftime("%Y-%m-%dT%H:%M:%SZ")

        result = format_capture_timestamp(iso_str, now=now_local)
        self.assertTrue(result.startswith("Today · "))
        self.assertIn("11:42", result)

    def test_format_capture_timestamp_yesterday(self) -> None:
        """Captures created yesterday display as 'Yesterday · <time>'."""
        now_local = datetime(2026, 10, 4, 15, 30, 0).astimezone()
        from datetime import timedelta
        yesterday_local = (now_local - timedelta(days=1)).replace(hour=20, minute=15)
        utc_yesterday = yesterday_local.astimezone(timezone.utc)
        iso_str = utc_yesterday.strftime("%Y-%m-%dT%H:%M:%SZ")

        result = format_capture_timestamp(iso_str, now=now_local)
        self.assertTrue(result.startswith("Yesterday · "))
        self.assertIn("8:15", result)

    def test_format_capture_timestamp_earlier_this_year(self) -> None:
        """Captures earlier this year display as 'MMM D · <time>'."""
        now_local = datetime(2026, 10, 4, 15, 30, 0).astimezone()
        earlier_local = now_local.replace(month=8, day=15, hour=9, minute=5)
        utc_earlier = earlier_local.astimezone(timezone.utc)
        iso_str = utc_earlier.strftime("%Y-%m-%dT%H:%M:%SZ")

        result = format_capture_timestamp(iso_str, now=now_local)
        self.assertIn("Aug 15", result)
        self.assertIn("9:05", result)
        self.assertNotIn("2026", result)

    def test_format_capture_timestamp_different_year(self) -> None:
        """Captures from previous years include the year."""
        now_local = datetime(2026, 10, 4, 15, 30, 0).astimezone()
        past_year_local = now_local.replace(year=2024, month=5, day=20, hour=14, minute=0)
        utc_past = past_year_local.astimezone(timezone.utc)
        iso_str = utc_past.strftime("%Y-%m-%dT%H:%M:%SZ")

        result = format_capture_timestamp(iso_str, now=now_local)
        self.assertIn("2024", result)
        self.assertIn("May 20", result)

    def test_format_capture_timestamp_fallback_on_invalid(self) -> None:
        """Invalid timestamp string falls back gracefully to raw string."""
        raw = "invalid-iso-date"
        result = format_capture_timestamp(raw)
        self.assertEqual(result, raw)


class TestRecentCapturesPanelUnit(unittest.TestCase):
    """Unit tests for RecentCapturesPanel widget."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_timeline"])

    def setUp(self) -> None:
        self.panel = RecentCapturesPanel()

    def tearDown(self) -> None:
        self.panel.cleanup()

    def test_panel_initial_dimensions_and_flags(self) -> None:
        """Panel has compact dimensions, popup flags, and translucency."""
        self.assertEqual(self.panel.width(), DEFAULT_TIMELINE_WIDTH)
        self.assertEqual(self.panel.height(), DEFAULT_TIMELINE_HEIGHT)
        flags = self.panel.windowFlags()
        self.assertTrue(bool(flags & Qt.WindowType.Popup))
        self.assertTrue(bool(flags & Qt.WindowType.FramelessWindowHint))
        self.assertTrue(self.panel.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))

    def test_empty_state_display(self) -> None:
        """Empty capture list displays empty state message."""
        self.panel.show_captures([])
        self.assertIsNotNone(self.panel.empty_label)
        self.assertTrue(self.panel.empty_label.isVisible())
        self.assertEqual(self.panel.empty_label.text(), "No captures yet.")
        self.assertEqual(len(self.panel.rendered_items), 0)

    def test_renders_captures_newest_first(self) -> None:
        """Panel renders records in the provided newest-first order with type, content, timestamp."""
        records = [
            CaptureRecord(
                id=3,
                capture_type=CaptureType.IDEA,
                content="Newest capture: build SQLite store",
                created_at="2026-10-04T12:00:00Z",
            ),
            CaptureRecord(
                id=2,
                capture_type=CaptureType.JOURNAL,
                content="Middle capture: finished milestone 2",
                created_at="2026-10-04T11:00:00Z",
            ),
            CaptureRecord(
                id=1,
                capture_type=CaptureType.MOOD,
                content="Oldest capture: feeling focused",
                created_at="2026-10-04T10:00:00Z",
            ),
        ]
        self.panel.show_captures(records)

        self.assertIsNone(self.panel.empty_label)
        self.assertEqual(len(self.panel.rendered_items), 3)

        # Inspect first rendered item (newest)
        first_item = self.panel.rendered_items[0]
        type_labels = [w for w in first_item.findChildren(QLabel) if w.text() == "Idea"]
        self.assertEqual(len(type_labels), 1)

        content_labels = [
            w for w in first_item.findChildren(QLabel) if "Newest capture" in w.text()
        ]
        self.assertEqual(len(content_labels), 1)
        self.assertTrue(content_labels[0].wordWrap())

        # Inspect second item
        second_item = self.panel.rendered_items[1]
        self.assertTrue(any(w.text() == "Journal" for w in second_item.findChildren(QLabel)))
        self.assertTrue(
            any("Middle capture" in w.text() for w in second_item.findChildren(QLabel))
        )

        # Inspect third item
        third_item = self.panel.rendered_items[2]
        self.assertTrue(any(w.text() == "Mood" for w in third_item.findChildren(QLabel)))
        self.assertTrue(
            any("Oldest capture" in w.text() for w in third_item.findChildren(QLabel))
        )

    def test_dismiss_emits_signal(self) -> None:
        """Dismissing the panel emits dismissed signal."""
        signal_received = False

        def on_dismiss() -> None:
            nonlocal signal_received
            signal_received = True

        self.panel.dismissed.connect(on_dismiss)
        self.panel.show()
        self.assertTrue(self.panel.isVisible())

        self.panel.dismiss()
        self.assertFalse(self.panel.isVisible())
        self.assertTrue(signal_received)

    def test_close_button_dismisses(self) -> None:
        """Clicking close button dismisses panel."""
        self.panel.show()
        self.assertTrue(self.panel.isVisible())

        self.panel.close_button.click()
        self.assertFalse(self.panel.isVisible())

    def test_esc_key_dismisses_panel(self) -> None:
        """Pressing Escape key dismisses the panel."""
        self.panel.show()
        self.assertTrue(self.panel.isVisible())

        esc_event = QKeyEvent(
            QKeyEvent.Type.KeyPress,
            int(Qt.Key.Key_Escape),
            Qt.KeyboardModifier.NoModifier,
        )
        self.panel.keyPressEvent(esc_event)
        self.assertFalse(self.panel.isVisible())

    def test_positioning_stays_on_screen(self) -> None:
        """show_near clamps panel position to usable screen bounds."""
        target = QRect(100, 100, 160, 160)
        screen = QRect(0, 0, 1920, 1080)
        self.panel.show_near(target, screen_bounds=screen)

        self.assertTrue(self.panel.isVisible())
        geom = self.panel.geometry()
        self.assertGreaterEqual(geom.left(), screen.left())
        self.assertLessEqual(geom.right(), screen.right())
        self.assertGreaterEqual(geom.top(), screen.top())
        self.assertLessEqual(geom.bottom(), screen.bottom())


class TestTimelineApplicationIntegration(unittest.TestCase):
    """Integration tests for Timeline with DoodleApplication and InteractionMenu."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_timeline_app"])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_timeline.db"
        self.store = CaptureStore(str(self.db_path))

        self.ini_path = Path(self.temp_dir.name) / "test_settings.ini"
        self.qsettings = QSettings(str(self.ini_path), QSettings.Format.IniFormat)
        self.qsettings.clear()
        self.settings_manager = SettingsManager(settings=self.qsettings)

        self.app = DoodleApplication(
            settings_manager=self.settings_manager,
            capture_store=self.store,
            enable_quick_capture=True,
        )

    def tearDown(self) -> None:
        self.app.lifecycle.shutdown()
        self.store.close()
        self.temp_dir.cleanup()

    def test_recent_captures_action_exists_in_interaction_menu(self) -> None:
        """InteractionMenu defines and exposes 'Recent Captures' action button."""
        action_names = [action_id for action_id, _ in AVAILABLE_ACTIONS]
        self.assertIn("recent_captures", action_names)

        btn = self.app.menu.get_action_button("recent_captures")
        self.assertIsNotNone(btn)
        self.assertEqual(btn.text(), "Recent Captures")
        self.assertTrue(btn.isEnabled())

    def test_action_disabled_when_quick_capture_disabled(self) -> None:
        """Recent Captures button is disabled when enable_quick_capture is False."""
        app_no_qc = DoodleApplication(
            settings_manager=self.settings_manager,
            enable_quick_capture=False,
        )
        try:
            self.assertIsNone(app_no_qc.recent_captures_panel)
            btn = app_no_qc.menu.get_action_button("recent_captures")
            self.assertIsNotNone(btn)
            self.assertFalse(btn.isEnabled())
        finally:
            app_no_qc.lifecycle.shutdown()

    def test_menu_action_opens_timeline(self) -> None:
        """Selecting 'Recent Captures' in InteractionMenu opens the timeline."""
        self.app.show_interaction_menu()
        self.assertTrue(self.app.menu.isVisible())

        # Select Recent Captures
        self.app.menu.action_requested.emit("recent_captures")

        # Menu is dismissed and panel is visible
        self.assertFalse(self.app.menu.isVisible())
        self.assertIsNotNone(self.app.recent_captures_panel)
        self.assertTrue(self.app.recent_captures_panel.isVisible())
        self.assertEqual(self.app.character.state, CharacterState.ATTENTION)

    def test_timeline_loads_from_store_and_shows_latest_first(self) -> None:
        """Timeline queries CaptureStore and renders captures newest first."""
        # Create 3 captures with slight delay
        rec1 = self.store.save_capture(CaptureType.IDEA, "First idea")
        rec2 = self.store.save_capture(CaptureType.JOURNAL, "Second journal")
        rec3 = self.store.save_capture(CaptureType.MOOD, "Third mood")

        self.app.show_recent_captures()

        panel = self.app.recent_captures_panel
        self.assertIsNotNone(panel)
        self.assertTrue(panel.isVisible())
        self.assertEqual(len(panel.rendered_items), 3)

        # First displayed item must be rec3 (newest)
        first_item = panel.rendered_items[0]
        self.assertTrue(any("Third mood" in w.text() for w in first_item.findChildren(QLabel)))

        # Last displayed item must be rec1 (oldest)
        last_item = panel.rendered_items[2]
        self.assertTrue(any("First idea" in w.text() for w in last_item.findChildren(QLabel)))

    def test_configured_recent_limit_respected(self) -> None:
        """Only the configured recent limit (default 10) is displayed when many captures exist."""
        # Create 15 captures
        for i in range(15):
            self.store.save_capture(CaptureType.IDEA, f"Capture number {i+1}")

        self.app.show_recent_captures(limit=DEFAULT_RECENT_LIMIT)

        panel = self.app.recent_captures_panel
        self.assertIsNotNone(panel)
        self.assertEqual(len(panel.rendered_items), 10)

        # Newest capture (#15) should be first
        first_item = panel.rendered_items[0]
        self.assertTrue(any("Capture number 15" in w.text() for w in first_item.findChildren(QLabel)))

        # 10th capture (#6) should be last
        tenth_item = panel.rendered_items[9]
        self.assertTrue(any("Capture number 6" in w.text() for w in tenth_item.findChildren(QLabel)))

    def test_closing_timeline_restores_character_to_idle(self) -> None:
        """Dismissing timeline returns companion to IDLE state without new character states."""
        self.app.show_recent_captures()
        self.assertEqual(self.app.character.state, CharacterState.ATTENTION)

        self.app.dismiss_recent_captures()
        self.assertFalse(self.app.recent_captures_panel.isVisible())
        self.assertEqual(self.app.character.state, CharacterState.IDLE)

    def test_clicking_character_dismisses_timeline(self) -> None:
        """Clicking the companion while timeline is open dismisses the timeline."""
        self.app.show_recent_captures()
        self.assertTrue(self.app.recent_captures_panel.isVisible())

        self.app._on_character_clicked()
        self.assertFalse(self.app.recent_captures_panel.isVisible())

    def test_moving_companion_dismisses_timeline(self) -> None:
        """Dragging companion while timeline is open dismisses the timeline."""
        self.app.show_recent_captures()
        self.assertTrue(self.app.recent_captures_panel.isVisible())

        self.app._on_character_moved(QPoint(100, 100))
        self.assertFalse(self.app.recent_captures_panel.isVisible())

    def test_hide_companion_dismisses_timeline(self) -> None:
        """Hiding companion window dismisses the timeline."""
        self.app.show_recent_captures()
        self.assertTrue(self.app.recent_captures_panel.isVisible())

        self.app.hide_companion()
        self.assertFalse(self.app.recent_captures_panel.isVisible())


if __name__ == "__main__":
    unittest.main()
