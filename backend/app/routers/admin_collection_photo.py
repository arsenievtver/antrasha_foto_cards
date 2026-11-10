"""Съёмка новой коллекции: штрихкод → кадр в очередь админки, без Fashn на телефоне."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.deps import AdminPrincipal, require_permission
from app.externals.http.exceptions import ApiClientAbortableException
from app.externals.http.moysklad import MoySkladClient, MoySkladProductRef
from app.models import AiIngestJob, Brand
from app.schemas.collection_photo import (
    CollectionPhotoLookupIn,
    CollectionPhotoLookupOut,
    CollectionPhotoStatusOut,
)
from app.services.brand_match import match_supplier, normalize_moysklad_id

log = logging.getLogger("app.api.collection_photo")

router = APIRouter(prefix="/admin/collection-photo", tags=["admin-collection-photo"])

_MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def _token() -> str:
    token = str(settings.moysklad_token or "").strip()
    if not token:
        raise HTTPException(status_code=503, detail="MOYSKLAD_TOKEN не задан")
    return token


async def _find(barcode: str) -> tuple[MoySkladProductRef, int, str | None]:
    client = MoySkladClient(_token(), keep_session=True)
    try:
        ref = await client.find_by_barcode(barcode)
        images_count, image_preview = await client.product_existing_image_preview(ref.product_id)
        return ref, images_count, image_preview
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ApiClientAbortableException as e:
        detail = e.parsed_response
        msg = str(detail)[:300] if detail else f"МойСклад HTTP {e.response.status}"
        raise HTTPException(status_code=502, detail=f"МойСклад: {msg}") from e
    except HTTPException:
        raise
    except Exception as e:
        log.exception("collection lookup barcode=%s", barcode)
        raise HTTPException(
            status_code=502,
            detail=f"Ошибка поиска в МойСклад: {type(e).__name__}: {e}",
        ) from e
    finally:
        await client.close()


def _lookup_out(
    ref: MoySkladProductRef,
    images_count: int,
    image_preview: str | None,
) -> CollectionPhotoLookupOut:
    db = SessionLocal()
    try:
        brands = list(db.scalars(select(Brand).order_by(Brand.name.asc())).all())
        match = match_supplier(brands, ref.supplier_id, ref.supplier_name)
    finally:
        db.close()
    return CollectionPhotoLookupOut(
        product_id=ref.product_id,
        name=ref.name,
        article=ref.article,
        code=ref.code,
        barcode=ref.barcode,
        path_name=ref.path_name,
        gender=ref.gender,
        supplier_id=ref.supplier_id,
        supplier_name=ref.supplier_name,
        brand_id=match.brand_id,
        brand_name=match.brand_name,
        brand_match=match.confidence,
        brand_warning=match.warning,
        existing_images_count=images_count,
        existing_image_preview=image_preview,
    )


@router.get("/status", response_model=CollectionPhotoStatusOut)
def collection_photo_status(
    _p: AdminPrincipal = Depends(require_permission("collection")),
) -> CollectionPhotoStatusOut:
    _ = _p
    ready = settings.moysklad_configured
    return CollectionPhotoStatusOut(moysklad_configured=ready, ready=ready)


@router.post("/lookup", response_model=CollectionPhotoLookupOut)
async def collection_photo_lookup(
    body: CollectionPhotoLookupIn,
    _p: AdminPrincipal = Depends(require_permission("collection")),
) -> CollectionPhotoLookupOut:
    _ = _p
    barcode = body.barcode.strip()
    if not barcode:
        raise HTTPException(status_code=400, detail="Укажите штрихкод")
    ref, images_count, image_preview = await _find(barcode)
    return _lookup_out(ref, images_count, image_preview)


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def collection_photo_job_create(
    barcode: str = Form(...),
    gender: str = Form(...),
    image: UploadFile = File(...),
    _p: AdminPrincipal = Depends(require_permission("collection")),
) -> dict:
    _ = _p
    g = gender.strip().lower()
    if g not in ("male", "female"):
        raise HTTPException(status_code=400, detail="gender: укажите male или female")
    code = barcode.strip()
    if not code:
        raise HTTPException(status_code=400, detail="Укажите штрихкод")
    raw = await image.read(_MAX_UPLOAD_BYTES + 1)
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="Файл слишком большой")
    if not raw:
        raise HTTPException(status_code=400, detail="Пустой файл изображения")

    ref, _images_count, _preview = await _find(code)
    job_id = uuid.uuid4()
    root = settings.ai_ingest_temp_path
    root.mkdir(parents=True, exist_ok=True)
    dest = (root / f"{job_id}.jpg").resolve()
    dest.write_bytes(raw)

    db = SessionLocal()
    try:
        brands = list(db.scalars(select(Brand)).all())
        match = match_supplier(brands, ref.supplier_id, ref.supplier_name)
        label = (ref.article or ref.name or "collection")[:240]
        job = AiIngestJob(
            id=job_id,
            gender=g,
            source_mode="single",
            brand_id=match.brand_id,
            show_badge=False,
            original_filename=label,
            temp_path=str(dest),
            status="inbox",
            moysklad_product_id=ref.product_id,
            moysklad_supplier_id=normalize_moysklad_id(ref.supplier_id),
            supplier_name=(ref.supplier_name or "")[:200] or None,
            product_name=(ref.name or "")[:500] or None,
            article=(ref.article or "")[:120] or None,
            barcode=(ref.barcode or code)[:64],
            path_name=ref.path_name,
        )
        db.add(job)
        db.commit()
    except Exception:
        db.rollback()
        dest.unlink(missing_ok=True)
        raise
    finally:
        db.close()

    log.info("collection inbox job=%s product=%s gender=%s", job_id, ref.product_id, g)
    return {"id": str(job_id), "status": "inbox"}
