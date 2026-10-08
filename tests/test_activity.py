"""Unit tests for Doodle's simplified Activity domain model (Task 21).

Focuses on:
- ActivityType and ActivityLifecycleState vocabulary
- Declarative Activity construction and defaults
- Explicit configuration and validation
- Deterministic ID generation
- PySide6 independence
- Absence of premature execution machinery
- Canonical import path
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

import pytest

import doodle.activity.model as activity_model_module
import doodle.activity.types as activity_types_module
from doodle.activity import (
    Activity,
    ActivityLifecycleState,
    ActivityType,
    reset_activity_id_counter,
)


@pytest.fixture(autouse=True)
def reset_id_counter() -> None:
    """Reset the activity ID counter before each test for determinism."""
    reset_activity_id_counter()


# ======================================================================
# Vocabulary & Enumerations
# ======================================================================


def test_activity_type_vocabulary() -> None:
    """Verify foundational ActivityType vocabulary."""
    expected = {"REST", "WALK", "LOOK_AROUND", "STRETCH", "SLEEP", "PLAY"}
    actual = {t.value for t in ActivityType}
    assert actual == expected

    for t in ActivityType:
        assert str(t) == t.value
        assert t == t.value


def test_activity_lifecycle_state_vocabulary() -> None:
    """Verify declarative ActivityLifecycleState vocabulary."""
    expected = {"PENDING", "RUNNING", "INTERRUPTED", "COMPLETED", "CANCELLED"}
    actual = {s.value for s in ActivityLifecycleState}
    assert actual == expected

    for s in ActivityLifecycleState:
        assert str(s) == s.value
        assert s == s.value


# ======================================================================
# Construction & Defaults
# ======================================================================


def test_activity_construction_defaults() -> None:
    """Verify that Activity constructs with sensible declarative defaults."""
    activity = Activity(ActivityType.REST)

    assert activity.activity_type == ActivityType.REST
    assert activity.activity_id == "act_rest_1"
    assert activity.lifecycle_state == ActivityLifecycleState.PENDING
    assert activity.interruptible is True
    assert activity.metadata == {}


def test_activity_construction_string_type_conversion() -> None:
    """Verify case-insensitive string activity_type is converted to enum."""
    act_lower = Activity("walk")
    assert act_lower.activity_type == ActivityType.WALK

    act_upper = Activity("LOOK_AROUND")
    assert act_upper.activity_type == ActivityType.LOOK_AROUND


def test_activity_construction_explicit_values() -> None:
    """Verify construction with fully specified domain attributes."""
    activity = Activity(
        activity_type=ActivityType.STRETCH,
        activity_id="custom_act_42",
        lifecycle_state=ActivityLifecycleState.RUNNING,
        interruptible=False,
        metadata={"priority": "high", "reason": "user_idle"},
    )

    assert activity.activity_type == ActivityType.STRETCH
    assert activity.activity_id == "custom_act_42"
    assert activity.lifecycle_state == ActivityLifecycleState.RUNNING
    assert activity.interruptible is False
    assert activity.metadata == {"priority": "high", "reason": "user_idle"}


def test_activity_id_deterministic_and_unique() -> None:
    """Verify auto-generated activity IDs are deterministic and sequential."""
    reset_activity_id_counter()
    act1 = Activity(ActivityType.REST)
    act2 = Activity(ActivityType.WALK)
    act3 = Activity(ActivityType.SLEEP)

    assert act1.activity_id == "act_rest_1"
    assert act2.activity_id == "act_walk_2"
    assert act3.activity_id == "act_sleep_3"

    reset_activity_id_counter()
    act_repeat = Activity(ActivityType.REST)
    assert act_repeat.activity_id == "act_rest_1"


def test_activity_custom_id_preserved() -> None:
    """Verify explicit custom activity_id is preserved and not overwritten."""
    activity = Activity(ActivityType.REST, activity_id="custom_id_999")
    assert activity.activity_id == "custom_id_999"


def test_activity_interruptibility() -> None:
    """Verify that interruptibility defaults to True and can be explicitly configured."""
    default_act = Activity(ActivityType.REST)
    assert default_act.interruptible is True

    uninterruptible_act = Activity(ActivityType.SLEEP, interruptible=False)
    assert uninterruptible_act.interruptible is False


def test_activity_metadata_storage() -> None:
    """Verify that metadata stores arbitrary semantic domain information without keyword restrictions."""
    domain_meta = {
        "target_location": (100, 200),
        "target_perch": "taskbar",
        "reason": "boredom",
        "nested_details": {"intensity": 0.8},
    }
    activity = Activity(ActivityType.LOOK_AROUND, metadata=domain_meta)
    assert activity.metadata == domain_meta
    assert activity.metadata["target_perch"] == "taskbar"


def test_activity_dataclass_equality() -> None:
    """Verify standard dataclass equality semantics."""
    act1 = Activity(ActivityType.REST, activity_id="same_id", interruptible=True)
    act2 = Activity(ActivityType.REST, activity_id="same_id", interruptible=True)
    act3 = Activity(ActivityType.REST, activity_id="diff_id", interruptible=True)

    assert act1 == act2
    assert act1 != act3


def test_activity_repr() -> None:
    """Verify standard dataclass repr contains essential fields."""
    activity = Activity(ActivityType.WALK, activity_id="act_test_10")
    r = repr(activity)
    assert "Activity" in r
    assert "WALK" in r
    assert "act_test_10" in r


# ======================================================================
# Validation
# ======================================================================


@pytest.mark.parametrize("invalid_type", [None, "", "INVALID_UNKNOWN", 123, []])
def test_invalid_activity_type_rejected(invalid_type: Any) -> None:
    """Verify invalid activity types raise ValueError."""
    with pytest.raises(ValueError):
        Activity(activity_type=invalid_type)


def test_invalid_lifecycle_state_rejected() -> None:
    """Verify invalid lifecycle_state raises ValueError."""
    with pytest.raises(ValueError):
        Activity(ActivityType.REST, lifecycle_state="RUNNING")  # type: ignore[arg-type]


def test_invalid_interruptible_rejected() -> None:
    """Verify non-boolean interruptible flag raises ValueError."""
    with pytest.raises(ValueError):
        Activity(ActivityType.REST, interruptible="yes")  # type: ignore[arg-type]


def test_invalid_metadata_rejected() -> None:
    """Verify non-dict metadata raises ValueError."""
    with pytest.raises(ValueError):
        Activity(ActivityType.REST, metadata="not-a-dict")  # type: ignore[arg-type]


# ======================================================================
# Architectural Boundaries
# ======================================================================


def test_no_pyside6_dependencies_in_activity() -> None:
    """Verify via AST parsing that activity modules do NOT import PySide6 or Qt."""
    for mod in [activity_types_module, activity_model_module]:
        file_path = inspect.getfile(mod)
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


def test_no_execution_methods_on_activity() -> None:
    """Verify Activity does NOT contain execution methods or lifecycle hooks.

    Execution belongs strictly to the future ActivityExecutor (Task 23).
    """
    forbidden_methods = {
        "start",
        "tick",
        "finish",
        "interrupt",
        "cancel",
        "on_start",
        "on_tick",
        "on_interrupt",
        "on_finish",
        "on_cancel",
        "can_start",
        "elapsed_time_s",
        "progress",
    }
    for method_name in forbidden_methods:
        assert not hasattr(Activity, method_name), (
            f"Activity illegally contains execution method or attribute '{method_name}'"
        )


def test_canonical_import_path_only() -> None:
    """Verify canonical import works and duplicate behavior/activity.py bridge does not exist."""
    from doodle.activity import Activity, ActivityLifecycleState, ActivityType

    act = Activity(ActivityType.REST)
    assert act.activity_type == ActivityType.REST

    with pytest.raises(ModuleNotFoundError):
        import doodle.behavior.activity  # type: ignore[import-not-found]
