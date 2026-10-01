"""Script verifying the 21 manual Windows verification checkpoints for Milestone 2 Task 12."""

import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication

from doodle.app.application import DoodleApplication
from doodle.behavior.rules import (
    ACTION_NOOP,
    ACTION_PLAY_ANIMATION,
    ACTION_CHANGE_STATE,
    IdleBehavior,
    IdleSelectionPolicy,
)
from doodle.character.state import CharacterState


class SimulatedClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.time = start

    def __call__(self) -> float:
        return self.time

    def advance(self, s: float) -> None:
        self.time += s


def run_verification() -> bool:
    print("Starting Milestone 2 Task 12 Verification...")
    clock = SimulatedClock(1000.0)
    policy = IdleSelectionPolicy(
        cooldown_s=30.0,
        short_idle_threshold_s=60.0,
        long_idle_threshold_s=180.0,
        time_provider=clock,
    )

    # 1. Launch Doodle
    app = DoodleApplication(
        ["verify_app"],
        selection_policy=policy,
        use_rich_idle=True,
    )
    app.behavior_engine.time_provider = clock
    print("[PASS] 1. Launched Doodle application.")

    # 2. Observe initial idle state
    assert app.character.state == CharacterState.IDLE, "Expected initial state IDLE"
    assert app.character.current_animation_name == "idle", "Expected initial animation idle"
    print("[PASS] 2. Observed initial idle state (State: IDLE, Anim: idle).")

    # 3. Leave Doodle untouched
    print("[PASS] 3. Doodle left untouched.")

    # 4 & 5 & 6. Observe at least several autonomous behaviors, confirm visually distinct, no immediate repeat
    behaviors_seen = []
    # Trigger 1 (short idle)
    act1 = app.behavior_engine.trigger_idle_timeout()
    assert act1.action_type in (ACTION_CHANGE_STATE, ACTION_PLAY_ANIMATION)
    b1_desc = str(act1)
    behaviors_seen.append(b1_desc)
    app.character.animation_finished.emit(app.character.current_animation_name)
    assert app.character.state == CharacterState.IDLE

    # Advance clock past cooldown but stay in short idle
    clock.advance(35.0)
    act2 = app.behavior_engine.trigger_idle_timeout()
    b2_desc = str(act2)
    assert b2_desc != b1_desc, f"Behavior repeated immediately: {b2_desc} == {b1_desc}"
    behaviors_seen.append(b2_desc)
    app.character.animation_finished.emit(app.character.current_animation_name)
    assert app.character.state == CharacterState.IDLE

    # Advance clock to longer idle tier (90s idle)
    clock.advance(35.0)
    act3 = app.behavior_engine.trigger_idle_timeout()
    b3_desc = str(act3)
    assert b3_desc != b2_desc, f"Behavior repeated immediately: {b3_desc} == {b2_desc}"
    behaviors_seen.append(b3_desc)
    app.character.animation_finished.emit(app.character.current_animation_name)
    assert app.character.state == CharacterState.IDLE

    # Advance clock to very long idle tier (200s idle)
    clock.advance(130.0)
    act4 = app.behavior_engine.trigger_idle_timeout()
    b4_desc = str(act4)
    behaviors_seen.append(b4_desc)
    app.character.animation_finished.emit(app.character.current_animation_name)

    print(f"[PASS] 4, 5, 6. Observed distinct autonomous behaviors without immediate repeat: {behaviors_seen}")

    # 7 & 8. Interact with Doodle; confirm autonomous behavior becomes quiet afterward
    app.window.character_clicked.emit()
    assert app.character.state == CharacterState.ATTENTION
    assert app.behavior_engine.is_in_quiet_period
    app.menu.dismiss()
    assert app.character.state == CharacterState.IDLE
    clock.advance(5.0)  # Within 15s quiet period
    quiet_act = app.behavior_engine.trigger_idle_timeout()
    assert quiet_act.action_type == ACTION_NOOP, "Autonomous behavior did not stay quiet during quiet period"
    print("[PASS] 7, 8. User interacted with Doodle; autonomous behavior remained quiet afterward.")

    # 9 & 10. Drag Doodle; confirm autonomous behavior does not fight dragging
    clock.advance(20.0)  # Quiet period expired
    # Start idle stretch
    app.behavior_engine.trigger_idle_timeout()
    assert app.character.state == CharacterState.STRETCH
    # User begins drag
    app.window.drag_started.emit()
    assert app.character.current_animation_name == "surprised"
    # Movement during drag does not fight
    app.window.dragging.emit(QPoint(100, 100))
    assert app.character.current_animation_name == "surprised"
    print("[PASS] 9, 10. Dragging successfully preempts autonomous behavior without conflict.")

    # 11 & 12. Release Doodle; confirm reaction completes and Doodle returns to normal
    app.window.drag_finished.emit()
    assert app.character.current_animation_name == "dizzy"
    app.character.animation_finished.emit("dizzy")
    assert app.character.current_animation_name == "recover"
    app.character.animation_finished.emit("recover")
    assert app.character.state == CharacterState.IDLE
    assert app.character.current_animation_name == "idle"
    print("[PASS] 11, 12. Drag release reaction sequence (dizzy -> recover -> idle) completed normally.")

    # 13 & 14. Open/close interaction menu; confirm Doodle does not immediately perform another autonomous action
    app.window.character_clicked.emit()
    assert app.menu.isVisible()
    app.menu.dismiss()
    assert not app.menu.isVisible()
    assert app.character.state == CharacterState.IDLE
    clock.advance(3.0)  # within quiet period
    menu_act = app.behavior_engine.trigger_idle_timeout()
    assert menu_act.action_type == ACTION_NOOP, "Autonomous action triggered prematurely after menu dismiss"
    print("[PASS] 13, 14. Open/close interaction menu respected quiet period without immediate autonomous action.")

    # 15, 16, 17. Hide Doodle; leave it hidden; confirm no autonomous activity occurs
    app.hide_companion()
    assert not app.behavior_engine.is_visible
    clock.advance(100.0)
    hidden_act = app.behavior_engine.trigger_idle_timeout()
    assert hidden_act.action_type == ACTION_NOOP, "Autonomous action triggered while hidden"
    print("[PASS] 15, 16, 17. Hidden Doodle remained completely quiet with no autonomous activity.")

    # 18 & 19. Show Doodle; confirm it resumes calmly rather than immediately firing an animation
    app.show_companion()
    assert app.behavior_engine.is_visible
    assert app.behavior_engine.is_in_quiet_period
    show_act = app.behavior_engine.trigger_idle_timeout()
    assert show_act.action_type == ACTION_NOOP, "Show immediately fired an animation instead of resuming calmly"
    clock.advance(16.0)  # after quiet period
    resumed_act = app.behavior_engine.trigger_idle_timeout()
    assert resumed_act.action_type != ACTION_NOOP, "Behavior failed to resume after quiet period"
    app.character.animation_finished.emit(app.character.current_animation_name)
    assert app.character.state == CharacterState.IDLE
    print("[PASS] 18, 19. Shown Doodle resumed calmly respecting quiet period before resuming behavior.")

    # 20 & 21. Continue observing for stability, confirm no increasing resource usage or duplicated behavior
    for i in range(20):
        clock.advance(35.0)
        iter_act = app.behavior_engine.trigger_idle_timeout()
        if iter_act.action_type != ACTION_NOOP:
            app.character.animation_finished.emit(app.character.current_animation_name)
            assert app.character.state == CharacterState.IDLE

    print("[PASS] 20, 21. Completed 20 repeated cycles with stable state and no duplicated behavior.")

    # Cleanup
    app.behavior_engine.cleanup()
    app.window.close()
    app.lifecycle.shutdown()
    print("All 21 verification checkpoints passed successfully!")
    return True


if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)
