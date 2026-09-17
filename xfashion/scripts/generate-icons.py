#!/usr/bin/env python3
"""Generate raster favicons from brand colors (run after changing favicon.svg concept)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"

BG = (12, 11, 10, 255)
GOLD = (201, 169, 110, 255)
CREAM = (245, 240, 232, 255)
BORDER = (201, 169, 110, 102)


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        p = Path(path)
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def draw_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), BG)
    draw = ImageDraw.Draw(img)
    radius = max(4, round(size * 0.22))
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, outline=BORDER, width=max(1, size // 64))

    font_size = round(size * 0.38)
    font_b = load_font(font_size)
    font_f = load_font(round(font_size * 0.92))

    text_x = "X"
    text_f = "f"
    bbox_x = draw.textbbox((0, 0), text_x, font=font_b)
    bbox_f = draw.textbbox((0, 0), text_f, font=font_f)
    w = (bbox_x[2] - bbox_x[0]) + (bbox_f[2] - bbox_f[0]) - round(size * 0.02)
    h = max(bbox_x[3] - bbox_x[1], bbox_f[3] - bbox_f[1])
    x0 = (size - w) // 2
    y0 = (size - h) // 2 - round(size * 0.02)

    draw.text((x0, y0), text_x, font=font_b, fill=GOLD)
    fx = x0 + (bbox_x[2] - bbox_x[0]) - round(size * 0.03)
    draw.text((fx, y0 + round(size * 0.04)), text_f, font=font_f, fill=CREAM)

    return img


def main() -> None:
    PUBLIC.mkdir(parents=True, exist_ok=True)
    sizes = {
        "favicon-32x32.png": 32,
        "apple-touch-icon.png": 180,
        "icon-192.png": 192,
        "icon-512.png": 512,
    }
    for name, px in sizes.items():
        draw_icon(px).save(PUBLIC / name, format="PNG", optimize=True)

    im32 = draw_icon(32)
    im16 = im32.resize((16, 16), Image.Resampling.LANCZOS)
    im48 = draw_icon(48)
    im16.save(
        PUBLIC / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48)],
        append_images=[im32, im48],
    )
    print("Wrote", ", ".join(sizes.keys()), "and favicon.ico")


if __name__ == "__main__":
    main()
