"""Character abstraction for Doodle."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtGui import QPixmap

from doodle.character.assets import load_asset
from doodle.character.state import CharacterState


class Character:
    """Represents a desktop companion character with state and visual representation."""

    def __init__(
        self,
        name: str = "panda",
        initial_state: CharacterState = CharacterState.IDLE,
        assets_dir: Optional[Path] = None,
    ) -> None:
        self._name: str = name
        self._state: CharacterState = initial_state
        self._assets_dir: Optional[Path] = assets_dir
        self._visual: Optional[QPixmap] = None
        self._refresh_visual()

    @property
    def name(self) -> str:
        """Return the character name."""
        return self._name

    @property
    def state(self) -> CharacterState:
        """Return the current character state."""
        return self._state

    @property
    def visual(self) -> Optional[QPixmap]:
        """Return the current visual pixmap representation for the desktop shell."""
        return self._visual

    def set_state(self, state: CharacterState) -> None:
        """Update the character state and refresh the visual content."""
        if self._state == state:
            return
        self._state = state
        self._refresh_visual()

    def _refresh_visual(self) -> None:
        """Attempt to load the visual asset for the current character state."""
        try:
            self._visual = load_asset(
                character_name=self._name,
                state=self._state,
                assets_dir=self._assets_dir,
            )
        except (FileNotFoundError, ValueError):
            self._visual = None
