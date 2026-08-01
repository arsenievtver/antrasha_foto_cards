from __future__ import annotations

from pathlib import Path
from typing import Literal

from app.config import settings

MEDIA_URL_PREFIX = "/api/media/home-v2"
Slot = Literal["male", "female"]


def home_v2_media_dir() -> Path:
    d = settings.home_v2_media_path
    d.mkdir(parents=True, exist_ok=True)
    return d


def _file_name(slot: Slot, ext: str) -> str:
    return f"{slot}{ext}"


def save_home_v2_image(slot: Slot, ext: str, body: bytes) -> str:
    path = home_v2_media_dir() / _file_name(slot, ext)
    path.write_bytes(body)
    return f"{MEDIA_URL_PREFIX}/{_file_name(slot, ext)}"


def delete_home_v2_image(url: str | None) -> None:
    if not url:
        return
    marker = f"{MEDIA_URL_PREFIX}/"
    if marker not in url:
        return
    name = url.split(marker, 1)[-1].split("?", 1)[0]
    if not name or "/" in name or ".." in name:
        return
    path = home_v2_media_dir() / name
    if path.is_file():
        path.unlink(missing_ok=True)
