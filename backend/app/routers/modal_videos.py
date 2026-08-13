"""Публичные ролики для модалки /watch/{slug}."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.modal_video import ModalVideoPublicOut
from app.services.modal_video import get_active_by_slug

router = APIRouter(prefix="/videos", tags=["videos"])


@router.get("/{slug}", response_model=ModalVideoPublicOut)
def get_video_by_slug(slug: str, db: Session = Depends(get_db)) -> ModalVideoPublicOut:
    row = get_active_by_slug(db, slug)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Видео не найдено")
    return ModalVideoPublicOut.model_validate(row)
