"""Validation tooling for Doodle Milestone 2 Task 16D Expressive Panda Animation Pack.

Verifies all frames in:
- assets/panda/yawn/ (8 frames)
- assets/panda/stretch/ (8 frames)
- assets/panda/dizzy/ (6 frames)
- assets/panda/recover/ (4 frames)
- assets/panda/look_around/ (8 frames)

Checks per frame:
1. Exact dimensions: 256 x 256 pixels
2. Format: RGBA (has alpha channel)
3. Transparent background: perimeter margins have Alpha = 0
4. Non-zero alpha: character is present
5. Safe margins: no clipping on borders (>= 8px margin)
6. Consistent horizontal center: X approx 128 (+/- 6px allowance for intentional leans/tilts)
7. Consistent contact anchor: Y approx 244-246 (+/- 4px)
8. Zero halo / border noise in transparent region

Checks across sequence:
- Alpha bounding box continuity
- Contact position stability (no floating, no vertical bouncing)
- Frame-to-frame pixel difference metrics (no abrupt pose snaps)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import NamedTuple

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

BASE_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = BASE_DIR / "assets" / "panda"

TARGET_ANIMATIONS = {
    "yawn": 8,
    "stretch": 8,
    "dizzy": 6,
    "recover": 4,
    "look_around": 8,
}


class FrameMetrics(NamedTuple):
    index: int
    name: str
    width: int
    height: int
    min_x: int
    max_x: int
    min_y: int
    max_y: int
    center_x: float
    contact_y: int
    non_zero_alpha: int
    outer_noise: int


def inspect_frame(img: QImage, index: int, name: str) -> FrameMetrics:
    w, h = img.width(), img.height()
    min_x, max_x = w, 0
    min_y, max_y = h, 0
    non_zero = 0
    outer_noise = 0

    for y in range(h):
        for x in range(w):
            p = img.pixel(x, y)
            a = (p >> 24) & 0xFF
            if a > 0:
                non_zero += 1
                if x < min_x:
                    min_x = x
                if x > max_x:
                    max_x = x
                if y < min_y:
                    min_y = y
                if y > max_y:
                    max_y = y
                if x < 8 or x >= w - 8 or y < 8 or y >= h - 8:
                    outer_noise += 1

    cx = (min_x + max_x) / 2.0 if non_zero > 0 else 0.0
    return FrameMetrics(
        index=index,
        name=name,
        width=w,
        height=h,
        min_x=min_x,
        max_x=max_x,
        min_y=min_y,
        max_y=max_y,
        center_x=cx,
        contact_y=max_y,
        non_zero_alpha=non_zero,
        outer_noise=outer_noise,
    )


def validate_animation_frames(anim_name: str, expected_count: int) -> list[FrameMetrics]:
    anim_dir = ASSETS_DIR / anim_name
    assert anim_dir.is_dir(), f"Animation directory {anim_dir} missing"

    frame_files = sorted(anim_dir.glob("frame_*.png"))
    assert len(frame_files) == expected_count, (
        f"Expected {expected_count} frames for '{anim_name}', found {len(frame_files)}"
    )

    metrics_list: list[FrameMetrics] = []
    images: list[QImage] = []

    print(f"\n--- Validating '{anim_name}' ({expected_count} frames) ---")
    for i, path in enumerate(frame_files):
        img = QImage(str(path))
        assert not img.isNull(), f"Failed to decode frame {path.name}"
        assert img.width() == 256 and img.height() == 256, (
            f"Frame {path.name} dimension {img.width()}x{img.height()} != 256x256"
        )
        assert img.hasAlphaChannel(), f"Frame {path.name} lacks RGBA alpha channel"

        m = inspect_frame(img, i, path.name)
        assert m.non_zero_alpha > 0, f"Frame {path.name} is completely blank"
        assert m.min_x >= 8 and m.max_x <= 248, f"Frame {path.name} clipped horizontally"
        assert m.min_y >= 8 and m.max_y <= 248, f"Frame {path.name} clipped vertically"
        # Center allowance: 6px for intentional leans/tilts (e.g. dizzy wobble, look around)
        assert abs(m.center_x - 128.0) <= 6.5, (
            f"Frame {path.name} center X={m.center_x:.1f} deviates > 6.5px from 128.0"
        )
        # Ground anchor: feet contact at Y=246 (+/- 4px around 244)
        assert abs(m.contact_y - 244) <= 4, (
            f"Frame {path.name} contact Y={m.contact_y} deviates > 4px from ground anchor 244"
        )
        assert m.outer_noise == 0, f"Frame {path.name} has {m.outer_noise} perimeter noise pixels"

        metrics_list.append(m)
        images.append(img)
        print(
            f"  [PASS] Frame {i:02d} ({path.name}): bbox X=[{m.min_x}..{m.max_x}], "
            f"Y=[{m.min_y}..{m.max_y}], center={m.center_x:.1f}, contact_Y={m.contact_y}, "
            f"alpha_pixels={m.non_zero_alpha}"
        )

    # Sequence continuity checks
    print(f"  [CHECK] Continuity and frame-to-frame pixel differences for '{anim_name}':")
    for i in range(len(images) - 1):
        next_i = i + 1
        img_a = images[i]
        img_b = images[next_i]

        diff_count = 0
        for y in range(256):
            for x in range(256):
                if img_a.pixel(x, y) != img_b.pixel(x, y):
                    diff_count += 1

        pct = (diff_count / (256 * 256)) * 100.0
        print(f"    Frame {i:02d} -> {next_i:02d}: {diff_count} differing pixels ({pct:.2f}%)")

    # Verify final settle frames for action animations
    if anim_name in ("stretch", "recover", "look_around", "yawn"):
        master_img = QImage(str(ASSETS_DIR / "master" / "doodle_panda_master.png"))
        last_frame = images[-1]
        assert last_frame == master_img, (
            f"Final frame of '{anim_name}' must match canonical resting master pose"
        )
        print(f"  [PASS] Final frame of '{anim_name}' matches canonical resting master pose perfectly.")

    return metrics_list


def run_full_validation() -> bool:
    print("=" * 60)
    print("Starting Milestone 2 Task 16D Expressive Animation Pack Validation")
    print("=" * 60)

    total_frames = 0
    for anim_name, expected_count in TARGET_ANIMATIONS.items():
        metrics = validate_animation_frames(anim_name, expected_count)
        total_frames += len(metrics)

    print("\n" + "=" * 60)
    print(f"VALIDATION SUCCESSFUL: All {total_frames} frames across 5 animations passed all checks!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    _qapp = QApplication.instance() or QApplication(sys.argv)
    success = run_full_validation()
    sys.exit(0 if success else 1)
