"""Кадр Fashn → изображение товара в МойСклад. Ошибка не откатывает фото каталога."""

from __future__ import annotations

import asyncio
import base64
import logging

from sqlalchemy.orm import Session

from app.config import settings
from app.externals.http.moysklad import MoySkladClient
from app.models import AiIngestJob, Photo

log = logging.getLogger("app.moysklad_image")


async def upload_catalog_png(product_id: str, png: bytes, *, filename: str) -> None:
    token = str(settings.moysklad_token or "").strip()
    if not token:
        raise RuntimeError("MOYSKLAD_TOKEN не задан")
    if not png:
        raise RuntimeError("пустой файл для МойСклад")
    client = MoySkladClient(token)
    try:
        await client.upload_product_image(
            product_id,
            filename=filename,
            content_b64=base64.b64encode(png).decode("ascii"),
        )
    finally:
        await client.close()


def upload_catalog_png_sync(product_id: str, png: bytes, *, filename: str) -> None:
    asyncio.run(upload_catalog_png(product_id, png, filename=filename))


def record_moysklad_upload(
    db: Session,
    job: AiIngestJob,
    *,
    photo_id,
    png: bytes,
) -> None:
    """Пишет PNG в карточку товара. Неуспех остаётся на задаче, фото каталога не трогает."""
    product_id = (job.moysklad_product_id or "").strip()
    if not product_id:
        return
    filename = f"collection-{job.id.hex[:12]}.png"
    try:
        upload_catalog_png_sync(product_id, png, filename=filename)
    except Exception as e:
        log.warning(
            "moysklad image job=%s product=%s: %s",
            job.id,
            product_id,
            e,
        )
        job.moysklad_upload_status = "failed"
        job.moysklad_upload_error = f"{type(e).__name__}: {e}"[:2000]
        db.commit()
        return
    photo = db.get(Photo, photo_id)
    if photo is not None:
        photo.moy_sklad_id = product_id[:128]
    job.moysklad_upload_status = "uploaded"
    job.moysklad_upload_error = None
    db.commit()
