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


def collection_product_ids(job: AiIngestJob) -> list[str]:
    """Все product_id комплекта: основной + linked_products, без дублей."""
    ids: list[str] = []
    primary = (job.moysklad_product_id or "").strip()
    if primary:
        ids.append(primary)
    for item in job.linked_products or []:
        if not isinstance(item, dict):
            continue
        pid = str(item.get("product_id") or "").strip()
        if pid and pid not in ids:
            ids.append(pid)
    return ids


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


async def upload_catalog_png_to_products(
    product_ids: list[str],
    png: bytes,
    *,
    filename: str,
) -> None:
    """Одно фото на все карточки комплекта. При частичном сбое — исключение со списком."""
    if not product_ids:
        return
    errors: list[str] = []
    for product_id in product_ids:
        try:
            await upload_catalog_png(product_id, png, filename=filename)
        except Exception as e:
            errors.append(f"{product_id}: {type(e).__name__}: {e}")
            log.warning("moysklad image product=%s: %s", product_id, e)
    if errors:
        raise RuntimeError("; ".join(errors)[:2000])


def upload_catalog_png_to_products_sync(
    product_ids: list[str],
    png: bytes,
    *,
    filename: str,
) -> None:
    asyncio.run(upload_catalog_png_to_products(product_ids, png, filename=filename))


def record_moysklad_upload(
    db: Session,
    job: AiIngestJob,
    *,
    photo_id,
    png: bytes,
) -> None:
    """Пишет PNG во все карточки комплекта. Неуспех остаётся на задаче, фото каталога не трогает."""
    product_ids = collection_product_ids(job)
    if not product_ids:
        return
    filename = f"collection-{job.id.hex[:12]}.png"
    try:
        upload_catalog_png_to_products_sync(product_ids, png, filename=filename)
    except Exception as e:
        log.warning(
            "moysklad image job=%s products=%s: %s",
            job.id,
            product_ids,
            e,
        )
        job.moysklad_upload_status = "failed"
        job.moysklad_upload_error = f"{type(e).__name__}: {e}"[:2000]
        db.commit()
        return
    photo = db.get(Photo, photo_id)
    if photo is not None:
        photo.moy_sklad_id = product_ids[0][:128]
    job.moysklad_upload_status = "uploaded"
    job.moysklad_upload_error = None
    db.commit()
