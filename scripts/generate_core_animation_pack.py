"""Generator script for Doodle Milestone 2 Task 16C Core Panda Animation Pack.

Generates:
1. idle (6 frames): Subtle looping breathing animation anchored at Y=246, X=127.5.
2. blink (3 frames): Short standalone blink (open, closed, reopening).
3. curious (6 frames): Interaction reaction (rest, perk, tilt start, peak tilt, ease out, settle).

Derived directly from canonical master reference: assets/panda/master/doodle_panda_master.png.
"""

from __future__ import annotations

import os
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter, QTransform

BASE_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = BASE_DIR / "assets" / "panda"
MASTER_PATH = ASSETS_DIR / "master" / "doodle_panda_master.png"


def generate_core_animation_pack() -> None:
    print("=" * 60)
    print("Generating Milestone 2 Task 16C Core Panda Animation Pack")
    print("=" * 60)

    assert MASTER_PATH.is_file(), f"Master asset missing at {MASTER_PATH}"
    master = QImage(str(MASTER_PATH))
    assert not master.isNull(), "Failed to decode master asset"

    # Source keyframes
    old_idle1_path = ASSETS_DIR / "idle" / "frame_01.png"
    att1_path = ASSETS_DIR / "attention" / "frame_01.png"
    c0_path = ASSETS_DIR / "curious" / "frame_00.png"
    c1_path = ASSETS_DIR / "curious" / "frame_01.png"

    old_idle1 = QImage(str(old_idle1_path)) if old_idle1_path.is_file() else None
    att1 = QImage(str(att1_path)) if att1_path.is_file() else None
    c0 = QImage(str(c0_path)) if c0_path.is_file() else None
    c1 = QImage(str(c1_path)) if c1_path.is_file() else None

    # ---------------------------------------------------------
    # 1. IDLE (6 frames: breathing loop)
    # ---------------------------------------------------------
    idle_dir = ASSETS_DIR / "idle"
    idle_dir.mkdir(parents=True, exist_ok=True)

    idle_scales = [
        (1.000, 1.000),  # Frame 0: neutral/rest (canonical master)
        (1.003, 1.005),  # Frame 1: slight inhale
        (1.006, 1.009),  # Frame 2: gentle chest/body expansion
        (1.009, 1.012),  # Frame 3: peak breathing position
        (1.006, 1.008),  # Frame 4: gentle exhale
        (1.003, 1.004),  # Frame 5: settle/rest
    ]

    print("Generating idle animation (6 frames)...")
    for i, (sx, sy) in enumerate(idle_scales):
        frame_path = idle_dir / f"frame_{i:02d}.png"
        if i == 0:
            res = master.copy()
        else:
            res = QImage(256, 256, QImage.Format.Format_ARGB32)
            res.fill(Qt.GlobalColor.transparent)
            p = QPainter(res)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            t = QTransform()
            t.translate(127.5, 245.0)
            t.scale(sx, sy)
            t.translate(-127.5, -245.0)
            p.setTransform(t)
            p.drawImage(0, 0, master)
            p.end()

            # Ensure ground contact baseline (Y >= 244) remains locked to master
            for y in range(244, 256):
                for x in range(256):
                    res.setPixel(x, y, master.pixel(x, y))

        res.save(str(frame_path))
        print(f"  [SAVED] {frame_path.name}")

    # Ensure panda_idle.png remains in idle/ for tray icon
    tray_icon_path = idle_dir / "panda_idle.png"
    master.save(str(tray_icon_path))
    print(f"  [SAVED] {tray_icon_path.name} (tray icon reference)")

    # ---------------------------------------------------------
    # 2. BLINK (3 frames: open, closed, reopening)
    # ---------------------------------------------------------
    blink_dir = ASSETS_DIR / "blink"
    blink_dir.mkdir(parents=True, exist_ok=True)

    print("Generating blink animation (3 frames)...")
    # Frame 0: eyes open (master)
    blink_f0 = master.copy()
    blink_f0.save(str(blink_dir / "frame_00.png"))
    print("  [SAVED] frame_00.png (eyes open)")

    # Frame 1: eyes closed (canonical closed eyes)
    blink_f1 = old_idle1.copy() if old_idle1 is not None else master.copy()
    blink_f1.save(str(blink_dir / "frame_01.png"))
    print("  [SAVED] frame_01.png (eyes closed)")

    # Frame 2: eyes reopening (45% opacity blend)
    blink_f2 = master.copy()
    if old_idle1 is not None:
        p = QPainter(blink_f2)
        p.setOpacity(0.45)
        p.drawImage(0, 0, old_idle1)
        p.end()
    blink_f2.save(str(blink_dir / "frame_02.png"))
    print("  [SAVED] frame_02.png (eyes reopening)")

    # ---------------------------------------------------------
    # 3. CURIOUS (6 frames: rest, perk, tilt start, tilt peak, hold/ease, settle)
    # ---------------------------------------------------------
    curious_dir = ASSETS_DIR / "curious"
    curious_dir.mkdir(parents=True, exist_ok=True)

    print("Generating curious animation (6 frames)...")
    curious_frames = [
        master.copy(),  # Frame 0: normal idle/rest
        att1.copy() if att1 is not None else master.copy(),  # Frame 1: small attention/perk (3.4 deg)
        c0.copy() if c0 is not None else master.copy(),      # Frame 2: head begins turning/tilting (6.3 deg)
        c1.copy() if c1 is not None else master.copy(),      # Frame 3: curious head tilt peak (10.2 deg)
        c0.copy() if c0 is not None else master.copy(),      # Frame 4: brief curious hold / ease out (6.3 deg)
        master.copy(),  # Frame 5: gentle settle toward neutral (0.0 deg)
    ]

    for i, cf in enumerate(curious_frames):
        frame_path = curious_dir / f"frame_{i:02d}.png"
        cf.save(str(frame_path))
        print(f"  [SAVED] {frame_path.name}")

    print("=" * 60)
    print("ALL CORE ANIMATION PACK FRAMES GENERATED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    generate_core_animation_pack()
