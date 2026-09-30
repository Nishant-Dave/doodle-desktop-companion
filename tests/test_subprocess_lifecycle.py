"""Subprocess-level integration tests for Doodle startup and shutdown."""

from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON_EXE = sys.executable


class TestSubprocessLifecycle(unittest.TestCase):
    """Subprocess tests verifying actual OS process launch, execution, and exit."""

    def test_subprocess_clean_startup_and_tray_exit(self) -> None:
        """Launch Doodle in an isolated subprocess and trigger clean exit via tray."""
        # Subprocess script initializing DoodleApplication, starting idle timer and triggering exit via tray
        script = """
import os
import sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QTimer
from doodle.app.application import DoodleApplication

app = DoodleApplication(["doodle_subprocess"])
# Schedule clean tray exit after event loop starts
QTimer.singleShot(250, app.tray.action_exit.trigger)
sys.exit(app.run())
"""
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        env["QT_QPA_PLATFORM"] = "offscreen"

        process = subprocess.Popen(
            [PYTHON_EXE, "-c", script],
            cwd=str(REPO_ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        stdout, stderr = process.communicate(timeout=10)
        self.assertEqual(process.returncode, 0, f"Process failed with stderr: {stderr}")
        self.assertEqual(stderr.strip(), "")

    def test_repeated_subprocess_launch_and_exit(self) -> None:
        """Verify multiple successive launch/exit cycles succeed without orphaned resources."""
        script = """
import os
import sys
os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QTimer
from doodle.app.application import DoodleApplication

app = DoodleApplication(["doodle_subprocess_repeated"])
QTimer.singleShot(100, app.tray.action_exit.trigger)
sys.exit(app.run())
"""
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT / "src")
        env["QT_QPA_PLATFORM"] = "offscreen"

        for cycle in range(3):
            process = subprocess.Popen(
                [PYTHON_EXE, "-c", script],
                cwd=str(REPO_ROOT),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(
                process.returncode, 0, f"Cycle {cycle} failed with stderr: {stderr}"
            )


if __name__ == "__main__":
    unittest.main()
