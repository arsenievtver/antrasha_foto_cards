"""Админка: промо-баннеры на стартовой странице приложения."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import AdminPrincipal, require_superuser
from app.models.promo_banner import PromoBanner
from app.schemas.promo_banner import (
    AdminPromoBannerCreateRequest,
    AdminPromoBannerImageUploadResponse,
    AdminPromoBannerListResponse,
    AdminPromoBannerOut,
    AdminPromoBannerUpdateRequest,
)
from app.services.promo_banner_storage import (
    delete_promo_banner_image,
    save_promo_banner_image,
)

log = logging.getLogger("app.api.admin_promo_banners")

router = APIRouter(prefix="/admin/promo-banners", tags=["admin-promo-banners"])

_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}


@router.get("", response_model=AdminPromoBannerListResponse)
def list_promo_banners(
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
) -> AdminPromoBannerListResponse:
    _ = _su
    rows = db.scalars(
        select(PromoBanner).order_by(
            PromoBanner.priority.desc(),
            PromoBanner.created_at.desc(),
        ),
    ).all()
    return AdminPromoBannerListResponse(
        items=[AdminPromoBannerOut.model_validate(r) for r in rows],
    )


@router.post("", response_model=AdminPromoBannerOut, status_code=status.HTTP_201_CREATED)
def create_promo_banner(
    body: AdminPromoBannerCreateRequest,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
) -> AdminPromoBannerOut:
    _ = _su
    if body.starts_at and body.ends_at and body.ends_at < body.starts_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Дата окончания раньше даты начала",
        )
    row = PromoBanner(
        title=body.title.strip(),
        body=body.body.strip() if body.body else None,
        image_url=body.image_url,
        image_fit=body.image_fit or "fit",
        link_url=body.link_url.strip() if body.link_url else None,
        link_label=body.link_label.strip() if body.link_label else None,
        show_gender_ctas=bool(body.show_gender_ctas),
        cta_male_label=body.cta_male_label.strip() if body.cta_male_label else None,
        cta_female_label=body.cta_female_label.strip() if body.cta_female_label else None,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        display_mode=body.display_mode,
        is_active=body.is_active,
        priority=body.priority,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return AdminPromoBannerOut.model_validate(row)


@router.patch("/{banner_id}", response_model=AdminPromoBannerOut)
def update_promo_banner(
    banner_id: uuid.UUID,
    body: AdminPromoBannerUpdateRequest,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
) -> AdminPromoBannerOut:
    _ = _su
    row = db.get(PromoBanner, banner_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Баннер не найден")

    if body.title is not None:
        row.title = body.title.strip()
    if body.body is not None:
        row.body = body.body.strip() if body.body else None
    if body.image_url is not None:
        if row.image_url and row.image_url != body.image_url:
            delete_promo_banner_image(row.image_url)
        row.image_url = body.image_url or None
    if body.clear_image and row.image_url:
        delete_promo_banner_image(row.image_url)
        row.image_url = None
    if body.image_fit is not None:
        row.image_fit = body.image_fit
    if body.link_url is not None:
        row.link_url = body.link_url.strip() if body.link_url else None
    if body.link_label is not None:
        row.link_label = body.link_label.strip() if body.link_label else None
    if body.show_gender_ctas is not None:
        row.show_gender_ctas = bool(body.show_gender_ctas)
    if body.cta_male_label is not None:
        row.cta_male_label = body.cta_male_label.strip() if body.cta_male_label else None
    if body.cta_female_label is not None:
        row.cta_female_label = body.cta_female_label.strip() if body.cta_female_label else None
    if body.starts_at is not None:
        row.starts_at = body.starts_at
    if body.ends_at is not None:
        row.ends_at = body.ends_at
    if body.display_mode is not None:
        row.display_mode = body.display_mode
    if body.is_active is not None:
        row.is_active = body.is_active
    if body.priority is not None:
        row.priority = body.priority

    if row.starts_at and row.ends_at and row.ends_at < row.starts_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Дата окончания раньше даты начала",
        )

    db.commit()
    db.refresh(row)
    return AdminPromoBannerOut.model_validate(row)


@router.delete("/{banner_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_promo_banner(
    banner_id: uuid.UUID,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
) -> None:
    _ = _su
    row = db.get(PromoBanner, banner_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Баннер не найден")
    if row.image_url:
        delete_promo_banner_image(row.image_url)
    db.delete(row)
    db.commit()


@router.post("/{banner_id}/image", response_model=AdminPromoBannerImageUploadResponse)
async def upload_promo_banner_image(
    banner_id: uuid.UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_superuser),
) -> AdminPromoBannerImageUploadResponse:
    _ = _su
    row = db.get(PromoBanner, banner_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Баннер не найден")

    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Допустимые форматы: {', '.join(sorted(_ALLOWED_EXT))}",
        )

    data = await file.read()
    max_bytes = settings.promo_banner_max_file_bytes
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Файл больше {max_bytes // (1024 * 1024)} МБ",
        )

    if row.image_url:
        delete_promo_banner_image(row.image_url)

    url = save_promo_banner_image(banner_id, ext, data)
    row.image_url = url
    db.commit()
    log.info("promo banner %s image uploaded", banner_id)
    return AdminPromoBannerImageUploadResponse(image_url=url)
