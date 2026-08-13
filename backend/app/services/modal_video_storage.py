from __future__ import annotations

import uuid
from pathlib import Path

from app.config import settings

MEDIA_URL_PREFIX = "/api/media/modal-videos"


def modal_video_media_dir() -> Path:
    d = settings.modal_video_media_path
    d.mkdir(parents=True, exist_ok=True)
    return d


def video_file_name(video_id: uuid.UUID) -> str:
    return f"{video_id}.mp4"


def poster_file_name(video_id: uuid.UUID) -> str:
    return f"{video_id}.jpg"


def video_file_path(video_id: uuid.UUID) -> Path:
    return modal_video_media_dir() / video_file_name(video_id)


def poster_file_path(video_id: uuid.UUID) -> Path:
    return modal_video_media_dir() / poster_file_name(video_id)


def video_url_for(video_id: uuid.UUID) -> str:
    return f"{MEDIA_URL_PREFIX}/{video_file_name(video_id)}"


def poster_url_for(video_id: uuid.UUID) -> str:
    return f"{MEDIA_URL_PREFIX}/{poster_file_name(video_id)}"


def _delete_by_url(url: str) -> None:
    if not url:
        return
    marker = f"{MEDIA_URL_PREFIX}/"
    if marker not in url:
        return
    name = url.split(marker, 1)[-1].split("?", 1)[0]
    if not name or "/" in name or ".." in name:
        return
    path = modal_video_media_dir() / name
    if path.is_file():
        path.unlink(missing_ok=True)


def delete_modal_video_file(url: str) -> None:
    _delete_by_url(url)


def delete_modal_poster_file(url: str) -> None:
    _delete_by_url(url)
