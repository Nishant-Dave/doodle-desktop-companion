"""Behavior layer for Doodle desktop companion."""

from doodle.behavior.engine import BehaviorEngine
from doodle.behavior.rules import (
    DEFAULT_IDLE_CYCLE,
    EVENT_ANIMATION_FINISHED,
    EVENT_CHARACTER_CLICKED,
    EVENT_IDLE_TIMEOUT,
    EVENT_MENU_DISMISSED,
    EVENT_MENU_OPENED,
    BehaviorAction,
    BehaviorContext,
    IdleBehaviorRules,
)

__all__ = [
    "BehaviorAction",
    "BehaviorContext",
    "BehaviorEngine",
    "DEFAULT_IDLE_CYCLE",
    "EVENT_ANIMATION_FINISHED",
    "EVENT_CHARACTER_CLICKED",
    "EVENT_IDLE_TIMEOUT",
    "EVENT_MENU_DISMISSED",
    "EVENT_MENU_OPENED",
    "IdleBehaviorRules",
]
