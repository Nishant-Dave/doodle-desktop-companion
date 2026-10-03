"""Character abstraction for Doodle."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPixmap

from doodle.character.animation import (
    DEFAULT_FRAME_DURATION_MS,
    PANDA_ANIMATION_SPECS,
    Animation,
    AnimationController,
)
from doodle.character.assets import load_animation_frames, load_asset
from doodle.character.mood import Mood
from doodle.character.state import CharacterState

KNOWN_ANIMATION_NAMES = (
    "idle",
    "blink",
    "sit",
    "sleep",
    "stretch",
    "attention",
    "surprised",
    "dizzy",
    "recover",
    "curious",
    "playful",
    "yawn",
    "look_around",
)


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
        self._mood: Mood = Mood.NEUTRAL
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
    def mood(self) -> Mood:
        """Return the current companion mood."""
        return self._mood

    def set_mood(self, mood: Mood) -> None:
        """Update the character's current mood."""
        self._mood = mood

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
            and self._animation_controller.is_playing
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
        raw_frames: dict[str, list[QPixmap]] = {}
        for anim_name in KNOWN_ANIMATION_NAMES:
            try:
                frames = load_animation_frames(
                    character_name=self._name,
                    animation_name=anim_name,
                    assets_dir=self._assets_dir,
                )
                if frames:
                    raw_frames[anim_name] = frames
            except (FileNotFoundError, ValueError):
                pass

        if not raw_frames:
            return

        idle_raw = raw_frames.get("idle", [])
        recover_raw = raw_frames.get("recover", [])
        blink_raw = raw_frames.get("blink", [])

        for anim_name, frames in raw_frames.items():
            spec = PANDA_ANIMATION_SPECS.get(anim_name)
            if spec is None:
                anim = Animation(
                    name=anim_name,
                    frames=frames,
                    frame_duration_ms=DEFAULT_FRAME_DURATION_MS,
                    loop=True,
                )
                self._animation_controller.register_animation(anim)
                continue

            # Construct choreographed frame sequences using project-owned assets
            anim_frames: list[QPixmap] = []
            if anim_name == "idle" and len(idle_raw) >= 1 and len(recover_raw) >= 1:
                # Use dedicated blink asset if available, otherwise idle_raw[1] or idle_raw[0]
                blink_frame = blink_raw[1] if len(blink_raw) >= 2 else (idle_raw[1] if len(idle_raw) >= 2 else idle_raw[0])
                breathe_frame = idle_raw[3] if len(idle_raw) >= 4 else idle_raw[0]
                # Rhythm: quiet -> blink -> quiet breathing -> double blink -> quiet -> weight shift -> quiet
                anim_frames = [
                    idle_raw[0],
                    blink_frame,
                    breathe_frame,
                    blink_frame,
                    idle_raw[0],
                    blink_frame,
                    idle_raw[0],
                    recover_raw[0],
                    idle_raw[0],
                ]
            elif anim_name == "stretch" and len(frames) >= 8:
                anim_frames = list(frames)
            elif anim_name == "stretch" and len(frames) >= 2 and len(recover_raw) >= 1 and len(idle_raw) >= 1:
                # Natural arc: enter -> peak stretch -> ease out -> settle -> rest
                anim_frames = [
                    frames[0],
                    frames[1],
                    frames[0],
                    recover_raw[0],
                    idle_raw[0],
                ]
            elif anim_name == "curious" and len(frames) >= 6:
                # Upgraded 6-frame pack: rest -> perk -> tilt start -> peak tilt -> ease out -> settle
                anim_frames = list(frames)
            elif anim_name == "yawn" and len(frames) >= 8:
                anim_frames = list(frames)
            elif anim_name == "look_around" and len(frames) >= 8:
                anim_frames = list(frames)
            elif anim_name == "recover" and len(frames) >= 4:
                anim_frames = list(frames)
            elif anim_name == "curious" and len(frames) >= 2 and len(recover_raw) >= 1 and len(idle_raw) >= 1:
                # Natural arc fallback for legacy 2-frame assets
                anim_frames = [
                    frames[0],
                    frames[1],
                    frames[0],
                    recover_raw[0],
                    idle_raw[0],
                ]
            elif anim_name == "playful" and len(frames) >= 2 and len(recover_raw) >= 1 and len(idle_raw) >= 1:
                # Natural arc: bounce 1-4 -> settle -> rest
                anim_frames = [
                    frames[0],
                    frames[1],
                    frames[0],
                    frames[1],
                    recover_raw[0],
                    idle_raw[0],
                ]
            elif anim_name == "sleep" and len(frames) >= 2 and len(recover_raw) >= 1 and len(idle_raw) >= 1:
                # Natural arc: calm inhale/exhale breath -> settle/wake -> rest
                anim_frames = [
                    frames[0],
                    frames[1],
                    recover_raw[0],
                    idle_raw[0],
                ]
            else:
                anim_frames = list(frames)

            # Match frame count with duration count safely
            durations = spec.frame_durations_ms
            if len(durations) != len(anim_frames):
                durations = None
                default_ms = (
                    spec.frame_durations_ms[0]
                    if spec.frame_durations_ms
                    else DEFAULT_FRAME_DURATION_MS
                )
            else:
                default_ms = spec.frame_durations_ms[0]

            anim = Animation(
                name=anim_name,
                frames=anim_frames,
                frame_duration_ms=default_ms,
                loop=spec.loop,
                frame_durations_ms=durations,
                loop_frame_count=spec.loop_frame_count,
            )
            self._animation_controller.register_animation(anim)

