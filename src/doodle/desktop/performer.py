"""Desktop activity performer coordinating physical presentation and window movement.

Implements the ActivityExecutionTarget protocol at the desktop layer, coordinating:
1. CharacterActivityPerformer (visual presentation & animation)
2. MovementPrimitive (2D spatial vector calculation)
3. CompanionWindow (actual desktop window positioning)

Per Architecture v2:
- Behavior/Decision chooses WHAT Doodle wants to do.
- Activity represents WHAT Doodle is doing over time.
- ActivityExecutor manages lifecycle transitions.
- DesktopActivityPerformer coordinates physical execution across desktop and character.
- CharacterActivityPerformer remains presentation-only.
- MovementPrimitive remains calculation-only.
- CompanionWindow owns window rendering and OS presentation.
- Upward completion flows via signals, not reverse coupling to ActivityExecutor.
"""

from __future__ import annotations

import logging
from typing import Optional, Union

from PySide6.QtCore import QObject, QPoint, Signal

from doodle.activity.executor import ActivityExecutionTarget
from doodle.activity.model import Activity
from doodle.activity.types import ActivityType
from doodle.character.performer import CharacterActivityPerformer
from doodle.desktop.companion_window import CompanionWindow
from doodle.desktop.movement import MovementPrimitive

logger = logging.getLogger(__name__)


class DesktopActivityPerformer(QObject):
    """Higher-level physical activity execution coordinator.

    Coordinates CharacterActivityPerformer, MovementPrimitive, and CompanionWindow
    to realize activities requiring both character presentation and spatial desktop
    translation.

    Conforms structurally to the ActivityExecutionTarget protocol (PEP 544).
    """

    activity_completed = Signal(Activity)
    activity_interrupted = Signal(Activity)
    activity_cancelled = Signal(Activity)

    def __init__(
        self,
        character_performer: CharacterActivityPerformer,
        movement: MovementPrimitive,
        window: CompanionWindow,
        parent: Optional[QObject] = None,
    ) -> None:
        """Initialize performer with character performer, movement primitive, and window.

        Args:
            character_performer: Character presentation adapter.
            movement: Spatial trajectory calculator.
            window: Companion window shell.
            parent: Optional Qt parent object.

        Raises:
            TypeError: If any required component is None.
        """
        super().__init__(parent)

        if character_performer is None:
            raise TypeError("character_performer must not be None")
        if movement is None:
            raise TypeError("movement must not be None")
        if window is None:
            raise TypeError("window must not be None")

        self._character_performer: CharacterActivityPerformer = character_performer
        self._movement: MovementPrimitive = movement
        self._window: CompanionWindow = window
        self._active_walk_activity: Optional[Activity] = None

    @property
    def character_performer(self) -> CharacterActivityPerformer:
        """Return the attached CharacterActivityPerformer."""
        return self._character_performer

    @property
    def movement(self) -> MovementPrimitive:
        """Return the attached MovementPrimitive."""
        return self._movement

    @property
    def window(self) -> CompanionWindow:
        """Return the attached CompanionWindow."""
        return self._window

    @property
    def active_walk_activity(self) -> Optional[Activity]:
        """Return the currently executing WALK activity, if any."""
        return self._active_walk_activity

    @property
    def is_walking(self) -> bool:
        """Return True if currently executing active WALK movement."""
        return self._active_walk_activity is not None and self._movement.is_moving

    def _extract_target(self, activity: Activity) -> Optional[QPoint]:
        """Extract a valid QPoint target from activity execution metadata.

        Supports QPoint, (x, y) tuple/list, or {'x': ..., 'y': ...} dict.
        """
        if not activity.metadata or not isinstance(activity.metadata, dict):
            return None

        target_raw = activity.metadata.get("target")
        if target_raw is None:
            return None

        if isinstance(target_raw, QPoint):
            return QPoint(target_raw)

        if isinstance(target_raw, (tuple, list)) and len(target_raw) >= 2:
            try:
                return QPoint(
                    int(round(float(target_raw[0]))),
                    int(round(float(target_raw[1]))),
                )
            except (ValueError, TypeError):
                return None

        if isinstance(target_raw, dict) and "x" in target_raw and "y" in target_raw:
            try:
                return QPoint(
                    int(round(float(target_raw["x"]))),
                    int(round(float(target_raw["y"]))),
                )
            except (ValueError, TypeError):
                return None

        return None

    def perform_activity(self, activity: Activity) -> None:
        """Begin physical realization of the given activity.

        For WALK:
        - Obtains target from metadata and current window position.
        - Configures MovementPrimitive.
        - Commands CharacterActivityPerformer to assume WALK presentation.
        - If already at target, emits completion immediately.

        For non-WALK activities:
        - Delegates directly to CharacterActivityPerformer.
        """
        if activity.activity_type == ActivityType.WALK:
            self._active_walk_activity = activity

            # 1. Obtain current window position
            current_pos = self._window.pos()

            # 2. Extract target from metadata, falling back to current position if unspecified
            target_pos = self._extract_target(activity)
            if target_pos is None:
                logger.warning(
                    "Activity WALK '%s' has no valid target metadata; using current position.",
                    activity.activity_id,
                )
                target_pos = current_pos

            # 3. Configure movement primitive
            self._movement.set_target(target_pos, start=current_pos)

            # 4. Request character presentation for WALK (neutral idle stance)
            self._character_performer.perform_activity(activity)

            # 5. If already at target (zero distance), complete immediately
            if self._movement.has_reached_target:
                finished = self._active_walk_activity
                self._active_walk_activity = None
                self.activity_completed.emit(finished)
        else:
            # Delegate non-movement activities cleanly to CharacterActivityPerformer
            self._character_performer.perform_activity(activity)

    def tick(self, dt_s: float) -> Optional[QPoint]:
        """Advance active walk movement by elapsed delta time dt_s seconds.

        Advances MovementPrimitive, repositions CompanionWindow, and signals
        activity completion if target coordinate has been arrived at.

        Args:
            dt_s: Elapsed delta time in seconds.

        Returns:
            The updated clamped window coordinate (QPoint), or None if no walk is active.
        """
        if self._active_walk_activity is None or not self._movement.is_moving:
            return None

        # Advance movement calculation
        new_pos = self._movement.step(dt_s)

        # Reposition window
        self._window.move_to(new_pos)

        # Detect target arrival
        if self._movement.has_reached_target:
            finished = self._active_walk_activity
            self._active_walk_activity = None
            logger.debug("WALK activity '%s' reached target.", finished.activity_id)
            self.activity_completed.emit(finished)

        return new_pos

    def interrupt_activity(self, activity: Activity) -> None:
        """Interrupt active physical realization.

        Halts movement, freezes window coordinate, and returns character to IDLE.
        """
        is_active_walk = (
            self._active_walk_activity is not None
            and (
                activity is self._active_walk_activity
                or activity.activity_id == self._active_walk_activity.activity_id
                or activity.activity_type == ActivityType.WALK
            )
        )

        if is_active_walk:
            interrupted_walk = self._active_walk_activity
            self._active_walk_activity = None
            self._movement.interrupt()
            self._character_performer.interrupt_activity(activity)
            logger.debug("Interrupted WALK activity: %s", activity.activity_id)
            self.activity_interrupted.emit(interrupted_walk or activity)
        else:
            self._character_performer.interrupt_activity(activity)

    def cancel_activity(self, activity: Activity) -> None:
        """Cancel active physical realization.

        Halts movement, resets movement primitive state, and returns character to IDLE.
        """
        is_active_walk = (
            self._active_walk_activity is not None
            and (
                activity is self._active_walk_activity
                or activity.activity_id == self._active_walk_activity.activity_id
                or activity.activity_type == ActivityType.WALK
            )
        )

        if is_active_walk:
            cancelled_walk = self._active_walk_activity
            self._active_walk_activity = None
            self._movement.interrupt()
            self._movement.reset(self._window.pos())
            self._character_performer.cancel_activity(activity)
            logger.debug("Cancelled WALK activity: %s", activity.activity_id)
            self.activity_cancelled.emit(cancelled_walk or activity)
        else:
            self._character_performer.cancel_activity(activity)

    def __repr__(self) -> str:
        walk_id = (
            self._active_walk_activity.activity_id
            if self._active_walk_activity is not None
            else None
        )
        return (
            f"DesktopActivityPerformer(window={self._window.pos()}, "
            f"active_walk={walk_id!r}, is_walking={self.is_walking})"
        )
