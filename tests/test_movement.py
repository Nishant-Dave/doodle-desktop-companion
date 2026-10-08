"""Unit tests for MovementPrimitive and 2D spatial movement calculation (Task 25).

Verifies deterministic behavior without Qt event-loop dependence, timers, sleeps,
or real display requirements:
1. Initial state is IDLE.
2. Target can be set.
3. Horizontal movement.
4. Vertical movement.
5. Diagonal movement.
6. Direction calculation (including facing helpers).
7. Distance calculation.
8. Explicit dt progression.
9. Exact target arrival.
10. Overshoot prevention.
11. Boundary clamping.
12. Negative virtual-desktop coordinates where valid.
13. Mid-flight interruption.
14. No movement after interruption.
15. Reset behavior.
16. Retargeting while moving.
17. Zero-distance target.
18. Invalid/negative dt handling.
19. Invalid speed handling.
20. Deterministic repeated calculations.
"""

from __future__ import annotations

import math
import pytest
from PySide6.QtCore import QPoint, QRect, QSize

from doodle.desktop.movement import (
    DEFAULT_MOVEMENT_SPEED_PX_PER_S,
    MovementDirection,
    MovementPrimitive,
    MovementStatus,
)


# ======================================================================
# 1. Initialization and Initial State
# ======================================================================


def test_initial_state_is_idle() -> None:
    """Verify newly instantiated MovementPrimitive has IDLE status and zero distance."""
    movement = MovementPrimitive()
    assert movement.status == MovementStatus.IDLE
    assert not movement.is_moving
    assert not movement.has_reached_target
    assert not movement.is_interrupted
    assert movement.current_position == QPoint(0, 0)
    assert movement.target_position is None
    assert movement.remaining_distance == 0.0
    assert movement.direction == MovementDirection(0.0, 0.0)


def test_custom_initial_position() -> None:
    """Verify custom initial coordinate is set correctly."""
    movement = MovementPrimitive(initial_position=QPoint(150, 300))
    assert movement.current_position == QPoint(150, 300)
    assert movement.start_position == QPoint(150, 300)
    assert movement.status == MovementStatus.IDLE


# ======================================================================
# 2. Setting Targets and Calculations
# ======================================================================


def test_target_can_be_set() -> None:
    """Verify setting target transitions status to MOVING and computes distance/direction."""
    movement = MovementPrimitive(speed_px_per_s=100.0, initial_position=QPoint(0, 0))
    movement.set_target(QPoint(100, 0))

    assert movement.status == MovementStatus.MOVING
    assert movement.is_moving
    assert movement.target_position == QPoint(100, 0)
    assert movement.start_position == QPoint(0, 0)
    assert movement.remaining_distance == 100.0
    assert movement.direction.dx == 1.0
    assert movement.direction.dy == 0.0
    assert movement.direction.is_facing_right
    assert not movement.direction.is_facing_left


def test_setting_target_with_explicit_start() -> None:
    """Verify setting target with an explicit start coordinate overrides current position."""
    movement = MovementPrimitive(speed_px_per_s=100.0, initial_position=QPoint(0, 0))
    movement.set_target(target=QPoint(300, 200), start=QPoint(100, 200))

    assert movement.current_position == QPoint(100, 200)
    assert movement.start_position == QPoint(100, 200)
    assert movement.target_position == QPoint(300, 200)
    assert movement.remaining_distance == 200.0
    assert movement.is_moving


def test_zero_distance_target() -> None:
    """Verify setting target equal to current position immediately sets status to REACHED."""
    movement = MovementPrimitive(initial_position=QPoint(50, 50))
    movement.set_target(QPoint(50, 50))

    assert movement.status == MovementStatus.REACHED
    assert movement.has_reached_target
    assert not movement.is_moving
    assert movement.current_position == QPoint(50, 50)
    assert movement.remaining_distance == 0.0
    assert movement.direction == MovementDirection(0.0, 0.0)


# ======================================================================
# 3. Horizontal, Vertical, and Diagonal Movement
# ======================================================================


def test_horizontal_movement() -> None:
    """Verify pure horizontal movement advances along X axis accurately."""
    movement = MovementPrimitive(speed_px_per_s=100.0, initial_position=QPoint(0, 50))
    movement.set_target(QPoint(200, 50))

    pos = movement.step(0.5)  # 50px advance
    assert pos == QPoint(50, 50)
    assert movement.current_position == QPoint(50, 50)
    assert movement.remaining_distance == 150.0
    assert movement.is_moving

    pos = movement.step(1.0)  # 100px advance
    assert pos == QPoint(150, 50)
    assert movement.remaining_distance == 50.0

    pos = movement.step(0.5)  # 50px advance -> arrival
    assert pos == QPoint(200, 50)
    assert movement.has_reached_target
    assert not movement.is_moving


def test_vertical_movement() -> None:
    """Verify pure vertical movement advances along Y axis accurately."""
    movement = MovementPrimitive(speed_px_per_s=120.0, initial_position=QPoint(40, 0))
    movement.set_target(QPoint(40, 60))

    pos = movement.step(0.25)  # 30px advance
    assert pos == QPoint(40, 30)
    assert movement.direction.dx == 0.0
    assert movement.direction.dy == 1.0

    pos = movement.step(0.25)  # 30px advance -> arrival
    assert pos == QPoint(40, 60)
    assert movement.has_reached_target


def test_diagonal_movement_3_4_5_triangle() -> None:
    """Verify diagonal movement along hypotenuse (30, 40 -> distance 50)."""
    movement = MovementPrimitive(speed_px_per_s=50.0, initial_position=QPoint(0, 0))
    movement.set_target(QPoint(30, 40))

    assert math.isclose(movement.remaining_distance, 50.0, abs_tol=1e-6)
    assert math.isclose(movement.direction.dx, 0.6, abs_tol=1e-6)
    assert math.isclose(movement.direction.dy, 0.8, abs_tol=1e-6)

    pos = movement.step(0.5)  # advances 25 px -> (15, 20)
    assert pos == QPoint(15, 20)
    assert math.isclose(movement.remaining_distance, 25.0, abs_tol=1e-6)

    pos = movement.step(0.5)  # advances remaining 25 px -> (30, 40)
    assert pos == QPoint(30, 40)
    assert movement.has_reached_target


# ======================================================================
# 4. Direction Calculation & Direction Helpers
# ======================================================================


def test_direction_calculation_facing_helpers() -> None:
    """Verify direction helpers correctly differentiate left vs right."""
    # Moving leftward
    left_move = MovementPrimitive(initial_position=QPoint(100, 100))
    left_move.set_target(QPoint(0, 100))
    assert left_move.direction.is_facing_left
    assert not left_move.direction.is_facing_right

    # Moving rightward
    right_move = MovementPrimitive(initial_position=QPoint(100, 100))
    right_move.set_target(QPoint(200, 100))
    assert right_move.direction.is_facing_right
    assert not right_move.direction.is_facing_left

    # Pure vertical has neither left nor right bias
    vertical_move = MovementPrimitive(initial_position=QPoint(100, 100))
    vertical_move.set_target(QPoint(100, 200))
    assert not vertical_move.direction.is_facing_left
    assert not vertical_move.direction.is_facing_right


# ======================================================================
# 5. Exact Target Arrival and Overshoot Prevention
# ======================================================================


def test_exact_target_arrival_and_no_overshoot() -> None:
    """Verify large dt does not overshoot target coordinate."""
    movement = MovementPrimitive(speed_px_per_s=100.0, initial_position=QPoint(0, 0))
    movement.set_target(QPoint(80, 0))

    # Stepping with dt=1.5 (would be 150px) must stop exactly at 80
    pos = movement.step(1.5)
    assert pos == QPoint(80, 0)
    assert movement.current_position == QPoint(80, 0)
    assert movement.has_reached_target
    assert movement.remaining_distance == 0.0


def test_further_steps_after_reaching_target_do_not_move() -> None:
    """Verify stepping after REACHED does not displace position."""
    movement = MovementPrimitive(speed_px_per_s=100.0, initial_position=QPoint(0, 0))
    movement.set_target(QPoint(50, 0))
    movement.step(1.0)
    assert movement.has_reached_target

    pos = movement.step(1.0)
    assert pos == QPoint(50, 0)
    assert movement.current_position == QPoint(50, 0)
    assert movement.has_reached_target


# ======================================================================
# 6. Screen Boundary Clamping and Virtual Desktops
# ======================================================================


def test_boundary_clamping_targets() -> None:
    """Verify target outside screen bounds is clamped to usable area."""
    bounds = QRect(0, 0, 1920, 1080)
    window_size = QSize(160, 160)
    movement = MovementPrimitive(
        speed_px_per_s=100.0,
        bounds_provider=bounds,
        window_size=window_size,
        initial_position=QPoint(0, 0),
    )

    # Attempt to target far offscreen right/bottom
    movement.set_target(QPoint(3000, 3000))

    expected_max_x = 1920 - 160  # 1760
    expected_max_y = 1080 - 160  # 920
    assert movement.target_position == QPoint(expected_max_x, expected_max_y)


def test_boundary_clamping_negative_virtual_desktop_coordinates() -> None:
    """Verify negative coordinates on multi-monitor secondary displays work cleanly."""
    # Secondary monitor placed to the left: X from -1920 to 0
    bounds = QRect(-1920, 0, 1920, 1080)
    window_size = QSize(160, 160)
    movement = MovementPrimitive(
        speed_px_per_s=200.0,
        bounds_provider=bounds,
        window_size=window_size,
        initial_position=QPoint(-500, 100),
    )

    # Valid negative target inside secondary monitor bounds
    movement.set_target(QPoint(-1000, 100))
    assert movement.target_position == QPoint(-1000, 100)

    # Step to target
    pos = movement.step(2.5)  # 500px advance
    assert pos == QPoint(-1000, 100)
    assert movement.has_reached_target


def test_boundary_clamping_left_edge_negative_excess() -> None:
    """Verify target beyond left edge of secondary monitor is clamped to bounds.x()."""
    bounds = QRect(-1920, 0, 1920, 1080)
    window_size = QSize(160, 160)
    movement = MovementPrimitive(
        speed_px_per_s=100.0,
        bounds_provider=bounds,
        window_size=window_size,
        initial_position=QPoint(-500, 100),
    )

    # Attempt to set target far to the left of the left monitor
    movement.set_target(QPoint(-3000, 100))
    assert movement.target_position == QPoint(-1920, 100)


# ======================================================================
# 7. Interruption and Recovery
# ======================================================================


def test_mid_flight_interruption() -> None:
    """Verify interrupt() halts active movement and freezes position."""
    movement = MovementPrimitive(speed_px_per_s=100.0, initial_position=QPoint(0, 0))
    movement.set_target(QPoint(200, 0))

    movement.step(0.5)  # at 50px
    assert movement.current_position == QPoint(50, 0)
    assert movement.is_moving

    movement.interrupt()
    assert movement.status == MovementStatus.INTERRUPTED
    assert movement.is_interrupted
    assert not movement.is_moving
    assert movement.current_position == QPoint(50, 0)


def test_no_movement_after_interruption() -> None:
    """Verify step() does not change coordinates while INTERRUPTED."""
    movement = MovementPrimitive(speed_px_per_s=100.0, initial_position=QPoint(0, 0))
    movement.set_target(QPoint(200, 0))
    movement.step(0.5)
    movement.interrupt()

    # Further steps must be no-ops
    pos = movement.step(1.0)
    assert pos == QPoint(50, 0)
    assert movement.current_position == QPoint(50, 0)
    assert movement.status == MovementStatus.INTERRUPTED


# ======================================================================
# 8. Retargeting While Moving
# ======================================================================


def test_retargeting_while_moving() -> None:
    """Verify set_target() mid-flight seamlessly replaces target without teleporting."""
    movement = MovementPrimitive(speed_px_per_s=100.0, initial_position=QPoint(0, 0))
    movement.set_target(QPoint(100, 0))

    movement.step(0.5)  # at 50px
    assert movement.current_position == QPoint(50, 0)

    # Redirect to (50, 100) (pure vertical from current position)
    movement.set_target(QPoint(50, 100))
    assert movement.current_position == QPoint(50, 0)
    assert movement.target_position == QPoint(50, 100)
    assert movement.remaining_distance == 100.0
    assert movement.direction.dx == 0.0
    assert movement.direction.dy == 1.0

    movement.step(1.0)
    assert movement.current_position == QPoint(50, 100)
    assert movement.has_reached_target


# ======================================================================
# 9. Reset
# ======================================================================


def test_reset_returns_to_idle() -> None:
    """Verify reset() clears targets and transitions status to IDLE."""
    movement = MovementPrimitive(speed_px_per_s=100.0, initial_position=QPoint(0, 0))
    movement.set_target(QPoint(100, 100))
    movement.step(0.5)
    assert movement.is_moving

    movement.reset()
    assert movement.status == MovementStatus.IDLE
    assert not movement.is_moving
    assert movement.target_position is None
    assert movement.remaining_distance == 0.0


def test_reset_with_specified_position() -> None:
    """Verify reset() sets new position when given."""
    movement = MovementPrimitive(speed_px_per_s=100.0, initial_position=QPoint(0, 0))
    movement.set_target(QPoint(100, 100))

    movement.reset(position=QPoint(400, 200))
    assert movement.status == MovementStatus.IDLE
    assert movement.current_position == QPoint(400, 200)
    assert movement.start_position == QPoint(400, 200)


# ======================================================================
# 10. Error Handling and Edge Cases
# ======================================================================


def test_invalid_negative_dt_raises_value_error() -> None:
    """Verify negative dt_s raises ValueError."""
    movement = MovementPrimitive()
    movement.set_target(QPoint(100, 100))

    with pytest.raises(ValueError, match="dt_s cannot be negative"):
        movement.step(-0.5)


def test_zero_dt_does_not_move() -> None:
    """Verify dt=0.0 returns current position without changing distance."""
    movement = MovementPrimitive(initial_position=QPoint(10, 20))
    movement.set_target(QPoint(100, 20))

    pos = movement.step(0.0)
    assert pos == QPoint(10, 20)
    assert movement.remaining_distance == 90.0
    assert movement.is_moving


def test_invalid_speed_handling() -> None:
    """Verify non-positive speed values raise ValueError."""
    with pytest.raises(ValueError, match="speed_px_per_s must be positive"):
        MovementPrimitive(speed_px_per_s=0.0)

    with pytest.raises(ValueError, match="speed_px_per_s must be positive"):
        MovementPrimitive(speed_px_per_s=-50.0)

    movement = MovementPrimitive(speed_px_per_s=100.0)
    with pytest.raises(ValueError, match="speed_px_per_s must be positive"):
        movement.speed_px_per_s = -10.0


def test_deterministic_repeated_calculations() -> None:
    """Verify multiple independent primitives produce bit-identical results."""
    m1 = MovementPrimitive(speed_px_per_s=85.0, initial_position=QPoint(12, 34))
    m2 = MovementPrimitive(speed_px_per_s=85.0, initial_position=QPoint(12, 34))

    m1.set_target(QPoint(150, 200))
    m2.set_target(QPoint(150, 200))

    for dt in (0.1, 0.25, 0.05, 0.8, 0.4):
        p1 = m1.step(dt)
        p2 = m2.step(dt)
        assert p1 == p2
        assert math.isclose(m1.remaining_distance, m2.remaining_distance, abs_tol=1e-9)

    assert m1.status == m2.status
