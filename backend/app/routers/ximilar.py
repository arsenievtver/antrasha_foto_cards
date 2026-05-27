from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import AdminPrincipal, get_admin_principal
from app.externals.http.exceptions import ApiClientAbortableException
from app.externals.http.ximilar import XimilarClient
from app.models import PHOTO_SOURCE_YC_OBJECT_STORAGE, Photo
from app.schemas.ximilar import XimilarMatchedItem, XimilarObjectBucket, XimilarSuggestResponse
from app.services.ximilar_label_map import map_tags_map, map_ximilar_records, summarize_tags_map

log = logging.getLogger("app.ximilar.router")

router = APIRouter(prefix="/admin/experimental/ximilar", tags=["admin-ximilar-experiment"])


@router.post("/photos/{photo_id}/suggest-tags", response_model=XimilarSuggestResponse)
async def ximilar_suggest_tags(
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

    client = XimilarClient(api_token=token)
    try:
        raw = await client.detect_tags_all(url)
    except ApiClientAbortableException as e:
        log.warning("ximilar request failed: status=%s body=%s", e.response.status, e.parsed_response)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Ximilar недоступен: HTTP {e.response.status}",
        ) from e

    st = raw.get("status") or {}
    if st.get("code") and int(st.get("code")) >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=st.get("text") or "Ximilar status error",
        )

    result = map_ximilar_records(db, raw)

    object_buckets: list[XimilarObjectBucket] = []
    for idx, obj in enumerate(
        obj
        for rec in (raw.get("records") or [])
        for obj in (rec.get("_objects") or [])
    ):
        tm: dict[str, Any] = obj.get("_tags_map") or {}
        one = map_tags_map(db, tm)
        _pv, _av = obj.get("prob"), obj.get("area")
        object_buckets.append(
            XimilarObjectBucket(
                index=idx,
                summary=summarize_tags_map(tm),
                prob=float(_pv) if isinstance(_pv, (int, float)) else None,
                area=float(_av) if isinstance(_av, (int, float)) else None,
                tag_ids=one.tag_ids,
                matched=[XimilarMatchedItem(**m) for m in one.matched],
                unmapped=one.unmapped,
            )
        )

    return XimilarSuggestResponse(
        tag_ids=result.tag_ids,
        matched=[XimilarMatchedItem(**m) for m in result.matched],
        unmapped=result.unmapped,
        objects=object_buckets,
        ximilar=raw,
    )