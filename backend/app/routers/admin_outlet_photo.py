"""Админка: аутлет — штрихкод → Fashn catalog → изображение в МойСклад."""

from __future__ import annotations

import base64
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import AdminPrincipal, require_permission
from app.externals.http.exceptions import ApiClientAbortableException
from app.externals.http.fashn import SOURCE_MODE_OUTLET_CATALOG, FashnClient
from app.externals.http.moysklad import MoySkladClient
from app.models.outlet_photo_upload import OutletPhotoUpload
from app.schemas.outlet_photo import (
    OutletPhotoGenerateOut,
    OutletPhotoLookupIn,
    OutletPhotoLookupOut,
    OutletPhotoStatusOut,
    OutletPhotoUploadIn,
    OutletPhotoUploadItemOut,
    OutletPhotoUploadListOut,
    OutletPhotoUploadOut,
    OutletPhotoUploadTransferredIn,
)
from app.services.image_prepare import build_fashn_image_data_url_from_bytes, normalize_png_bytes

log = logging.getLogger("app.api.admin_outlet_photo")

router = APIRouter(prefix="/admin/outlet-photo", tags=["admin-outlet-photo"])

_MAX_UPLOAD_BYTES = 35 * 1024 * 1024
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _moysklad_token() -> str | None:
    token = settings.moysklad_token
    if token and str(token).strip():
        return str(token).strip()
    return None


def _fashn_key() -> str | None:
    key = settings.fashn_api_key
    if key and str(key).strip():
        return str(key).strip()
    return None


def _require_moysklad() -> str:
    token = _moysklad_token()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="MOYSKLAD_TOKEN не задан в окружении сервера",
        )
    return token


def _require_fashn() -> str:
    key = _fashn_key()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FASHN_API_KEY не задан в окружении сервера",
        )
    return key


def _uploader_identity(principal: AdminPrincipal) -> tuple[uuid.UUID | None, str]:
    if principal.role == "superuser" or principal.user is None:
        return None, "Суперпользователь"
    user = principal.user
    label = (user.display_name or "").strip() or user.phone
    return user.id, label


def _upload_item_out(row: OutletPhotoUpload) -> OutletPhotoUploadItemOut:
    return OutletPhotoUploadItemOut(
        id=row.id,
        product_id=row.product_id,
        product_name=row.product_name,
        article=row.article,
        code=row.code,
        barcode=row.barcode,
        path_name=row.path_name,
        gender=row.gender,
        uploaded_by_user_id=row.uploaded_by_user_id,
        uploaded_by_label=row.uploaded_by_label,
        transferred=row.transferred,
        transferred_at=row.transferred_at,
        created_at=row.created_at,
    )


@router.get("/status", response_model=OutletPhotoStatusOut)
def outlet_photo_status(
    _p: AdminPrincipal = Depends(require_permission("outlet")),
) -> OutletPhotoStatusOut:
    ms = bool(_moysklad_token())
    fashn = bool(_fashn_key())
    return OutletPhotoStatusOut(
        moysklad_configured=ms,
        fashn_configured=fashn,
        ready=ms and fashn,
    )


@router.get("/uploads", response_model=OutletPhotoUploadListOut)
def list_outlet_photo_uploads(
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(require_permission("outlet_transfer")),
    filter: Literal["pending", "transferred", "all"] = Query(
        "pending",
        description="pending = не перенесённые (по умолчанию)",
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> OutletPhotoUploadListOut:
    _ = _p
    q = select(OutletPhotoUpload)
    count_q = select(func.count()).select_from(OutletPhotoUpload)
    if filter == "pending":
        q = q.where(OutletPhotoUpload.transferred.is_(False))
        count_q = count_q.where(OutletPhotoUpload.transferred.is_(False))
    elif filter == "transferred":
        q = q.where(OutletPhotoUpload.transferred.is_(True))
        count_q = count_q.where(OutletPhotoUpload.transferred.is_(True))

    total = db.scalar(count_q) or 0
    rows = db.scalars(
        q.order_by(OutletPhotoUpload.created_at.desc()).offset(skip).limit(limit),
    ).all()
    return OutletPhotoUploadListOut(
        items=[_upload_item_out(r) for r in rows],
        total=int(total),
        skip=skip,
        limit=limit,
        filter=filter,
    )


@router.patch("/uploads/{upload_id}", response_model=OutletPhotoUploadItemOut)
def patch_outlet_photo_upload(
    upload_id: uuid.UUID,
    body: OutletPhotoUploadTransferredIn,
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(require_permission("outlet_transfer")),
) -> OutletPhotoUploadItemOut:
    _ = _p
    row = db.get(OutletPhotoUpload, upload_id)
    if not row:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    row.transferred = body.transferred
    row.transferred_at = (
        datetime.now(timezone.utc) if body.transferred else None
    )
    db.commit()
    db.refresh(row)
    return _upload_item_out(row)


@router.post("/lookup", response_model=OutletPhotoLookupOut)
async def outlet_photo_lookup(
    body: OutletPhotoLookupIn,
    _p: AdminPrincipal = Depends(require_permission("outlet")),
) -> OutletPhotoLookupOut:
    token = _require_moysklad()
    barcode = body.barcode.strip()
    if not barcode:
        raise HTTPException(status_code=400, detail="Укажите штрихкод")

    client = MoySkladClient(token)
    try:
        ref = await client.find_by_barcode(barcode)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ApiClientAbortableException as e:
        detail = e.parsed_response
        msg = str(detail)[:300] if detail else f"МойСклад HTTP {e.response.status}"
        raise HTTPException(status_code=502, detail=f"МойСклад: {msg}") from e
    except Exception as e:
        log.exception("outlet lookup barcode=%s", barcode)
        raise HTTPException(
            status_code=502,
            detail=f"Ошибка поиска в МойСклад: {type(e).__name__}: {e}",
        ) from e
    finally:
        await client.close()

    return OutletPhotoLookupOut(
        product_id=ref.product_id,
        name=ref.name,
        article=ref.article,
        code=ref.code,
        barcode=ref.barcode,
        entity_type=ref.entity_type,
        variant_id=ref.variant_id,
        path_name=ref.path_name,
        gender=ref.gender,
    )


@router.post("/generate", response_model=OutletPhotoGenerateOut)
async def outlet_photo_generate(
    gender: str = Form(...),
    image: UploadFile = File(...),
    _p: AdminPrincipal = Depends(require_permission("outlet")),
) -> OutletPhotoGenerateOut:
    _require_moysklad()  # flow always needs MS later; fail early if misconfigured
    api_key = _require_fashn()

    g = gender.strip().lower()
    if g not in ("male", "female"):
        raise HTTPException(status_code=400, detail="gender: укажите male или female")

    raw = await image.read(_MAX_UPLOAD_BYTES + 1)
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Файл слишком большой (макс {_MAX_UPLOAD_BYTES // (1024 * 1024)} МБ)",
        )
    if not raw:
        raise HTTPException(status_code=400, detail="Пустой файл изображения")

    try:
        data_url, _size = build_fashn_image_data_url_from_bytes(raw)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Не удалось прочитать изображение: {e}",
        ) from e

    proxy = str(settings.fashn_https_proxy).strip() if settings.fashn_https_proxy else None
    client = FashnClient(
        api_key=api_key,
        proxy=proxy,
        connect_timeout=settings.fashn_http_connect_timeout,
        submit_timeout=settings.fashn_http_read_timeout_submit,
        poll_timeout=settings.fashn_http_read_timeout_poll,
        download_timeout=settings.fashn_http_read_timeout_download,
    )
    try:
        png_bytes = await client.run_product_to_model(
            gender=g,
            product_image_data_url=data_url,
            source_mode=SOURCE_MODE_OUTLET_CATALOG,
        )
        png_bytes = normalize_png_bytes(png_bytes)
    except Exception as e:
        log.warning("outlet generate failed: %s: %s", type(e).__name__, e, exc_info=True)
        raise HTTPException(
            status_code=502,
            detail=f"Fashn: {type(e).__name__}: {e}",
        ) from e

    b64 = base64.b64encode(png_bytes).decode("ascii")
    fname = f"outlet-{uuid.uuid4().hex[:12]}.png"
    return OutletPhotoGenerateOut(image_base64=b64, mime="image/png", filename=fname)


@router.post("/upload", response_model=OutletPhotoUploadOut)
async def outlet_photo_upload(
    body: OutletPhotoUploadIn,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(require_permission("outlet")),
) -> OutletPhotoUploadOut:
    token = _require_moysklad()
    product_id = body.product_id.strip()
    if not _UUID_RE.match(product_id):
        raise HTTPException(status_code=400, detail="product_id: ожидается UUID товара МойСклад")

    filename = body.filename.strip() or f"outlet-{uuid.uuid4().hex[:8]}.png"
    if "." not in filename:
        filename = f"{filename}.png"

    client = MoySkladClient(token)
    try:
        images = await client.upload_product_image(
            product_id,
            filename=filename,
            content_b64=body.content,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ApiClientAbortableException as e:
        detail = e.parsed_response
        msg = str(detail)[:300] if detail else f"МойСклад HTTP {e.response.status}"
        raise HTTPException(status_code=502, detail=f"МойСклад: {msg}") from e
    except Exception as e:
        log.exception("outlet upload product=%s", product_id)
        raise HTTPException(
            status_code=502,
            detail=f"Ошибка загрузки в МойСклад: {type(e).__name__}: {e}",
        ) from e
    finally:
        await client.close()

    user_id, label = _uploader_identity(principal)
    gender = (body.gender or "").strip().lower() or None
    if gender not in ("male", "female", None):
        gender = None

    row = OutletPhotoUpload(
        product_id=product_id,
        product_name=(body.name or "").strip() or "Без названия",
        article=(body.article or "").strip() or None,
        code=(body.code or "").strip() or None,
        barcode=(body.barcode or "").strip() or None,
        path_name=(body.path_name or "").strip() or None,
        gender=gender,
        uploaded_by_user_id=user_id,
        uploaded_by_label=label,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return OutletPhotoUploadOut(
        product_id=product_id,
        images_count=len(images),
        images=images,
        upload_id=row.id,
    )
