"""Подготовка локального файла для Fashn: как в рабочем скрипте — JPEG без перекодирования."""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image, ImageOps

# Большой JSON с base64 на POST /v1/run часто рвёт TLS (UNEXPECTED_EOF_WHILE_READING).
_JPEG_REENCODE_IF_LARGER_THAN_BYTES = 2_500_000
_JPEG_MAX_LONG_EDGE_PX = 2048
_JPEG_REENCODE_QUALITY = 88

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


def _apply_exif_orientation(img: Image.Image) -> Image.Image:
    """Снимки с телефона часто лежат «боком» в пикселях, ориентация — в EXIF."""
    try:
        return ImageOps.exif_transpose(img)
    except Exception:
        return img


def _image_to_rgb(img: Image.Image) -> Image.Image:
    if img.mode == "LA":
        img = img.convert("RGBA")
    if img.mode in ("RGBA",) or (img.mode == "P" and "transparency" in getattr(img, "info", {})):
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[-1])
        return bg
    if img.mode == "P":
        return img.convert("RGB")
    if img.mode == "L":
        return img.convert("RGB")
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def _resize_long_edge(img: Image.Image, max_px: int = _JPEG_MAX_LONG_EDGE_PX) -> Image.Image:
    w, h = img.size
    m = max(w, h)
    if m <= max_px:
        return img
    scale = max_px / m
    new_w = max(1, int(w * scale))
    new_h = max(1, int(h * scale))
    return img.resize((new_w, new_h), Image.Resampling.LANCZOS)


def _reencode_jpeg_smaller_for_transport(raw: bytes) -> bytes:
    """Уменьшает разрешение/вес JPEG для стабильного HTTPS POST на api.fashn.ai."""
    img = Image.open(io.BytesIO(raw))
    img.load()
    img = _apply_exif_orientation(img)
    img = _image_to_rgb(img)
    img = _resize_long_edge(img)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=_JPEG_REENCODE_QUALITY, optimize=True)
    return buf.getvalue()


def normalize_png_bytes(png_bytes: bytes) -> bytes:
    """PNG от Fashn → с корректной ориентацией и без лишнего EXIF."""
    img = Image.open(io.BytesIO(png_bytes))
    img.load()
    img = _apply_exif_orientation(img)
    img = _image_to_rgb(img)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def build_fashn_image_data_url_from_bytes(raw: bytes) -> tuple[str, tuple[int, int]]:
    """Фото пользователя → JPEG data URL для Fashn. Возвращает (url, (width, height))."""
    _register_heif_once()
    img = Image.open(io.BytesIO(raw))
    img.load()
    img = _apply_exif_orientation(img)
    img = _image_to_rgb(img)
    img = _resize_long_edge(img)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92, optimize=True)
    jpeg = buf.getvalue()
    b64 = base64.b64encode(jpeg).decode("ascii")
    return f"data:image/jpeg;base64,{b64}", img.size


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
        if len(raw) > _JPEG_REENCODE_IF_LARGER_THAN_BYTES:
            raw = _reencode_jpeg_smaller_for_transport(raw)
        b64 = base64.b64encode(raw).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"

    if ext in (".heic", ".heif"):
        _register_heif_once()

    img = Image.open(path)
    img.load()
    img = _apply_exif_orientation(img)

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


def png_bytes_to_webp(png_bytes: bytes, *, quality: int = 100) -> bytes:
    """PNG от Fashn → WebP для загрузки в Object Storage (качество 0–100, по умолчанию 100)."""
    img = Image.open(io.BytesIO(png_bytes))
    img.load()
    if img.mode == "P":
        img = img.convert("RGBA")
    elif img.mode == "LA":
        img = img.convert("RGBA")
    elif img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    out = io.BytesIO()
    img.save(out, format="WEBP", quality=quality, method=6)
    return out.getvalue()
