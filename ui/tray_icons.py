"""Иконка tray: загрузка icon.ico или синтез буквы «T» (Pillow)."""
from __future__ import annotations

from pathlib import Path
from typing import Any, List

from PIL import Image, ImageDraw, ImageFont


def _pick_font(size: int, candidates: List[str]) -> Any:
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=int(size * 0.55))
        except Exception:
            continue
    return ImageFont.load_default()


def synthesize_letter_t_icon(size: int, font_candidates: List[str]) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    margin = 2
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=(0, 136, 204, 255),
    )
    font = _pick_font(size, font_candidates)
    bbox = draw.textbbox((0, 0), "T", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = (size - tw) // 2 - bbox[0]
    ty = (size - th) // 2 - bbox[1]
    draw.text((tx, ty), "T", fill=(255, 255, 255, 255), font=font)
    return img


def load_ico_or_synthesize(
    ico_path: Path,
    font_candidates: List[str],
    size: int = 64,
) -> Image.Image:
    if ico_path.exists():
        try:
            return Image.open(str(ico_path))
        except Exception:
            pass
    return synthesize_letter_t_icon(size, font_candidates)
