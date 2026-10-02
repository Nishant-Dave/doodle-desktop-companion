"""Character, animation, and visual representation components for Doodle."""

from doodle.character.animation import (
    PANDA_ANIMATION_SPECS,
    Animation,
    AnimationController,
    AnimationSpec,
)
from doodle.character.assets import load_animation_frames, load_asset, resolve_asset_path
from doodle.character.character import Character
from doodle.character.mood import (
    DEFAULT_MOOD_DECAY_S,
    DEFAULT_SLEEPY_THRESHOLD_S,
    Mood,
    MoodManager,
)
from doodle.character.state import CharacterState

__all__ = [
    "Animation",
    "AnimationController",
    "AnimationSpec",
    "Character",
    "CharacterState",
    "DEFAULT_MOOD_DECAY_S",
    "DEFAULT_SLEEPY_THRESHOLD_S",
    "Mood",
    "MoodManager",
    "PANDA_ANIMATION_SPECS",
    "load_animation_frames",
    "load_asset",
    "resolve_asset_path",
]
