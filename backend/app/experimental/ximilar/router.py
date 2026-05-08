"""
Экспериментальные маршруты Ximilar. Удаляется вместе с каталогом experimental/ximilar/.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import AdminPrincipal, get_admin_principal
from app.models import PHOTO_SOURCE_YC_OBJECT_STORAGE, Photo
from app.experimental.ximilar.client import detect_tags_all
from app.experimental.ximilar.label_map import (
    map_tags_map_to_catalog,
    map_ximilar_records_to_catalog,
    summarize_ximilar_tags_map,
)

log = logging.getLogger("app.ximilar.router")

router = APIRouter(prefix="/experimental/ximilar", tags=["admin-ximilar-experiment"])


class XimilarMatchedItem(BaseModel):
    tag_id: uuid.UUID
    tag_name: str
    group_slug: str
    source: str


class XimilarObjectBucket(BaseModel):
    """Один детектированный объект одежды — отдельное сопоставление с каталогом."""

    index: int
    summary: str
    prob: float | None = None
    area: float | None = None
    tag_ids: list[uuid.UUID]
    matched: list[XimilarMatchedItem]
    unmapped: list[dict[str, str]] = Field(default_factory=list)


class XimilarSuggestResponse(BaseModel):
    """Слияние всех объектов (как раньше) + разбивка по объектам для выбора в UI."""

    tag_ids: list[uuid.UUID]
    matched: list[XimilarMatchedItem]
    unmapped: list[dict[str, str]] = Field(default_factory=list)
    objects: list[XimilarObjectBucket] = Field(default_factory=list)
    ximilar: dict[str, Any] = Field(
        default_factory=dict,
        description="Полный JSON-ответ Ximilar (для отладки)",
    )


@router.post("/photos/{photo_id}/suggest-tags", response_model=XimilarSuggestResponse)
def ximilar_suggest_tags(
    photo_id: uuid.UUID,
    db: Session = Depends(get_db),
    _principal: AdminPrincipal = Depends(get_admin_principal),
) -> XimilarSuggestResponse:
    _ = _principal
    token = (settings.api_ximilar or "").strip()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Ximilar выключен: задайте API_XIMILAR в окружении",
        )

    photo = db.execute(
        select(Photo).where(Photo.id == photo_id),
    ).scalar_one_or_none()
    if not photo or photo.source_type != PHOTO_SOURCE_YC_OBJECT_STORAGE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    url = (photo.url or "").strip()
    if not url.startswith("http"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="У фото нет публичного URL для Ximilar",
        )

    try:
        raw = detect_tags_all(image_url=url, api_token=token, timeout=90.0)
    except requests.RequestException as e:
        log.warning("ximilar request failed: %s", e)
        msg = str(e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ximilar недоступен: {msg}"[:1500],
        ) from e

    st = raw.get("status") or {}
    if st.get("code") and int(st.get("code")) >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=st.get("text") or "Ximilar status error",
        )

    result = map_ximilar_records_to_catalog(db, raw)

    object_buckets: list[XimilarObjectBucket] = []
    idx = 0
    for rec in raw.get("records") or []:
        for obj in rec.get("_objects") or []:
            tm = obj.get("_tags_map") or {}
            one = map_tags_map_to_catalog(db, tm)
            _pv, _av = obj.get("prob"), obj.get("area")
            object_buckets.append(
                XimilarObjectBucket(
                    index=idx,
                    summary=summarize_ximilar_tags_map(tm),
                    prob=float(_pv) if isinstance(_pv, (int, float)) else None,
                    area=float(_av) if isinstance(_av, (int, float)) else None,
                    tag_ids=one.tag_ids,
                    matched=[XimilarMatchedItem(**m) for m in one.matched],
                    unmapped=one.unmapped,
                )
            )
            idx += 1

    return XimilarSuggestResponse(
        tag_ids=result.tag_ids,
        matched=[XimilarMatchedItem(**m) for m in result.matched],
        unmapped=result.unmapped,
        objects=object_buckets,
        ximilar=raw,
    )
