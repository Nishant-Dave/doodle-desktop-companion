"""Automated tests for the Doodle application foundation."""

import os
import unittest

# Ensure Qt runs offscreen during automated test execution
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from doodle.app.application import DoodleApplication
from doodle.app.lifecycle import AppLifecycle
from doodle.character.character import Character
from doodle.desktop.companion_window import CompanionWindow
from doodle.persistence.settings import SettingsManager


class TestAppLifecycle(unittest.TestCase):
    """Tests for the application lifecycle manager."""

    def test_lifecycle_startup_and_shutdown(self) -> None:
        lifecycle = AppLifecycle()
        self.assertFalse(lifecycle.is_running)

        lifecycle.startup()
        self.assertTrue(lifecycle.is_running)

        hook_called = False

        def hook() -> None:
            nonlocal hook_called
            hook_called = True

        lifecycle.add_shutdown_hook(hook)
        lifecycle.shutdown()
        self.assertFalse(lifecycle.is_running)
        self.assertTrue(hook_called)


class TestDoodleApplication(unittest.TestCase):
    """Tests for the composition root and application initialization."""

    def test_application_construction(self) -> None:
        app = DoodleApplication(["doodle_test"])

        self.assertIsInstance(app.qapp, QApplication)
        self.assertEqual(app.qapp.applicationName(), "Doodle")
        self.assertIsInstance(app.lifecycle, AppLifecycle)
        self.assertIsInstance(app.settings_manager, SettingsManager)
        self.assertIsInstance(app.character, Character)
        self.assertIsNotNone(app.window)
        self.assertIsInstance(app.window, CompanionWindow)
        self.assertEqual(app.window.windowTitle(), "Doodle")


if __name__ == "__main__":
    unittest.main()
