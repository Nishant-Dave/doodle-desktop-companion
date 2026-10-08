"""Declarative Activity domain model for the Doodle companion.

Central Architectural Principle:
    Behavior decides WHAT Doodle wants to do.
    Activity represents WHAT Doodle is doing over time.
    Character and animation systems will later determine HOW it is physically performed.

Activity is a pure domain entity describing a companion activity.
It does not execute itself, track time, or contain animation or Qt dependencies.
Execution is handled separately by the future ActivityExecutor (Task 23).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any, Union

from doodle.activity.types import ActivityLifecycleState, ActivityType

_id_counter = itertools.count(1)


def reset_activity_id_counter(start: int = 1) -> None:
    """Reset the deterministic ID counter, primarily for testing."""
    global _id_counter
    _id_counter = itertools.count(start)


def _generate_activity_id(activity_type: Union[ActivityType, str]) -> str:
    type_name = str(activity_type).lower().replace(" ", "_")
    return f"act_{type_name}_{next(_id_counter)}"


@dataclass
class Activity:
    """Declarative domain model representing what Doodle is doing over time.

    Attributes:
        activity_type: The semantic type of the activity (e.g., REST, WALK).
        activity_id: Unique identifier for the activity instance. Auto-generated if omitted.
        lifecycle_state: Declarative lifecycle state. Defaults to PENDING.
        interruptible: Whether the activity may be preempted by higher-priority events.
        metadata: Optional semantic domain metadata.
    """

    activity_type: ActivityType
    activity_id: str = field(default="")
    lifecycle_state: ActivityLifecycleState = ActivityLifecycleState.PENDING
    interruptible: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.activity_type, str) and not isinstance(self.activity_type, ActivityType):
            try:
                self.activity_type = ActivityType(self.activity_type.upper().strip())
            except ValueError:
                raise ValueError(f"Invalid activity type: {self.activity_type!r}")
        elif not isinstance(self.activity_type, ActivityType):
            raise ValueError(
                f"activity_type must be an ActivityType or valid string, got {type(self.activity_type).__name__}"
            )

        if not self.activity_id:
            self.activity_id = _generate_activity_id(self.activity_type)

        if not isinstance(self.lifecycle_state, ActivityLifecycleState):
            raise ValueError(
                f"lifecycle_state must be an ActivityLifecycleState, got {type(self.lifecycle_state).__name__}"
            )

        if not isinstance(self.interruptible, bool):
            raise ValueError(
                f"interruptible must be a bool, got {type(self.interruptible).__name__}"
            )

        if not isinstance(self.metadata, dict):
            raise ValueError(
                f"metadata must be a dict, got {type(self.metadata).__name__}"
            )
