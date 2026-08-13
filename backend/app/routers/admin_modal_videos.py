"""Админка: библиотека видео для модалки."""

from __future__ import annotations

import logging
import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import AdminPrincipal, require_permission
from app.models.modal_video import ModalVideo
from app.schemas.modal_video import (
    AdminModalVideoCreateRequest,
    AdminModalVideoListResponse,
    AdminModalVideoOut,
    AdminModalVideoUpdateRequest,
    AdminModalVideoUploadResponse,
)
from app.services.modal_video import validate_slug
from app.services.modal_video_storage import (
    delete_modal_poster_file,
    delete_modal_video_file,
    poster_file_path,
    poster_url_for,
    video_file_path,
    video_url_for,
)
from app.services.video_transcode import (
    extract_poster,
    ffmpeg_available,
    transcode_to_mp4,
)

log = logging.getLogger("app.api.admin_modal_videos")

router = APIRouter(prefix="/admin/videos", tags=["admin-videos"])

_ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".webm", ".m4v", ".qt"}
_ALLOWED_POSTER_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def _strip_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    s = value.strip()
    return s or None


def _parse_slug(value: str) -> str:
    try:
        return validate_slug(value)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("", response_model=AdminModalVideoListResponse)
def list_videos(
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("ads")),
) -> AdminModalVideoListResponse:
    _ = _su
    rows = db.scalars(select(ModalVideo).order_by(ModalVideo.created_at.desc())).all()
    return AdminModalVideoListResponse(
        items=[AdminModalVideoOut.model_validate(r) for r in rows],
    )


@router.post("", response_model=AdminModalVideoOut, status_code=status.HTTP_201_CREATED)
def create_video(
    body: AdminModalVideoCreateRequest,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("ads")),
) -> AdminModalVideoOut:
    _ = _su
    row = ModalVideo(
        slug=_parse_slug(body.slug),
        title=body.title.strip(),
        body=_strip_or_none(body.body),
        cta_mode=body.cta_mode,
        cta_label=_strip_or_none(body.cta_label),
        lead_note=_strip_or_none(body.lead_note),
        is_active=body.is_active,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Такой slug уже занят",
        ) from exc
    db.refresh(row)
    return AdminModalVideoOut.model_validate(row)


@router.patch("/{video_id}", response_model=AdminModalVideoOut)
def update_video(
    video_id: uuid.UUID,
    body: AdminModalVideoUpdateRequest,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("ads")),
) -> AdminModalVideoOut:
    _ = _su
    row = db.get(ModalVideo, video_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Видео не найдено")

    if body.slug is not None:
        row.slug = _parse_slug(body.slug)
    if body.title is not None:
        row.title = body.title.strip()
    if body.body is not None:
        row.body = _strip_or_none(body.body)
    if body.cta_mode is not None:
        row.cta_mode = body.cta_mode
    if body.cta_label is not None:
        row.cta_label = _strip_or_none(body.cta_label)
    if body.lead_note is not None:
        row.lead_note = _strip_or_none(body.lead_note)
    if body.is_active is not None:
        row.is_active = body.is_active
    if body.clear_video and row.video_url:
        delete_modal_video_file(row.video_url)
        row.video_url = None
    if body.clear_poster and row.poster_url:
        delete_modal_poster_file(row.poster_url)
        row.poster_url = None

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Такой slug уже занят",
        ) from exc
    db.refresh(row)
    return AdminModalVideoOut.model_validate(row)


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_video(
    video_id: uuid.UUID,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("ads")),
) -> None:
    _ = _su
    row = db.get(ModalVideo, video_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Видео не найдено")
    if row.video_url:
        delete_modal_video_file(row.video_url)
    if row.poster_url:
        delete_modal_poster_file(row.poster_url)
    db.delete(row)
    db.commit()


@router.post("/{video_id}/file", response_model=AdminModalVideoUploadResponse)
async def upload_video_file(
    video_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("ads")),
) -> AdminModalVideoUploadResponse:
    _ = _su
    row = db.get(ModalVideo, video_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Видео не найдено")

    ext = Path(file.filename or "").suffix.lower()
    if ext == ".quicktime":
        ext = ".mov"
    if ext not in _ALLOWED_VIDEO_EXT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Допустимые форматы: {', '.join(sorted(_ALLOWED_VIDEO_EXT))}",
        )

    max_bytes = settings.modal_video_max_file_bytes
    dest = video_file_path(video_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    poster_dest = poster_file_path(video_id)

    with tempfile.TemporaryDirectory(prefix="antrasha-video-") as tmp:
        src = Path(tmp) / f"src{ext}"
        written = 0
        with src.open("wb") as fh:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Файл больше {max_bytes // (1024 * 1024)} МБ",
                    )
                fh.write(chunk)
        if written == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Пустой файл",
            )

        out = Path(tmp) / "out.mp4"
        try:
            if ffmpeg_available():
                transcode_to_mp4(src, out)
            else:
                log.warning("ffmpeg не найден — сохраняем исходник без сжатия")
                out.write_bytes(src.read_bytes())
            dest.write_bytes(out.read_bytes())
        except Exception as exc:
            log.exception("video transcode failed")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Не удалось обработать видео: {exc}",
            ) from exc

        if ffmpeg_available():
            try:
                extract_poster(dest, poster_dest)
            except Exception:
                log.exception("poster extract failed")

    if row.video_url and row.video_url != video_url_for(video_id):
        delete_modal_video_file(row.video_url)
    row.video_url = video_url_for(video_id)
    if poster_dest.is_file():
        row.poster_url = poster_url_for(video_id)

    db.commit()
    log.info("modal video %s uploaded", video_id)
    return AdminModalVideoUploadResponse(
        video_url=row.video_url,
        poster_url=row.poster_url,
    )


@router.post("/{video_id}/poster", response_model=AdminModalVideoUploadResponse)
async def upload_poster(
    video_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("ads")),
) -> AdminModalVideoUploadResponse:
    _ = _su
    row = db.get(ModalVideo, video_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Видео не найдено")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_POSTER_EXT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Постер: {', '.join(sorted(_ALLOWED_POSTER_EXT))}",
        )

    data = await file.read()
    if len(data) > settings.hero_banner_max_file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Постер больше 8 МБ",
        )

    dest = poster_file_path(video_id)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    if row.poster_url and row.poster_url != poster_url_for(video_id):
        delete_modal_poster_file(row.poster_url)
    row.poster_url = poster_url_for(video_id)
    db.commit()
    return AdminModalVideoUploadResponse(
        video_url=row.video_url,
        poster_url=row.poster_url,
    )
