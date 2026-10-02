"""Validation script for the canonical Doodle panda master asset (Milestone 2 Task 16B).

Programmatically verifies:
1. Master asset exists at assets/panda/master/doodle_panda_master.png.
2. Dimensions are exactly 256 x 256 pixels.
3. Image format is RGBA (hasAlphaChannel is True).
4. Transparent background: outer perimeter pixels have Alpha = 0.
5. Non-zero alpha pixels exist (subject is present).
6. Character is not cropped (safe margin on left, right, top, bottom).
7. Character is horizontally centered (center of bounding box is near X = 128).
8. Bottom contact anchor is grounded near Y = 244 (+/- 4px).
9. No rectangular halos or unexpected background noise in the transparent zone.
"""

from __future__ import annotations

import os
import sys

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication


def validate_master_asset(asset_path: str = "assets/panda/master/doodle_panda_master.png") -> bool:
    app = QApplication.instance() or QApplication(["validate_master"])

    print("=" * 60)
    print("Validating Canonical Panda Master Asset")
    print(f"Target: {asset_path}")
    print("=" * 60)

    # 1. Existence
    assert os.path.isfile(asset_path), f"Master asset not found at {asset_path}"
    print(f"[PASS] 1. Master asset file exists: {asset_path}")

    img = QImage(asset_path)
    assert not img.isNull(), "Image failed to decode"

    # 2. Dimensions
    width, height = img.width(), img.height()
    assert width == 256 and height == 256, f"Expected 256x256, got {width}x{height}"
    print(f"[PASS] 2. Dimensions exactly 256x256 pixels ({width}x{height}).")

    # 3. Format / RGBA
    assert img.hasAlphaChannel(), "Image must have an alpha channel (RGBA)"
    print(f"[PASS] 3. RGBA format with alpha channel verified (Format: {img.format()}).")

    # 4 & 5. Alpha scanning and bounding box calculation
    min_x, max_x = width, 0
    min_y, max_y = height, 0
    non_zero_alpha_count = 0
    outer_opaque_noise = 0

    for y in range(height):
        for x in range(width):
            pixel = img.pixel(x, y)
            alpha = (pixel >> 24) & 0xFF
            if alpha > 0:
                non_zero_alpha_count += 1
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y
                # Check perimeter margin (outer 8px edge) for stray noise
                if x < 8 or x >= width - 8 or y < 8 or y >= height - 8:
                    outer_opaque_noise += 1

    assert non_zero_alpha_count > 0, "Image has no non-transparent pixels (blank image)"
    print(f"[PASS] 4. Non-zero alpha pixels present ({non_zero_alpha_count} pixels, {non_zero_alpha_count/(width*height)*100:.1f}% coverage).")

    # 6. Safe margins / Not cropped
    assert min_x >= 8, f"Character clipped on left (min_x={min_x})"
    assert max_x <= width - 8, f"Character clipped on right (max_x={max_x})"
    assert min_y >= 8, f"Character clipped on top (min_y={min_y})"
    assert max_y <= height - 8, f"Character clipped on bottom (max_y={max_y})"
    bbox_w = max_x - min_x + 1
    bbox_h = max_y - min_y + 1
    print(f"[PASS] 5. Character is not cropped. Bounding box: X=[{min_x}..{max_x}] (W={bbox_w}), Y=[{min_y}..{max_y}] (H={bbox_h}).")

    # 7. Horizontal Centering
    center_x = (min_x + max_x) / 2.0
    centering_offset = abs(center_x - 128.0)
    assert centering_offset <= 4.0, f"Character not horizontally centered: center_x={center_x} (offset={centering_offset}px)"
    print(f"[PASS] 6. Character is horizontally centered: center_x={center_x:.1f} (within {centering_offset:.1f}px of 128.0).")

    # 8. Bottom contact anchor
    contact_y = max_y
    anchor_offset = abs(contact_y - 244)
    assert anchor_offset <= 4, f"Contact anchor Y={contact_y} differs from canonical Y=244 by {anchor_offset}px"
    print(f"[PASS] 7. Seated contact anchor grounded at Y={contact_y} (target 244 +/- 4px).")

    # 9. Outer perimeter transparency / no halos
    assert outer_opaque_noise == 0, f"Detected {outer_opaque_noise} stray pixels in outer margin"
    print("[PASS] 8. Clean transparent background verified with zero border noise or halos.")

    print("=" * 60)
    print("ALL CANONICAL MASTER ASSET VALIDATIONS PASSED!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = validate_master_asset()
    sys.exit(0 if success else 1)
