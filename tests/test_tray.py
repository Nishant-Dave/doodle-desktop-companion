"""Automated tests for system tray integration and application lifecycle coordination."""

import os
import tempfile
import unittest
from pathlib import Path

# Ensure Qt runs offscreen during automated test execution
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QSettings
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from doodle.app.application import DoodleApplication
from doodle.app.lifecycle import AppLifecycle
from doodle.desktop.tray import DoodleTrayIcon
from doodle.persistence.settings import SettingsManager


class TestDoodleTrayIcon(unittest.TestCase):
    """Unit tests for DoodleTrayIcon actions and signals."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_tray"])

    def setUp(self) -> None:
        self.tray = DoodleTrayIcon()

    def tearDown(self) -> None:
        self.tray.cleanup()
        self.tray.deleteLater()

    def test_tray_creation_and_actions(self) -> None:
        self.assertIsNotNone(self.tray)
        self.assertTrue(bool(self.tray.toolTip()))

        # Verify context menu items exist
        self.assertEqual(self.tray.action_show.text(), "Show Doodle")
        self.assertEqual(self.tray.action_hide.text(), "Hide Doodle")
        self.assertEqual(self.tray.action_exit.text(), "Exit Doodle")

    def test_tray_show_request(self) -> None:
        show_emitted = False

        def on_show() -> None:
            nonlocal show_emitted
            show_emitted = True

        self.tray.show_requested.connect(on_show)
        self.tray.action_show.trigger()
        self.assertTrue(show_emitted)

    def test_tray_activation_trigger_requests_show(self) -> None:
        show_emitted = False

        def on_show() -> None:
            nonlocal show_emitted
            show_emitted = True

        self.tray.show_requested.connect(on_show)
        self.tray.activated.emit(QSystemTrayIcon.ActivationReason.Trigger)
        self.assertTrue(show_emitted)

    def test_tray_hide_request(self) -> None:
        hide_emitted = False

        def on_hide() -> None:
            nonlocal hide_emitted
            hide_emitted = True

        self.tray.hide_requested.connect(on_hide)
        self.tray.action_hide.trigger()
        self.assertTrue(hide_emitted)

    def test_tray_exit_request(self) -> None:
        exit_emitted = False

        def on_exit() -> None:
            nonlocal exit_emitted
            exit_emitted = True

        self.tray.exit_requested.connect(on_exit)
        self.tray.action_exit.trigger()
        self.assertTrue(exit_emitted)


class TestTrayAndLifecycleIntegration(unittest.TestCase):
    """Integration tests verifying show/hide, exit flow, and lifecycle safety."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_tray_lifecycle"])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ini_path = Path(self.temp_dir.name) / "test_tray_app.ini"
        self.qsettings = QSettings(str(self.ini_path), QSettings.Format.IniFormat)
        self.settings_manager = SettingsManager(settings=self.qsettings)
        self.app = DoodleApplication(
            argv=["doodle_test"],
            settings_manager=self.settings_manager,
        )

    def tearDown(self) -> None:
        self.app.lifecycle.shutdown()
        self.qsettings.clear()
        self.qsettings.sync()
        del self.qsettings
        self.temp_dir.cleanup()

    def test_show_and_hide_companion(self) -> None:
        # Show window
        self.app.show_companion()
        self.assertTrue(self.app.window.isVisible())

        # Hide window: window is hidden, but application and tray remain alive
        self.app.hide_companion()
        self.assertFalse(self.app.window.isVisible())
        self.assertIsNotNone(self.app.tray)

        # Restore window
        self.app.show_companion()
        self.assertTrue(self.app.window.isVisible())

    def test_tray_exit_triggers_lifecycle_and_shutdown(self) -> None:
        quit_called = False
        original_quit = self.app.qapp.quit

        def mock_quit() -> None:
            nonlocal quit_called
            quit_called = True

        self.app.qapp.quit = mock_quit
        try:
            self.app.lifecycle.startup()
            self.assertTrue(self.app.lifecycle.is_running)

            # Trigger exit from tray
            self.app.tray.action_exit.trigger()

            # Lifecycle must be shut down and Qt quit invoked
            self.assertFalse(self.app.lifecycle.is_running)
            self.assertTrue(quit_called)
        finally:
            self.app.qapp.quit = original_quit

    def test_repeated_startup_shutdown_safety(self) -> None:
        lifecycle = self.app.lifecycle

        # Repeated startups do not cause issues
        lifecycle.startup()
        self.assertTrue(lifecycle.is_running)
        lifecycle.startup()
        self.assertTrue(lifecycle.is_running)

        # Repeated shutdowns do not double-run hooks or error
        hook_count = 0

        def hook() -> None:
            nonlocal hook_count
            hook_count += 1

        lifecycle.add_shutdown_hook(hook)
        lifecycle.shutdown()
        self.assertFalse(lifecycle.is_running)
        self.assertEqual(hook_count, 1)

        lifecycle.shutdown()
        self.assertFalse(lifecycle.is_running)
        self.assertEqual(hook_count, 1)

    def test_position_persisted_on_clean_shutdown(self) -> None:
        new_pos = QPoint(520, 380)
        self.app.window.move(new_pos)

        # Trigger clean exit
        self.app.lifecycle.startup()
        self.app.quit()

        # Position must have been saved in settings
        saved = self.settings_manager.load_window_position()
        self.assertEqual(saved, new_pos)


if __name__ == "__main__":
    unittest.main()
