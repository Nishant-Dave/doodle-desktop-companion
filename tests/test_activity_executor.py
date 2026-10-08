"""Unit tests for ActivityExecutor (Task 23: Activity Execution Boundary).

Verifies:
1. Executor starts an Activity and transitions state to RUNNING.
2. current_activity and is_executing track execution accurately.
3. Completing an Activity transitions state to COMPLETED and clears executor.
4. Interrupting an Activity transitions state to INTERRUPTED and clears executor.
5. Cancelling an Activity transitions state to CANCELLED and clears executor.
6. Lifecycle state changes are deterministic.
7. Invalid lifecycle operations fail deterministically (e.g., complete/interrupt when idle).
8. Activity.interruptible is respected (cannot interrupt non-interruptible activity).
9. Active activity replacement follows deterministic rules:
   - Interruptible active activity is auto-interrupted and replaced.
   - Non-interruptible active activity rejects replacement with error.
10. Executor does NOT contain activity selection logic or decision rules.
11. Executor has NO PySide6/UI/rendering dependencies.
12. Activity domain model itself still has NO execution methods.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

import pytest

import doodle.activity.executor as executor_module
from doodle.activity import (
    Activity,
    ActivityExecutionError,
    ActivityExecutor,
    ActivityLifecycleState,
    ActivityType,
)


@pytest.fixture
def executor() -> ActivityExecutor:
    """Fixture providing a fresh ActivityExecutor instance."""
    return ActivityExecutor()


@pytest.fixture
def sample_activity() -> Activity:
    """Fixture providing a standard interruptible Activity."""
    return Activity(ActivityType.REST, interruptible=True)


@pytest.fixture
def non_interruptible_activity() -> Activity:
    """Fixture providing a non-interruptible Activity."""
    return Activity(ActivityType.SLEEP, interruptible=False)


# ======================================================================
# 1. Starting an Activity
# ======================================================================


def test_start_activity_sets_current_and_executing(
    executor: ActivityExecutor, sample_activity: Activity
) -> None:
    """Verify starting an activity sets current_activity and is_executing."""
    assert executor.current_activity is None
    assert not executor.is_executing

    started = executor.start(sample_activity)

    assert started is sample_activity
    assert executor.current_activity is sample_activity
    assert executor.is_executing
    assert sample_activity.lifecycle_state == ActivityLifecycleState.RUNNING


def test_start_invalid_type_raises_type_error(executor: ActivityExecutor) -> None:
    """Verify passing a non-Activity instance to start raises TypeError."""
    with pytest.raises(TypeError, match="Expected an Activity instance"):
        executor.start("not-an-activity")  # type: ignore[arg-type]


def test_cannot_start_same_activity_twice(
    executor: ActivityExecutor, sample_activity: Activity
) -> None:
    """Verify attempting to start an already running activity raises error."""
    executor.start(sample_activity)
    with pytest.raises(ActivityExecutionError, match="already executing"):
        executor.start(sample_activity)


@pytest.mark.parametrize(
    "terminal_state",
    [
        ActivityLifecycleState.COMPLETED,
        ActivityLifecycleState.INTERRUPTED,
        ActivityLifecycleState.CANCELLED,
    ],
)
def test_cannot_start_terminal_activity(
    executor: ActivityExecutor, terminal_state: ActivityLifecycleState
) -> None:
    """Verify attempting to start an activity already in terminal state raises error."""
    act = Activity(ActivityType.WALK, lifecycle_state=terminal_state)
    with pytest.raises(ActivityExecutionError, match="terminal state"):
        executor.start(act)


# ======================================================================
# 2. Completing an Activity
# ======================================================================


def test_complete_transitions_state_and_clears_executor(
    executor: ActivityExecutor, sample_activity: Activity
) -> None:
    """Verify completing an activity sets COMPLETED and resets executor to idle."""
    executor.start(sample_activity)
    completed = executor.complete()

    assert completed is sample_activity
    assert sample_activity.lifecycle_state == ActivityLifecycleState.COMPLETED
    assert executor.current_activity is None
    assert not executor.is_executing


def test_complete_with_matching_activity_succeeds(
    executor: ActivityExecutor, sample_activity: Activity
) -> None:
    """Verify completing with the expected matching Activity succeeds."""
    executor.start(sample_activity)
    completed = executor.complete(sample_activity)
    assert completed is sample_activity
    assert sample_activity.lifecycle_state == ActivityLifecycleState.COMPLETED


def test_complete_with_mismatched_activity_raises_error(
    executor: ActivityExecutor, sample_activity: Activity
) -> None:
    """Verify completing with a mismatched Activity raises ActivityExecutionError."""
    other_act = Activity(ActivityType.PLAY)
    executor.start(sample_activity)
    with pytest.raises(ActivityExecutionError, match="not currently executing"):
        executor.complete(other_act)
    assert executor.current_activity is sample_activity


def test_complete_when_idle_raises_error(executor: ActivityExecutor) -> None:
    """Verify completing when no activity is active raises error."""
    with pytest.raises(ActivityExecutionError, match="No active activity to complete"):
        executor.complete()


# ======================================================================
# 3. Interrupting an Activity
# ======================================================================


def test_interrupt_transitions_state_and_clears_executor(
    executor: ActivityExecutor, sample_activity: Activity
) -> None:
    """Verify interrupting an activity sets INTERRUPTED and resets executor."""
    executor.start(sample_activity)
    interrupted = executor.interrupt()

    assert interrupted is sample_activity
    assert sample_activity.lifecycle_state == ActivityLifecycleState.INTERRUPTED
    assert executor.current_activity is None
    assert not executor.is_executing


def test_interrupt_when_idle_raises_error(executor: ActivityExecutor) -> None:
    """Verify interrupting when no activity is active raises error."""
    with pytest.raises(ActivityExecutionError, match="No active activity to interrupt"):
        executor.interrupt()


def test_interrupt_non_interruptible_activity_raises_error(
    executor: ActivityExecutor, non_interruptible_activity: Activity
) -> None:
    """Verify interrupting a non-interruptible activity is rejected."""
    executor.start(non_interruptible_activity)

    with pytest.raises(ActivityExecutionError, match="Cannot interrupt non-interruptible"):
        executor.interrupt()

    # Active activity must remain running and untouched
    assert executor.current_activity is non_interruptible_activity
    assert executor.is_executing
    assert non_interruptible_activity.lifecycle_state == ActivityLifecycleState.RUNNING


# ======================================================================
# 4. Cancelling an Activity
# ======================================================================


def test_cancel_transitions_state_and_clears_executor(
    executor: ActivityExecutor, sample_activity: Activity
) -> None:
    """Verify cancelling sets CANCELLED and resets executor."""
    executor.start(sample_activity)
    cancelled = executor.cancel()

    assert cancelled is sample_activity
    assert sample_activity.lifecycle_state == ActivityLifecycleState.CANCELLED
    assert executor.current_activity is None
    assert not executor.is_executing


def test_cancel_non_interruptible_activity_succeeds(
    executor: ActivityExecutor, non_interruptible_activity: Activity
) -> None:
    """Verify cancel unconditionally aborts active activity regardless of interruptible flag."""
    executor.start(non_interruptible_activity)
    cancelled = executor.cancel()

    assert cancelled is non_interruptible_activity
    assert non_interruptible_activity.lifecycle_state == ActivityLifecycleState.CANCELLED
    assert executor.current_activity is None


def test_cancel_when_idle_raises_error(executor: ActivityExecutor) -> None:
    """Verify cancelling when no activity is active raises error."""
    with pytest.raises(ActivityExecutionError, match="No active activity to cancel"):
        executor.cancel()


# ======================================================================
# 5. Replacement Policy & Preemption
# ======================================================================


def test_start_replaces_interruptible_active_activity(
    executor: ActivityExecutor, sample_activity: Activity
) -> None:
    """Verify starting another activity auto-interrupts the active interruptible one."""
    executor.start(sample_activity)
    new_act = Activity(ActivityType.PLAY)

    executor.start(new_act)

    # First activity was interrupted
    assert sample_activity.lifecycle_state == ActivityLifecycleState.INTERRUPTED
    # New activity is now running
    assert new_act.lifecycle_state == ActivityLifecycleState.RUNNING
    assert executor.current_activity is new_act


def test_start_rejects_replacement_of_non_interruptible_activity(
    executor: ActivityExecutor, non_interruptible_activity: Activity
) -> None:
    """Verify starting another activity fails if the active one is non-interruptible."""
    executor.start(non_interruptible_activity)
    new_act = Activity(ActivityType.REST)

    with pytest.raises(ActivityExecutionError, match="Cannot replace active non-interruptible"):
        executor.start(new_act)

    # Original non-interruptible activity remains running
    assert executor.current_activity is non_interruptible_activity
    assert non_interruptible_activity.lifecycle_state == ActivityLifecycleState.RUNNING
    # New activity was never started
    assert new_act.lifecycle_state == ActivityLifecycleState.PENDING


# ======================================================================
# 6. Architectural Boundaries & Decoupling
# ======================================================================


def test_executor_has_no_selection_logic(executor: ActivityExecutor) -> None:
    """Verify executor contains no behavior selection, mood, or context methods."""
    forbidden = [
        "select",
        "choose",
        "evaluate",
        "decide",
        "policy",
        "mood",
        "context",
        "proximity",
    ]
    for attr in forbidden:
        assert not hasattr(executor, attr), f"Executor illegally contains selection attribute '{attr}'"


def test_executor_has_no_pyside6_dependencies() -> None:
    """Verify via AST parsing that executor module has no PySide6 or Qt imports."""
    file_path = inspect.getfile(executor_module)
    tree = ast.parse(Path(file_path).read_text(encoding="utf-8"))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("PySide6"), f"Illegal import {alias.name}"
                assert not alias.name.startswith("PyQt"), f"Illegal import {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                assert not node.module.startswith("PySide6"), f"Illegal import {node.module}"
                assert not node.module.startswith("PyQt"), f"Illegal import {node.module}"


def test_activity_domain_model_has_no_execution_methods() -> None:
    """Verify Activity domain model remains purely declarative without execution methods."""
    forbidden = [
        "start",
        "tick",
        "finish",
        "interrupt",
        "cancel",
        "on_start",
        "on_tick",
        "on_finish",
        "on_interrupt",
        "on_cancel",
    ]
    for attr in forbidden:
        assert not hasattr(Activity, attr), f"Activity illegally contains execution method '{attr}'"


def test_executor_repr(executor: ActivityExecutor, sample_activity: Activity) -> None:
    """Verify representation string accurately reflects current state."""
    assert "is_executing=False" in repr(executor)
    executor.start(sample_activity)
    assert "is_executing=True" in repr(executor)
    assert sample_activity.activity_id in repr(executor)


# ======================================================================
# 13. Target Delegation (Task 24)
# ======================================================================


class StubExecutionTarget:
    """Stub target capturing physical realization calls."""

    def __init__(self) -> None:
        self.performed: list[Activity] = []
        self.interrupted: list[Activity] = []
        self.cancelled: list[Activity] = []

    def perform_activity(self, activity: Activity) -> None:
        self.performed.append(activity)

    def interrupt_activity(self, activity: Activity) -> None:
        self.interrupted.append(activity)

    def cancel_activity(self, activity: Activity) -> None:
        self.cancelled.append(activity)


def test_executor_delegates_to_target_on_start(sample_activity: Activity) -> None:
    target = StubExecutionTarget()
    exec_with_target = ActivityExecutor(target=target)
    assert exec_with_target.target is target

    exec_with_target.start(sample_activity)
    assert target.performed == [sample_activity]
    assert target.interrupted == []
    assert target.cancelled == []


def test_executor_delegates_to_target_on_interrupt(sample_activity: Activity) -> None:
    target = StubExecutionTarget()
    exec_with_target = ActivityExecutor(target=target)
    exec_with_target.start(sample_activity)

    exec_with_target.interrupt()
    assert target.interrupted == [sample_activity]
    assert target.cancelled == []


def test_executor_delegates_to_target_on_cancel(sample_activity: Activity) -> None:
    target = StubExecutionTarget()
    exec_with_target = ActivityExecutor(target=target)
    exec_with_target.start(sample_activity)

    exec_with_target.cancel()
    assert target.cancelled == [sample_activity]
    assert target.interrupted == []


def test_executor_does_not_call_target_on_complete(sample_activity: Activity) -> None:
    target = StubExecutionTarget()
    exec_with_target = ActivityExecutor(target=target)
    exec_with_target.start(sample_activity)

    exec_with_target.complete()
    # Target only receives start; completion is an external notification, not a command to target
    assert target.performed == [sample_activity]
    assert target.interrupted == []
    assert target.cancelled == []


def test_executor_delegates_on_auto_interrupt_replacement(sample_activity: Activity) -> None:
    target = StubExecutionTarget()
    exec_with_target = ActivityExecutor(target=target)
    exec_with_target.start(sample_activity)

    new_act = Activity(ActivityType.STRETCH, interruptible=True)
    exec_with_target.start(new_act)

    assert target.interrupted == [sample_activity]
    assert target.performed == [sample_activity, new_act]

