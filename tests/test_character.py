"""Automated tests for character abstraction, states, assets, and window integration."""

import os
import unittest
from pathlib import Path
from unittest.mock import patch

# Ensure Qt runs offscreen during automated test execution
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from doodle.character.assets import load_asset, resolve_asset_path, DEFAULT_ASSETS_DIR
from doodle.character.character import Character
from doodle.character.state import CharacterState
from doodle.desktop.companion_window import CompanionWindow


class TestCharacterState(unittest.TestCase):
    """Tests for character state definitions and behavior."""

    def test_defined_states_exist(self) -> None:
        expected_states = {"IDLE", "SIT", "SLEEP", "STRETCH", "ATTENTION"}
        actual_states = {state.value for state in CharacterState}
        self.assertEqual(expected_states, actual_states)

    def test_state_representation_is_stable(self) -> None:
        self.assertEqual(CharacterState.IDLE.value, "IDLE")
        self.assertEqual(str(CharacterState.IDLE), "IDLE")
        self.assertEqual(CharacterState.SIT.value, "SIT")
        self.assertEqual(CharacterState.SLEEP.value, "SLEEP")
        self.assertEqual(CharacterState.STRETCH.value, "STRETCH")
        self.assertEqual(CharacterState.ATTENTION.value, "ATTENTION")

    def test_character_starts_in_idle(self) -> None:
        character = Character()
        self.assertEqual(character.state, CharacterState.IDLE)
        self.assertEqual(character.name, "panda")
        self.assertIsNotNone(character.visual)
        self.assertFalse(character.visual.isNull())

    def test_character_state_transition(self) -> None:
        character = Character()
        self.assertEqual(character.state, CharacterState.IDLE)

        # Transitioning to state without asset (e.g. SIT) updates state safely
        character.set_state(CharacterState.SIT)
        self.assertEqual(character.state, CharacterState.SIT)
        self.assertIsNone(character.visual)

        # Transitioning back to IDLE restores visual
        character.set_state(CharacterState.IDLE)
        self.assertEqual(character.state, CharacterState.IDLE)
        self.assertIsNotNone(character.visual)


class TestAssetLoading(unittest.TestCase):
    """Tests for locating and loading character assets."""

    def test_panda_idle_asset_loaded(self) -> None:
        pixmap = load_asset("panda", CharacterState.IDLE)
        self.assertIsInstance(pixmap, QPixmap)
        self.assertFalse(pixmap.isNull())
        self.assertGreater(pixmap.width(), 0)
        self.assertGreater(pixmap.height(), 0)

    def test_missing_asset_fails_clearly_and_safely(self) -> None:
        # Non-existent character
        with self.assertRaises(FileNotFoundError):
            load_asset("unicorn", "idle")

        # Non-existent state
        with self.assertRaises(FileNotFoundError):
            load_asset("panda", "nonexistent_state")

        # Non-existent file in existing state
        with self.assertRaises(FileNotFoundError):
            load_asset("panda", "idle", filename="does_not_exist.png")

    def test_asset_loading_independent_of_working_directory(self) -> None:
        # Change current working directory to a different path (e.g. parent or tests dir)
        original_cwd = os.getcwd()
        try:
            os.chdir(Path(__file__).parent)
            pixmap = load_asset("panda", CharacterState.IDLE)
            self.assertFalse(pixmap.isNull())
        finally:
            os.chdir(original_cwd)


class TestWindowIntegration(unittest.TestCase):
    """Tests verifying Character integration with CompanionWindow."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_character_window"])

    def setUp(self) -> None:
        self.character = Character(name="panda")
        self.window = CompanionWindow(character=self.character)

    def tearDown(self) -> None:
        if self.window.isVisible():
            self.window.close()
        self.window.deleteLater()

    def test_character_attached_to_window(self) -> None:
        self.assertIs(self.window.character, self.character)
        self.assertIsNotNone(self.character.visual)

    def test_window_render_with_character(self) -> None:
        self.window.show()
        self.assertTrue(self.window.isVisible())
        # Force a repaint to verify paintEvent with character executes cleanly
        self.window.repaint()
        self.window.close()

    def test_attach_and_detach_character(self) -> None:
        self.window.set_character(None)
        self.assertIsNone(self.window.character)
        self.window.repaint()

        self.window.set_character(self.character)
        self.assertIs(self.window.character, self.character)
        self.window.repaint()


if __name__ == "__main__":
    unittest.main()
