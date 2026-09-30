"""Automated tests for frame-based animation models and controller."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from doodle.character.animation import Animation, AnimationController
from doodle.character.character import Character


class TestAnimation(unittest.TestCase):
    """Tests for Animation dataclass and frame validation."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_anim"])

    def setUp(self) -> None:
        self.pixmap1 = QPixmap(32, 32)
        self.pixmap1.fill()
        self.pixmap2 = QPixmap(32, 32)
        self.pixmap2.fill()

    def test_animation_definition_creation(self) -> None:
        anim = Animation(
            name="idle",
            frames=(self.pixmap1, self.pixmap2),
            frame_duration_ms=400,
            loop=True,
        )
        self.assertEqual(anim.name, "idle")
        self.assertEqual(anim.frame_count, 2)
        self.assertEqual(anim.frame_duration_ms, 400)
        self.assertTrue(anim.loop)
        self.assertTrue(anim.is_valid)

    def test_ordered_frame_sequence(self) -> None:
        anim = Animation(
            name="test_seq",
            frames=(self.pixmap1, self.pixmap2),
        )
        self.assertIs(anim.get_frame(0), self.pixmap1)
        self.assertIs(anim.get_frame(1), self.pixmap2)
        self.assertIsNone(anim.get_frame(2))
        self.assertIsNone(anim.get_frame(-1))

    def test_frame_timing(self) -> None:
        anim_fast = Animation(name="fast", frames=(self.pixmap1,), frame_duration_ms=100)
        anim_slow = Animation(name="slow", frames=(self.pixmap1,), frame_duration_ms=800)
        self.assertEqual(anim_fast.frame_duration_ms, 100)
        self.assertEqual(anim_slow.frame_duration_ms, 800)

    def test_empty_or_invalid_animation_handling(self) -> None:
        empty_anim = Animation(name="empty", frames=())
        self.assertFalse(empty_anim.is_valid)
        self.assertEqual(empty_anim.frame_count, 0)
        self.assertIsNone(empty_anim.get_frame(0))

        null_pixmap = QPixmap()  # isNull() is True
        invalid_anim = Animation(name="invalid", frames=(null_pixmap,))
        self.assertFalse(invalid_anim.is_valid)


class TestAnimationController(unittest.TestCase):
    """Tests for AnimationController playback, timing, and signals."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_anim_controller"])

    def setUp(self) -> None:
        self.pixmap1 = QPixmap(32, 32)
        self.pixmap1.fill()
        self.pixmap2 = QPixmap(32, 32)
        self.pixmap2.fill()
        self.anim = Animation(
            name="idle",
            frames=(self.pixmap1, self.pixmap2),
            frame_duration_ms=200,
            loop=True,
        )
        self.controller = AnimationController()
        self.controller.register_animation(self.anim)

    def tearDown(self) -> None:
        self.controller.stop()

    def test_initial_and_current_frame(self) -> None:
        self.assertFalse(self.controller.is_playing)
        self.assertIsNone(self.controller.current_frame)
        self.assertIsNone(self.controller.current_animation_name)

        self.controller.play("idle")
        self.assertTrue(self.controller.is_playing)
        self.assertEqual(self.controller.current_animation_name, "idle")
        self.assertEqual(self.controller.current_frame_index, 0)
        self.assertIs(self.controller.current_frame, self.pixmap1)

    def test_play_and_start_signals(self) -> None:
        started_names: list[str] = []
        changed_frames: list[QPixmap] = []

        self.controller.animation_started.connect(started_names.append)
        self.controller.frame_changed.connect(changed_frames.append)

        started = self.controller.play("idle")
        self.assertTrue(started)
        self.assertEqual(started_names, ["idle"])
        self.assertEqual(len(changed_frames), 1)

    def test_frame_advancement_and_looping(self) -> None:
        self.controller.play("idle", loop=True)
        self.assertEqual(self.controller.current_frame_index, 0)

        # Advance to frame 1
        self.controller.advance_frame()
        self.assertEqual(self.controller.current_frame_index, 1)
        self.assertIs(self.controller.current_frame, self.pixmap2)

        # Loop back to frame 0
        self.controller.advance_frame()
        self.assertEqual(self.controller.current_frame_index, 0)
        self.assertIs(self.controller.current_frame, self.pixmap1)

    def test_stop(self) -> None:
        self.controller.play("idle")
        self.assertTrue(self.controller.is_playing)

        self.controller.stop()
        self.assertFalse(self.controller.is_playing)

    def test_completion_signal_non_looping(self) -> None:
        non_looping_anim = Animation(
            name="stretch",
            frames=(self.pixmap1, self.pixmap2),
            loop=False,
        )
        self.controller.register_animation(non_looping_anim)

        finished_names: list[str] = []
        self.controller.animation_finished.connect(finished_names.append)

        self.controller.play("stretch", loop=False)
        self.controller.advance_frame()  # to frame 1
        self.assertEqual(self.controller.current_frame_index, 1)
        self.assertEqual(finished_names, [])

        self.controller.advance_frame()  # reaches completion
        self.assertEqual(finished_names, ["stretch"])
        self.assertFalse(self.controller.is_playing)

    def test_unknown_animation_handling(self) -> None:
        started = self.controller.play("non_existent_animation")
        self.assertFalse(started)
        self.assertFalse(self.controller.is_playing)

    def test_invalid_animation_handling(self) -> None:
        empty = Animation(name="empty", frames=())
        self.controller.register_animation(empty)

        started = self.controller.play("empty")
        self.assertFalse(started)
        self.assertFalse(self.controller.is_playing)


class TestCharacterAnimation(unittest.TestCase):
    """Tests verifying Character coordinate its AnimationController."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_char_anim"])

    def test_character_animation_request(self) -> None:
        character = Character(name="panda")
        self.assertEqual(character.current_animation_name, "idle")
        self.assertIsNotNone(character.visual)

        # Request sit animation
        started = character.play_animation("sit")
        self.assertTrue(started)
        self.assertEqual(character.current_animation_name, "sit")
        self.assertIsNotNone(character.visual)

        # Request sleep animation
        started = character.play_animation("sleep")
        self.assertTrue(started)
        self.assertEqual(character.current_animation_name, "sleep")

        # Request stretch animation
        started = character.play_animation("stretch")
        self.assertTrue(started)
        self.assertEqual(character.current_animation_name, "stretch")

        # Request attention animation
        started = character.play_animation("attention")
        self.assertTrue(started)
        self.assertEqual(character.current_animation_name, "attention")

        # Unknown animation fails safely
        started = character.play_animation("unknown")
        self.assertFalse(started)

        # Stop animation
        character.stop_animation()
        self.assertFalse(character.animation_controller.is_playing)


if __name__ == "__main__":
    unittest.main()
