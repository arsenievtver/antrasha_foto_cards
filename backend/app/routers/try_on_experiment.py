"""Эксперимент: виртуальная примерка через FASHN API (скрытая страница в приложении)."""

from __future__ import annotations

import base64
import logging
import time
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_session_or_404, parse_session_id
from app.externals.http.fashn import FashnClient
from app.models import Photo
from app.schemas.try_on_experiment import (
    TryOnCatalogPhotoOut,
    TryOnCatalogResponse,
    TryOnExperimentStatusOut,
    TryOnRunResponse,
)
from app.services.image_prepare import build_fashn_image_data_url_from_bytes
from app.services.weights import touch_session

log = logging.getLogger("app.api.try_on_experiment")

router = APIRouter(prefix="/try-on-experiment", tags=["try-on-experiment"])

_MAX_PERSON_BYTES = 12 * 1024 * 1024
_ALLOWED_CONTENT_PREFIX = "image/"


def _require_fashn() -> None:
    if not settings.fashn_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FASHN_API_KEY не настроен на сервере",
        )


@router.get("/status", response_model=TryOnExperimentStatusOut)
def try_on_status() -> TryOnExperimentStatusOut:
    if settings.fashn_configured:
        return TryOnExperimentStatusOut(enabled=True)
    return TryOnExperimentStatusOut(
        enabled=False,
        message="Примерка недоступна: нет ключа FASHN на сервере",
    )


@router.get("/photos", response_model=TryOnCatalogResponse)
def list_catalog_photos(
    db: Session = Depends(get_db),
    gender: str = Query(..., min_length=1, max_length=10),
    limit: int = Query(48, ge=1, le=80),
    session_id: uuid.UUID = Depends(parse_session_id),
) -> TryOnCatalogResponse:
    _require_fashn()
    get_session_or_404(db, session_id)
    touch_session(db, session_id)
    db.commit()

    g = gender.strip().lower()
    if g not in ("male", "female"):
        raise HTTPException(status_code=400, detail="gender must be male or female")

    rows = db.scalars(
        select(Photo)
        .where(Photo.is_active.is_(True), Photo.gender == g)
        .order_by(Photo.created_at.desc())
        .limit(limit),
    ).all()

    return TryOnCatalogResponse(
        photos=[
            TryOnCatalogPhotoOut(
                id=p.id,
                url=p.url,
                gender=p.gender,
                brand=p.brand,
            )
            for p in rows
        ],
    )


@router.post("/run", response_model=TryOnRunResponse)
async def run_try_on(
    db: Session = Depends(get_db),
    session_id: uuid.UUID = Depends(parse_session_id),
    photo_id: uuid.UUID = Form(...),
    person_image: UploadFile = File(...),
) -> TryOnRunResponse:
    _require_fashn()
    get_session_or_404(db, session_id)
    touch_session(db, session_id)
    db.commit()

    photo = db.get(Photo, photo_id)
    if not photo or not photo.is_active:
        raise HTTPException(status_code=404, detail="Фото образа не найдено")
    if not photo.url or not photo.url.strip():
        raise HTTPException(status_code=400, detail="У образа нет URL")

    ct = (person_image.content_type or "").strip().lower()
    if ct and not ct.startswith(_ALLOWED_CONTENT_PREFIX):
        raise HTTPException(status_code=400, detail="Нужен файл изображения (JPEG, PNG, HEIC…)")

    raw = await person_image.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Пустой файл")
    if len(raw) > _MAX_PERSON_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Фото слишком большое (макс. {_MAX_PERSON_BYTES // (1024 * 1024)} МБ)",
        )

    try:
        model_data_url = build_fashn_image_data_url_from_bytes(raw)
    except Exception as e:
        log.warning("try_on: не удалось обработать фото пользователя: %s", e)
        raise HTTPException(status_code=400, detail="Не удалось прочитать изображение") from e

    garment_url = photo.url.strip()
    log.info(
        "try_on run session=%s photo_id=%s garment_url_len=%s person_b64_len=%s",
        session_id,
        photo_id,
        len(garment_url),
        len(model_data_url),
    )

    t0 = time.monotonic()
    client = FashnClient(
        api_key=str(settings.fashn_api_key).strip(),
        proxy=str(settings.fashn_https_proxy).strip() if settings.fashn_https_proxy else None,
        connect_timeout=settings.fashn_http_connect_timeout,
        submit_timeout=settings.fashn_http_read_timeout_submit,
        poll_timeout=settings.fashn_http_read_timeout_poll,
        download_timeout=settings.fashn_http_read_timeout_download,
    )
    try:
        png = await client.run_tryon_v16(
            model_image=model_data_url,
            garment_image=garment_url,
            garment_photo_type="model",
        )
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail="Fashn: превышено время ожидания") from e
    except Exception as e:
        log.exception("try_on Fashn failed session=%s photo_id=%s", session_id, photo_id)
        raise HTTPException(
            status_code=502,
            detail=f"Ошибка примерки: {type(e).__name__}",
        ) from e
    elapsed = time.monotonic() - t0

    # Отдаём результат как data URL, чтобы не зависеть от срока жизни CDN Fashn.
    b64 = base64.b64encode(png).decode("ascii")
    result_url = f"data:image/png;base64,{b64}"

    log.info(
        "try_on OK session=%s photo_id=%s elapsed=%.1fs png_bytes=%s",
        session_id,
        photo_id,
        elapsed,
        len(png),
    )
    return TryOnRunResponse(
        result_url=result_url,
        photo_id=photo_id,
        elapsed_seconds=round(elapsed, 1),
    )
