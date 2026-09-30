"""Automated unit tests for screen positioning and boundary clamping."""

import unittest

from PySide6.QtCore import QPoint, QRect, QSize

from doodle.desktop.positioning import (
    DEFAULT_SCREEN_MARGIN,
    PositionManager,
    calculate_default_position,
    clamp_to_bounds,
)


class TestPositioning(unittest.TestCase):
    """Unit tests for desktop screen boundary clamping and PositionManager."""

    def setUp(self) -> None:
        # Standard synthetic screen geometry (1920x1080 with 0,0 origin)
        self.bounds = QRect(0, 0, 1920, 1080)
        self.window_size = QSize(160, 160)
        self.positioner = PositionManager(
            window_size=self.window_size,
            screen_bounds_provider=lambda: self.bounds,
        )

    def test_valid_position(self) -> None:
        pos = self.positioner.get_position()
        self.assertIsInstance(pos, QPoint)

    def test_position_assignment(self) -> None:
        target = QPoint(500, 400)
        result = self.positioner.set_position(target)
        self.assertEqual(result, target)
        self.assertEqual(self.positioner.get_position(), target)

    def test_screen_boundary_clamping(self) -> None:
        # Point far outside bottom-right
        clamped = self.positioner.clamp_to_screen(QPoint(3000, 3000))
        expected_x = 1920 - 160  # 1760
        expected_y = 1080 - 160  # 920
        self.assertEqual(clamped, QPoint(expected_x, expected_y))

    def test_left_edge_clamping(self) -> None:
        pos = QPoint(-50, 300)
        clamped = self.positioner.clamp_to_screen(pos)
        self.assertEqual(clamped.x(), 0)
        self.assertEqual(clamped.y(), 300)

    def test_right_edge_clamping(self) -> None:
        pos = QPoint(2000, 300)
        clamped = self.positioner.clamp_to_screen(pos)
        self.assertEqual(clamped.x(), 1920 - 160)
        self.assertEqual(clamped.y(), 300)

    def test_top_edge_clamping(self) -> None:
        pos = QPoint(300, -80)
        clamped = self.positioner.clamp_to_screen(pos)
        self.assertEqual(clamped.x(), 300)
        self.assertEqual(clamped.y(), 0)

    def test_bottom_edge_clamping(self) -> None:
        pos = QPoint(300, 1200)
        clamped = self.positioner.clamp_to_screen(pos)
        self.assertEqual(clamped.x(), 300)
        self.assertEqual(clamped.y(), 1080 - 160)

    def test_positions_inside_bounds_remain_unchanged(self) -> None:
        inside = QPoint(450, 350)
        clamped = self.positioner.clamp_to_screen(inside)
        self.assertEqual(clamped, inside)

    def test_oversized_positions_safely_corrected(self) -> None:
        huge_size = QSize(2500, 1500)
        clamped = clamp_to_bounds(QPoint(500, 500), huge_size, self.bounds)
        # Should safely clamp to top-left rather than invert
        self.assertEqual(clamped, QPoint(0, 0))

    def test_invalid_geometry_handling(self) -> None:
        invalid_bounds = QRect()
        pos = QPoint(150, 250)
        result = clamp_to_bounds(pos, self.window_size, invalid_bounds)
        # Should return position safely without error
        self.assertEqual(result, pos)

    def test_calculate_default_position(self) -> None:
        default_pos = calculate_default_position(
            window_size=self.window_size,
            bounds=self.bounds,
            margin=DEFAULT_SCREEN_MARGIN,
        )
        expected_x = 1920 - 160 - DEFAULT_SCREEN_MARGIN
        expected_y = 1080 - 160 - DEFAULT_SCREEN_MARGIN
        self.assertEqual(default_pos, QPoint(expected_x, expected_y))


if __name__ == "__main__":
    unittest.main()
