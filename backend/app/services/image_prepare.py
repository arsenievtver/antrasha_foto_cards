"""Подготовка локального файла для Fashn: как в рабочем скрипте — JPEG без перекодирования."""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image

_HEIF_REGISTERED = False


def _register_heif_once() -> None:
    global _HEIF_REGISTERED
    if _HEIF_REGISTERED:
        return
    try:
        from pillow_heif import register_heif_opener

        register_heif_opener()
    except ImportError:
        pass
    _HEIF_REGISTERED = True


def build_fashn_product_image_data_url(path: Path) -> str:
    """
    `product_image` для Fashn: `data:image/jpeg;base64,...`

    Как в рабочем main: для .jpg/.jpeg — сырые байты файла + base64, без PIL
    (меньше тело запроса и быстрее, чем пересохранение через Pillow).
    HEIC/HEIF, PNG, WEBP и т.д. — декодирование и приведение к RGB JPEG.
    """
    ext = path.suffix.lower()
    if ext in (".jpg", ".jpeg"):
        raw = path.read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"

    if ext in (".heic", ".heif"):
        _register_heif_once()

    img = Image.open(path)
    img.load()

    if img.mode == "LA":
        img = img.convert("RGBA")
    if img.mode in ("RGBA",) or (img.mode == "P" and "transparency" in getattr(img, "info", {})):
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[-1])
        img = bg
    elif img.mode == "P":
        img = img.convert("RGB")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92, optimize=True)
    raw = buf.getvalue()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"
