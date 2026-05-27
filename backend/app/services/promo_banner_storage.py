from __future__ import annotations

import uuid
from pathlib import Path

from app.config import settings

_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".avif": "image/avif",
}

# Публичный путь (через nginx/vite proxy /api → backend).
MEDIA_URL_PREFIX = "/api/media/promo-banners"


def promo_banner_media_dir() -> Path:
    d = settings.promo_banner_media_path
    d.mkdir(parents=True, exist_ok=True)
    return d


def _file_path(banner_id: uuid.UUID, ext: str) -> Path:
    return promo_banner_media_dir() / f"{banner_id}{ext}"


def _url_for(banner_id: uuid.UUID, ext: str) -> str:
    return f"{MEDIA_URL_PREFIX}/{banner_id}{ext}"


def save_promo_banner_image(banner_id: uuid.UUID, ext: str, body: bytes) -> str:
    path = _file_path(banner_id, ext)
    path.write_bytes(body)
    return _url_for(banner_id, ext)


def delete_promo_banner_image(url: str) -> None:
    if not url:
        return
    marker = f"{MEDIA_URL_PREFIX}/"
    if marker not in url:
        return
    name = url.split(marker, 1)[-1].split("?", 1)[0]
    if not name or "/" in name or ".." in name:
        return
    path = promo_banner_media_dir() / name
    if path.is_file():
        path.unlink(missing_ok=True)
