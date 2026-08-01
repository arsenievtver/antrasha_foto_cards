"""Админка: полноэкранные hero-баннеры стартовой страницы."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import AdminPrincipal, require_permission
from app.models.hero_banner import HeroBanner
from app.schemas.hero_banner import (
    AdminHeroBannerCreateRequest,
    AdminHeroBannerImageUploadResponse,
    AdminHeroBannerListResponse,
    AdminHeroBannerOut,
    AdminHeroBannerUpdateRequest,
)
from app.services.hero_banner_storage import (
    delete_hero_banner_image,
    save_hero_banner_image,
)

log = logging.getLogger("app.api.admin_hero_banners")

router = APIRouter(prefix="/admin/hero-banners", tags=["admin-hero-banners"])

_ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}


def _strip_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    s = value.strip()
    return s or None


@router.get("", response_model=AdminHeroBannerListResponse)
def list_hero_banners(
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("ads")),
) -> AdminHeroBannerListResponse:
    _ = _su
    rows = db.scalars(
        select(HeroBanner).order_by(
            HeroBanner.priority.desc(),
            HeroBanner.created_at.desc(),
        ),
    ).all()
    return AdminHeroBannerListResponse(
        items=[AdminHeroBannerOut.model_validate(r) for r in rows],
    )


@router.post("", response_model=AdminHeroBannerOut, status_code=status.HTTP_201_CREATED)
def create_hero_banner(
    body: AdminHeroBannerCreateRequest,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("ads")),
) -> AdminHeroBannerOut:
    _ = _su
    if body.starts_at and body.ends_at and body.ends_at < body.starts_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Дата окончания раньше даты начала",
        )
    row = HeroBanner(
        title=body.title.strip(),
        subtitle=_strip_or_none(body.subtitle),
        body=_strip_or_none(body.body),
        image_url=body.image_url,
        image_url_desktop=body.image_url_desktop,
        link_url=_strip_or_none(body.link_url),
        link_label=_strip_or_none(body.link_label),
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        is_active=body.is_active,
        priority=body.priority,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return AdminHeroBannerOut.model_validate(row)


@router.patch("/{banner_id}", response_model=AdminHeroBannerOut)
def update_hero_banner(
    banner_id: uuid.UUID,
    body: AdminHeroBannerUpdateRequest,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("ads")),
) -> AdminHeroBannerOut:
    _ = _su
    row = db.get(HeroBanner, banner_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Баннер не найден")

    if body.title is not None:
        row.title = body.title.strip()
    if body.subtitle is not None:
        row.subtitle = _strip_or_none(body.subtitle)
    if body.body is not None:
        row.body = _strip_or_none(body.body)
    if body.image_url is not None:
        if row.image_url and row.image_url != body.image_url:
            delete_hero_banner_image(row.image_url)
        row.image_url = body.image_url or None
    if body.image_url_desktop is not None:
        if row.image_url_desktop and row.image_url_desktop != body.image_url_desktop:
            delete_hero_banner_image(row.image_url_desktop)
        row.image_url_desktop = body.image_url_desktop or None
    if body.clear_image and row.image_url:
        delete_hero_banner_image(row.image_url)
        row.image_url = None
    if body.clear_image_desktop and row.image_url_desktop:
        delete_hero_banner_image(row.image_url_desktop)
        row.image_url_desktop = None
    if body.link_url is not None:
        row.link_url = _strip_or_none(body.link_url)
    if body.link_label is not None:
        row.link_label = _strip_or_none(body.link_label)
    if body.starts_at is not None:
        row.starts_at = body.starts_at
    if body.ends_at is not None:
        row.ends_at = body.ends_at
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
    return AdminHeroBannerOut.model_validate(row)


@router.delete("/{banner_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_hero_banner(
    banner_id: uuid.UUID,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("ads")),
) -> None:
    _ = _su
    row = db.get(HeroBanner, banner_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Баннер не найден")
    if row.image_url:
        delete_hero_banner_image(row.image_url)
    if row.image_url_desktop:
        delete_hero_banner_image(row.image_url_desktop)
    db.delete(row)
    db.commit()


@router.post("/{banner_id}/image", response_model=AdminHeroBannerImageUploadResponse)
async def upload_hero_banner_image(
    banner_id: uuid.UUID,
    file: UploadFile = File(...),
    variant: str = Form("mobile"),
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("ads")),
) -> AdminHeroBannerImageUploadResponse:
    _ = _su
    row = db.get(HeroBanner, banner_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Баннер не найден")

    v = (variant or "mobile").strip().lower()
    if v not in ("mobile", "desktop"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="variant: mobile или desktop",
        )

    ext = Path(file.filename or "").suffix.lower()
    if ext not in _ALLOWED_EXT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Допустимые форматы: {', '.join(sorted(_ALLOWED_EXT))}",
        )

    data = await file.read()
    max_bytes = settings.hero_banner_max_file_bytes
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Файл больше {max_bytes // (1024 * 1024)} МБ",
        )

    if v == "desktop":
        if row.image_url_desktop:
            delete_hero_banner_image(row.image_url_desktop)
        url = save_hero_banner_image(banner_id, ext, data, variant="desktop")
        row.image_url_desktop = url
    else:
        if row.image_url:
            delete_hero_banner_image(row.image_url)
        url = save_hero_banner_image(banner_id, ext, data, variant="mobile")
        row.image_url = url

    db.commit()
    log.info("hero banner %s %s image uploaded", banner_id, v)
    return AdminHeroBannerImageUploadResponse(
        image_url=row.image_url,
        image_url_desktop=row.image_url_desktop,
    )
