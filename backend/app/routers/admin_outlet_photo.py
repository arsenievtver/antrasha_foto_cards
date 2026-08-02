"""Админка: аутлет — штрихкод → Fashn catalog → изображение в МойСклад."""

from __future__ import annotations

import base64
import logging
import re
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.config import settings
from app.deps import AdminPrincipal, require_permission
from app.externals.http.exceptions import ApiClientAbortableException
from app.externals.http.fashn import SOURCE_MODE_OUTLET_CATALOG, FashnClient
from app.externals.http.moysklad import MoySkladClient
from app.schemas.outlet_photo import (
    OutletPhotoGenerateOut,
    OutletPhotoLookupIn,
    OutletPhotoLookupOut,
    OutletPhotoStatusOut,
    OutletPhotoUploadIn,
    OutletPhotoUploadOut,
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
    _p: AdminPrincipal = Depends(require_permission("outlet")),
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

    return OutletPhotoUploadOut(
        product_id=product_id,
        images_count=len(images),
        images=images,
    )
