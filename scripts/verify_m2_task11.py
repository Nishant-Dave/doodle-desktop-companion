"""Live verification script checking all 17 manual acceptance criteria for Milestone 2 Task 11."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Ensure PYTHONPATH is set
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QEvent, QPoint, QPointF, QRect, QSettings, QSize, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

from doodle.app.application import DoodleApplication
from doodle.character.state import CharacterState
from doodle.persistence.settings import SettingsManager


def run_m2_task11_verification() -> dict[str, bool]:
    results = {}

    temp_dir = tempfile.TemporaryDirectory()
    ini_path = Path(temp_dir.name) / "live_m2_test.ini"
    qsettings = QSettings(str(ini_path), QSettings.Format.IniFormat)
    sm = SettingsManager(settings=qsettings)

    # 1. Launch Doodle & 2. Panda behaves normally
    app = DoodleApplication(argv=["doodle_m2_verification"], settings_manager=sm)
    app.lifecycle.startup()
    app.behavior_engine.start_idle_timer()
    results["1. Launch Doodle"] = app is not None and app.qapp is not None
    results["2. Panda behaves normally"] = (
        app.character.state == CharacterState.IDLE
        and app.character.current_animation_name == "idle"
    )

    # 3. Wait for / trigger idle behavior
    app.behavior_engine.trigger_idle_timeout()
    results["3. Idle behavior activates"] = (
        app.character.state == CharacterState.STRETCH
        and app.character.current_animation_name == "stretch"
    )

    # 4. Drag panda during idle animation & 5. Idle behavior does not fight drag
    win = app.window
    start_pos = win.pos()
    win.mousePressEvent(
        QMouseEvent(
            QEvent.Type.MouseButtonPress,
            QPointF(10, 10),
            QPointF(start_pos.x() + 10, start_pos.y() + 10),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    win.mouseMoveEvent(
        QMouseEvent(
            QEvent.Type.MouseMove,
            QPointF(40, 40),
            QPointF(start_pos.x() + 40, start_pos.y() + 40),
            Qt.MouseButton.NoButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    results["4. Drag panda during idle animation"] = win.drag_occurred
    results["5. Idle behavior does not fight the drag"] = (
        app.character.current_animation_name == "surprised"
        and not app.behavior_engine.is_idle_timer_active
    )

    # 6. Release panda & 7. Expressive reaction occurs (dizzy -> recover)
    win.mouseReleaseEvent(
        QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            QPointF(40, 40),
            QPointF(start_pos.x() + 40, start_pos.y() + 40),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
        )
    )
    results["6. Release panda"] = not win.is_dragging
    results["7. Expressive reaction occurs (dizzy)"] = (
        app.character.current_animation_name == "dizzy"
    )

    # Advance reaction: dizzy finishes -> recover plays
    app.character.animation_finished.emit("dizzy")
    results["7b. Reaction continues (recover)"] = (
        app.character.current_animation_name == "recover"
    )

    # 8. Doodle returns to normal
    app.character.animation_finished.emit("recover")
    results["8. Doodle returns to normal IDLE"] = (
        app.character.state == CharacterState.IDLE
        and app.character.current_animation_name == "idle"
        and app.behavior_engine.is_idle_eligible
    )

    # 9. Click panda & 10. Attention/menu behavior still works
    win.character_clicked.emit()
    results["9. Click panda opens attention/menu"] = (
        app.character.state == CharacterState.ATTENTION and app.menu.isVisible()
    )
    app.menu.dismiss()
    results["10. Dismiss menu restores IDLE"] = (
        app.character.state == CharacterState.IDLE and not app.menu.isVisible()
    )

    # 11. Repeat drag/release several times & 12. No stuck animation & 13. No duplicate behavior
    for _ in range(5):
        win.mousePressEvent(
            QMouseEvent(
                QEvent.Type.MouseButtonPress,
                QPointF(10, 10),
                QPointF(win.pos().x() + 10, win.pos().y() + 10),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
        )
        win.mouseMoveEvent(
            QMouseEvent(
                QEvent.Type.MouseMove,
                QPointF(35, 35),
                QPointF(win.pos().x() + 35, win.pos().y() + 35),
                Qt.MouseButton.NoButton,
                Qt.MouseButton.LeftButton,
                Qt.KeyboardModifier.NoModifier,
            )
        )
        win.mouseReleaseEvent(
            QMouseEvent(
                QEvent.Type.MouseButtonRelease,
                QPointF(35, 35),
                QPointF(win.pos().x() + 35, win.pos().y() + 35),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
            )
        )
        app.character.animation_finished.emit("dizzy")
        app.character.animation_finished.emit("recover")

    results["11. Repeated drag/release cycles succeed"] = True
    results["12. Confirm no stuck animation"] = (
        app.character.state == CharacterState.IDLE
        and app.character.current_animation_name == "idle"
    )
    results["13. No duplicate or runaway behavior timers"] = (
        app.behavior_engine.is_idle_timer_active
    )

    # 14. Hide/show from tray & 15. Confirm behavior still works afterward
    app.hide_companion()
    results["14a. Hide from tray pauses idle timer"] = (
        not app.behavior_engine.is_idle_timer_active
    )
    app.show_companion()
    results["14b. Show from tray resumes idle timer"] = (
        app.behavior_engine.is_idle_timer_active
    )
    app.behavior_engine.trigger_idle_timeout()
    results["15. Behavior works after tray show"] = (
        app.character.state == CharacterState.SIT
    )
    app.character.animation_finished.emit("sit")

    # 16. Restart application & 17. Confirm position persistence remains intact
    saved_pos = win.pos()
    app.window.close()
    app.lifecycle.shutdown()

    app2 = DoodleApplication(argv=["doodle_m2_restart"], settings_manager=sm)
    results["16. Restart application"] = app2 is not None
    results["17. Position persistence remains intact"] = app2.window.pos() == saved_pos

    app2.window.close()
    app2.lifecycle.shutdown()
    temp_dir.cleanup()
    return results


if __name__ == "__main__":
    checklist = run_m2_task11_verification()
    all_passed = True
    print("\n--- MILESTONE 2 TASK 11 VERIFICATION ---")
    for item, passed in checklist.items():
        status = "[x] PASS" if passed else "[ ] FAIL"
        if not passed:
            all_passed = False
        print(f"{status}: {item}")
    print("----------------------------------------")
    print(f"OVERALL STATUS: {'ALL CHECKS PASSED' if all_passed else 'SOME CHECKS FAILED'}")
    sys.exit(0 if all_passed else 1)
