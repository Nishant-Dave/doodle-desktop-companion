"""Automated unit and integration tests for QSettings-based position persistence."""

import os
import tempfile
import unittest
from pathlib import Path

# Ensure Qt runs offscreen during automated test execution
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QSettings, QSize, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from doodle.app.application import DoodleApplication
from doodle.desktop.companion_window import CompanionWindow
from doodle.desktop.positioning import PositionManager
from doodle.persistence.settings import (
    KEY_WINDOW_POSITION,
    KEY_WINDOW_POSITION_X,
    KEY_WINDOW_POSITION_Y,
    SettingsManager,
)


class TestSettingsManager(unittest.TestCase):
    """Unit tests for SettingsManager and QSettings persistence isolation."""

    def setUp(self) -> None:
        # Create an isolated temporary INI file for each test
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ini_path = Path(self.temp_dir.name) / "test_settings.ini"
        self.qsettings = QSettings(str(self.ini_path), QSettings.Format.IniFormat)
        self.manager = SettingsManager(settings=self.qsettings)

    def tearDown(self) -> None:
        self.qsettings.clear()
        self.qsettings.sync()
        del self.qsettings
        self.temp_dir.cleanup()

    def test_settings_isolation_during_tests(self) -> None:
        # Verify the settings file resides strictly in the temporary directory
        self.assertTrue(str(self.ini_path).startswith(self.temp_dir.name))
        self.manager.save_window_position(QPoint(123, 456))
        # The file on disk was created inside temp_dir
        self.assertTrue(self.ini_path.exists())

    def test_default_position_when_no_saved_position_exists(self) -> None:
        loaded = self.manager.load_window_position()
        self.assertIsNone(loaded)

    def test_save_position(self) -> None:
        target = QPoint(350, 420)
        self.manager.save_window_position(target)
        self.assertTrue(self.qsettings.contains(KEY_WINDOW_POSITION))

    def test_load_saved_position(self) -> None:
        target = QPoint(280, 190)
        self.manager.save_window_position(target)
        loaded = self.manager.load_window_position()
        self.assertEqual(loaded, target)

    def test_save_load_round_trip(self) -> None:
        positions = [QPoint(0, 0), QPoint(100, 200), QPoint(1760, 920)]
        for pos in positions:
            self.manager.save_window_position(pos)
            self.assertEqual(self.manager.load_window_position(), pos)

    def test_invalid_corrupted_position_values(self) -> None:
        # Raw corrupted string
        self.qsettings.setValue(KEY_WINDOW_POSITION, "corrupted_non_point_data")
        self.qsettings.sync()
        self.assertIsNone(self.manager.load_window_position())

        # Boolean or unexpected object
        self.qsettings.setValue(KEY_WINDOW_POSITION, True)
        self.qsettings.sync()
        self.assertIsNone(self.manager.load_window_position())

    def test_missing_individual_coordinates(self) -> None:
        # Clear primary key
        self.qsettings.remove(KEY_WINDOW_POSITION)

        # Only X present
        self.qsettings.setValue(KEY_WINDOW_POSITION_X, 200)
        self.qsettings.remove(KEY_WINDOW_POSITION_Y)
        self.qsettings.sync()
        self.assertIsNone(self.manager.load_window_position())

        # Only Y present
        self.qsettings.remove(KEY_WINDOW_POSITION_X)
        self.qsettings.setValue(KEY_WINDOW_POSITION_Y, 300)
        self.qsettings.sync()
        self.assertIsNone(self.manager.load_window_position())

        # Non-numeric coordinate values
        self.qsettings.setValue(KEY_WINDOW_POSITION_X, "abc")
        self.qsettings.setValue(KEY_WINDOW_POSITION_Y, 300)
        self.qsettings.sync()
        self.assertIsNone(self.manager.load_window_position())

    def test_position_values_outside_current_screen_bounds(self) -> None:
        # Save position far outside a 1920x1080 screen
        self.manager.save_window_position(QPoint(4000, 3000))

        bounds = QRect(0, 0, 1920, 1080)
        positioner = PositionManager(
            window_size=QSize(160, 160),
            screen_bounds_provider=lambda: bounds,
            settings_manager=self.manager,
        )

        # restore_position should safely clamp to the available screen geometry
        restored = positioner.restore_position()
        self.assertEqual(restored, QPoint(1760, 920))


class TestPositionPersistenceIntegration(unittest.TestCase):
    """Integration tests verifying application startup, movement saving, and restart restoration."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_persistence_integration"])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ini_path = Path(self.temp_dir.name) / "test_app_settings.ini"
        self.qsettings = QSettings(str(self.ini_path), QSettings.Format.IniFormat)
        self.settings_manager = SettingsManager(settings=self.qsettings)

    def tearDown(self) -> None:
        self.qsettings.clear()
        self.qsettings.sync()
        del self.qsettings
        self.temp_dir.cleanup()

    def test_application_startup_restores_saved_position(self) -> None:
        saved_target = QPoint(320, 240)
        self.settings_manager.save_window_position(saved_target)

        app = DoodleApplication(
            argv=["doodle_test"],
            settings_manager=self.settings_manager,
        )
        self.assertEqual(app.window.pos(), saved_target)

    def test_moved_position_is_saved_and_restored_across_restart(self) -> None:
        # 1. First run: Start app with fresh settings
        app1 = DoodleApplication(
            argv=["doodle_test"],
            settings_manager=self.settings_manager,
        )
        win1 = app1.window

        # Drag window to a new location
        press = QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(20, 20),
            QPointF(win1.pos().x() + 20, win1.pos().y() + 20),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        win1.mousePressEvent(press)

        target_point = QPoint(400, 300)
        move = QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(20, 20),
            QPointF(target_point.x() + 20, target_point.y() + 20),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
        win1.mouseMoveEvent(move)

        release = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            QPointF(20, 20),
            QPointF(target_point.x() + 20, target_point.y() + 20),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
        win1.mouseReleaseEvent(release)
        self.assertEqual(win1.pos(), target_point)

        # Verify saved in settings
        saved = self.settings_manager.load_window_position()
        self.assertEqual(saved, target_point)

        win1.close()

        # 2. Second run: New application instance with same settings simulates restart
        app2 = DoodleApplication(
            argv=["doodle_test"],
            settings_manager=self.settings_manager,
        )
        win2 = app2.window
        self.assertEqual(win2.pos(), target_point)
        win2.close()

    def test_invalid_saved_position_safely_handled(self) -> None:
        # Put corrupted value in settings
        self.qsettings.setValue(KEY_WINDOW_POSITION, "corrupted_xyz")
        self.qsettings.sync()

        app = DoodleApplication(
            argv=["doodle_test"],
            settings_manager=self.settings_manager,
        )
        # Should cleanly fall back to default position without crash
        self.assertIsNotNone(app.window.pos())
        self.assertIsInstance(app.window.pos(), QPoint)
        app.window.close()


if __name__ == "__main__":
    unittest.main()
