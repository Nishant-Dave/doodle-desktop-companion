"""Render visual validation filmstrips at 160x160 for the Milestone 2 Task 16D expressive pack."""

from __future__ import annotations

import os
from pathlib import Path

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QPainter,
    QPen,
)

BASE_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = BASE_DIR / "assets" / "panda"
OUTPUT_DIR = Path(r"C:\Users\nisha\.gemini\antigravity-ide\brain\8261deba-ab80-4a7a-a643-816a5ca71686")

ANIMATIONS = [
    ("yawn", 8, "Sleepy Yawn: inhale -> rising -> mouth opening -> peak -> ease -> settle -> rest"),
    ("stretch", 8, "Continuous Stretch: crouch -> rise -> paws extend -> peak -> hold -> release -> rest"),
    ("dizzy", 6, "Rotational Wobble: disoriented -> peak left -> center wobble -> peak right -> damped left -> stabilize"),
    ("recover", 4, "Post-Dizzy Settle: slightly dazed -> head shake/blink -> body settle -> exact idle resting pose"),
    ("look_around", 8, "Environmental Awareness: neutral -> eyes left -> head left -> hold -> center -> eyes/head right -> hold -> rest"),
]


def draw_checkerboard(painter: QPainter, rect: QRect, square_size: int = 8) -> None:
    c1 = QColor(245, 245, 250)
    c2 = QColor(230, 230, 238)
    for y in range(rect.top(), rect.bottom(), square_size):
        for x in range(rect.left(), rect.right(), square_size):
            is_even = ((x // square_size) + (y // square_size)) % 2 == 0
            painter.fillRect(x, y, square_size, square_size, c1 if is_even else c2)


def render_strips():
    frame_w, frame_h = 160, 160
    label_h = 32
    padding = 12
    title_h = 40
    row_h = title_h + frame_h + label_h + padding

    max_frames = 8
    total_w = padding * 2 + max_frames * (frame_w + padding)
    total_h = padding * 2 + len(ANIMATIONS) * row_h

    canvas = QImage(total_w, total_h, QImage.Format.Format_ARGB32)
    canvas.fill(QColor(25, 26, 32))  # Dark sleek IDE theme background

    p = QPainter(canvas)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    font_title = QFont("Arial", 11, QFont.Weight.Bold)
    font_sub = QFont("Arial", 9)
    font_frame = QFont("Arial", 9, QFont.Weight.Bold)

    for row_idx, (anim_name, count, desc) in enumerate(ANIMATIONS):
        y_top = padding + row_idx * row_h

        # Title
        p.setFont(font_title)
        p.setPen(QColor(240, 240, 255))
        p.drawText(padding, y_top + 18, f"{anim_name.upper()} ({count} frames)")

        p.setFont(font_sub)
        p.setPen(QColor(170, 175, 195))
        p.drawText(padding + 220, y_top + 18, desc)

        anim_dir = ASSETS_DIR / anim_name
        frames = sorted(anim_dir.glob("frame_*.png"))

        for col_idx in range(count):
            x_left = padding + col_idx * (frame_w + padding)
            frame_y = y_top + title_h

            # Checkerboard frame background
            frame_rect = QRect(x_left, frame_y, frame_w, frame_h)
            p.save()
            p.setClipRect(frame_rect)
            draw_checkerboard(p, frame_rect, 10)
            p.restore()

            # Frame border
            p.setPen(QPen(QColor(70, 75, 95), 1.0))
            p.drawRect(frame_rect)

            # Draw 160x160 scaled panda frame
            if col_idx < len(frames):
                img = QImage(str(frames[col_idx]))
                scaled = img.scaled(
                    frame_w,
                    frame_h,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                p.drawImage(x_left, frame_y, scaled)

            # Frame label
            p.setFont(font_frame)
            p.setPen(QColor(220, 225, 240))
            lbl_rect = QRect(x_left, frame_y + frame_h + 4, frame_w, 20)
            p.drawText(lbl_rect, Qt.AlignmentFlag.AlignCenter, f"Frame {col_idx:02d}")

    p.end()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "visual_validation_16d.png"
    canvas.save(str(out_path))
    print(f"[SAVED] Visual validation sheet saved to {out_path} ({total_w}x{total_h})")


if __name__ == "__main__":
    import sys
    from PySide6.QtGui import QGuiApplication
    _app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    render_strips()
