"""Integration and unit tests for ActivityExecutionCoordinator (Task 27A).

Verifies:
1. Construction, dependency validation, and default property values.
2. Runtime timer starts when continuous physical execution is required.
3. Timer remains stopped when no continuous progression is required (REST, SLEEP, etc.).
4. Deterministic progression via step(dt_s) forwards dt_s and updates coordinates.
5. Completion reaches the ActivityExecutor and immediately stops the timer.
6. Interruption stops progression and preserves distinct INTERRUPTED lifecycle semantics.
7. Cancellation stops progression and preserves distinct CANCELLED lifecycle semantics.
8. Elapsed time clamping: large delta steps clamp to max_delta_time_s (0.1s).
9. Single timer ownership: exactly one QTimer owned, no duplicate timers created.
10. Clean shutdown: cleanup() / stop() terminates timer safely.
11. Generic eligibility: coordinator has no hard-coded ActivityTypes.
12. Zero wall-clock sleeps or real hardware delays required.
"""

from __future__ import annotations

import ast
import inspect
import os
from typing import List
from unittest.mock import MagicMock

import pytest

# Ensure Qt runs offscreen during automated test execution
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QElapsedTimer, QPoint, QTimer
from PySide6.QtWidgets import QApplication

import doodle.desktop.coordinator as coordinator_module
from doodle.activity import (
    Activity,
    ActivityExecutor,
    ActivityLifecycleState,
    ActivityType,
)
from doodle.character import (
    Character,
    CharacterActivityPerformer,
    CharacterState,
)
from doodle.desktop import (
    ActivityExecutionCoordinator,
    CompanionWindow,
    DesktopActivityPerformer,
    MovementPrimitive,
)


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Ensure a singleton QApplication instance exists for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["test_execution_coordinator"])
    return app


@pytest.fixture
def character(qapp: QApplication) -> Character:
    """Provide a fresh Character instance."""
    return Character(name="panda")


@pytest.fixture
def character_performer(character: Character) -> CharacterActivityPerformer:
    """Provide a CharacterActivityPerformer backed by character."""
    return CharacterActivityPerformer(character=character)


@pytest.fixture
def window(qapp: QApplication) -> CompanionWindow:
    """Provide a CompanionWindow instance cleaned up after test."""
    win = CompanionWindow()
    yield win
    if win.isVisible():
        win.close()
    win.deleteLater()


@pytest.fixture
def movement() -> MovementPrimitive:
    """Provide a fresh MovementPrimitive with standard test speed."""
    return MovementPrimitive(speed_px_per_s=100.0, initial_position=QPoint(100, 100))


@pytest.fixture
def performer(
    character_performer: CharacterActivityPerformer,
    movement: MovementPrimitive,
    window: CompanionWindow,
) -> DesktopActivityPerformer:
    """Provide a DesktopActivityPerformer coordinating the test fixtures."""
    return DesktopActivityPerformer(
        character_performer=character_performer,
        movement=movement,
        window=window,
    )


@pytest.fixture
def executor(performer: DesktopActivityPerformer) -> ActivityExecutor:
    """Provide an ActivityExecutor targeting the DesktopActivityPerformer."""
    return ActivityExecutor(target=performer)


@pytest.fixture
def coordinator(
    executor: ActivityExecutor,
    performer: DesktopActivityPerformer,
) -> ActivityExecutionCoordinator:
    """Provide an ActivityExecutionCoordinator coordinating executor and performer."""
    coord = ActivityExecutionCoordinator(executor=executor, performer=performer)
    yield coord
    coord.cleanup()


# ======================================================================
# 1. Construction and Property Validation
# ======================================================================


def test_coordinator_construction_and_properties(
    executor: ActivityExecutor,
    performer: DesktopActivityPerformer,
) -> None:
    """Verify coordinator initialization, default properties, and repr."""
    coord = ActivityExecutionCoordinator(
        executor=executor,
        performer=performer,
        tick_interval_ms=25,
        max_delta_time_s=0.08,
    )

    assert coord.executor is executor
    assert coord.performer is performer
    assert coord.tick_interval_ms == 25
    assert coord.max_delta_time_s == 0.08
    assert coord.is_running is False
    assert coord.is_progression_required is False

    rep = repr(coord)
    assert "ActivityExecutionCoordinator" in rep
    assert "running=False" in rep
    assert "interval_ms=25" in rep
    coord.cleanup()


def test_coordinator_construction_validates_dependencies(
    executor: ActivityExecutor,
    performer: DesktopActivityPerformer,
) -> None:
    """Verify coordinator raises appropriate errors on invalid constructor arguments."""
    with pytest.raises(TypeError, match="executor must not be None"):
        ActivityExecutionCoordinator(executor=None, performer=performer)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="performer must not be None"):
        ActivityExecutionCoordinator(executor=executor, performer=None)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="tick_interval_ms must be positive"):
        ActivityExecutionCoordinator(executor=executor, performer=performer, tick_interval_ms=0)

    with pytest.raises(ValueError, match="max_delta_time_s must be positive"):
        ActivityExecutionCoordinator(executor=executor, performer=performer, max_delta_time_s=-0.1)


# ======================================================================
# 2. Timer Starts for Active Continuous Execution
# ======================================================================


def test_timer_starts_for_active_continuous_execution(
    coordinator: ActivityExecutionCoordinator,
    window: CompanionWindow,
) -> None:
    """Verify coordinator starts its timer when continuous execution begins."""
    window.move(QPoint(100, 100))
    walk_act = Activity(
        activity_type=ActivityType.WALK,
        metadata={"target": QPoint(300, 100)},  # 200 px distance
    )

    progression_started_mock = MagicMock()
    coordinator.progression_started.connect(progression_started_mock)

    assert coordinator.is_running is False

    coordinator.start_activity(walk_act)

    assert coordinator.is_progression_required is True
    assert coordinator.is_running is True
    progression_started_mock.assert_called_once()


# ======================================================================
# 3. Timer Remains Stopped When No Progression Required
# ======================================================================


@pytest.mark.parametrize(
    "activity_type",
    [
        ActivityType.REST,
        ActivityType.SLEEP,
        ActivityType.STRETCH,
        ActivityType.LOOK_AROUND,
        ActivityType.PLAY,
    ],
)
def test_timer_remains_stopped_for_non_continuous_activities(
    coordinator: ActivityExecutionCoordinator,
    activity_type: ActivityType,
) -> None:
    """Verify timer stays stopped for non-continuous activities (REST, SLEEP, etc.)."""
    act = Activity(activity_type=activity_type)

    coordinator.start_activity(act)

    assert coordinator.is_progression_required is False
    assert coordinator.is_running is False


def test_timer_remains_stopped_for_zero_distance_walk(
    coordinator: ActivityExecutionCoordinator,
    window: CompanionWindow,
) -> None:
    """Verify zero-distance target completes immediately without running the timer."""
    window.move(QPoint(80, 80))
    zero_dist_walk = Activity(
        activity_type=ActivityType.WALK,
        metadata={"target": QPoint(80, 80)},
    )

    coordinator.start_activity(zero_dist_walk)

    assert coordinator.is_progression_required is False
    assert coordinator.is_running is False
    assert zero_dist_walk.lifecycle_state == ActivityLifecycleState.COMPLETED


# ======================================================================
# 4. Deterministic Progression via step(dt_s)
# ======================================================================


def test_step_forwards_dt_s_deterministically(
    coordinator: ActivityExecutionCoordinator,
    window: CompanionWindow,
) -> None:
    """Verify step(dt_s) advances position deterministically and emits ticked signal."""
    window.move(QPoint(100, 100))
    coordinator.performer.movement.speed_px_per_s = 100.0  # 100 px/s

    walk_act = Activity(
        activity_type=ActivityType.WALK,
        metadata={"target": QPoint(200, 100)},  # 100 px east
    )
    coordinator.start_activity(walk_act)

    ticked_points: List[QPoint] = []
    coordinator.ticked.connect(ticked_points.append)

    # Step 0.05 seconds -> advances by 5.0 px -> (105, 100)
    pos = coordinator.step(0.05)
    assert pos == QPoint(105, 100)
    assert window.pos() == QPoint(105, 100)
    assert len(ticked_points) == 1
    assert ticked_points[0] == QPoint(105, 100)


def test_step_rejects_negative_dt_s(
    coordinator: ActivityExecutionCoordinator,
) -> None:
    """Verify step raises ValueError on negative delta time."""
    with pytest.raises(ValueError, match="dt_s cannot be negative"):
        coordinator.step(-0.01)


def test_step_returns_none_when_no_continuous_execution_active(
    coordinator: ActivityExecutionCoordinator,
) -> None:
    """Verify step returns None when no movement is active."""
    assert coordinator.step(0.05) is None


# ======================================================================
# 5. Completion Reaches Executor and Stops Timer
# ======================================================================


def test_completion_reaches_executor_and_stops_timer(
    coordinator: ActivityExecutionCoordinator,
    window: CompanionWindow,
) -> None:
    """Verify target arrival stops timer and transitions executor to COMPLETED."""
    window.move(QPoint(0, 0))
    coordinator.performer.movement.speed_px_per_s = 100.0

    walk_act = Activity(
        activity_type=ActivityType.WALK,
        metadata={"target": QPoint(100, 0)},  # 100 px east
    )
    coordinator.start_activity(walk_act)
    assert coordinator.is_running is True
    assert coordinator.executor.is_executing is True

    completed_signals: List[Activity] = []
    coordinator.activity_completed.connect(completed_signals.append)

    # Step 0.5s -> (50, 0)
    coordinator.step(0.5)
    assert coordinator.is_running is True
    assert coordinator.executor.is_executing is True

    # Step 0.5s -> arrives at (100, 0)
    coordinator.step(0.5)

    # Timer must be stopped immediately
    assert coordinator.is_running is False
    assert coordinator.is_progression_required is False

    # Executor transitioned to COMPLETED
    assert coordinator.executor.is_executing is False
    assert walk_act.lifecycle_state == ActivityLifecycleState.COMPLETED
    assert len(completed_signals) == 1
    assert completed_signals[0] is walk_act


# ======================================================================
# 6. Interruption Stops Progression
# ======================================================================


def test_interruption_stops_progression_and_timer(
    coordinator: ActivityExecutionCoordinator,
    window: CompanionWindow,
) -> None:
    """Verify interruption stops timer, halts movement, and preserves position."""
    window.move(QPoint(0, 0))
    coordinator.performer.movement.speed_px_per_s = 100.0

    walk_act = Activity(
        activity_type=ActivityType.WALK,
        metadata={"target": QPoint(200, 0)},
    )
    coordinator.start_activity(walk_act)
    coordinator.step(0.5)  # Moved to (50, 0)
    assert window.pos() == QPoint(50, 0)
    assert coordinator.is_running is True

    interrupted_signals: List[Activity] = []
    coordinator.activity_interrupted.connect(interrupted_signals.append)

    # Interrupt via executor
    coordinator.executor.interrupt()

    # Timer must be stopped
    assert coordinator.is_running is False
    assert coordinator.is_progression_required is False
    assert walk_act.lifecycle_state == ActivityLifecycleState.INTERRUPTED
    assert len(interrupted_signals) == 1
    assert interrupted_signals[0] is walk_act

    # Physical position is preserved exactly
    assert window.pos() == QPoint(50, 0)

    # Further steps do nothing
    assert coordinator.step(0.5) is None
    assert window.pos() == QPoint(50, 0)


# ======================================================================
# 7. Cancellation Stops Progression
# ======================================================================


def test_cancellation_stops_progression_and_timer(
    coordinator: ActivityExecutionCoordinator,
    window: CompanionWindow,
) -> None:
    """Verify cancellation stops timer and preserves CANCELLED lifecycle semantics."""
    window.move(QPoint(0, 0))
    coordinator.performer.movement.speed_px_per_s = 100.0

    walk_act = Activity(
        activity_type=ActivityType.WALK,
        metadata={"target": QPoint(200, 0)},
    )
    coordinator.start_activity(walk_act)
    coordinator.step(0.5)
    current_pos_mid = window.pos()
    assert coordinator.is_running is True

    cancelled_signals: List[Activity] = []
    coordinator.activity_cancelled.connect(cancelled_signals.append)

    # Cancel via executor
    coordinator.executor.cancel()

    # Timer stopped
    assert coordinator.is_running is False
    assert coordinator.is_progression_required is False
    assert walk_act.lifecycle_state == ActivityLifecycleState.CANCELLED
    assert len(cancelled_signals) == 1
    assert cancelled_signals[0] is walk_act
    assert window.pos() == current_pos_mid


# ======================================================================
# 8. Elapsed Time Clamping
# ======================================================================


def test_elapsed_time_clamping_prevents_large_jumps(
    coordinator: ActivityExecutionCoordinator,
    window: CompanionWindow,
) -> None:
    """Verify large delta time steps are clamped to max_delta_time_s (0.1s)."""
    window.move(QPoint(0, 0))
    coordinator.performer.movement.speed_px_per_s = 100.0  # 100 px/s

    walk_act = Activity(
        activity_type=ActivityType.WALK,
        metadata={"target": QPoint(500, 0)},
    )
    coordinator.start_activity(walk_act)

    # Step with an exaggerated 5.0 second lag spike with clamp=True
    # With speed 100 px/s, an unclamped 5.0s step would move 500 px.
    # But clamped to max_delta_time_s (0.1s), it must advance at most 10 px!
    pos = coordinator.step(5.0, clamp=True)

    assert pos == QPoint(10, 0)
    assert window.pos() == QPoint(10, 0)


def test_on_timeout_with_mock_elapsed_timer(
    executor: ActivityExecutor,
    performer: DesktopActivityPerformer,
    window: CompanionWindow,
) -> None:
    """Verify _on_timeout measures elapsed time and clamps it correctly."""
    mock_clock = MagicMock(spec=QElapsedTimer)
    mock_clock.isValid.return_value = True
    # Simulate 2.5 seconds elapsed (2_500_000_000 ns)
    mock_clock.nsecsElapsed.return_value = 2_500_000_000

    coord = ActivityExecutionCoordinator(
        executor=executor,
        performer=performer,
        clock=mock_clock,
    )

    window.move(QPoint(0, 0))
    performer.movement.speed_px_per_s = 100.0

    walk_act = Activity(
        activity_type=ActivityType.WALK,
        metadata={"target": QPoint(500, 0)},
    )
    coord.start_activity(walk_act)

    # Invoke timeout slot directly
    coord._on_timeout()

    # Must be clamped to 0.1s -> 10 px
    assert window.pos() == QPoint(10, 0)
    coord.cleanup()


# ======================================================================
# 9. Single Timer Ownership
# ======================================================================


def test_single_timer_ownership_and_no_multiplication(
    coordinator: ActivityExecutionCoordinator,
) -> None:
    """Verify exactly one QTimer is owned and start() does not multiply timers."""
    timers = [child for child in coordinator.children() if isinstance(child, QTimer)]
    assert len(timers) == 1

    # Calling start multiple times does not create new timers
    coordinator.start()
    coordinator.start()
    timers_after = [child for child in coordinator.children() if isinstance(child, QTimer)]
    assert len(timers_after) == 1


# ======================================================================
# 10. Clean Shutdown
# ======================================================================


def test_clean_shutdown(
    coordinator: ActivityExecutionCoordinator,
    window: CompanionWindow,
) -> None:
    """Verify cleanup() terminates timer safely and idempotently."""
    window.move(QPoint(0, 0))
    walk_act = Activity(
        activity_type=ActivityType.WALK,
        metadata={"target": QPoint(200, 0)},
    )
    coordinator.start_activity(walk_act)
    assert coordinator.is_running is True

    # Shutdown cleanup
    coordinator.cleanup()
    assert coordinator.is_running is False

    # Calling cleanup again is safe
    coordinator.cleanup()
    assert coordinator.is_running is False


# ======================================================================
# 11. Generic Execution Eligibility
# ======================================================================


def test_generic_eligibility_without_hardcoded_activity_types() -> None:
    """Verify coordinator contains zero hard-coded references to specific ActivityTypes."""
    source = inspect.getsource(coordinator_module)
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in (
            "WALK",
            "REST",
            "SLEEP",
            "STRETCH",
            "LOOK_AROUND",
            "PLAY",
        ):
            pytest.fail(f"Coordinator must not hard-code ActivityType.{node.attr}")
