"""Frame-based animation model and controller for Doodle characters."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Sequence

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QPixmap

logger = logging.getLogger(__name__)

DEFAULT_FRAME_DURATION_MS: int = 500


@dataclass
class Animation:
    """Represents a named sequence of ordered visual frames with timing."""

    name: str
    frames: Sequence[QPixmap] = field(default_factory=tuple)
    frame_duration_ms: int = DEFAULT_FRAME_DURATION_MS
    loop: bool = True

    def __post_init__(self) -> None:
        self.frames = tuple(self.frames)

    @property
    def frame_count(self) -> int:
        """Return the total number of frames."""
        return len(self.frames)

    @property
    def is_valid(self) -> bool:
        """Return True if the animation contains at least one non-null frame."""
        return self.frame_count > 0 and all(not f.isNull() for f in self.frames)

    def get_frame(self, index: int) -> Optional[QPixmap]:
        """Return the frame at the specified index, or None if out of bounds."""
        if 0 <= index < self.frame_count:
            return self.frames[index]
        return None


class AnimationController(QObject):
    """Manages playing named frame animations with timing and signals."""

    # Qt Signals for animation events
    animation_started = Signal(str)      # Emitted with animation name on start
    frame_changed = Signal(QPixmap)      # Emitted with new frame on update
    animation_finished = Signal(str)     # Emitted on completion of non-looping animation

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._animations: dict[str, Animation] = {}
        self._current_animation: Optional[Animation] = None
        self._current_frame_index: int = 0
        self._is_playing: bool = False
        self._loop_override: Optional[bool] = None

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.advance_frame)

    @property
    def is_playing(self) -> bool:
        """Return True if an animation is currently playing."""
        return self._is_playing

    @property
    def current_animation_name(self) -> Optional[str]:
        """Return the name of the currently active animation, if any."""
        return self._current_animation.name if self._current_animation is not None else None

    @property
    def current_animation(self) -> Optional[Animation]:
        """Return the currently active animation definition, if any."""
        return self._current_animation

    @property
    def current_frame_index(self) -> int:
        """Return the index of the current frame."""
        return self._current_frame_index

    @property
    def current_frame(self) -> Optional[QPixmap]:
        """Return the current frame pixmap, or None if no animation is active."""
        if self._current_animation is not None:
            return self._current_animation.get_frame(self._current_frame_index)
        return None

    def register_animation(self, animation: Animation) -> None:
        """Register a named animation definition."""
        self._animations[animation.name.lower()] = animation

    def get_animation(self, name: str) -> Optional[Animation]:
        """Retrieve a registered animation definition by name."""
        return self._animations.get(name.lower())

    def has_animation(self, name: str) -> bool:
        """Check whether an animation with the given name is registered."""
        return name.lower() in self._animations

    def play(self, name: str, loop: Optional[bool] = None) -> bool:
        """Start playing a registered animation by name.

        Returns True if the animation started successfully, False if unknown or invalid.
        """
        animation = self.get_animation(name)
        if animation is None:
            logger.warning("Attempted to play unknown animation: '%s'", name)
            return False

        if not animation.is_valid:
            logger.warning("Attempted to play invalid or empty animation: '%s'", name)
            return False

        self.stop()

        self._current_animation = animation
        self._current_frame_index = 0
        self._loop_override = loop
        self._is_playing = True

        self.animation_started.emit(animation.name)
        current = self.current_frame
        if current is not None:
            self.frame_changed.emit(current)

        duration = max(1, animation.frame_duration_ms)
        self._timer.start(duration)
        return True

    def stop(self) -> None:
        """Stop the currently active animation."""
        if self._timer.isActive():
            self._timer.stop()
        self._is_playing = False

    def advance_frame(self) -> None:
        """Advance to the next animation frame according to timing and loop rules."""
        if self._current_animation is None or not self._is_playing:
            return

        animation = self._current_animation
        should_loop = (
            self._loop_override
            if self._loop_override is not None
            else animation.loop
        )

        if self._current_frame_index + 1 < animation.frame_count:
            self._current_frame_index += 1
            pixmap = self.current_frame
            if pixmap is not None:
                self.frame_changed.emit(pixmap)
        else:
            if should_loop:
                self._current_frame_index = 0
                pixmap = self.current_frame
                if pixmap is not None:
                    self.frame_changed.emit(pixmap)
            else:
                self.stop()
                self.animation_finished.emit(animation.name)
