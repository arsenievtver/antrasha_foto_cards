"""Публичный список брендов (лента на главной)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.brand import Brand

router = APIRouter(prefix="/brands", tags=["brands"])


class BrandPublicOut(BaseModel):
    name: str


class BrandPublicListResponse(BaseModel):
    items: list[BrandPublicOut]


@router.get("", response_model=BrandPublicListResponse)
def list_public_brands(
    response: Response,
    db: Session = Depends(get_db),
) -> BrandPublicListResponse:
    rows = db.scalars(select(Brand.name).order_by(Brand.name.asc())).all()
    # Короткий кэш — список меняется редко, нагрузка нулевая
    response.headers["Cache-Control"] = "public, max-age=300"
    return BrandPublicListResponse(items=[BrandPublicOut(name=n) for n in rows])
