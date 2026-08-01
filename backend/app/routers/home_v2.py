"""Публичные настройки главной /v2."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.home_v2_settings import HomeV2Settings
from app.schemas.home_v2 import HomeV2GenderCardsOut

router = APIRouter(prefix="/home-v2", tags=["home-v2"])


@router.get("/gender-cards", response_model=HomeV2GenderCardsOut)
def get_gender_cards(db: Session = Depends(get_db)) -> HomeV2GenderCardsOut:
    row = db.get(HomeV2Settings, 1)
    if not row:
        return HomeV2GenderCardsOut()
    return HomeV2GenderCardsOut.model_validate(row)
