"""Публичные hero-баннеры стартовой страницы."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.hero_banner import HeroBannerActiveResponse, HeroBannerPublicOut
from app.services.hero_banner import list_active_hero_banners

router = APIRouter(prefix="/hero-banners", tags=["hero-banners"])


@router.get("/active", response_model=HeroBannerActiveResponse)
def get_active_hero_banners(db: Session = Depends(get_db)) -> HeroBannerActiveResponse:
    rows = list_active_hero_banners(db)
    return HeroBannerActiveResponse(
        items=[HeroBannerPublicOut.model_validate(r) for r in rows],
    )
