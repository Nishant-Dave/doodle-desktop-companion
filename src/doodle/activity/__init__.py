"""Activity domain package for the Doodle desktop companion.

Establishes Activity as a first-class domain concept per Architecture v2:
- Behavior chooses WHAT Doodle wants to do.
- Activity represents WHAT Doodle is doing over time.
- Character and animation systems later determine HOW it is physically performed.
"""

from __future__ import annotations

from doodle.activity.executor import (
    ActivityExecutionError,
    ActivityExecutionTarget,
    ActivityExecutor,
)
from doodle.activity.model import Activity, reset_activity_id_counter
from doodle.activity.types import ActivityLifecycleState, ActivityType

__all__ = [
    "Activity",
    "ActivityExecutionError",
    "ActivityExecutionTarget",
    "ActivityExecutor",
    "ActivityLifecycleState",
    "ActivityType",
    "reset_activity_id_counter",
]
