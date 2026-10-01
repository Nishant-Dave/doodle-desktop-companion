"""Automated tests for Milestone 2 Task 13: Cursor Proximity Awareness.

Verifies:
1. Proximity Geometry:
   - Inside, boundary, outside calculations
   - Different window positions, dimensions, and multi-monitor coordinates
2. Transition Detection:
   - Edge-triggered: outside -> inside emits exactly 1 event
   - inside -> inside emits no repeated events
   - inside -> outside resets state
   - outside -> inside again produces new event
3. Cooldown:
   - Proximity triggers reaction when eligible
   - Repeated proximity entries during cooldown produce NOOP
   - Proximity reaction becomes eligible again after cooldown expires
4. Hidden State:
   - Hidden window suppresses proximity processing and reactions
   - Showing window while cursor is already nearby does NOT immediately trigger reaction
   - Moving cursor outside and re-entering triggers normally
5. Interaction Priority:
   - Proximity does not interrupt dragging
   - Proximity does not override click / ATTENTION reaction
   - Proximity does not interfere with interaction menu
   - Existing Task 11 and Task 12 behaviors remain authoritative
6. Behavior Engine & Application Integration:
   - Proximity event reaches Behavior Engine
   - Clean return to IDLE upon reaction animation finish
   - Companion window show/hide lifecycle stops/starts proximity monitor
   - Full application wiring and clean shutdown
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

# Ensure Qt runs offscreen during automated test execution
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect, QSettings
from PySide6.QtWidgets import QApplication

from doodle.app.application import DoodleApplication
from doodle.behavior.engine import BehaviorEngine
from doodle.behavior.rules import (
    ACTION_CHANGE_STATE,
    ACTION_NOOP,
    ACTION_PLAY_ANIMATION,
    DEFAULT_PROXIMITY_COOLDOWN_S,
    EVENT_ANIMATION_FINISHED,
    EVENT_CHARACTER_CLICKED,
    EVENT_CURSOR_ENTERED_PROXIMITY,
    EVENT_DRAG_RELEASED,
    EVENT_DRAG_STARTED,
    EVENT_MENU_DISMISSED,
    EVENT_MENU_OPENED,
    BehaviorAction,
    BehaviorContext,
    IdleBehaviorRules,
)
from doodle.character.character import Character
from doodle.character.state import CharacterState
from doodle.desktop.companion_window import CompanionWindow
from doodle.desktop.proximity import (
    DEFAULT_PROXIMITY_MARGIN,
    CursorProximityMonitor,
    CursorProximityTracker,
    compute_proximity_zone,
    is_point_in_proximity,
)
from doodle.persistence.settings import SettingsManager


class TestProximityGeometry(unittest.TestCase):
    """Unit tests for proximity bounding box calculations and coordinate checks."""

    def test_compute_proximity_zone_margins(self) -> None:
        target = QRect(100, 100, 200, 150)
        zone = compute_proximity_zone(target, margin=50)
        self.assertEqual(zone.left(), 50)
        self.assertEqual(zone.top(), 50)
        self.assertEqual(zone.right(), 349)
        self.assertEqual(zone.bottom(), 299)
        self.assertEqual(zone.width(), 300)
        self.assertEqual(zone.height(), 250)

    def test_compute_proximity_zone_zero_margin(self) -> None:
        target = QRect(200, 300, 160, 160)
        zone = compute_proximity_zone(target, margin=0)
        self.assertEqual(zone, target)

    def test_compute_proximity_zone_negative_margin_clamped(self) -> None:
        target = QRect(100, 100, 160, 160)
        zone = compute_proximity_zone(target, margin=-20)
        self.assertEqual(zone, target)

    def test_is_point_in_proximity_outside(self) -> None:
        target = QRect(200, 200, 100, 100)
        # Margin = 50 -> proximity zone: [150, 150] to [349, 349]
        self.assertFalse(is_point_in_proximity(QPoint(100, 100), target, margin=50))
        self.assertFalse(is_point_in_proximity(QPoint(400, 250), target, margin=50))
        self.assertFalse(is_point_in_proximity(QPoint(250, 400), target, margin=50))
        self.assertFalse(is_point_in_proximity(QPoint(149, 250), target, margin=50))

    def test_is_point_in_proximity_inside(self) -> None:
        target = QRect(200, 200, 100, 100)
        # Directly inside window
        self.assertTrue(is_point_in_proximity(QPoint(250, 250), target, margin=50))
        # Inside proximity zone margin but outside window
        self.assertTrue(is_point_in_proximity(QPoint(160, 250), target, margin=50))
        self.assertTrue(is_point_in_proximity(QPoint(320, 250), target, margin=50))

    def test_is_point_in_proximity_boundary(self) -> None:
        target = QRect(100, 100, 100, 100)
        # Margin = 50 -> adjusted zone: x in [50, 249], y in [50, 249]
        zone = compute_proximity_zone(target, margin=50)

        # Points exactly on the bounding edges are considered inside
        self.assertTrue(is_point_in_proximity(QPoint(zone.left(), zone.top()), target, margin=50))
        self.assertTrue(is_point_in_proximity(QPoint(zone.right(), zone.bottom()), target, margin=50))

        # 1 pixel beyond the boundary is outside
        self.assertFalse(is_point_in_proximity(QPoint(zone.left() - 1, zone.top()), target, margin=50))
        self.assertFalse(is_point_in_proximity(QPoint(zone.right() + 1, zone.bottom()), target, margin=50))
        self.assertFalse(is_point_in_proximity(QPoint(zone.left(), zone.top() - 1), target, margin=50))
        self.assertFalse(is_point_in_proximity(QPoint(zone.left(), zone.bottom() + 1), target, margin=50))

    def test_geometry_different_positions_and_sizes(self) -> None:
        # Origin position
        rect1 = QRect(0, 0, 160, 160)
        self.assertTrue(is_point_in_proximity(QPoint(0, 0), rect1, margin=30))
        self.assertTrue(is_point_in_proximity(QPoint(-20, -20), rect1, margin=30))
        self.assertFalse(is_point_in_proximity(QPoint(-40, 0), rect1, margin=30))

        # Arbitrary screen position and size
        rect2 = QRect(800, 600, 240, 180)
        self.assertTrue(is_point_in_proximity(QPoint(850, 650), rect2, margin=50))
        self.assertTrue(is_point_in_proximity(QPoint(760, 600), rect2, margin=50))
        self.assertFalse(is_point_in_proximity(QPoint(740, 600), rect2, margin=50))

    def test_multi_monitor_negative_and_large_coordinates(self) -> None:
        # Multi-monitor setup where secondary monitor has negative X coordinates
        rect_left_monitor = QRect(-1920, 100, 160, 160)
        self.assertTrue(is_point_in_proximity(QPoint(-1900, 150), rect_left_monitor, margin=50))
        self.assertTrue(is_point_in_proximity(QPoint(-1950, 150), rect_left_monitor, margin=50))
        self.assertFalse(is_point_in_proximity(QPoint(-2000, 150), rect_left_monitor, margin=50))

        # Secondary monitor at high positive coordinates (e.g. 4K setup)
        rect_4k = QRect(3840, 1000, 160, 160)
        self.assertTrue(is_point_in_proximity(QPoint(3840, 1000), rect_4k, margin=50))
        self.assertFalse(is_point_in_proximity(QPoint(3700, 1000), rect_4k, margin=50))


class TestCursorProximityTracker(unittest.TestCase):
    """Unit tests for edge-triggered transition tracking logic."""

    def setUp(self) -> None:
        self.tracker = CursorProximityTracker(margin=50)
        self.target = QRect(200, 200, 100, 100)

    def test_outside_to_inside_generates_one_entry_event(self) -> None:
        # Start outside
        self.assertFalse(self.tracker.update(QPoint(50, 50), self.target))
        self.assertFalse(self.tracker.is_inside)

        # Move inside proximity
        self.assertTrue(self.tracker.update(QPoint(220, 220), self.target))
        self.assertTrue(self.tracker.is_inside)

    def test_inside_to_inside_generates_no_repeated_events(self) -> None:
        # Enter proximity
        self.assertTrue(self.tracker.update(QPoint(220, 220), self.target))

        # Continue moving within proximity zone: no repeat events
        self.assertFalse(self.tracker.update(QPoint(230, 230), self.target))
        self.assertFalse(self.tracker.update(QPoint(180, 220), self.target))
        self.assertFalse(self.tracker.update(QPoint(210, 210), self.target))
        self.assertTrue(self.tracker.is_inside)

    def test_inside_to_outside_resets_state_without_event(self) -> None:
        # Enter proximity
        self.assertTrue(self.tracker.update(QPoint(220, 220), self.target))

        # Move outside: no entry event, but state resets
        self.assertFalse(self.tracker.update(QPoint(500, 500), self.target))
        self.assertFalse(self.tracker.is_inside)

    def test_outside_to_inside_again_generates_new_entry_event(self) -> None:
        # 1. Enter
        self.assertTrue(self.tracker.update(QPoint(220, 220), self.target))
        # 2. Stay inside
        self.assertFalse(self.tracker.update(QPoint(230, 230), self.target))
        # 3. Leave
        self.assertFalse(self.tracker.update(QPoint(500, 500), self.target))
        # 4. Re-enter: must produce new entry event
        self.assertTrue(self.tracker.update(QPoint(220, 220), self.target))
        self.assertTrue(self.tracker.is_inside)

    def test_reset_priming_behavior(self) -> None:
        # Reset with initial_inside=True primes tracker so first inside position is not an event
        self.tracker.reset(initial_inside=True)
        self.assertTrue(self.tracker.is_inside)
        self.assertFalse(self.tracker.update(QPoint(220, 220), self.target))

        # Reset with initial_inside=False allows immediate entry event
        self.tracker.reset(initial_inside=False)
        self.assertFalse(self.tracker.is_inside)
        self.assertTrue(self.tracker.update(QPoint(220, 220), self.target))


class TestCursorProximityMonitor(unittest.TestCase):
    """Unit tests for Qt-timer driven CursorProximityMonitor."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_proximity"])

    def setUp(self) -> None:
        self.window = CompanionWindow()
        self.window.resize(160, 160)
        self.window.move(300, 300)
        self.window.show()

        self.current_cursor = QPoint(50, 50)
        self.monitor = CursorProximityMonitor(
            window=self.window,
            margin=50,
            interval_ms=50,
            cursor_provider=lambda: self.current_cursor,
        )

        self.emitted_count = 0
        self.monitor.proximity_entered.connect(self._on_proximity_entered)

    def tearDown(self) -> None:
        self.monitor.stop()
        if self.window.isVisible():
            self.window.close()
        self.window.deleteLater()

    def _on_proximity_entered(self) -> None:
        self.emitted_count += 1

    def test_monitor_emits_once_on_crossing_into_proximity(self) -> None:
        # Outside
        self.current_cursor = QPoint(50, 50)
        self.assertFalse(self.monitor.check_proximity())
        self.assertEqual(self.emitted_count, 0)

        # Cross into proximity
        self.current_cursor = QPoint(320, 320)
        self.assertTrue(self.monitor.check_proximity())
        self.assertEqual(self.emitted_count, 1)

        # Move inside proximity: no repeated emission
        self.current_cursor = QPoint(330, 330)
        self.assertFalse(self.monitor.check_proximity())
        self.assertEqual(self.emitted_count, 1)

    def test_monitor_suppressed_when_disabled(self) -> None:
        self.monitor.is_enabled = False
        self.current_cursor = QPoint(320, 320)
        self.assertFalse(self.monitor.check_proximity())
        self.assertEqual(self.emitted_count, 0)

    def test_monitor_suppressed_when_window_hidden(self) -> None:
        self.window.hide()
        self.current_cursor = QPoint(320, 320)
        self.assertFalse(self.monitor.check_proximity())
        self.assertEqual(self.emitted_count, 0)

    def test_monitor_suppressed_during_active_drag(self) -> None:
        # Simulate active dragging
        self.window._is_dragging = True
        self.current_cursor = QPoint(320, 320)
        self.assertFalse(self.monitor.check_proximity())
        self.assertEqual(self.emitted_count, 0)
        self.window._is_dragging = False

    def test_start_primes_existing_nearby_cursor_without_reaction(self) -> None:
        # Cursor is ALREADY inside proximity when monitor is started
        self.current_cursor = QPoint(320, 320)
        self.monitor.start()

        # Check proximity must NOT emit immediately
        self.assertFalse(self.monitor.check_proximity())
        self.assertEqual(self.emitted_count, 0)

        # Moving outside resets state
        self.current_cursor = QPoint(50, 50)
        self.assertFalse(self.monitor.check_proximity())
        self.assertEqual(self.emitted_count, 0)

        # Now entering proximity from outside triggers reaction
        self.current_cursor = QPoint(320, 320)
        self.assertTrue(self.monitor.check_proximity())
        self.assertEqual(self.emitted_count, 1)


class TestProximityBehaviorRules(unittest.TestCase):
    """Unit tests for IdleBehaviorRules handling of EVENT_CURSOR_ENTERED_PROXIMITY."""

    def setUp(self) -> None:
        self.current_time = 100.0
        self.rules = IdleBehaviorRules(
            proximity_cooldown_s=30.0,
            time_provider=lambda: self.current_time,
        )

    def test_proximity_when_eligible_plays_curious_animation(self) -> None:
        ctx = BehaviorContext(
            current_state=CharacterState.IDLE,
            is_visible=True,
            is_dragging=False,
            is_menu_open=False,
            current_animation=None,
            current_time_s=100.0,
        )
        action = self.rules.evaluate(EVENT_CURSOR_ENTERED_PROXIMITY, ctx)
        self.assertEqual(action.action_type, ACTION_PLAY_ANIMATION)
        self.assertEqual(action.animation_name, "curious")
        self.assertFalse(action.loop)
        self.assertEqual(self.rules.last_proximity_time, 100.0)

    def test_proximity_cooldown_suppresses_repeated_events(self) -> None:
        # First trigger at t=100.0
        ctx1 = BehaviorContext(
            current_state=CharacterState.IDLE,
            is_visible=True,
            current_time_s=100.0,
        )
        action1 = self.rules.evaluate(EVENT_CURSOR_ENTERED_PROXIMITY, ctx1)
        self.assertEqual(action1.action_type, ACTION_PLAY_ANIMATION)

        # Second trigger 10 seconds later (cooldown is 30s) -> must be NOOP
        ctx2 = BehaviorContext(
            current_state=CharacterState.IDLE,
            is_visible=True,
            current_time_s=110.0,
        )
        action2 = self.rules.evaluate(EVENT_CURSOR_ENTERED_PROXIMITY, ctx2)
        self.assertEqual(action2.action_type, ACTION_NOOP)

        # Third trigger 29 seconds later -> still on cooldown -> NOOP
        ctx3 = BehaviorContext(
            current_state=CharacterState.IDLE,
            is_visible=True,
            current_time_s=129.9,
        )
        action3 = self.rules.evaluate(EVENT_CURSOR_ENTERED_PROXIMITY, ctx3)
        self.assertEqual(action3.action_type, ACTION_NOOP)

        # Fourth trigger 31 seconds later (cooldown expired) -> triggers reaction!
        ctx4 = BehaviorContext(
            current_state=CharacterState.IDLE,
            is_visible=True,
            current_time_s=131.0,
        )
        action4 = self.rules.evaluate(EVENT_CURSOR_ENTERED_PROXIMITY, ctx4)
        self.assertEqual(action4.action_type, ACTION_PLAY_ANIMATION)
        self.assertEqual(action4.animation_name, "curious")
        self.assertEqual(self.rules.last_proximity_time, 131.0)

    def test_proximity_cooldown_reset(self) -> None:
        ctx1 = BehaviorContext(current_state=CharacterState.IDLE, is_visible=True, current_time_s=100.0)
        self.rules.evaluate(EVENT_CURSOR_ENTERED_PROXIMITY, ctx1)
        self.assertTrue(self.rules.is_proximity_on_cooldown(110.0))

        # Explicit reset
        self.rules.reset_proximity_cooldown()
        self.assertFalse(self.rules.is_proximity_on_cooldown(110.0))

        action = self.rules.evaluate(EVENT_CURSOR_ENTERED_PROXIMITY, ctx1)
        self.assertEqual(action.action_type, ACTION_PLAY_ANIMATION)

    def test_reset_cycle_clears_proximity_cooldown(self) -> None:
        ctx1 = BehaviorContext(current_state=CharacterState.IDLE, is_visible=True, current_time_s=100.0)
        self.rules.evaluate(EVENT_CURSOR_ENTERED_PROXIMITY, ctx1)
        self.assertTrue(self.rules.is_proximity_on_cooldown(110.0))

        self.rules.reset_cycle()
        self.assertFalse(self.rules.is_proximity_on_cooldown(110.0))

    def test_proximity_suppressed_when_character_not_idle(self) -> None:
        # In ATTENTION (e.g. clicked)
        ctx_attention = BehaviorContext(current_state=CharacterState.ATTENTION, is_visible=True)
        action = self.rules.evaluate(EVENT_CURSOR_ENTERED_PROXIMITY, ctx_attention)
        self.assertEqual(action.action_type, ACTION_NOOP)

        # In SLEEP state
        ctx_sleep = BehaviorContext(current_state=CharacterState.SLEEP, is_visible=True)
        action = self.rules.evaluate(EVENT_CURSOR_ENTERED_PROXIMITY, ctx_sleep)
        self.assertEqual(action.action_type, ACTION_NOOP)

    def test_proximity_suppressed_when_animation_playing(self) -> None:
        # Playing dizzy
        ctx_dizzy = BehaviorContext(
            current_state=CharacterState.IDLE,
            is_visible=True,
            current_animation="dizzy",
        )
        action = self.rules.evaluate(EVENT_CURSOR_ENTERED_PROXIMITY, ctx_dizzy)
        self.assertEqual(action.action_type, ACTION_NOOP)

        # Playing stretch
        ctx_stretch = BehaviorContext(
            current_state=CharacterState.IDLE,
            is_visible=True,
            current_animation="stretch",
        )
        action = self.rules.evaluate(EVENT_CURSOR_ENTERED_PROXIMITY, ctx_stretch)
        self.assertEqual(action.action_type, ACTION_NOOP)

    def test_proximity_suppressed_when_dragging(self) -> None:
        ctx_drag = BehaviorContext(
            current_state=CharacterState.IDLE,
            is_visible=True,
            is_dragging=True,
        )
        action = self.rules.evaluate(EVENT_CURSOR_ENTERED_PROXIMITY, ctx_drag)
        self.assertEqual(action.action_type, ACTION_NOOP)

    def test_proximity_suppressed_when_menu_open(self) -> None:
        ctx_menu = BehaviorContext(
            current_state=CharacterState.IDLE,
            is_visible=True,
            is_menu_open=True,
        )
        action = self.rules.evaluate(EVENT_CURSOR_ENTERED_PROXIMITY, ctx_menu)
        self.assertEqual(action.action_type, ACTION_NOOP)

    def test_proximity_suppressed_when_hidden(self) -> None:
        ctx_hidden = BehaviorContext(
            current_state=CharacterState.IDLE,
            is_visible=False,
        )
        action = self.rules.evaluate(EVENT_CURSOR_ENTERED_PROXIMITY, ctx_hidden)
        self.assertEqual(action.action_type, ACTION_NOOP)

    def test_curious_animation_finishes_back_to_idle(self) -> None:
        ctx = BehaviorContext(current_state=CharacterState.IDLE)
        action = self.rules.evaluate(
            EVENT_ANIMATION_FINISHED,
            ctx,
            animation_name="curious",
        )
        self.assertEqual(action.action_type, ACTION_CHANGE_STATE)
        self.assertEqual(action.state, CharacterState.IDLE)
        self.assertTrue(action.loop)


class TestBehaviorEngineProximityIntegration(unittest.TestCase):
    """Unit tests verifying BehaviorEngine slot invocation and interaction priority."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_behavior_engine"])

    def setUp(self) -> None:
        self.sim_time = 200.0
        self.character = Character()
        self.rules = IdleBehaviorRules(
            proximity_cooldown_s=30.0,
            time_provider=lambda: self.sim_time,
        )
        self.engine = BehaviorEngine(
            character=self.character,
            rules=self.rules,
            time_provider=lambda: self.sim_time,
        )

        self.executed_actions: list[BehaviorAction] = []
        self.engine.action_executed.connect(self.executed_actions.append)

    def tearDown(self) -> None:
        self.engine.cleanup()
        self.character.stop_animation()

    def test_on_cursor_entered_proximity_triggers_action(self) -> None:
        action = self.engine.on_cursor_entered_proximity()
        self.assertEqual(action.action_type, ACTION_PLAY_ANIMATION)
        self.assertEqual(action.animation_name, "curious")
        self.assertIn(action, self.executed_actions)

    def test_click_preempts_proximity(self) -> None:
        # Click transitions character to ATTENTION
        self.engine.on_character_clicked()
        self.assertEqual(self.character.state, CharacterState.ATTENTION)

        # Proximity during ATTENTION is rejected
        action = self.engine.on_cursor_entered_proximity()
        self.assertEqual(action.action_type, ACTION_NOOP)

    def test_drag_preempts_proximity(self) -> None:
        # Drag start
        self.engine.on_drag_started()
        self.assertTrue(self.engine.is_dragging)

        # Proximity during dragging is rejected
        action = self.engine.on_cursor_entered_proximity()
        self.assertEqual(action.action_type, ACTION_NOOP)

        # Conclude drag
        self.engine.on_drag_released()
        self.assertFalse(self.engine.is_dragging)

    def test_menu_preempts_proximity(self) -> None:
        self.engine.on_menu_opened()
        self.assertTrue(self.engine.is_menu_open)

        action = self.engine.on_cursor_entered_proximity()
        self.assertEqual(action.action_type, ACTION_NOOP)

        self.engine.on_menu_dismissed()
        self.assertFalse(self.engine.is_menu_open)


class TestDoodleApplicationProximityIntegration(unittest.TestCase):
    """Integration tests verifying full app wiring of cursor proximity awareness."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_doodle_app"])

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.settings_path = Path(self.temp_dir.name) / "test_settings.ini"
        self.settings = QSettings(str(self.settings_path), QSettings.Format.IniFormat)
        self.settings_manager = SettingsManager(settings=self.settings)

        self.sim_time = 500.0
        self.app = DoodleApplication(
            settings_manager=self.settings_manager,
            use_rich_idle=True,
        )
        self.app.behavior_engine.time_provider = lambda: self.sim_time
        self.app.behavior_engine.rules._time_provider = lambda: self.sim_time

    def tearDown(self) -> None:
        self.app.quit()
        self.temp_dir.cleanup()

    def test_cursor_entered_proximity_signal_wired_to_engine(self) -> None:
        received_actions: list[BehaviorAction] = []
        self.app.behavior_engine.action_executed.connect(received_actions.append)

        # Emit the window's cursor_entered_proximity signal
        self.app.companion_window.cursor_entered_proximity.emit()

        self.assertEqual(len(received_actions), 1)
        action = received_actions[0]
        self.assertEqual(action.action_type, ACTION_PLAY_ANIMATION)
        self.assertEqual(action.animation_name, "curious")

    def test_companion_window_show_and_hide_controls_proximity_monitor(self) -> None:
        window = self.app.companion_window
        monitor = window.proximity_monitor

        # Show companion
        self.app.show_companion()
        self.assertTrue(window.isVisible())
        self.assertTrue(monitor.is_active)

        # Hide companion
        self.app.hide_companion()
        self.assertFalse(window.isVisible())
        self.assertFalse(monitor.is_active)

    def test_show_when_cursor_already_nearby_does_not_trigger_immediately(self) -> None:
        window = self.app.companion_window
        window.move(400, 400)
        window.resize(160, 160)

        simulated_cursor = QPoint(420, 420)  # Inside window bounds
        window.proximity_monitor.cursor_provider = lambda: simulated_cursor

        received_actions: list[BehaviorAction] = []
        self.app.behavior_engine.action_executed.connect(received_actions.append)

        # Show companion while cursor is ALREADY nearby
        self.app.show_companion()
        self.assertTrue(window.isVisible())

        # Check proximity must NOT emit because tracker was primed on show
        entered = window.proximity_monitor.check_proximity()
        self.assertFalse(entered)
        self.assertEqual(len(received_actions), 0)

        # Move cursor far away
        simulated_cursor = QPoint(50, 50)
        entered = window.proximity_monitor.check_proximity()
        self.assertFalse(entered)
        self.assertEqual(len(received_actions), 0)

        # Move cursor back into proximity: now triggers reaction!
        simulated_cursor = QPoint(420, 420)
        entered = window.proximity_monitor.check_proximity()
        self.assertTrue(entered)
        self.assertEqual(len(received_actions), 1)
        self.assertEqual(received_actions[0].animation_name, "curious")

    def test_shutdown_stops_proximity_monitor(self) -> None:
        self.app.show_companion()
        self.assertTrue(self.app.companion_window.proximity_monitor.is_active)

        self.app.quit()
        self.assertFalse(self.app.companion_window.proximity_monitor.is_active)
