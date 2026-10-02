"""Unit tests for Doodle Milestone 2 Task 16C Core Panda Animation Pack.

Verifies:
1. Frame existence, counts, and file naming for idle (6), blink (3), and curious (6).
2. Per-frame technical requirements: 256x256, RGBA, transparent background, centering, ground anchor.
3. Motion continuity and grounding stability (zero vertical jumping).
4. Integration with Character and AnimationController.
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication

from doodle.character.animation import PANDA_ANIMATION_SPECS
from doodle.character.assets import DEFAULT_ASSETS_DIR, load_animation_frames
from doodle.character.character import KNOWN_ANIMATION_NAMES, Character

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class TestCorePandaAnimationPackAssets(unittest.TestCase):
    """Asset layer validation for the core panda animation pack."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_core_pack"])
        cls.panda_dir = DEFAULT_ASSETS_DIR / "panda"

    def test_animation_directories_and_frame_counts(self) -> None:
        expected_counts = {
            "idle": 6,
            "blink": 3,
            "curious": 6,
        }
        for anim_name, count in expected_counts.items():
            anim_dir = self.panda_dir / anim_name
            self.assertTrue(anim_dir.is_dir(), f"Directory missing: {anim_dir}")
            frame_files = sorted(anim_dir.glob("frame_*.png"))
            self.assertEqual(
                len(frame_files),
                count,
                f"Expected {count} frames in {anim_name}, got {len(frame_files)}",
            )
            # Check sequential zero-padded naming
            for i, f in enumerate(frame_files):
                self.assertEqual(f.name, f"frame_{i:02d}.png")

    def test_frame_dimensions_format_and_transparency(self) -> None:
        for anim_name in ("idle", "blink", "curious"):
            anim_dir = self.panda_dir / anim_name
            for frame_path in sorted(anim_dir.glob("frame_*.png")):
                img = QImage(str(frame_path))
                self.assertFalse(img.isNull(), f"Failed to load {frame_path}")
                self.assertEqual(img.width(), 256, f"{frame_path.name} width != 256")
                self.assertEqual(img.height(), 256, f"{frame_path.name} height != 256")
                self.assertTrue(img.hasAlphaChannel(), f"{frame_path.name} must have alpha")

                # Verify perimeter transparency (outer 8px edge)
                for x in (0, 1, 2, 7, 248, 254, 255):
                    for y in range(256):
                        self.assertEqual(
                            (img.pixel(x, y) >> 24) & 0xFF,
                            0,
                            f"Stray noise at ({x}, {y}) in {frame_path.name}",
                        )
                for y in (0, 1, 2, 7, 248, 254, 255):
                    for x in range(256):
                        self.assertEqual(
                            (img.pixel(x, y) >> 24) & 0xFF,
                            0,
                            f"Stray noise at ({x}, {y}) in {frame_path.name}",
                        )

    def test_horizontal_centering_and_contact_grounding(self) -> None:
        for anim_name in ("idle", "blink", "curious"):
            anim_dir = self.panda_dir / anim_name
            for frame_path in sorted(anim_dir.glob("frame_*.png")):
                img = QImage(str(frame_path))
                min_x, max_x = 256, 0
                max_y = 0
                for y in range(256):
                    for x in range(256):
                        if (img.pixel(x, y) >> 24) & 0xFF > 0:
                            min_x = min(min_x, x)
                            max_x = max(max_x, x)
                            max_y = max(max_y, y)

                center_x = (min_x + max_x) / 2.0
                self.assertLessEqual(
                    abs(center_x - 128.0),
                    4.0,
                    f"{frame_path.name} center {center_x:.1f} deviates > 4px from 128.0",
                )
                self.assertLessEqual(
                    abs(max_y - 244),
                    4,
                    f"{frame_path.name} contact {max_y} deviates > 4px from ground anchor 244",
                )

    def test_grounding_continuity_across_frames(self) -> None:
        """Verify no floating or vertical bouncing between consecutive frames."""
        for anim_name in ("idle", "blink", "curious"):
            anim_dir = self.panda_dir / anim_name
            frames = [QImage(str(p)) for p in sorted(anim_dir.glob("frame_*.png"))]
            contact_points = []
            for img in frames:
                cy = max(
                    y for y in range(256) for x in range(256)
                    if (img.pixel(x, y) >> 24) & 0xFF > 0
                )
                contact_points.append(cy)

            for i in range(len(contact_points)):
                next_i = (i + 1) % len(contact_points)
                delta = abs(contact_points[i] - contact_points[next_i])
                self.assertLessEqual(
                    delta,
                    1,
                    f"Ground jump in {anim_name} between frame {i} and {next_i}: delta={delta}px",
                )


class TestCorePandaAnimationPackIntegration(unittest.TestCase):
    """Integration layer validation for character and animation controller."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_core_integration"])

    def setUp(self) -> None:
        self.char = Character(name="panda")

    def tearDown(self) -> None:
        self.char.stop_animation()

    def test_known_animation_names_includes_blink(self) -> None:
        self.assertIn("blink", KNOWN_ANIMATION_NAMES)
        self.assertIn("blink", PANDA_ANIMATION_SPECS)

    def test_raw_frames_loaded_correctly(self) -> None:
        idle_frames = load_animation_frames("panda", "idle")
        blink_frames = load_animation_frames("panda", "blink")
        curious_frames = load_animation_frames("panda", "curious")

        self.assertEqual(len(idle_frames), 6)
        self.assertEqual(len(blink_frames), 3)
        self.assertEqual(len(curious_frames), 6)

    def test_standalone_blink_playback(self) -> None:
        finished: list[str] = []
        self.char.animation_finished.connect(finished.append)

        started = self.char.play_animation("blink", loop=False)
        self.assertTrue(started)
        self.assertEqual(self.char.current_animation_name, "blink")

        blink_anim = self.char.animation_controller.get_animation("blink")
        self.assertIsNotNone(blink_anim)
        self.assertEqual(blink_anim.frame_count, 3)

        # Step through 3 frames
        for _ in range(3):
            self.char.animation_controller.advance_frame()

        self.assertEqual(finished, ["blink"])
        self.assertFalse(self.char.animation_controller.is_playing)

    def test_curious_animation_six_frames(self) -> None:
        curious_anim = self.char.animation_controller.get_animation("curious")
        self.assertIsNotNone(curious_anim)
        self.assertEqual(curious_anim.frame_count, 6)

        # Final settle frame matches resting idle frame
        idle_anim = self.char.animation_controller.get_animation("idle")
        self.assertEqual(
            curious_anim.get_frame(5).toImage(),
            idle_anim.get_frame(0).toImage(),
        )


if __name__ == "__main__":
    unittest.main()
