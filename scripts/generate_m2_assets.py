"""Generator for Milestone 2 expressive panda animation frames."""

import os
import sys
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QGuiApplication,
    QImage,
    QPainter,
    QPainterPath,
    QPen,
)


def draw_panda_frame(
    ear_offset=(0, 0),
    eye_style="normal",  # 'normal', 'blink', 'sleep', 'alert', 'surprised', 'dizzy', 'wink'
    paw_style="lap",  # 'lap', 'reach', 'wide', 'head'
    body_squash=0,
    head_tilt=0,
    mouth_style="smile",  # 'smile', 'sleep', 'open_o', 'wavy'
    sleep_z=None,
) -> QImage:
    size = 256
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)

    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    black = QColor(35, 35, 40)
    white = QColor(250, 250, 255)
    inner_ear = QColor(65, 65, 75)
    blush = QColor(255, 175, 190, 160)
    nose = QColor(40, 40, 45)
    highlight = QColor(255, 255, 255)

    # 1. Ears
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(black))
    p.drawEllipse(QRectF(30 + ear_offset[0], 30 + ear_offset[1], 60, 60))
    p.drawEllipse(QRectF(166 - ear_offset[0], 30 + ear_offset[1], 60, 60))

    p.setBrush(QBrush(inner_ear))
    p.drawEllipse(QRectF(42 + ear_offset[0], 42 + ear_offset[1], 36, 36))
    p.drawEllipse(QRectF(178 - ear_offset[0], 42 + ear_offset[1], 36, 36))

    # 2. Body
    p.setBrush(QBrush(black))
    if paw_style == "reach":
        p.drawRoundedRect(QRectF(50, 130, 156, 100), 40, 40)
        p.drawEllipse(QRectF(36, 90, 48, 54))
        p.drawEllipse(QRectF(172, 90, 48, 54))
    elif paw_style == "wide":
        p.drawRoundedRect(QRectF(48, 140, 160, 90), 40, 40)
        p.drawEllipse(QRectF(22, 145, 52, 44))
        p.drawEllipse(QRectF(182, 145, 52, 44))
    elif paw_style == "head":
        p.drawRoundedRect(QRectF(50, 140 + body_squash, 156, 90 - body_squash), 40, 40)
        p.drawEllipse(QRectF(32, 115, 48, 48))
        p.drawEllipse(QRectF(176, 115, 48, 48))
    else:
        p.drawRoundedRect(QRectF(50, 140 + body_squash, 156, 90 - body_squash), 40, 40)
        p.drawEllipse(QRectF(40, 175 + body_squash, 48, 48))
        p.drawEllipse(QRectF(168, 175 + body_squash, 48, 48))

    # White belly
    p.setBrush(QBrush(white))
    p.drawEllipse(QRectF(78, 148 + body_squash, 100, 84 - body_squash))

    # Feet
    p.setBrush(QBrush(black))
    p.drawEllipse(QRectF(65, 215, 44, 32))
    p.drawEllipse(QRectF(147, 215, 44, 32))

    # 3. Head with optional tilt
    p.save()
    if head_tilt:
        p.translate(128, 118)
        p.rotate(head_tilt)
        p.translate(-128, -118)

    p.setBrush(QBrush(white))
    p.setPen(QPen(QColor(230, 230, 235), 1.5))
    p.drawEllipse(QRectF(44, 48, 168, 140))

    # Eye patches
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(black))
    p.save()
    p.translate(85, 115)
    p.rotate(-18)
    p.drawEllipse(QRectF(-22, -16, 44, 32))
    p.restore()

    p.save()
    p.translate(171, 115)
    p.rotate(18)
    p.drawEllipse(QRectF(-22, -16, 44, 32))
    p.restore()

    # Eyes
    if eye_style == "blink":
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(white, 3.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        path_l = QPainterPath()
        path_l.moveTo(74, 116)
        path_l.quadTo(85, 108, 96, 116)
        p.drawPath(path_l)

        path_r = QPainterPath()
        path_r.moveTo(160, 116)
        path_r.quadTo(171, 108, 182, 116)
        p.drawPath(path_r)
    elif eye_style == "sleep":
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(white, 3.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        path_l = QPainterPath()
        path_l.moveTo(76, 114)
        path_l.quadTo(85, 120, 94, 114)
        p.drawPath(path_l)

        path_r = QPainterPath()
        path_r.moveTo(162, 114)
        path_r.quadTo(171, 120, 180, 114)
        p.drawPath(path_r)
    elif eye_style == "alert":
        p.setBrush(QBrush(black))
        p.drawEllipse(QRectF(78, 104, 20, 22))
        p.drawEllipse(QRectF(158, 104, 20, 22))
        p.setBrush(QBrush(highlight))
        p.drawEllipse(QRectF(82, 106, 8, 8))
        p.drawEllipse(QRectF(90, 118, 4, 4))
        p.drawEllipse(QRectF(162, 106, 8, 8))
        p.drawEllipse(QRectF(170, 118, 4, 4))
    elif eye_style == "surprised":
        # Extra large round eyes with small central pupils
        p.setBrush(QBrush(white))
        p.drawEllipse(QRectF(75, 102, 22, 24))
        p.drawEllipse(QRectF(159, 102, 22, 24))
        p.setBrush(QBrush(black))
        p.drawEllipse(QRectF(81, 109, 10, 10))
        p.drawEllipse(QRectF(165, 109, 10, 10))
        p.setBrush(QBrush(highlight))
        p.drawEllipse(QRectF(83, 111, 4, 4))
        p.drawEllipse(QRectF(167, 111, 4, 4))
    elif eye_style == "dizzy":
        # Spiral/swirling eyes
        p.setBrush(Qt.BrushStyle.NoBrush)
        dizzy_pen = QPen(white, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        p.setPen(dizzy_pen)
        # Left spiral
        path_dl = QPainterPath()
        path_dl.addEllipse(QRectF(78, 107, 16, 16))
        path_dl.addEllipse(QRectF(82, 111, 8, 8))
        p.drawPath(path_dl)
        # Right spiral
        path_dr = QPainterPath()
        path_dr.addEllipse(QRectF(162, 107, 16, 16))
        path_dr.addEllipse(QRectF(166, 111, 8, 8))
        p.drawPath(path_dr)
    elif eye_style == "wink":
        # Left eye winks, right eye alert
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(white, 3.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        path_l = QPainterPath()
        path_l.moveTo(74, 116)
        path_l.quadTo(85, 108, 96, 116)
        p.drawPath(path_l)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(black))
        p.drawEllipse(QRectF(158, 104, 20, 22))
        p.setBrush(QBrush(highlight))
        p.drawEllipse(QRectF(162, 106, 8, 8))
        p.drawEllipse(QRectF(170, 118, 4, 4))
    else:  # normal
        p.setBrush(QBrush(black))
        p.drawEllipse(QRectF(80, 106, 16, 18))
        p.drawEllipse(QRectF(160, 106, 16, 18))
        p.setBrush(QBrush(highlight))
        p.drawEllipse(QRectF(82, 108, 6, 6))
        p.drawEllipse(QRectF(88, 117, 3, 3))
        p.drawEllipse(QRectF(162, 108, 6, 6))
        p.drawEllipse(QRectF(168, 117, 3, 3))

    # Blush
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(blush))
    p.drawEllipse(QRectF(56, 134, 28, 16))
    p.drawEllipse(QRectF(172, 134, 28, 16))

    # Nose
    p.setBrush(QBrush(nose))
    p.drawRoundedRect(QRectF(120, 126, 16, 10), 4, 4)

    # Mouth
    p.setBrush(Qt.BrushStyle.NoBrush)
    smile_pen = QPen(black, 2.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(smile_pen)
    if mouth_style == "open_o":
        p.setBrush(QBrush(black))
        p.drawEllipse(QRectF(123, 138, 10, 12))
    elif mouth_style == "wavy":
        wpath = QPainterPath()
        wpath.moveTo(117, 140)
        wpath.quadTo(122, 136, 127, 140)
        wpath.quadTo(132, 144, 137, 140)
        p.drawPath(wpath)
    elif mouth_style == "sleep":
        spath = QPainterPath()
        spath.moveTo(122, 138)
        spath.quadTo(128, 142, 134, 138)
        p.drawPath(spath)
    else:  # smile
        spath = QPainterPath()
        spath.moveTo(118, 138)
        spath.quadTo(124, 146, 128, 140)
        spath.quadTo(132, 146, 138, 138)
        p.drawPath(spath)

    p.restore()

    # Sleep Z's using vector paths
    if sleep_z:
        p.setPen(QPen(QColor(100, 150, 240, 220), 3))
        zx, zy = sleep_z.get("x", 190), sleep_z.get("y", 70)
        zw = sleep_z.get("w", 12)
        zh = sleep_z.get("h", 14)
        zpath = QPainterPath()
        zpath.moveTo(zx, zy)
        zpath.lineTo(zx + zw, zy)
        zpath.lineTo(zx, zy + zh)
        zpath.lineTo(zx + zw, zy + zh)
        p.drawPath(zpath)

    p.end()
    return img


def generate_all():
    root = Path(__file__).resolve().parents[1]
    assets_dir = root / "assets" / "panda"

    animations = {
        "surprised": [
            draw_panda_frame(
                ear_offset=(0, -8),
                eye_style="surprised",
                paw_style="wide",
                mouth_style="open_o",
            ),
            draw_panda_frame(
                ear_offset=(0, -6),
                eye_style="surprised",
                paw_style="wide",
                head_tilt=2,
                mouth_style="open_o",
            ),
        ],
        "dizzy": [
            draw_panda_frame(
                ear_offset=(-4, 2),
                eye_style="dizzy",
                paw_style="wide",
                head_tilt=-8,
                mouth_style="wavy",
            ),
            draw_panda_frame(
                ear_offset=(4, 2),
                eye_style="dizzy",
                paw_style="wide",
                head_tilt=8,
                mouth_style="wavy",
            ),
        ],
        "recover": [
            draw_panda_frame(
                ear_offset=(2, -2),
                eye_style="blink",
                paw_style="head",
                head_tilt=3,
                mouth_style="smile",
            ),
            draw_panda_frame(
                ear_offset=(0, 0),
                eye_style="normal",
                paw_style="lap",
                head_tilt=0,
                mouth_style="smile",
            ),
        ],
        "curious": [
            draw_panda_frame(
                ear_offset=(4, -4),
                eye_style="alert",
                paw_style="lap",
                head_tilt=7,
                mouth_style="smile",
            ),
            draw_panda_frame(
                ear_offset=(6, -6),
                eye_style="alert",
                paw_style="lap",
                head_tilt=12,
                mouth_style="smile",
            ),
        ],
        "playful": [
            draw_panda_frame(
                ear_offset=(2, -3),
                eye_style="wink",
                paw_style="reach",
                head_tilt=-4,
                mouth_style="smile",
            ),
            draw_panda_frame(
                ear_offset=(-2, -3),
                eye_style="normal",
                paw_style="wide",
                head_tilt=4,
                mouth_style="smile",
            ),
        ],
    }

    for name, frames in animations.items():
        folder = assets_dir / name
        folder.mkdir(parents=True, exist_ok=True)
        for idx, frame in enumerate(frames):
            fn = folder / f"frame_{idx:02d}.png"
            frame.save(str(fn))
            print(f"Saved {fn}")

    print("Milestone 2 expressive animation frames generated successfully!")


if __name__ == "__main__":
    app = QGuiApplication(sys.argv)
    generate_all()
