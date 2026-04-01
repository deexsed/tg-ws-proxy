"""Иконка tray: бейдж статуса на базе основной иконки."""
from __future__ import annotations

from typing import Tuple

from PIL import Image, ImageDraw


def _resample_lanczos() -> int:
    try:
        return Image.Resampling.LANCZOS  # type: ignore[attr-defined]
    except AttributeError:
        return Image.LANCZOS


def normalize_tray_icon_image(img: Image.Image, size: int = 64) -> Image.Image:
    """RGBA и единый размер для стабильного отрисовывания бейджа."""
    im = img
    try:
        n = getattr(im, "n_frames", 1)
        if n > 1:
            best = None
            best_area = 0
            for i in range(n):
                im.seek(i)
                w, h = im.size
                area = w * h
                if area > best_area:
                    best_area = area
                    best = im.copy()
            im = best if best is not None else im.copy()
        else:
            im = im.copy()
    except Exception:
        im = img.copy()
    im = im.convert("RGBA")
    if im.size != (size, size):
        im = im.resize((size, size), _resample_lanczos())
    return im


def badge_rgb_for_phase(phase: str) -> Tuple[int, int, int]:
    if phase == "listening":
        return (34, 197, 94)
    if phase == "error":
        return (239, 68, 68)
    return (234, 179, 8)


def apply_status_badge(base: Image.Image, phase: str) -> Image.Image:
    """Круглый индикатор внизу справа (как бейдж уведомления)."""
    img = base.copy()
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    w, h = img.size
    rgb = badge_rgb_for_phase(phase)
    r = max(4, min(w, h) // 7)
    margin = max(1, min(w, h) // 18)
    cx = w - margin - r
    cy = h - margin - r
    draw = ImageDraw.Draw(img)
    draw.ellipse([cx - r + 1, cy - r + 1, cx + r + 1, cy + r + 1], fill=(0, 0, 0, 70))
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=rgb + (255,))
    border_w = max(1, r // 5)
    draw.ellipse(
        [cx - r, cy - r, cx + r, cy + r],
        outline=(255, 255, 255, 230),
        width=border_w,
    )
    return img
