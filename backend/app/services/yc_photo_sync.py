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

from sqlalchemy import delete, func, select
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
    # Полностью удалены из БД (каскадно зачищаются photo_tags/interactions,
    # fitting_requests.photo_id ← NULL). Используется только при purge=True.
    rows_purged: int = 0
    # True, если бакет вернул 0 ключей при наличии существующих строк в БД для
    # этого пола: вероятный сбой/неверный prefix — БД оставляем как есть.
    safety_skip: bool = False


def sync_bucket_to_db(
    db: Session,
    *,
    settings: Settings,
    bucket: str,
    gender: str,
    prefix: str,
    deactivate_not_in_bucket: bool,
    purge_not_in_bucket: bool = False,
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

    # Защита от случайного «обнуления»: если бакет вдруг вернул 0 ключей, но
    # в БД есть записи для этого пола — почти наверняка это временный сбой
    # (неверный prefix, RO-ошибка ключа, частичная недоступность). Не трогаем БД.
    safety_skip = False
    if (deactivate_not_in_bucket or purge_not_in_bucket) and len(keys) == 0:
        existing_count = db.scalar(
            select(func.count())
            .select_from(Photo)
            .where(
                Photo.gender == gender,
                Photo.source_type == PHOTO_SOURCE_YC_OBJECT_STORAGE,
            ),
        ) or 0
        if existing_count > 0:
            safety_skip = True
            log.warning(
                "yc_photo_sync SAFETY-SKIP gender=%s bucket=%s prefix=%r "
                "(bucket вернул 0 ключей, в БД %s записей) — БД не меняем",
                gender, bucket, prefix, existing_count,
            )

    deactivated = 0
    purged = 0
    if not safety_skip:
        if purge_not_in_bucket:
            # Удаляем «осиротевшие» в БД (URL, которых нет в бакете) одним SQL:
            # ON DELETE CASCADE на photo_tags/interactions и SET NULL на
            # fitting_requests.photo_id — на уровне схемы.
            orphan_q = select(Photo.id).where(
                Photo.gender == gender,
                Photo.source_type == PHOTO_SOURCE_YC_OBJECT_STORAGE,
            )
            if existing_urls:
                orphan_q = orphan_q.where(Photo.url.notin_(existing_urls))
            orphan_ids = list(db.execute(orphan_q).scalars().all())
            if orphan_ids:
                db.execute(delete(Photo).where(Photo.id.in_(orphan_ids)))
                purged = len(orphan_ids)
        elif deactivate_not_in_bucket:
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
        rows_purged=purged,
        safety_skip=safety_skip,
    )


def ensure_photo_row_for_yc_key(
    db: Session,
    *,
    settings: Settings,
    gender: str,
    bucket: str,
    key: str,
    brand_id: uuid.UUID | None = None,
    show_badge: bool | None = None,
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
        if show_badge is not None:
            row.show_badge = bool(show_badge)
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
            show_badge=bool(show_badge) if show_badge is not None else False,
        )
    )


def sync_all_buckets_from_yc(
    db: Session,
    *,
    settings: Settings,
    deactivate_not_in_bucket: bool = True,
    purge_not_in_bucket: bool = False,
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
        purge_not_in_bucket=purge_not_in_bucket,
    )
    f = sync_bucket_to_db(
        db,
        settings=settings,
        bucket=settings.yc_bucket_women,
        gender="female",
        prefix=settings.yc_s3_prefix_women,
        deactivate_not_in_bucket=deactivate_not_in_bucket,
        purge_not_in_bucket=purge_not_in_bucket,
    )
    return m, f


def stats_as_dict(m: BucketSyncStats, f: BucketSyncStats) -> dict[str, Any]:
    return {
        "male": {
            "bucket": m.bucket,
            "keys_in_bucket": m.keys_in_bucket,
            "rows_added": m.rows_added,
            "rows_deactivated": m.rows_deactivated,
            "rows_purged": m.rows_purged,
            "safety_skip": m.safety_skip,
        },
        "female": {
            "bucket": f.bucket,
            "keys_in_bucket": f.keys_in_bucket,
            "rows_added": f.rows_added,
            "rows_deactivated": f.rows_deactivated,
            "rows_purged": f.rows_purged,
            "safety_skip": f.safety_skip,
        },
    }


def run_sync_job_commit(
    settings: Settings,
    *,
    deactivate_not_in_bucket: bool = True,
    purge_not_in_bucket: bool = False,
) -> dict[str, Any]:
    """Одна транзакция на полный цикл (для CLI, фона и админ-эндпоинта)."""
    from app.database import SessionLocal

    db = SessionLocal()
    try:
        m, f = sync_all_buckets_from_yc(
            db,
            settings=settings,
            deactivate_not_in_bucket=deactivate_not_in_bucket,
            purge_not_in_bucket=purge_not_in_bucket,
        )
        db.commit()
        out = stats_as_dict(m, f)
        log.info(
            "yc_photo_sync OK male keys=%s +%s ~%s -%s skip=%s | "
            "female keys=%s +%s ~%s -%s skip=%s",
            m.keys_in_bucket, m.rows_added, m.rows_deactivated, m.rows_purged, m.safety_skip,
            f.keys_in_bucket, f.rows_added, f.rows_deactivated, f.rows_purged, f.safety_skip,
        )
        if m.rows_added + f.rows_added > 0:
            from app.services.web_push import maybe_notify_after_photo_sync

            maybe_notify_after_photo_sync(
                settings,
                rows_added_male=m.rows_added,
                rows_added_female=f.rows_added,
            )
        return out
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
