"""Админка: фото MEN/WOMEN на главной /v2."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import AdminPrincipal, require_permission
from app.models.home_v2_settings import HomeV2Settings
from app.schemas.home_v2 import (
    AdminHomeV2ImageUploadResponse,
    AdminHomeV2SettingsOut,
    AdminHomeV2SettingsPatch,
)
from app.services.home_v2_storage import delete_home_v2_image, save_home_v2_image

log = logging.getLogger("app.api.admin_home_v2")

router = APIRouter(prefix="/admin/home-v2", tags=["admin-home-v2"])

_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}


def _get_or_create(db: Session) -> HomeV2Settings:
    row = db.get(HomeV2Settings, 1)
    if row:
        return row
    row = HomeV2Settings(id=1)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _touch(row: HomeV2Settings) -> None:
    row.updated_at = datetime.now(timezone.utc)


@router.get("/settings", response_model=AdminHomeV2SettingsOut)
def get_home_v2_settings(
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("ads")),
) -> AdminHomeV2SettingsOut:
    _ = _su
    row = _get_or_create(db)
    return AdminHomeV2SettingsOut.model_validate(row)


@router.patch("/settings", response_model=AdminHomeV2SettingsOut)
def patch_home_v2_settings(
    body: AdminHomeV2SettingsPatch,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("ads")),
) -> AdminHomeV2SettingsOut:
    _ = _su
    row = _get_or_create(db)
    if body.clear_image_male and row.image_url_male:
        delete_home_v2_image(row.image_url_male)
        row.image_url_male = None
        _touch(row)
    if body.clear_image_female and row.image_url_female:
        delete_home_v2_image(row.image_url_female)
        row.image_url_female = None
        _touch(row)
    db.commit()
    db.refresh(row)
    return AdminHomeV2SettingsOut.model_validate(row)


@router.post("/settings/image", response_model=AdminHomeV2ImageUploadResponse)
async def upload_home_v2_gender_image(
    file: UploadFile = File(...),
    slot: str = Form(...),
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("ads")),
) -> AdminHomeV2ImageUploadResponse:
    _ = _su
    s = (slot or "").strip().lower()
    if s not in ("male", "female"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="slot: male или female",
        )

    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Допустимые форматы: {', '.join(sorted(_ALLOWED_EXT))}",
        )

    data = await file.read()
    max_bytes = settings.home_v2_max_file_bytes
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Файл больше {max_bytes // (1024 * 1024)} МБ",
        )

    row = _get_or_create(db)
    if s == "male":
        if row.image_url_male:
            delete_home_v2_image(row.image_url_male)
        row.image_url_male = save_home_v2_image("male", ext, data)
    else:
        if row.image_url_female:
            delete_home_v2_image(row.image_url_female)
        row.image_url_female = save_home_v2_image("female", ext, data)
    _touch(row)
    db.commit()
    db.refresh(row)
    log.info("home-v2 %s image uploaded", s)
    return AdminHomeV2ImageUploadResponse(
        image_url_male=row.image_url_male,
        image_url_female=row.image_url_female,
        updated_at=row.updated_at,
    )
