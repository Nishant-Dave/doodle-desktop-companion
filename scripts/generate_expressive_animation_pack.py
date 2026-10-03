"""Generator for Doodle Milestone 2 Task 16D Expressive Panda Animation Pack.

Generates the 5 expressive animations using the canonical Doodle panda master geometry:
1. yawn (8 frames): Sleepy yawn with readable mouth opening, subtle rise, grounded contact (Y=246).
2. stretch (8 frames): Full-body stretch with anticipation crouch, continuous paw extension, peak hold, release, and settle to idle.
3. dizzy (6 frames): Damped rotational wobble sequence with phase-shifted swirling eyes leading to recover.
4. recover (4 frames): Post-dizzy recovery (dazed, head shake/eye clearing, body settle, exact idle rest).
5. look_around (8 frames): Environmental awareness with gaze leading head turn (left hold, center, right hold, settle to idle).

All frames strictly preserve the canonical master identity (assets/panda/master/doodle_panda_master.png).
"""

from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Optional

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
    QTransform,
)

BASE_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = BASE_DIR / "assets" / "panda"
MASTER_PATH = ASSETS_DIR / "master" / "doodle_panda_master.png"


def draw_expressive_panda_frame(
    ear_offset: tuple[float, float] = (0.0, 0.0),
    eye_style: str = "normal",  # 'normal', 'blink', 'sleep', 'alert', 'surprised', 'dizzy', 'squint'
    eye_offset: tuple[float, float] = (0.0, 0.0),
    dizzy_phase: float = 0.0,
    paw_style: str = "lap",  # 'lap', 'reach', 'wide', 'head', 'custom'
    custom_left_paw: Optional[QRectF] = None,
    custom_right_paw: Optional[QRectF] = None,
    body_squash: float = 0.0,
    head_tilt: float = 0.0,
    head_offset: tuple[float, float] = (0.0, 0.0),
    body_tilt: float = 0.0,
    mouth_style: str = "smile",  # 'smile', 'sleep', 'open_o', 'wavy', 'yawn_small', 'yawn_mid', 'yawn_peak'
) -> QImage:
    """Draw a canonical panda frame with expressive parameters while strictly maintaining identity."""
    size = 256
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)

    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    # Canonical color palette
    black = QColor(35, 35, 40)
    white = QColor(250, 250, 255)
    inner_ear = QColor(65, 65, 75)
    blush = QColor(255, 175, 190, 160)
    nose = QColor(40, 40, 45)
    highlight = QColor(255, 255, 255)
    mouth_inner = QColor(35, 35, 40)
    tongue_color = QColor(255, 160, 175)

    # Optional body tilt for dizzy rotational swaying anchored at grounded hips (128, 230)
    if body_tilt != 0.0:
        p.save()
        p.translate(128.0, 230.0)
        p.rotate(body_tilt)
        p.translate(-128.0, -230.0)

    # 1. Ears
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(black))
    p.drawEllipse(QRectF(30 + ear_offset[0] + head_offset[0], 30 + ear_offset[1] + head_offset[1], 60, 60))
    p.drawEllipse(QRectF(166 - ear_offset[0] + head_offset[0], 30 + ear_offset[1] + head_offset[1], 60, 60))

    p.setBrush(QBrush(inner_ear))
    p.drawEllipse(QRectF(42 + ear_offset[0] + head_offset[0], 42 + ear_offset[1] + head_offset[1], 36, 36))
    p.drawEllipse(QRectF(178 - ear_offset[0] + head_offset[0], 42 + ear_offset[1] + head_offset[1], 36, 36))

    # 2. Body
    p.setBrush(QBrush(black))
    if custom_left_paw is not None and custom_right_paw is not None:
        p.drawRoundedRect(QRectF(50, 140 + body_squash, 156, 90 - body_squash), 40, 40)
        p.drawEllipse(custom_left_paw)
        p.drawEllipse(custom_right_paw)
    elif paw_style == "reach":
        p.drawRoundedRect(QRectF(50, 130 + body_squash, 156, 100 - body_squash), 40, 40)
        p.drawEllipse(QRectF(36, 90 + body_squash, 48, 54))
        p.drawEllipse(QRectF(172, 90 + body_squash, 48, 54))
    elif paw_style == "wide":
        p.drawRoundedRect(QRectF(48, 140 + body_squash, 160, 90 - body_squash), 40, 40)
        p.drawEllipse(QRectF(22, 145, 52, 44))
        p.drawEllipse(QRectF(182, 145, 52, 44))
    elif paw_style == "head":
        p.drawRoundedRect(QRectF(50, 140 + body_squash, 156, 90 - body_squash), 40, 40)
        p.drawEllipse(QRectF(32, 115, 48, 48))
        p.drawEllipse(QRectF(176, 115, 48, 48))
    else:  # 'lap'
        p.drawRoundedRect(QRectF(50, 140 + body_squash, 156, 90 - body_squash), 40, 40)
        p.drawEllipse(QRectF(40, 175 + body_squash, 48, 48))
        p.drawEllipse(QRectF(168, 175 + body_squash, 48, 48))

    # White belly
    p.setBrush(QBrush(white))
    p.drawEllipse(QRectF(78, 148 + body_squash, 100, 84 - body_squash))

    if body_tilt != 0.0:
        p.restore()  # Close body tilt before drawing feet so feet remain perfectly grounded

    # Feet (always strictly grounded at Y=246, untouched by tilts)
    p.setBrush(QBrush(black))
    p.drawEllipse(QRectF(65, 215, 44, 32))
    p.drawEllipse(QRectF(147, 215, 44, 32))

    # 3. Head with optional translation and tilt
    p.save()
    head_cx = 128.0 + head_offset[0]
    head_cy = 118.0 + head_offset[1]
    if head_tilt != 0.0 or head_offset != (0.0, 0.0):
        p.translate(head_cx, head_cy)
        p.rotate(head_tilt)
        p.translate(-head_cx, -head_cy)

    head_x = 44.0 + head_offset[0]
    head_y = 48.0 + head_offset[1]

    # White head base
    p.setBrush(QBrush(white))
    p.setPen(QPen(QColor(230, 230, 235), 1.5))
    p.drawEllipse(QRectF(head_x, head_y, 168, 140))

    # Eye patches (relative to head center)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(black))

    # Left eye patch
    p.save()
    p.translate(85.0 + head_offset[0], 115.0 + head_offset[1])
    p.rotate(-18)
    p.drawEllipse(QRectF(-22, -16, 44, 32))
    p.restore()

    # Right eye patch
    p.save()
    p.translate(171.0 + head_offset[0], 115.0 + head_offset[1])
    p.rotate(18)
    p.drawEllipse(QRectF(-22, -16, 44, 32))
    p.restore()

    # Eyes
    hx, hy = head_offset[0], head_offset[1]
    ex, ey = eye_offset[0], eye_offset[1]

    if eye_style == "blink":
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(white, 3.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        path_l = QPainterPath()
        path_l.moveTo(74 + hx, 116 + hy)
        path_l.quadTo(85 + hx, 108 + hy, 96 + hx, 116 + hy)
        p.drawPath(path_l)

        path_r = QPainterPath()
        path_r.moveTo(160 + hx, 116 + hy)
        path_r.quadTo(171 + hx, 108 + hy, 182 + hx, 116 + hy)
        p.drawPath(path_r)

    elif eye_style == "sleep":
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(white, 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        path_l = QPainterPath()
        path_l.moveTo(76 + hx, 114 + hy)
        path_l.quadTo(85 + hx, 120 + hy, 94 + hx, 114 + hy)
        p.drawPath(path_l)

        path_r = QPainterPath()
        path_r.moveTo(162 + hx, 114 + hy)
        path_r.quadTo(171 + hx, 120 + hy, 180 + hx, 114 + hy)
        p.drawPath(path_r)

    elif eye_style == "squint":
        # Happy / yawn satisfied squint: ^  ^
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(white, 3.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        path_l = QPainterPath()
        path_l.moveTo(75 + hx, 116 + hy)
        path_l.lineTo(85 + hx, 108 + hy)
        path_l.lineTo(95 + hx, 116 + hy)
        p.drawPath(path_l)

        path_r = QPainterPath()
        path_r.moveTo(161 + hx, 116 + hy)
        path_r.lineTo(171 + hx, 108 + hy)
        path_r.lineTo(181 + hx, 116 + hy)
        p.drawPath(path_r)

    elif eye_style == "alert":
        p.setBrush(QBrush(black))
        p.drawEllipse(QRectF(78 + hx + ex, 104 + hy + ey, 20, 22))
        p.drawEllipse(QRectF(158 + hx + ex, 104 + hy + ey, 20, 22))
        p.setBrush(QBrush(highlight))
        p.drawEllipse(QRectF(82 + hx + ex, 106 + hy + ey, 8, 8))
        p.drawEllipse(QRectF(90 + hx + ex, 118 + hy + ey, 4, 4))
        p.drawEllipse(QRectF(162 + hx + ex, 106 + hy + ey, 8, 8))
        p.drawEllipse(QRectF(170 + hx + ex, 118 + hy + ey, 4, 4))

    elif eye_style == "dizzy":
        # Rotational spiral arcs that smoothly animate as dizzy_phase advances
        p.setBrush(Qt.BrushStyle.NoBrush)
        dizzy_pen = QPen(white, 2.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(dizzy_pen)

        for center_x in (86.0 + hx, 170.0 + hx):
            center_y = 114.0 + hy
            path = QPainterPath()
            steps = 40
            max_turns = 1.8
            for s in range(steps + 1):
                t = s / steps
                angle = dizzy_phase + t * max_turns * 2.0 * math.pi
                r = 1.5 + t * 7.5
                px = center_x + r * math.cos(angle)
                py = center_y + r * math.sin(angle)
                if s == 0:
                    path.moveTo(px, py)
                else:
                    path.lineTo(px, py)
            p.drawPath(path)

    else:  # 'normal'
        p.setBrush(QBrush(black))
        p.drawEllipse(QRectF(80 + hx + ex, 106 + hy + ey, 16, 18))
        p.drawEllipse(QRectF(160 + hx + ex, 106 + hy + ey, 16, 18))
        p.setBrush(QBrush(highlight))
        p.drawEllipse(QRectF(82 + hx + ex, 108 + hy + ey, 6, 6))
        p.drawEllipse(QRectF(88 + hx + ex, 117 + hy + ey, 3, 3))
        p.drawEllipse(QRectF(162 + hx + ex, 108 + hy + ey, 6, 6))
        p.drawEllipse(QRectF(168 + hx + ex, 117 + hy + ey, 3, 3))

    # Blush
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(blush))
    p.drawEllipse(QRectF(56 + hx, 134 + hy, 28, 16))
    p.drawEllipse(QRectF(172 + hx, 134 + hy, 28, 16))

    # Nose
    p.setBrush(QBrush(nose))
    p.drawRoundedRect(QRectF(120 + hx, 126 + hy, 16, 10), 4, 4)

    # Mouth
    p.setBrush(Qt.BrushStyle.NoBrush)
    smile_pen = QPen(black, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(smile_pen)

    if mouth_style == "open_o":
        p.setBrush(QBrush(black))
        p.drawEllipse(QRectF(123 + hx, 138 + hy, 10, 12))

    elif mouth_style == "wavy":
        wpath = QPainterPath()
        wpath.moveTo(117 + hx, 140 + hy)
        wpath.quadTo(122 + hx, 136 + hy, 127 + hx, 140 + hy)
        wpath.quadTo(132 + hx, 144 + hy, 137 + hx, 140 + hy)
        p.drawPath(wpath)

    elif mouth_style == "sleep":
        spath = QPainterPath()
        spath.moveTo(122 + hx, 138 + hy)
        spath.quadTo(128 + hx, 142 + hy, 134 + hx, 138 + hy)
        p.drawPath(spath)

    elif mouth_style == "yawn_small":
        # Small open mouth beginning yawn
        p.setPen(QPen(black, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(QBrush(mouth_inner))
        ypath = QPainterPath()
        ypath.addRoundedRect(QRectF(122 + hx, 137 + hy, 12, 10), 5, 5)
        p.drawPath(ypath)
        # Little tongue
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(tongue_color))
        p.drawEllipse(QRectF(124 + hx, 142 + hy, 8, 5))

    elif mouth_style == "yawn_mid":
        # Medium opening mouth with visible tongue
        p.setPen(QPen(black, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(QBrush(mouth_inner))
        ypath = QPainterPath()
        ypath.addRoundedRect(QRectF(120 + hx, 135 + hy, 16, 14), 7, 7)
        p.drawPath(ypath)
        # Tongue
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(tongue_color))
        p.drawEllipse(QRectF(122 + hx, 142 + hy, 12, 7))

    elif mouth_style == "yawn_peak":
        # Full yawn peak: wide open drop shape with tongue and depth
        p.setPen(QPen(black, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(QBrush(mouth_inner))
        ypath = QPainterPath()
        ypath.addRoundedRect(QRectF(118 + hx, 133 + hy, 20, 18), 9, 9)
        p.drawPath(ypath)
        # Cute tongue curve inside
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(tongue_color))
        p.drawEllipse(QRectF(120 + hx, 143 + hy, 16, 8))

    else:  # 'smile'
        spath = QPainterPath()
        spath.moveTo(118 + hx, 138 + hy)
        spath.quadTo(124 + hx, 146 + hy, 128 + hx, 140 + hy)
        spath.quadTo(132 + hx, 146 + hy, 138 + hx, 138 + hy)
        p.drawPath(spath)

    p.restore()  # End head transform

    p.end()
    return img


def generate_expressive_pack() -> None:
    """Generate all 5 expressive animations into assets/panda/."""
    print("=" * 60)
    print("Generating Milestone 2 Task 16D Expressive Animation Pack")
    print("=" * 60)

    assert MASTER_PATH.is_file(), f"Master asset missing at {MASTER_PATH}"
    master = QImage(str(MASTER_PATH))
    assert not master.isNull(), "Failed to decode master asset"

    # -------------------------------------------------------------
    # 1. YAWN (8 frames: sleepy yawn)
    # -------------------------------------------------------------
    yawn_dir = ASSETS_DIR / "yawn"
    yawn_dir.mkdir(parents=True, exist_ok=True)
    print("Generating yawn animation (8 frames)...")

    # Sequence:
    # 0: normal/resting pose (exact master)
    # 1: small sleepy anticipation / inhale
    # 2: head and shoulders begin rising
    # 3: mouth begins opening
    # 4: full yawn peak
    # 5: brief relaxed hold / tiny sleepy shudder
    # 6: mouth closes and body begins settling
    # 7: soft return toward idle (exact master)
    yawn_frames = [
        master.copy(),  # Frame 0: rest
        draw_expressive_panda_frame(
            head_offset=(0.0, -1.0),
            body_squash=-1.0,
            eye_style="sleep",
            mouth_style="sleep",
        ),  # Frame 1: sleepy anticipation / inhale
        draw_expressive_panda_frame(
            head_offset=(0.0, -2.5),
            head_tilt=-1.5,
            ear_offset=(0.0, -2.0),
            body_squash=-2.0,
            eye_style="sleep",
            mouth_style="yawn_small",
            custom_left_paw=QRectF(40, 173, 48, 48),
            custom_right_paw=QRectF(168, 173, 48, 48),
        ),  # Frame 2: head and shoulders rising
        draw_expressive_panda_frame(
            head_offset=(0.0, -3.5),
            head_tilt=-2.5,
            ear_offset=(-1.0, -3.0),
            body_squash=-2.5,
            eye_style="sleep",
            mouth_style="yawn_mid",
            custom_left_paw=QRectF(39, 171, 48, 48),
            custom_right_paw=QRectF(169, 171, 48, 48),
        ),  # Frame 3: mouth opening wider
        draw_expressive_panda_frame(
            head_offset=(0.0, -4.5),
            head_tilt=-3.0,
            ear_offset=(-1.5, -4.0),
            body_squash=-3.0,
            eye_style="squint",
            mouth_style="yawn_peak",
            custom_left_paw=QRectF(38, 169, 48, 48),
            custom_right_paw=QRectF(170, 169, 48, 48),
        ),  # Frame 4: full yawn peak!
        draw_expressive_panda_frame(
            head_offset=(0.0, -3.0),
            head_tilt=-1.5,
            ear_offset=(-1.0, -2.5),
            body_squash=-2.0,
            eye_style="squint",
            mouth_style="yawn_mid",
            custom_left_paw=QRectF(39, 171, 48, 48),
            custom_right_paw=QRectF(169, 171, 48, 48),
        ),  # Frame 5: relaxed hold / ease
        draw_expressive_panda_frame(
            head_offset=(0.0, -1.0),
            head_tilt=0.0,
            ear_offset=(0.0, -1.0),
            body_squash=-1.0,
            eye_style="sleep",
            mouth_style="sleep",
            custom_left_paw=QRectF(40, 174, 48, 48),
            custom_right_paw=QRectF(168, 174, 48, 48),
        ),  # Frame 6: mouth closes, body settling
        master.copy(),  # Frame 7: soft return toward idle (exact master)
    ]

    for i, frame in enumerate(yawn_frames):
        path = yawn_dir / f"frame_{i:02d}.png"
        frame.save(str(path))
        print(f"  [SAVED] {path.name}")

    # -------------------------------------------------------------
    # 2. STRETCH (8 frames: full-body continuous stretch)
    # -------------------------------------------------------------
    stretch_dir = ASSETS_DIR / "stretch"
    stretch_dir.mkdir(parents=True, exist_ok=True)
    print("Generating stretch animation (8 frames)...")

    # Sequence:
    # 0: resting pose (exact master)
    # 1: slight crouch / anticipation
    # 2: body begins rising, paws moving outward
    # 3: paws extending upward
    # 4: full stretch peak
    # 5: brief peak / hold
    # 6: release begins, paws ease down
    # 7: settle back into seated rest (exact master)
    stretch_frames = [
        master.copy(),  # Frame 0: rest
        draw_expressive_panda_frame(
            head_offset=(0.0, 2.0),
            body_squash=2.5,
            custom_left_paw=QRectF(42, 178, 48, 48),
            custom_right_paw=QRectF(166, 178, 48, 48),
            eye_style="alert",
            mouth_style="smile",
        ),  # Frame 1: crouch / anticipation
        draw_expressive_panda_frame(
            head_offset=(0.0, -2.0),
            body_squash=-1.5,
            custom_left_paw=QRectF(36, 150, 48, 48),
            custom_right_paw=QRectF(172, 150, 48, 48),
            eye_style="normal",
            mouth_style="smile",
        ),  # Frame 2: rising
        draw_expressive_panda_frame(
            head_offset=(0.0, -5.0),
            ear_offset=(-1.5, -2.5),
            body_squash=-3.5,
            custom_left_paw=QRectF(30, 120, 48, 50),
            custom_right_paw=QRectF(178, 120, 48, 50),
            eye_style="sleep",
            mouth_style="smile",
        ),  # Frame 3: extending
        draw_expressive_panda_frame(
            head_offset=(0.0, -7.0),
            ear_offset=(-2.5, -4.5),
            body_squash=-5.0,
            custom_left_paw=QRectF(26, 94, 48, 52),
            custom_right_paw=QRectF(182, 94, 48, 52),
            eye_style="squint",
            mouth_style="smile",
        ),  # Frame 4: full stretch!
        draw_expressive_panda_frame(
            head_offset=(0.0, -6.0),
            ear_offset=(-2.0, -3.5),
            body_squash=-4.0,
            custom_left_paw=QRectF(28, 100, 48, 52),
            custom_right_paw=QRectF(180, 100, 48, 52),
            eye_style="squint",
            mouth_style="smile",
        ),  # Frame 5: peak hold / ease
        draw_expressive_panda_frame(
            head_offset=(0.0, -2.5),
            ear_offset=(-1.0, -1.5),
            body_squash=-1.5,
            custom_left_paw=QRectF(35, 140, 48, 48),
            custom_right_paw=QRectF(173, 140, 48, 48),
            eye_style="normal",
            mouth_style="smile",
        ),  # Frame 6: release begins
        master.copy(),  # Frame 7: settle to rest (exact master)
    ]

    for i, frame in enumerate(stretch_frames):
        path = stretch_dir / f"frame_{i:02d}.png"
        frame.save(str(path))
        print(f"  [SAVED] {path.name}")

    # -------------------------------------------------------------
    # 3. DIZZY (6 frames: rotational wobble with phase swirls)
    # -------------------------------------------------------------
    dizzy_dir = ASSETS_DIR / "dizzy"
    dizzy_dir.mkdir(parents=True, exist_ok=True)
    print("Generating dizzy animation (6 frames)...")

    # Sequence:
    # 0: initial disorientation (tilt left -3.5 deg)
    # 1: peak lean left (-7.5 deg, ear motion lag)
    # 2: center / wobble crossing (+1.0 deg)
    # 3: peak lean right (+6.5 deg, ear motion lag)
    # 4: smaller wobble damped (-2.5 deg)
    # 5: stabilizing pose (+0.5 deg)
    dizzy_frames = [
        draw_expressive_panda_frame(
            head_tilt=-3.5,
            head_offset=(-2.0, 0.5),
            ear_offset=(1.0, 1.0),
            body_tilt=-2.0,
            eye_style="dizzy",
            dizzy_phase=0.0,
            paw_style="wide",
            mouth_style="wavy",
        ),  # Frame 0: disorientation
        draw_expressive_panda_frame(
            head_tilt=-7.5,
            head_offset=(-4.5, 1.0),
            ear_offset=(2.5, 1.5),
            body_tilt=-4.5,
            eye_style="dizzy",
            dizzy_phase=math.pi / 3.0,
            paw_style="wide",
            mouth_style="wavy",
        ),  # Frame 1: lean left peak
        draw_expressive_panda_frame(
            head_tilt=1.5,
            head_offset=(1.0, 0.0),
            ear_offset=(-1.0, 0.0),
            body_tilt=1.0,
            eye_style="dizzy",
            dizzy_phase=2.0 * math.pi / 3.0,
            paw_style="wide",
            mouth_style="wavy",
        ),  # Frame 2: center wobble
        draw_expressive_panda_frame(
            head_tilt=6.5,
            head_offset=(3.5, 1.0),
            ear_offset=(-2.5, 1.5),
            body_tilt=4.0,
            eye_style="dizzy",
            dizzy_phase=math.pi,
            paw_style="wide",
            mouth_style="wavy",
        ),  # Frame 3: lean right
        draw_expressive_panda_frame(
            head_tilt=-2.5,
            head_offset=(-1.5, 0.0),
            ear_offset=(1.0, 0.0),
            body_tilt=-1.5,
            eye_style="dizzy",
            dizzy_phase=4.0 * math.pi / 3.0,
            paw_style="wide",
            mouth_style="wavy",
        ),  # Frame 4: smaller wobble
        draw_expressive_panda_frame(
            head_tilt=0.5,
            head_offset=(0.0, 0.0),
            ear_offset=(0.0, 0.0),
            body_tilt=0.0,
            eye_style="dizzy",
            dizzy_phase=5.0 * math.pi / 3.0,
            custom_left_paw=QRectF(30, 130, 48, 48),
            custom_right_paw=QRectF(178, 130, 48, 48),
            mouth_style="wavy",
        ),  # Frame 5: stabilizing pose (leads to recover)
    ]

    for i, frame in enumerate(dizzy_frames):
        path = dizzy_dir / f"frame_{i:02d}.png"
        frame.save(str(path))
        print(f"  [SAVED] {path.name}")

    # -------------------------------------------------------------
    # 4. RECOVER (4 frames: post-dizzy settle)
    # -------------------------------------------------------------
    recover_dir = ASSETS_DIR / "recover"
    recover_dir.mkdir(parents=True, exist_ok=True)
    print("Generating recover animation (4 frames)...")

    # Sequence:
    # 0: still slightly dazed (paws at head, soft tilt +2.0 deg)
    # 1: small head shake / eye clearing (tilt -2.0 deg, blink shut)
    # 2: body settles (tilt 0.0 deg, paws returning to lap)
    # 3: stable resting pose matching idle (exact master)
    recover_frames = [
        draw_expressive_panda_frame(
            head_tilt=2.5,
            head_offset=(1.0, 0.0),
            ear_offset=(-1.0, 0.0),
            paw_style="head",
            eye_style="sleep",
            mouth_style="sleep",
        ),  # Frame 0: slightly dazed
        draw_expressive_panda_frame(
            head_tilt=-2.0,
            head_offset=(-1.0, 0.0),
            ear_offset=(1.0, -1.0),
            custom_left_paw=QRectF(36, 140, 48, 48),
            custom_right_paw=QRectF(172, 140, 48, 48),
            eye_style="blink",
            mouth_style="smile",
        ),  # Frame 1: head shake / eye clearing
        draw_expressive_panda_frame(
            head_tilt=0.0,
            head_offset=(0.0, 0.0),
            custom_left_paw=QRectF(39, 168, 48, 48),
            custom_right_paw=QRectF(169, 168, 48, 48),
            eye_style="normal",
            mouth_style="smile",
        ),  # Frame 2: body settles
        master.copy(),  # Frame 3: exact resting pose (matches idle frame 0)
    ]

    for i, frame in enumerate(recover_frames):
        path = recover_dir / f"frame_{i:02d}.png"
        frame.save(str(path))
        print(f"  [SAVED] {path.name}")

    # -------------------------------------------------------------
    # 5. LOOK_AROUND (8 frames: subtle environmental awareness)
    # -------------------------------------------------------------
    look_dir = ASSETS_DIR / "look_around"
    look_dir.mkdir(parents=True, exist_ok=True)
    print("Generating look_around animation (8 frames)...")

    # Sequence:
    # 0: neutral (exact master)
    # 1: eyes move left
    # 2: head begins turning left
    # 3: left look / hold
    # 4: return toward center
    # 5: eyes/head begin looking right
    # 6: right look / hold
    # 7: settle back to center (exact master)
    look_frames = [
        master.copy(),  # Frame 0: neutral rest
        draw_expressive_panda_frame(
            eye_offset=(-3.5, 0.0),
            mouth_style="smile",
        ),  # Frame 1: eyes move left
        draw_expressive_panda_frame(
            head_offset=(-2.0, 0.0),
            head_tilt=-1.8,
            ear_offset=(-1.5, 0.0),
            eye_offset=(-4.5, 0.0),
            mouth_style="smile",
        ),  # Frame 2: head begins turning left
        draw_expressive_panda_frame(
            head_offset=(-3.5, 0.0),
            head_tilt=-2.5,
            ear_offset=(-2.0, 0.0),
            eye_offset=(-4.5, 0.0),
            mouth_style="smile",
        ),  # Frame 3: left look / hold
        draw_expressive_panda_frame(
            head_offset=(-1.0, 0.0),
            head_tilt=-0.8,
            ear_offset=(-0.8, 0.0),
            eye_offset=(-1.5, 0.0),
            mouth_style="smile",
        ),  # Frame 4: return toward center
        draw_expressive_panda_frame(
            head_offset=(2.0, 0.0),
            head_tilt=1.8,
            ear_offset=(1.5, 0.0),
            eye_offset=(4.0, 0.0),
            mouth_style="smile",
        ),  # Frame 5: eyes and head begin looking right
        draw_expressive_panda_frame(
            head_offset=(3.5, 0.0),
            head_tilt=2.5,
            ear_offset=(2.0, 0.0),
            eye_offset=(4.5, 0.0),
            mouth_style="smile",
        ),  # Frame 6: right look / hold
        master.copy(),  # Frame 7: settle back to center (exact master)
    ]

    for i, frame in enumerate(look_frames):
        path = look_dir / f"frame_{i:02d}.png"
        frame.save(str(path))
        print(f"  [SAVED] {path.name}")

    print("=" * 60)
    print("ALL 5 EXPRESSIVE ANIMATIONS GENERATED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    generate_expressive_pack()
