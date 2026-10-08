"""Integration and unit tests for Task 26 — Walk Activity Integration.

Verifies:
A. DesktopActivityPerformer creation and protocol conformance.
B. WALK activity starts movement.
C. WALK target metadata is interpreted correctly (QPoint, tuple, list, dict, invalid).
D. MovementPrimitive receives the correct starting position and target.
E. tick(dt_s) advances movement deterministically.
F. CompanionWindow receives the calculated position via move_to().
G. Arrival produces an activity_completed signal/callback.
H. Completion can be connected at a composition boundary to ActivityExecutor.complete().
I. Interruption stops movement.
J. Interruption calls MovementPrimitive.interrupt().
K. Interruption resets character presentation to IDLE.
L. Cancellation stops movement and preserves position.
M. Cancellation resets character presentation to IDLE.
N. Non-WALK activities delegate to CharacterActivityPerformer.
O. CompanionWindow.move_to() does not invoke mouse-drag handlers.
P. CompanionWindow.move_to() respects existing position clamping.
Q. Existing drag behavior remains unchanged.
"""

from __future__ import annotations

import ast
import inspect
import os
from pathlib import Path
from typing import List
from unittest.mock import MagicMock

import pytest

# Ensure Qt runs offscreen during automated test execution
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRect, QSize, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

import doodle.activity.executor as executor_module
import doodle.desktop.performer as performer_module
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
from doodle.desktop import (
    CompanionWindow,
    DesktopActivityPerformer,
    MovementDirection,
    MovementPrimitive,
    MovementStatus,
)


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    """Ensure a singleton QApplication instance exists for tests."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(["test_walk_integration"])
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


# ======================================================================
# A. DesktopActivityPerformer Creation
# ======================================================================


def test_a_performer_creation_and_protocol_conformance(
    character_performer: CharacterActivityPerformer,
    movement: MovementPrimitive,
    window: CompanionWindow,
) -> None:
    """Verify performer creation, properties, and ActivityExecutionTarget protocol conformance."""
    p = DesktopActivityPerformer(character_performer, movement, window)

    # Conforms structurally to ActivityExecutionTarget (PEP 544)
    assert isinstance(p, ActivityExecutionTarget)
    assert issubclass(DesktopActivityPerformer, ActivityExecutionTarget)
    assert DesktopActivityPerformer.__bases__ == (QObject,)
    assert type(DesktopActivityPerformer) is type(QObject)

    # Properties
    assert p.character_performer is character_performer
    assert p.movement is movement
    assert p.window is window
    assert p.active_walk_activity is None
    assert not p.is_walking

    # String representation
    rep = repr(p)
    assert "DesktopActivityPerformer" in rep
    assert "is_walking=False" in rep


def test_a_performer_creation_validates_dependencies(
    character_performer: CharacterActivityPerformer,
    movement: MovementPrimitive,
    window: CompanionWindow,
) -> None:
    """Verify performer rejects None dependencies with TypeError."""
    with pytest.raises(TypeError, match="character_performer must not be None"):
        DesktopActivityPerformer(None, movement, window)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="movement must not be None"):
        DesktopActivityPerformer(character_performer, None, window)  # type: ignore[arg-type]

    with pytest.raises(TypeError, match="window must not be None"):
        DesktopActivityPerformer(character_performer, movement, None)  # type: ignore[arg-type]


# ======================================================================
# B. WALK Activity Starts Movement
# ======================================================================


def test_b_walk_activity_starts_movement(
    performer: DesktopActivityPerformer,
    window: CompanionWindow,
) -> None:
    """Verify performing a WALK activity initiates movement state."""
    window.move(QPoint(100, 100))
    walk_act = Activity(
        activity_type=ActivityType.WALK,
        metadata={"target": QPoint(300, 100)},
    )

    performer.perform_activity(walk_act)

    assert performer.is_walking is True
    assert performer.active_walk_activity is walk_act
    assert performer.movement.is_moving is True
    assert performer.movement.status == MovementStatus.MOVING


# ======================================================================
# C. Target Metadata Interpretation
# ======================================================================


@pytest.mark.parametrize(
    ("target_input", "expected_point"),
    [
        (QPoint(250, 350), QPoint(250, 350)),
        ((250, 350), QPoint(250, 350)),
        ([250, 350], QPoint(250, 350)),
        ({"x": 250, "y": 350}, QPoint(250, 350)),
        ((250.4, 349.6), QPoint(250, 350)),
        ({"x": 250.2, "y": 349.8}, QPoint(250, 350)),
    ],
)
def test_c_target_metadata_formats(
    performer: DesktopActivityPerformer,
    window: CompanionWindow,
    target_input: object,
    expected_point: QPoint,
) -> None:
    """Verify target metadata parses QPoint, tuples, lists, and dicts correctly."""
    window.move(QPoint(50, 50))
    walk_act = Activity(
        activity_type=ActivityType.WALK,
        metadata={"target": target_input},
    )

    performer.perform_activity(walk_act)

    assert performer.movement.target_position == expected_point


def test_c_target_metadata_safe_fallback_when_missing_or_invalid(
    performer: DesktopActivityPerformer,
    window: CompanionWindow,
) -> None:
    """Verify missing, empty, or invalid target metadata falls back to current position safely."""
    window.move(QPoint(120, 140))

    # Missing metadata
    act_no_meta = Activity(activity_type=ActivityType.WALK)
    performer.perform_activity(act_no_meta)
    # Since target equals current position, it arrives immediately
    assert performer.movement.current_position == QPoint(120, 140)

    # Invalid metadata type
    window.move(QPoint(150, 160))
    act_bad_meta = Activity(
        activity_type=ActivityType.WALK,
        metadata={"target": "invalid_coordinates"},
    )
    performer.perform_activity(act_bad_meta)
    assert performer.movement.current_position == QPoint(150, 160)


# ======================================================================
# D. MovementPrimitive Receives Correct Start and Target
# ======================================================================


def test_d_movement_primitive_receives_start_and_target(
    performer: DesktopActivityPerformer,
    window: CompanionWindow,
) -> None:
    """Verify MovementPrimitive receives window position as start and metadata as target."""
    window.move(QPoint(150, 220))
    walk_act = Activity(
        activity_type=ActivityType.WALK,
        metadata={"target": QPoint(450, 620)},
    )

    performer.perform_activity(walk_act)

    assert performer.movement.start_position == QPoint(150, 220)
    assert performer.movement.target_position == QPoint(450, 620)
    assert performer.movement.current_position == QPoint(150, 220)


# ======================================================================
# E. tick(dt_s) Advances Movement
# ======================================================================


def test_e_tick_advances_movement(
    performer: DesktopActivityPerformer,
    window: CompanionWindow,
) -> None:
    """Verify tick(dt_s) advances position proportionally by dt * speed."""
    window.move(QPoint(100, 100))
    performer.movement.speed_px_per_s = 100.0  # 100 px per second

    walk_act = Activity(
        activity_type=ActivityType.WALK,
        metadata={"target": QPoint(200, 100)},  # 100 px east
    )
    performer.perform_activity(walk_act)

    # Advance 0.5 seconds -> 50 px
    pos = performer.tick(0.5)
    assert pos == QPoint(150, 100)
    assert performer.movement.current_position == QPoint(150, 100)
    assert performer.is_walking is True


def test_e_tick_when_not_walking_returns_none(
    performer: DesktopActivityPerformer,
) -> None:
    """Verify tick returns None when no walk activity is executing."""
    assert performer.tick(0.1) is None


# ======================================================================
# F. CompanionWindow Receives Calculated Position
# ======================================================================


def test_f_companion_window_receives_calculated_position(
    performer: DesktopActivityPerformer,
    window: CompanionWindow,
) -> None:
    """Verify CompanionWindow is physically repositioned on each tick."""
    window.move(QPoint(50, 50))
    performer.movement.speed_px_per_s = 200.0

    walk_act = Activity(
        activity_type=ActivityType.WALK,
        metadata={"target": QPoint(250, 50)},
    )
    performer.perform_activity(walk_act)

    performer.tick(0.5)  # 100 px step
    assert window.pos() == QPoint(150, 50)


# ======================================================================
# G. Arrival Produces Activity Completed Signal
# ======================================================================


def test_g_arrival_produces_activity_completed_signal(
    performer: DesktopActivityPerformer,
    window: CompanionWindow,
) -> None:
    """Verify arriving at target emits activity_completed signal and ends walking state."""
    window.move(QPoint(0, 0))
    performer.movement.speed_px_per_s = 100.0

    walk_act = Activity(
        activity_type=ActivityType.WALK,
        metadata={"target": QPoint(100, 0)},
    )

    completed_activities: List[Activity] = []
    performer.activity_completed.connect(completed_activities.append)

    performer.perform_activity(walk_act)
    assert len(completed_activities) == 0

    # Advance 1.0s to arrive exactly at target
    performer.tick(1.0)

    assert len(completed_activities) == 1
    assert completed_activities[0] is walk_act
    assert performer.is_walking is False
    assert performer.active_walk_activity is None
    assert performer.movement.has_reached_target is True
    assert window.pos() == QPoint(100, 0)


def test_g_immediate_arrival_when_already_at_target(
    performer: DesktopActivityPerformer,
    window: CompanionWindow,
) -> None:
    """Verify zero-distance target completes immediately without ticking."""
    window.move(QPoint(80, 80))
    walk_act = Activity(
        activity_type=ActivityType.WALK,
        metadata={"target": QPoint(80, 80)},
    )

    completed_activities: List[Activity] = []
    performer.activity_completed.connect(completed_activities.append)

    performer.perform_activity(walk_act)

    assert len(completed_activities) == 1
    assert completed_activities[0] is walk_act
    assert performer.is_walking is False


# ======================================================================
# H. Composition Boundary Connection to ActivityExecutor.complete()
# ======================================================================


def test_h_composition_boundary_completes_activity_executor(
    performer: DesktopActivityPerformer,
    window: CompanionWindow,
) -> None:
    """Verify composition wiring: performer.activity_completed -> executor.complete()."""
    executor = ActivityExecutor(target=performer)
    performer.activity_completed.connect(executor.complete)

    window.move(QPoint(10, 10))
    performer.movement.speed_px_per_s = 100.0

    walk_act = Activity(
        activity_type=ActivityType.WALK,
        metadata={"target": QPoint(110, 10)},
    )

    # Start via executor
    executor.start(walk_act)
    assert executor.is_executing is True
    assert executor.current_activity is walk_act
    assert walk_act.lifecycle_state == ActivityLifecycleState.RUNNING
    assert performer.is_walking is True

    # Advance movement halfway
    performer.tick(0.5)
    assert executor.is_executing is True
    assert walk_act.lifecycle_state == ActivityLifecycleState.RUNNING

    # Advance movement to target
    performer.tick(0.5)

    # Executor transitioned to COMPLETED
    assert executor.is_executing is False
    assert executor.current_activity is None
    assert walk_act.lifecycle_state == ActivityLifecycleState.COMPLETED
    assert performer.is_walking is False


# ======================================================================
# I & J. Interruption
# ======================================================================


def test_i_j_interruption_stops_movement_and_calls_movement_interrupt(
    performer: DesktopActivityPerformer,
    window: CompanionWindow,
) -> None:
    """Verify interrupt_activity stops movement, halts primitive, and emits signal."""
    window.move(QPoint(0, 0))
    performer.movement.speed_px_per_s = 100.0

    walk_act = Activity(
        activity_type=ActivityType.WALK,
        metadata={"target": QPoint(200, 0)},
    )
    performer.perform_activity(walk_act)
    performer.tick(0.5)  # Moved to (50, 0)
    assert window.pos() == QPoint(50, 0)

    interrupted_activities: List[Activity] = []
    performer.activity_interrupted.connect(interrupted_activities.append)

    performer.interrupt_activity(walk_act)

    assert performer.is_walking is False
    assert performer.active_walk_activity is None
    assert performer.movement.is_interrupted is True
    assert performer.movement.status == MovementStatus.INTERRUPTED
    assert len(interrupted_activities) == 1
    assert interrupted_activities[0] is walk_act

    # Physical position is preserved exactly
    assert window.pos() == QPoint(50, 0)

    # Further ticks do nothing
    assert performer.tick(0.5) is None
    assert window.pos() == QPoint(50, 0)


# ======================================================================
# K. Interruption Resets Character Presentation to IDLE
# ======================================================================


def test_k_interruption_resets_character_to_idle(
    performer: DesktopActivityPerformer,
    character: Character,
    window: CompanionWindow,
) -> None:
    """Verify interruption restores character posture to CharacterState.IDLE."""
    window.move(QPoint(0, 0))
    walk_act = Activity(
        activity_type=ActivityType.WALK,
        metadata={"target": QPoint(100, 100)},
    )
    performer.perform_activity(walk_act)

    performer.interrupt_activity(walk_act)

    assert character.state == CharacterState.IDLE


# ======================================================================
# L & M. Cancellation
# ======================================================================


def test_l_m_cancellation_stops_movement_preserves_pos_resets_character(
    performer: DesktopActivityPerformer,
    character: Character,
    window: CompanionWindow,
) -> None:
    """Verify cancellation stops movement, preserves position, and resets character to IDLE."""
    window.move(QPoint(0, 0))
    performer.movement.speed_px_per_s = 100.0

    walk_act = Activity(
        activity_type=ActivityType.WALK,
        metadata={"target": QPoint(200, 200)},
    )
    performer.perform_activity(walk_act)
    performer.tick(0.5)
    current_pos_mid = window.pos()

    cancelled_activities: List[Activity] = []
    performer.activity_cancelled.connect(cancelled_activities.append)

    performer.cancel_activity(walk_act)

    assert performer.is_walking is False
    assert performer.active_walk_activity is None
    assert performer.movement.is_moving is False
    assert character.state == CharacterState.IDLE
    assert window.pos() == current_pos_mid
    assert len(cancelled_activities) == 1
    assert cancelled_activities[0] is walk_act


# ======================================================================
# N. Non-WALK Activities Delegation
# ======================================================================


@pytest.mark.parametrize(
    ("activity_type", "expected_state"),
    [
        (ActivityType.REST, CharacterState.SIT),
        (ActivityType.SLEEP, CharacterState.SLEEP),
        (ActivityType.STRETCH, CharacterState.STRETCH),
        (ActivityType.LOOK_AROUND, CharacterState.IDLE),
        (ActivityType.PLAY, CharacterState.IDLE),
    ],
)
def test_n_non_walk_activities_delegate_to_character_performer(
    performer: DesktopActivityPerformer,
    character: Character,
    window: CompanionWindow,
    activity_type: ActivityType,
    expected_state: CharacterState,
) -> None:
    """Verify non-WALK activities delegate strictly to CharacterActivityPerformer."""
    window.move(QPoint(100, 100))
    act = Activity(activity_type=activity_type)

    performer.perform_activity(act)

    # Character presentation updated
    assert character.state == expected_state
    # Window movement untouched
    assert performer.is_walking is False
    assert performer.active_walk_activity is None
    assert performer.movement.is_moving is False
    assert window.pos() == QPoint(100, 100)


def test_n_non_walk_interruption_and_cancellation(
    performer: DesktopActivityPerformer,
    character: Character,
) -> None:
    """Verify non-WALK interrupt and cancel delegate to CharacterActivityPerformer."""
    rest_act = Activity(activity_type=ActivityType.REST)
    performer.perform_activity(rest_act)
    assert character.state == CharacterState.SIT

    performer.interrupt_activity(rest_act)
    assert character.state == CharacterState.IDLE

    sleep_act = Activity(activity_type=ActivityType.SLEEP)
    performer.perform_activity(sleep_act)
    assert character.state == CharacterState.SLEEP

    performer.cancel_activity(sleep_act)
    assert character.state == CharacterState.IDLE


# ======================================================================
# O. CompanionWindow.move_to() Does Not Invoke Drag Handlers
# ======================================================================


def test_o_move_to_does_not_invoke_mouse_drag_handlers(
    window: CompanionWindow,
) -> None:
    """Verify move_to() repositions window without triggering dragging handlers or state."""
    drag_started = MagicMock()
    drag_released = MagicMock()
    dragging = MagicMock()
    character_moved = MagicMock()

    window.drag_started.connect(drag_started)
    window.drag_released.connect(drag_released)
    window.dragging.connect(dragging)
    window.character_moved.connect(character_moved)

    window.move(QPoint(50, 50))
    assert window.is_dragging is False
    assert window.drag_occurred is False

    # Call move_to
    target = QPoint(120, 150)
    window.move_to(target)

    # Window moved and character_moved emitted
    assert window.pos() == target
    character_moved.assert_called_once_with(target)

    # Zero drag events or states triggered
    assert window.is_dragging is False
    assert window.drag_occurred is False
    drag_started.assert_not_called()
    drag_released.assert_not_called()
    dragging.assert_not_called()


# ======================================================================
# P. CompanionWindow.move_to() Respects Position Clamping
# ======================================================================


def test_p_move_to_respects_position_clamping(
    window: CompanionWindow,
) -> None:
    """Verify move_to() clamps coordinates to usable desktop screen bounds."""
    bounds = window._position_manager.get_usable_bounds()
    win_size = window.size()

    # Beyond top-left
    window.move_to(QPoint(-5000, -5000))
    assert window.pos().x() >= bounds.x()
    assert window.pos().y() >= bounds.y()

    # Beyond bottom-right
    window.move_to(QPoint(50000, 50000))
    max_x = bounds.x() + bounds.width() - win_size.width()
    max_y = bounds.y() + bounds.height() - win_size.height()
    assert window.pos().x() <= max_x
    assert window.pos().y() <= max_y


# ======================================================================
# Q. Existing Drag Behavior Remains Unchanged
# ======================================================================


def test_q_existing_mouse_dragging_remains_operational(
    window: CompanionWindow,
) -> None:
    """Verify mouse-drag interaction remains completely operational and independent."""
    drag_started = MagicMock()
    drag_released = MagicMock()
    character_clicked = MagicMock()

    window.drag_started.connect(drag_started)
    window.drag_released.connect(drag_released)
    window.character_clicked.connect(character_clicked)

    window.move(QPoint(100, 100))

    # Mouse press
    press_event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(30, 30),
        QPointF(130, 130),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.mousePressEvent(press_event)
    assert window.is_dragging is True
    assert window.drag_occurred is False

    # Mouse move exceeding threshold
    move_event = QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(60, 60),
        QPointF(160, 160),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.mouseMoveEvent(move_event)
    assert window.drag_occurred is True
    drag_started.assert_called_once()

    # Mouse release concludes drag
    release_event = QMouseEvent(
        QEvent.Type.MouseButtonRelease,
        QPointF(60, 60),
        QPointF(160, 160),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.mouseReleaseEvent(release_event)
    assert window.is_dragging is False
    drag_released.assert_called_once()
    character_clicked.assert_not_called()


# ======================================================================
# Architectural Boundaries Verification
# ======================================================================


def test_architectural_boundaries() -> None:
    """Verify strict architectural boundaries and module separation."""
    # 1. Performer must not import ActivityExecutor
    performer_source = inspect.getsource(performer_module)
    parsed = ast.parse(performer_source)
    for node in ast.walk(parsed):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert "ActivityExecutor" not in alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.module and "executor" in node.module:
                for alias in node.names:
                    assert alias.name != "ActivityExecutor"

    # 2. Activity package must not import DesktopActivityPerformer or PySide6
    activity_dir = Path(executor_module.__file__).parent
    for py_file in activity_dir.glob("*.py"):
        file_ast = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(file_ast):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "DesktopActivityPerformer" not in alias.name
                    assert "PySide6" not in alias.name
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "DesktopActivityPerformer" not in node.module
                    assert "PySide6" not in node.module
                for alias in node.names:
                    assert "DesktopActivityPerformer" not in alias.name
                    assert "PySide6" not in alias.name

    # 3. CharacterState must have exactly 5 posture states
    assert len(CharacterState) == 5
    assert not hasattr(CharacterState, "WALK")
    assert not hasattr(CharacterState, "MOVING")
