"""Unit tests for CharacterActivityPerformer and Activity ↔ Animation boundary (Task 24).

Verifies:
1. Protocol conformance: CharacterActivityPerformer conforms to ActivityExecutionTarget.
2. Activity realization: Maps all 6 ActivityTypes to existing Character capabilities.
3. Unsupported activity fallback: WALK falls back to neutral IDLE without fake movement.
4. Physical recovery: interrupt_activity() and cancel_activity() return Character to IDLE.
5. Architectural separation:
   - Performer has no reference to ActivityExecutor.
   - Performer does not import ActivityExecutor.
   - CharacterState remains strictly 5 physical states (no WALK, PLAY, etc.).
   - doodle.activity package remains 100% free of PySide6/Qt imports.
6. Completion boundary: Demonstrates composition wiring (character.animation_finished ->
   composition callback -> executor.complete()) without performer holding executor reference.
"""

from __future__ import annotations

import ast
import inspect
import os
from pathlib import Path

import pytest

# Ensure Qt runs offscreen during test execution
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import doodle.activity.executor as executor_module
import doodle.character.performer as performer_module
from doodle.activity import (
    Activity,
    ActivityExecutionTarget,
    ActivityExecutor,
    ActivityLifecycleState,
    ActivityType,
)
from doodle.character import (
    Character,
    CharacterActivityPerformer,
    CharacterState,
)


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Ensure a singleton QApplication instance exists for tests using Character."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["test_activity_performer"])
    return app


@pytest.fixture
def character(qapp: QApplication) -> Character:
    """Fixture providing a fresh Character instance."""
    return Character(name="panda")


@pytest.fixture
def performer(character: Character) -> CharacterActivityPerformer:
    """Fixture providing a CharacterActivityPerformer attached to character."""
    return CharacterActivityPerformer(character)


# ======================================================================
# A. Protocol Conformance
# ======================================================================


class TestProtocolConformance:
    """Verify CharacterActivityPerformer adheres to ActivityExecutionTarget."""

    def test_performer_isinstance_target(self, performer: CharacterActivityPerformer) -> None:
        assert isinstance(performer, ActivityExecutionTarget)

    def test_performer_has_exact_required_methods(
        self, performer: CharacterActivityPerformer
    ) -> None:
        assert hasattr(performer, "perform_activity")
        assert callable(performer.perform_activity)

        assert hasattr(performer, "interrupt_activity")
        assert callable(performer.interrupt_activity)

        assert hasattr(performer, "cancel_activity")
        assert callable(performer.cancel_activity)

    def test_performer_does_not_have_complete_activity(
        self, performer: CharacterActivityPerformer
    ) -> None:
        """Verify complete_activity was intentionally omitted per architectural design."""
        assert not hasattr(performer, "complete_activity")

    def test_performer_requires_character_instance(self) -> None:
        with pytest.raises(TypeError):
            CharacterActivityPerformer(None)  # type: ignore[arg-type]

        with pytest.raises(TypeError):
            CharacterActivityPerformer("not_a_character")  # type: ignore[arg-type]

    def test_performer_character_property(
        self, character: Character, performer: CharacterActivityPerformer
    ) -> None:
        assert performer.character is character
        assert "panda" in repr(performer)


# ======================================================================
# B. Activity Realization (Mapping)
# ======================================================================


class TestActivityRealization:
    """Verify Activity -> Character/Animation mapping across all 6 ActivityTypes."""

    def test_realize_rest_always_maps_to_sit(
        self, character: Character, performer: CharacterActivityPerformer
    ) -> None:
        """Verify REST always maps deterministically to CharacterState.SIT and 'sit' animation."""
        character.set_state(CharacterState.IDLE)
        act = Activity(ActivityType.REST)
        performer.perform_activity(act)

        assert character.state == CharacterState.SIT
        assert character.current_animation_name == "sit"

    def test_realize_rest_cannot_override_presentation_via_metadata(
        self, character: Character, performer: CharacterActivityPerformer
    ) -> None:
        """Verify Activity metadata cannot override CharacterState or animation for REST."""
        # Even if metadata attempts to request IDLE, ATTENTION, or arbitrary postures:
        act_attempt_idle = Activity(
            ActivityType.REST, metadata={"state": "IDLE", "posture": "IDLE"}
        )
        performer.perform_activity(act_attempt_idle)
        assert character.state == CharacterState.SIT
        assert character.current_animation_name == "sit"

        act_attempt_anim = Activity(
            ActivityType.REST, metadata={"animation": "idle", "loop": False}
        )
        performer.perform_activity(act_attempt_anim)
        assert character.state == CharacterState.SIT
        assert character.current_animation_name == "sit"

    def test_upstream_activity_creation_requires_no_character_state(self) -> None:
        """Verify creating a REST Activity requires zero knowledge or import of CharacterState."""
        act = Activity(ActivityType.REST)
        assert "state" not in act.metadata
        assert act.activity_type == ActivityType.REST

    def test_realize_walk_fallback_to_idle(
        self, character: Character, performer: CharacterActivityPerformer
    ) -> None:
        """Verify WALK safely falls back to CharacterState.IDLE without fake movement."""
        character.set_state(CharacterState.SIT)
        act = Activity(ActivityType.WALK)
        performer.perform_activity(act)

        assert character.state == CharacterState.IDLE
        assert character.current_animation_name == "idle"

    def test_realize_look_around(
        self, character: Character, performer: CharacterActivityPerformer
    ) -> None:
        act = Activity(ActivityType.LOOK_AROUND)
        performer.perform_activity(act)

        assert character.current_animation_name == "look_around"
        assert character.state == CharacterState.IDLE

    def test_realize_look_around_resets_non_idle_posture(
        self, character: Character, performer: CharacterActivityPerformer
    ) -> None:
        character.set_state(CharacterState.SIT)
        assert character.state == CharacterState.SIT

        act = Activity(ActivityType.LOOK_AROUND)
        performer.perform_activity(act)

        assert character.state == CharacterState.IDLE
        assert character.current_animation_name == "look_around"

    def test_realize_stretch(
        self, character: Character, performer: CharacterActivityPerformer
    ) -> None:
        act = Activity(ActivityType.STRETCH)
        performer.perform_activity(act)

        assert character.state == CharacterState.STRETCH
        assert character.current_animation_name == "stretch"

    def test_realize_sleep(
        self, character: Character, performer: CharacterActivityPerformer
    ) -> None:
        act = Activity(ActivityType.SLEEP)
        performer.perform_activity(act)

        assert character.state == CharacterState.SLEEP
        assert character.current_animation_name == "sleep"

    def test_realize_play_maps_to_playful_animation(
        self, character: Character, performer: CharacterActivityPerformer
    ) -> None:
        act = Activity(ActivityType.PLAY)
        performer.perform_activity(act)

        assert character.current_animation_name == "playful"
        assert character.state == CharacterState.IDLE

    def test_realize_play_resets_non_idle_posture(
        self, character: Character, performer: CharacterActivityPerformer
    ) -> None:
        character.set_state(CharacterState.SLEEP)
        assert character.state == CharacterState.SLEEP

        act = Activity(ActivityType.PLAY)
        performer.perform_activity(act)

        assert character.state == CharacterState.IDLE
        assert character.current_animation_name == "playful"


# ======================================================================
# C. Physical Recovery (Interruption & Cancellation)
# ======================================================================


class TestPhysicalRecovery:
    """Verify interrupt_activity and cancel_activity return character to CharacterState.IDLE."""

    def test_interrupt_from_stretch_returns_to_idle(
        self, character: Character, performer: CharacterActivityPerformer
    ) -> None:
        act = Activity(ActivityType.STRETCH)
        performer.perform_activity(act)
        assert character.state == CharacterState.STRETCH

        performer.interrupt_activity(act)
        assert character.state == CharacterState.IDLE
        assert character.current_animation_name == "idle"

    def test_interrupt_from_sleep_returns_to_idle(
        self, character: Character, performer: CharacterActivityPerformer
    ) -> None:
        act = Activity(ActivityType.SLEEP)
        performer.perform_activity(act)
        assert character.state == CharacterState.SLEEP

        performer.interrupt_activity(act)
        assert character.state == CharacterState.IDLE
        assert character.current_animation_name == "idle"

    def test_interrupt_from_look_around_returns_to_idle(
        self, character: Character, performer: CharacterActivityPerformer
    ) -> None:
        act = Activity(ActivityType.LOOK_AROUND)
        performer.perform_activity(act)
        assert character.current_animation_name == "look_around"

        performer.interrupt_activity(act)
        assert character.state == CharacterState.IDLE
        assert character.current_animation_name == "idle"

    def test_cancel_from_stretch_stops_animation_and_returns_to_idle(
        self, character: Character, performer: CharacterActivityPerformer
    ) -> None:
        act = Activity(ActivityType.STRETCH)
        performer.perform_activity(act)
        assert character.state == CharacterState.STRETCH

        performer.cancel_activity(act)
        assert character.state == CharacterState.IDLE
        assert character.current_animation_name == "idle"

    def test_cancel_from_sleep_stops_animation_and_returns_to_idle(
        self, character: Character, performer: CharacterActivityPerformer
    ) -> None:
        act = Activity(ActivityType.SLEEP)
        performer.perform_activity(act)
        assert character.state == CharacterState.SLEEP

        performer.cancel_activity(act)
        assert character.state == CharacterState.IDLE
        assert character.current_animation_name == "idle"


# ======================================================================
# D. Architectural Separation
# ======================================================================


class TestArchitecturalSeparation:
    """Verify clean boundaries between Activity, Executor, Performer, and Character."""

    def test_performer_has_no_executor_reference(
        self, performer: CharacterActivityPerformer
    ) -> None:
        """Performer must NOT hold or reference ActivityExecutor."""
        assert not hasattr(performer, "executor")
        assert not hasattr(performer, "_executor")
        assert not hasattr(performer, "activity_executor")

    def test_performer_module_does_not_import_activity_executor(self) -> None:
        """Verify performer.py AST does not import ActivityExecutor class."""
        file_path = inspect.getfile(performer_module)
        tree = ast.parse(Path(file_path).read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "ActivityExecutor"
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    assert alias.name != "ActivityExecutor", (
                        f"performer.py illegally imports ActivityExecutor from {node.module}"
                    )

    def test_character_state_has_exactly_five_states(self) -> None:
        """CharacterState must remain strictly 5 physical postures (not expanded with activities)."""
        expected_states = {"IDLE", "SIT", "SLEEP", "STRETCH", "ATTENTION"}
        actual_states = {state.value for state in CharacterState}
        assert actual_states == expected_states

        forbidden_states = {"WALK", "PLAY", "LOOK_AROUND", "REST"}
        for forbidden in forbidden_states:
            assert not hasattr(CharacterState, forbidden), (
                f"CharacterState illegally expanded with activity value '{forbidden}'"
            )

    def test_doodle_activity_package_has_zero_qt_imports(self) -> None:
        """Verify via AST parsing that all modules in doodle.activity have NO Qt imports."""
        activity_pkg_dir = Path(inspect.getfile(executor_module)).parent
        py_files = list(activity_pkg_dir.glob("*.py"))
        assert len(py_files) >= 3  # model.py, types.py, executor.py, __init__.py

        for py_file in py_files:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith("PySide6"), (
                            f"{py_file.name} illegally imports {alias.name}"
                        )
                        assert not alias.name.startswith("PyQt"), (
                            f"{py_file.name} illegally imports {alias.name}"
                        )
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        assert not node.module.startswith("PySide6"), (
                            f"{py_file.name} illegally imports from {node.module}"
                        )
                        assert not node.module.startswith("PyQt"), (
                            f"{py_file.name} illegally imports from {node.module}"
                        )


# ======================================================================
# E. Completion Boundary (Composition Concept)
# ======================================================================


class TestCompletionBoundary:
    """Demonstrate completion routing via composition boundary without reverse coupling."""

    def test_completion_routed_via_composition_boundary(
        self, character: Character, performer: CharacterActivityPerformer
    ) -> None:
        """Verify completion flows: Character -> signal -> composition boundary -> executor.complete()."""
        executor = ActivityExecutor(target=performer)

        # Performer has NO executor reference
        assert not hasattr(performer, "executor")

        # Integration boundary wiring (composition root level)
        completed_names: list[str] = []

        def on_animation_finished(animation_name: str) -> None:
            completed_names.append(animation_name)
            if executor.is_executing:
                executor.complete()

        character.animation_finished.connect(on_animation_finished)

        # Start activity on executor
        act = Activity(ActivityType.LOOK_AROUND)
        executor.start(act)

        assert executor.is_executing is True
        assert executor.current_activity is act
        assert act.lifecycle_state == ActivityLifecycleState.RUNNING
        assert character.current_animation_name == "look_around"

        # Emit animation completion from character layer
        character.animation_finished.emit("look_around")

        # Verify activity was completed by executor via composition boundary
        assert executor.is_executing is False
        assert executor.current_activity is None
        assert act.lifecycle_state == ActivityLifecycleState.COMPLETED
        assert completed_names == ["look_around"]

    def test_executor_with_performer_auto_interrupts_and_starts_new(
        self, character: Character, performer: CharacterActivityPerformer
    ) -> None:
        """Verify replacement of interruptible activity safely updates character presentation."""
        executor = ActivityExecutor(target=performer)

        act1 = Activity(ActivityType.STRETCH, interruptible=True)
        executor.start(act1)
        assert character.state == CharacterState.STRETCH

        act2 = Activity(ActivityType.SLEEP, interruptible=True)
        executor.start(act2)

        assert act1.lifecycle_state == ActivityLifecycleState.INTERRUPTED
        assert act2.lifecycle_state == ActivityLifecycleState.RUNNING
        assert executor.current_activity is act2
        assert character.state == CharacterState.SLEEP
