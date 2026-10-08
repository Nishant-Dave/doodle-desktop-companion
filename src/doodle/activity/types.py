"""Types and enumerations for Doodle's Activity domain model.

Establishes the foundational vocabulary and lifecycle states for companion activities.
Strictly independent of PySide6, UI, animation, and rendering concepts.
"""

from __future__ import annotations

from enum import Enum


class ActivityType(str, Enum):
    """Vocabulary of foundational companion activity types.

    Represents what Doodle is doing at a semantic level.
    This vocabulary is intentionally small and extensible, not a giant
    exhaustive catalogue of every future behavior.
    """

    REST = "REST"
    WALK = "WALK"
    LOOK_AROUND = "LOOK_AROUND"
    STRETCH = "STRETCH"
    SLEEP = "SLEEP"
    PLAY = "PLAY"

    def __str__(self) -> str:
        return self.value


class ActivityLifecycleState(str, Enum):
    """Declarative lifecycle progression states for an activity.

    Tracks whether an activity is pending execution, actively running,
    or has reached a terminal state (completed, interrupted, or cancelled).
    This is pure declarative state; execution transitions belong to the executor.
    """

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    INTERRUPTED = "INTERRUPTED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"

    def __str__(self) -> str:
        return self.value
