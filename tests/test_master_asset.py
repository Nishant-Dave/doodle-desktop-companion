"""Automated test validating canonical Doodle panda master asset properties (Milestone 2 Task 16B)."""

from __future__ import annotations

import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from doodle.character.assets import DEFAULT_ASSETS_DIR


class TestPandaMasterAsset(unittest.TestCase):
    """Tests confirming the canonical master asset adheres to visual and technical standards."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.qapp = QApplication.instance() or QApplication(["test_master_asset"])
        cls.master_path = DEFAULT_ASSETS_DIR / "panda" / "master" / "doodle_panda_master.png"

    def test_master_asset_exists(self) -> None:
        self.assertTrue(
            self.master_path.is_file(),
            f"Master asset must exist at {self.master_path}",
        )

    def test_master_asset_dimensions_and_format(self) -> None:
        img = QImage(str(self.master_path))
        self.assertFalse(img.isNull(), "Master image failed to decode")
        self.assertEqual(img.width(), 256)
        self.assertEqual(img.height(), 256)
        self.assertTrue(img.hasAlphaChannel(), "Master image must possess an alpha channel")

    def test_master_asset_anchor_and_margins(self) -> None:
        img = QImage(str(self.master_path))
        width, height = img.width(), img.height()

        min_x, max_x = width, 0
        min_y, max_y = height, 0
        non_zero_alpha = 0

        for y in range(height):
            for x in range(width):
                alpha = (img.pixel(x, y) >> 24) & 0xFF
                if alpha > 0:
                    non_zero_alpha += 1
                    if x < min_x:
                        min_x = x
                    if x > max_x:
                        max_x = x
                    if y < min_y:
                        min_y = y
                    if y > max_y:
                        max_y = y

        self.assertGreater(non_zero_alpha, 0, "Image must not be blank")

        # Unclipped safe margins
        self.assertGreaterEqual(min_x, 8)
        self.assertLessEqual(max_x, width - 8)
        self.assertGreaterEqual(min_y, 8)
        self.assertLessEqual(max_y, height - 8)

        # Centering
        center_x = (min_x + max_x) / 2.0
        self.assertAlmostEqual(center_x, 128.0, delta=4.0)

        # Seated contact anchor near Y=244
        contact_y = max_y
        self.assertAlmostEqual(contact_y, 244, delta=4)


if __name__ == "__main__":
    unittest.main()
