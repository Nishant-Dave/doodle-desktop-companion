"""Frame-based animation model and controller for Doodle characters."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional, Sequence

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QPixmap

logger = logging.getLogger(__name__)

# Centralized animation timing constants (milliseconds)
DEFAULT_FRAME_DURATION_MS: int = 500

# Idle rhythm: quiet periods interspersed with natural blinks and subtle posture shifts
IDLE_REST_SHORT_MS: int = 3200
IDLE_REST_MED_MS: int = 3600
IDLE_REST_LONG_MS: int = 4000
IDLE_REST_END_MS: int = 3000
IDLE_BLINK_MS: int = 180
IDLE_DOUBLE_BLINK_GAP_MS: int = 220
IDLE_WEIGHT_SHIFT_MS: int = 550

# Expressive action timings
STRETCH_ENTER_MS: int = 500
STRETCH_HOLD_MS: int = 850
STRETCH_EASE_MS: int = 450
STRETCH_SETTLE_MS: int = 450
STRETCH_REST_MS: int = 350

# Milestone 2 Task 16D expressive pack frame timings
YAWN_FRAME_DURATIONS_MS: tuple[int, ...] = (240, 240, 260, 280, 360, 280, 240, 240)
STRETCH_EXPRESSIVE_DURATIONS_MS: tuple[int, ...] = (220, 240, 260, 300, 380, 320, 260, 220)
DIZZY_EXPRESSIVE_DURATIONS_MS: tuple[int, ...] = (160, 160, 150, 160, 150, 150)
RECOVER_EXPRESSIVE_DURATIONS_MS: tuple[int, ...] = (220, 200, 200, 200)
LOOK_AROUND_FRAME_DURATIONS_MS: tuple[int, ...] = (250, 260, 280, 420, 280, 280, 420, 250)

BLINK_ENTER_MS: int = 60
BLINK_HOLD_MS: int = 80
BLINK_EXIT_MS: int = 60

CURIOUS_ENTER_MS: int = 200
CURIOUS_PERK_MS: int = 250
CURIOUS_TILT_MS: int = 300
CURIOUS_HOLD_MS: int = 650
CURIOUS_EASE_MS: int = 300
CURIOUS_SETTLE_MS: int = 200

PLAYFUL_BOUNCE_MS: int = 280
PLAYFUL_SETTLE_MS: int = 400
PLAYFUL_REST_MS: int = 300

SLEEP_BREATH_MS: int = 1200
SLEEP_WAKE_SETTLE_MS: int = 500
SLEEP_REST_MS: int = 350

DIZZY_FRAME_MS: int = 300
RECOVER_SETTLE_MS: int = 450
RECOVER_REST_MS: int = 400
ATTENTION_ALERT_MS: int = 350
SURPRISED_FRAME_MS: int = 300
SIT_FRAME_MS: int = 900


@dataclass(frozen=True)
class AnimationSpec:
    """Specification describing timing and transition structure for a named animation."""

    name: str
    frame_durations_ms: tuple[int, ...]
    loop: bool = True
    loop_frame_count: Optional[int] = None


PANDA_ANIMATION_SPECS: dict[str, AnimationSpec] = {
    "idle": AnimationSpec(
        name="idle",
        frame_durations_ms=(
            IDLE_REST_SHORT_MS,
            IDLE_BLINK_MS,
            IDLE_REST_MED_MS,
            IDLE_BLINK_MS,
            IDLE_DOUBLE_BLINK_GAP_MS,
            IDLE_BLINK_MS,
            IDLE_REST_LONG_MS,
            IDLE_WEIGHT_SHIFT_MS,
            IDLE_REST_END_MS,
        ),
        loop=True,
    ),
    "blink": AnimationSpec(
        name="blink",
        frame_durations_ms=(
            BLINK_ENTER_MS,
            BLINK_HOLD_MS,
            BLINK_EXIT_MS,
        ),
        loop=False,
    ),
    "stretch": AnimationSpec(
        name="stretch",
        frame_durations_ms=STRETCH_EXPRESSIVE_DURATIONS_MS,
        loop=True,
        loop_frame_count=3,
    ),
    "curious": AnimationSpec(
        name="curious",
        frame_durations_ms=(
            CURIOUS_ENTER_MS,
            CURIOUS_PERK_MS,
            CURIOUS_TILT_MS,
            CURIOUS_HOLD_MS,
            CURIOUS_EASE_MS,
            CURIOUS_SETTLE_MS,
        ),
        loop=True,
        loop_frame_count=3,
    ),
    "playful": AnimationSpec(
        name="playful",
        frame_durations_ms=(
            PLAYFUL_BOUNCE_MS,
            PLAYFUL_BOUNCE_MS,
            PLAYFUL_BOUNCE_MS,
            PLAYFUL_BOUNCE_MS,
            PLAYFUL_SETTLE_MS,
            PLAYFUL_REST_MS,
        ),
        loop=True,
        loop_frame_count=4,
    ),
    "sleep": AnimationSpec(
        name="sleep",
        frame_durations_ms=(
            SLEEP_BREATH_MS,
            SLEEP_BREATH_MS,
            SLEEP_WAKE_SETTLE_MS,
            SLEEP_REST_MS,
        ),
        loop=True,
        loop_frame_count=2,
    ),
    "dizzy": AnimationSpec(
        name="dizzy",
        frame_durations_ms=DIZZY_EXPRESSIVE_DURATIONS_MS,
        loop=False,
    ),
    "recover": AnimationSpec(
        name="recover",
        frame_durations_ms=RECOVER_EXPRESSIVE_DURATIONS_MS,
        loop=False,
    ),
    "yawn": AnimationSpec(
        name="yawn",
        frame_durations_ms=YAWN_FRAME_DURATIONS_MS,
        loop=False,
    ),
    "look_around": AnimationSpec(
        name="look_around",
        frame_durations_ms=LOOK_AROUND_FRAME_DURATIONS_MS,
        loop=False,
    ),
    "attention": AnimationSpec(
        name="attention",
        frame_durations_ms=(ATTENTION_ALERT_MS, ATTENTION_ALERT_MS),
        loop=True,
    ),
    "surprised": AnimationSpec(
        name="surprised",
        frame_durations_ms=(SURPRISED_FRAME_MS, SURPRISED_FRAME_MS),
        loop=True,
    ),
    "sit": AnimationSpec(
        name="sit",
        frame_durations_ms=(SIT_FRAME_MS, SIT_FRAME_MS),
        loop=True,
    ),
}


@dataclass
class Animation:
    """Represents a named sequence of ordered visual frames with timing."""

    name: str
    frames: Sequence[QPixmap] = field(default_factory=tuple)
    frame_duration_ms: int = DEFAULT_FRAME_DURATION_MS
    loop: bool = True
    frame_durations_ms: Optional[Sequence[int]] = None
    loop_frame_count: Optional[int] = None

    def __post_init__(self) -> None:
        self.frames = tuple(self.frames)
        if self.frame_durations_ms is not None:
            self.frame_durations_ms = tuple(self.frame_durations_ms)

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

    def get_frame_duration(self, index: int) -> int:
        """Return the duration in milliseconds for the frame at the specified index."""
        if self.frame_durations_ms and 0 <= index < len(self.frame_durations_ms):
            return max(1, self.frame_durations_ms[index])
        return max(1, self.frame_duration_ms)


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

    @property
    def current_frame_duration_ms(self) -> int:
        """Return the duration in milliseconds of the current frame."""
        if self._current_animation is not None:
            return self._current_animation.get_frame_duration(self._current_frame_index)
        return DEFAULT_FRAME_DURATION_MS

    def register_animation(self, animation: Animation) -> None:
        """Register a named animation definition."""
        self._animations[animation.name.lower()] = animation

    def get_animation(self, name: str) -> Optional[Animation]:
        """Retrieve a registered animation definition by name."""
        return self._animations.get(name.lower())

    def has_animation(self, name: str) -> bool:
        """Check whether an animation with the given name is registered."""
        return name.lower() in self._animations

    @property
    def available_animation_names(self) -> list[str]:
        """Return the names of all registered animations."""
        return list(self._animations.keys())

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

        duration = animation.get_frame_duration(0)
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
            if (
                should_loop
                and animation.loop_frame_count is not None
                and self._current_frame_index + 1 >= animation.loop_frame_count
            ):
                self._current_frame_index = 0
                pixmap = self.current_frame
                if pixmap is not None:
                    self.frame_changed.emit(pixmap)
                duration = animation.get_frame_duration(0)
                self._timer.setInterval(duration)
            else:
                self._current_frame_index += 1
                pixmap = self.current_frame
                if pixmap is not None:
                    self.frame_changed.emit(pixmap)
                duration = animation.get_frame_duration(self._current_frame_index)
                self._timer.setInterval(duration)
        else:
            if should_loop:
                self._current_frame_index = 0
                pixmap = self.current_frame
                if pixmap is not None:
                    self.frame_changed.emit(pixmap)
                duration = animation.get_frame_duration(0)
                self._timer.setInterval(duration)
            else:
                self.stop()
                self.animation_finished.emit(animation.name)

