from __future__ import annotations

import uuid
from pathlib import Path
from typing import Literal

from app.config import settings

_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".avif": "image/avif",
}

MEDIA_URL_PREFIX = "/api/media/hero-banners"
Variant = Literal["mobile", "desktop"]


def hero_banner_media_dir() -> Path:
    d = settings.hero_banner_media_path
    d.mkdir(parents=True, exist_ok=True)
    return d


def _file_name(banner_id: uuid.UUID, ext: str, variant: Variant) -> str:
    suffix = "-desktop" if variant == "desktop" else ""
    return f"{banner_id}{suffix}{ext}"


def _file_path(banner_id: uuid.UUID, ext: str, variant: Variant) -> Path:
    return hero_banner_media_dir() / _file_name(banner_id, ext, variant)


def _url_for(banner_id: uuid.UUID, ext: str, variant: Variant) -> str:
    return f"{MEDIA_URL_PREFIX}/{_file_name(banner_id, ext, variant)}"


def save_hero_banner_image(
    banner_id: uuid.UUID,
    ext: str,
    body: bytes,
    *,
    variant: Variant = "mobile",
) -> str:
    path = _file_path(banner_id, ext, variant)
    path.write_bytes(body)
    return _url_for(banner_id, ext, variant)


def delete_hero_banner_image(url: str) -> None:
    if not url:
        return
    marker = f"{MEDIA_URL_PREFIX}/"
    if marker not in url:
        return
    name = url.split(marker, 1)[-1].split("?", 1)[0]
    if not name or "/" in name or ".." in name:
        return
    path = hero_banner_media_dir() / name
    if path.is_file():
        path.unlink(missing_ok=True)
