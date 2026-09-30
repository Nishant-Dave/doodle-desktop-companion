"""Character abstraction for Doodle."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPixmap

from doodle.character.animation import Animation, AnimationController
from doodle.character.assets import load_animation_frames, load_asset
from doodle.character.state import CharacterState

KNOWN_ANIMATION_NAMES = ("idle", "sit", "sleep", "stretch", "attention")


class Character(QObject):
    """Represents a desktop companion character with state, animation, and visual representation."""

    # Qt signals forwarding animation events to desktop or behavior consumers
    frame_changed = Signal(QPixmap)
    animation_started = Signal(str)
    animation_finished = Signal(str)

    def __init__(
        self,
        name: str = "panda",
        initial_state: CharacterState = CharacterState.IDLE,
        assets_dir: Optional[Path] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._name: str = name
        self._state: CharacterState = initial_state
        self._assets_dir: Optional[Path] = assets_dir

        # Initialize animation controller and forward its signals
        self._animation_controller = AnimationController(self)
        self._animation_controller.frame_changed.connect(self.frame_changed.emit)
        self._animation_controller.animation_started.connect(self.animation_started.emit)
        self._animation_controller.animation_finished.connect(self.animation_finished.emit)

        # Load available animation definitions and start initial animation
        self._load_all_animations()
        self.play_animation(self._state.value.lower())

    @property
    def name(self) -> str:
        """Return the character name."""
        return self._name

    @property
    def state(self) -> CharacterState:
        """Return the current character state."""
        return self._state

    @property
    def animation_controller(self) -> AnimationController:
        """Return the character's animation controller."""
        return self._animation_controller

    @property
    def current_animation_name(self) -> Optional[str]:
        """Return the currently playing animation name, if any."""
        return self._animation_controller.current_animation_name

    @property
    def visual(self) -> Optional[QPixmap]:
        """Return the current visual pixmap representation for the desktop shell."""
        current = self._animation_controller.current_frame
        if current is not None and not current.isNull():
            return current

        # Fallback to single static asset if controller has no frame
        try:
            return load_asset(
                character_name=self._name,
                state=self._state,
                assets_dir=self._assets_dir,
            )
        except (FileNotFoundError, ValueError):
            return None

    def play_animation(self, name: str, loop: Optional[bool] = None) -> bool:
        """Request the character to play a named animation."""
        return self._animation_controller.play(name, loop=loop)

    def stop_animation(self) -> None:
        """Stop the currently playing animation."""
        self._animation_controller.stop()

    def set_state(self, state: CharacterState, loop: Optional[bool] = None) -> None:
        """Update the character state and request the corresponding animation if available."""
        if (
            self._state == state
            and self.current_animation_name == state.value.lower()
            and loop is None
        ):
            return
        self._state = state
        anim_name = state.value.lower()
        if self._animation_controller.has_animation(anim_name):
            self.play_animation(anim_name, loop=loop)
        else:
            self._animation_controller.stop()

    def _load_all_animations(self) -> None:
        """Discover and register animation frame sequences for known animation names."""
        for anim_name in KNOWN_ANIMATION_NAMES:
            try:
                frames = load_animation_frames(
                    character_name=self._name,
                    animation_name=anim_name,
                    assets_dir=self._assets_dir,
                )
                if frames:
                    anim = Animation(
                        name=anim_name,
                        frames=frames,
                        frame_duration_ms=500,
                        loop=True,
                    )
                    self._animation_controller.register_animation(anim)
            except (FileNotFoundError, ValueError):
                pass
