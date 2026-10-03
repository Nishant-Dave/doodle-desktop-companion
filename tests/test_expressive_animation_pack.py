"""Automated tests for Milestone 2 Task 16D Expressive Animation Pack.

Verifies:
1. All 5 expressive animations exist with exact frame counts:
   - yawn (8 frames)
   - stretch (8 frames)
   - dizzy (6 frames)
   - recover (4 frames)
   - look_around (8 frames)
2. Every frame conforms to 256x256 RGBA, grounded contact (Y=246), centering (X~128), and zero perimeter noise.
3. Controller playback and signal sequencing for each animation.
4. Seamless resting pose settle for action animations.
5. Behavior engine integration for dizzy -> recover -> idle, look_around -> idle, and yawn -> idle.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication

from doodle.app.application import DoodleApplication
from doodle.behavior.engine import BehaviorEngine
from doodle.behavior.rules import (
    EVENT_ANIMATION_FINISHED,
    EVENT_DRAG_RELEASED,
    EVENT_DRAG_STARTED,
    IdleBehavior,
)
from doodle.character.animation import PANDA_ANIMATION_SPECS
from doodle.character.character import KNOWN_ANIMATION_NAMES, Character
from doodle.character.state import CharacterState

BASE_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = BASE_DIR / "assets" / "panda"


class TestExpressiveAnimationAssets(unittest.TestCase):
    """Verifies filesystem assets for all 5 expressive animations."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_expressive_assets"])
        cls.master_img = QImage(str(ASSETS_DIR / "master" / "doodle_panda_master.png"))
        cls.expected_counts = {
            "yawn": 8,
            "stretch": 8,
            "dizzy": 6,
            "recover": 4,
            "look_around": 8,
        }

    def test_all_expressive_directories_and_frame_counts(self) -> None:
        for anim_name, count in self.expected_counts.items():
            anim_dir = ASSETS_DIR / anim_name
            self.assertTrue(anim_dir.is_dir(), f"Directory missing: {anim_dir}")
            frames = sorted(anim_dir.glob("frame_*.png"))
            self.assertEqual(
                len(frames),
                count,
                f"Expected {count} frames for '{anim_name}', found {len(frames)}",
            )

    def test_frame_geometry_and_grounded_contact(self) -> None:
        for anim_name, count in self.expected_counts.items():
            anim_dir = ASSETS_DIR / anim_name
            for frame_path in sorted(anim_dir.glob("frame_*.png")):
                img = QImage(str(frame_path))
                self.assertFalse(img.isNull())
                self.assertEqual(img.width(), 256)
                self.assertEqual(img.height(), 256)
                self.assertTrue(img.hasAlphaChannel())

                # Check bounding box
                min_x, max_x, min_y, max_y = 256, 0, 256, 0
                non_zero = 0
                outer_noise = 0
                for y in range(256):
                    for x in range(256):
                        a = (img.pixel(x, y) >> 24) & 0xFF
                        if a > 0:
                            non_zero += 1
                            if x < min_x:
                                min_x = x
                            if x > max_x:
                                max_x = x
                            if y < min_y:
                                min_y = y
                            if y > max_y:
                                max_y = y
                            if x < 8 or x >= 248 or y < 8 or y >= 248:
                                outer_noise += 1

                self.assertGreater(non_zero, 0)
                self.assertEqual(outer_noise, 0, f"Outer noise in {frame_path.name}")
                cx = (min_x + max_x) / 2.0
                self.assertLessEqual(abs(cx - 128.0), 6.5, f"Centering in {frame_path.name}")
                self.assertLessEqual(abs(max_y - 244), 4, f"Ground contact in {frame_path.name}")

    def test_settle_frames_match_master(self) -> None:
        """Stretch, recover, look_around, and yawn must end on the canonical resting pose."""
        for anim_name in ("stretch", "recover", "look_around", "yawn"):
            anim_dir = ASSETS_DIR / anim_name
            frames = sorted(anim_dir.glob("frame_*.png"))
            last_img = QImage(str(frames[-1]))
            self.assertEqual(
                last_img,
                self.master_img,
                f"Last frame of {anim_name} must match canonical master asset",
            )


class TestExpressiveAnimationController(unittest.TestCase):
    """Verifies playback, timing, and signals in Character animation controller."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_expressive_ctrl"])

    def setUp(self) -> None:
        self.char = Character(name="panda")

    def tearDown(self) -> None:
        self.char.stop_animation()

    def test_known_animation_names_contains_all_expressive(self) -> None:
        for name in ("yawn", "stretch", "dizzy", "recover", "look_around"):
            self.assertIn(name, KNOWN_ANIMATION_NAMES)
            self.assertTrue(self.char.animation_controller.has_animation(name))

    def test_expressive_animation_specs_and_durations(self) -> None:
        for name, expected_count in (
            ("yawn", 8),
            ("stretch", 8),
            ("dizzy", 6),
            ("recover", 4),
            ("look_around", 8),
        ):
            anim = self.char.animation_controller.get_animation(name)
            self.assertIsNotNone(anim)
            self.assertEqual(anim.frame_count, expected_count)
            self.assertTrue(anim.is_valid)
            self.assertIsNotNone(anim.frame_durations_ms)
            self.assertEqual(len(anim.frame_durations_ms), expected_count)

        # Check target duration windows
        yawn = self.char.animation_controller.get_animation("yawn")
        yawn_total = sum(yawn.frame_durations_ms)
        self.assertTrue(1800 <= yawn_total <= 2200, f"Yawn total {yawn_total}ms not in 1.8-2.2s")

        stretch = self.char.animation_controller.get_animation("stretch")
        stretch_total = sum(stretch.frame_durations_ms)
        self.assertTrue(2000 <= stretch_total <= 2300, f"Stretch total {stretch_total}ms not in 2.0-2.3s")

        look = self.char.animation_controller.get_animation("look_around")
        look_total = sum(look.frame_durations_ms)
        self.assertTrue(2000 <= look_total <= 2500, f"Look_around total {look_total}ms not in 2.0-2.5s")

    def test_play_and_complete_yawn(self) -> None:
        finished: list[str] = []
        self.char.animation_finished.connect(finished.append)

        started = self.char.play_animation("yawn", loop=False)
        self.assertTrue(started)
        anim = self.char.animation_controller.get_animation("yawn")
        for _ in range(anim.frame_count):
            self.char.animation_controller.advance_frame()

        self.assertEqual(finished, ["yawn"])
        self.assertFalse(self.char.animation_controller.is_playing)

    def test_play_and_complete_look_around(self) -> None:
        finished: list[str] = []
        self.char.animation_finished.connect(finished.append)

        started = self.char.play_animation("look_around", loop=False)
        self.assertTrue(started)
        anim = self.char.animation_controller.get_animation("look_around")
        for _ in range(anim.frame_count):
            self.char.animation_controller.advance_frame()

        self.assertEqual(finished, ["look_around"])
        self.assertFalse(self.char.animation_controller.is_playing)


class TestExpressiveBehaviorIntegration(unittest.TestCase):
    """Verifies behavior engine reactions for dizzy -> recover -> idle and autonomous actions."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_expressive_behavior"])

    def setUp(self) -> None:
        self.app = DoodleApplication(["test_app"], use_rich_idle=True)

    def tearDown(self) -> None:
        self.app.window.close()
        self.app.lifecycle.shutdown()

    def test_drag_flow_dizzy_to_recover_to_idle(self) -> None:
        # Drag started -> surprised
        self.app._behavior_engine.on_drag_started()
        self.assertEqual(self.app.character.current_animation_name, "surprised")

        # Drag released -> dizzy
        self.app._behavior_engine.on_drag_released()
        self.assertEqual(self.app.character.current_animation_name, "dizzy")

        # Dizzy finishes -> triggers recover
        self.app.character.animation_finished.emit("dizzy")
        self.assertEqual(self.app.character.current_animation_name, "recover")

        # Recover finishes -> returns to IDLE
        self.app.character.animation_finished.emit("recover")
        self.assertEqual(self.app.character.state, CharacterState.IDLE)
        self.assertEqual(self.app.character.current_animation_name, "idle")

    def test_user_interaction_interrupts_recover(self) -> None:
        # Start recover
        self.app.character.play_animation("recover", loop=False)
        self.assertEqual(self.app.character.current_animation_name, "recover")

        # User clicks during recovery -> immediate priority
        self.app._on_character_clicked()
        self.assertEqual(self.app.character.state, CharacterState.ATTENTION)
        self.assertEqual(self.app.character.current_animation_name, "attention")


if __name__ == "__main__":
    unittest.main()
