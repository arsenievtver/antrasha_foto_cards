"""
Бакеты Object Storage — источник истины по составу фото: добавление новых ключей,
деактивация строк в БД, которых уже нет в бакете.

Вызывается из скрипта CLI, фонового цикла API и HTTP /internal/sync-object-storage.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import PHOTO_SOURCE_YC_OBJECT_STORAGE, Brand, Photo
from app.services.yc_storage import get_s3_client, list_image_keys, public_object_url

log = logging.getLogger("app.yc_photo_sync")


@dataclass(frozen=True)
class BucketSyncStats:
    gender: str
    bucket: str
    keys_in_bucket: int
    rows_added: int
    rows_deactivated: int


def sync_bucket_to_db(
    db: Session,
    *,
    settings: Settings,
    bucket: str,
    gender: str,
    prefix: str,
    deactivate_not_in_bucket: bool,
) -> BucketSyncStats:
    client = get_s3_client()
    keys = list_image_keys(client, bucket, prefix)
    added = 0
    existing_urls: set[str] = set()

    for key in keys:
        url = public_object_url(bucket, key)
        existing_urls.add(url)
        row = db.execute(select(Photo).where(Photo.url == url)).scalar_one_or_none()
        if row:
            if row.source_type != PHOTO_SOURCE_YC_OBJECT_STORAGE:
                row.source_type = PHOTO_SOURCE_YC_OBJECT_STORAGE
            if not row.is_active:
                row.is_active = True
            if row.gender != gender:
                row.gender = gender
            continue
        db.add(
            Photo(
                id=uuid.uuid4(),
                url=url,
                gender=gender,
                source_type=PHOTO_SOURCE_YC_OBJECT_STORAGE,
                is_active=True,
            )
        )
        added += 1

    deactivated = 0
    if deactivate_not_in_bucket:
        q = select(Photo).where(
            Photo.gender == gender,
            Photo.source_type == PHOTO_SOURCE_YC_OBJECT_STORAGE,
        )
        for p in db.execute(q).scalars().all():
            if p.url not in existing_urls and p.is_active:
                p.is_active = False
                deactivated += 1

    return BucketSyncStats(
        gender=gender,
        bucket=bucket,
        keys_in_bucket=len(keys),
        rows_added=added,
        rows_deactivated=deactivated,
    )


def ensure_photo_row_for_yc_key(
    db: Session,
    *,
    settings: Settings,
    gender: str,
    bucket: str,
    key: str,
    brand_id: uuid.UUID | None = None,
) -> None:
    """
    Одна запись `photos` для загруженного в бакет ключа (без полного list бакета).
    Логика согласована с sync_bucket_to_db.
    """
    url = public_object_url(bucket, key)
    brand_name: str | None = None
    if brand_id is not None:
        b = db.get(Brand, brand_id)
        if b is not None:
            brand_name = b.name
        else:
            brand_id = None

    row = db.execute(select(Photo).where(Photo.url == url)).scalar_one_or_none()
    if row:
        if row.source_type != PHOTO_SOURCE_YC_OBJECT_STORAGE:
            row.source_type = PHOTO_SOURCE_YC_OBJECT_STORAGE
        if not row.is_active:
            row.is_active = True
        if row.gender != gender:
            row.gender = gender
        if brand_id is not None and brand_name is not None:
            row.brand_id = brand_id
            row.brand = brand_name
        return
    db.add(
        Photo(
            id=uuid.uuid4(),
            url=url,
            gender=gender,
            source_type=PHOTO_SOURCE_YC_OBJECT_STORAGE,
            is_active=True,
            brand_id=brand_id,
            brand=brand_name,
        )
    )


def sync_all_buckets_from_yc(
    db: Session,
    *,
    settings: Settings,
    deactivate_not_in_bucket: bool = True,
) -> tuple[BucketSyncStats, BucketSyncStats]:
    if not settings.yc_s3_configured:
        raise RuntimeError("Yandex Object Storage: не заданы YC_S3_ACCESS_KEY_ID / YC_S3_SECRET_ACCESS_KEY")

    m = sync_bucket_to_db(
        db,
        settings=settings,
        bucket=settings.yc_bucket_men,
        gender="male",
        prefix=settings.yc_s3_prefix_men,
        deactivate_not_in_bucket=deactivate_not_in_bucket,
    )
    f = sync_bucket_to_db(
        db,
        settings=settings,
        bucket=settings.yc_bucket_women,
        gender="female",
        prefix=settings.yc_s3_prefix_women,
        deactivate_not_in_bucket=deactivate_not_in_bucket,
    )
    return m, f


def stats_as_dict(m: BucketSyncStats, f: BucketSyncStats) -> dict[str, Any]:
    return {
        "male": {
            "bucket": m.bucket,
            "keys_in_bucket": m.keys_in_bucket,
            "rows_added": m.rows_added,
            "rows_deactivated": m.rows_deactivated,
        },
        "female": {
            "bucket": f.bucket,
            "keys_in_bucket": f.keys_in_bucket,
            "rows_added": f.rows_added,
            "rows_deactivated": f.rows_deactivated,
        },
    }


def run_sync_job_commit(settings: Settings, *, deactivate_not_in_bucket: bool = True) -> dict[str, Any]:
    """Одна транзакция на полный цикл (для CLI и фона)."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        m, f = sync_all_buckets_from_yc(db, settings=settings, deactivate_not_in_bucket=deactivate_not_in_bucket)
        db.commit()
        out = stats_as_dict(m, f)
        log.info(
            "yc_photo_sync OK male keys=%s +%s ~%s | female keys=%s +%s ~%s",
            m.keys_in_bucket,
            m.rows_added,
            m.rows_deactivated,
            f.keys_in_bucket,
            f.rows_added,
            f.rows_deactivated,
        )
        return out
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
