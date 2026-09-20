from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import AiIngestJob, FeedReleaseBatch, Photo, PhotoEmbedding
from app.services.photo_embedding import embed_photo_url, upsert_photo_embedding

log = logging.getLogger("app.feed_release_batch")


def get_draft_batch(db: Session, *, gender: str) -> FeedReleaseBatch | None:
    g = gender.strip().lower()
    return db.execute(
        select(FeedReleaseBatch).where(
            FeedReleaseBatch.gender == g,
            FeedReleaseBatch.status == "draft",
        )
    ).scalar_one_or_none()


def get_or_create_draft_batch(db: Session, *, gender: str) -> FeedReleaseBatch:
    row = get_draft_batch(db, gender=gender)
    if row:
        return row
    g = gender.strip().lower()
    row = FeedReleaseBatch(gender=g, status="draft")
    db.add(row)
    db.flush()
    return row


def draft_batch_summary(db: Session, *, gender: str) -> dict:
    draft = get_draft_batch(db, gender=gender)
    if not draft:
        return {
            "batch_id": None,
            "photo_count": 0,
            "embed_error_count": 0,
            "last_embed_error": None,
        }
    photos = db.execute(
        select(Photo).where(
            Photo.release_batch_id == draft.id,
            Photo.feed_visible.is_(False),
        )
    ).scalars().all()
    err_n = sum(1 for p in photos if p.vector_embed_error)
    return {
        "batch_id": draft.id,
        "photo_count": len(photos),
        "embed_error_count": err_n,
        "last_embed_error": draft.last_embed_error,
    }


def publish_draft_batch(db: Session, *, gender: str) -> dict:
    """
    Embed всех фото черновика и выпустить в ленту.
    При ошибке embed черновик остаётся, успешные embed сохраняются, feed_visible не меняется.
    """
    try:
        from fastembed import ImageEmbedding  # noqa: F401
    except ImportError as e:
        raise RuntimeError(
            "На сервере не установлен fastembed — выпуск с векторами недоступен. "
            "Установите requirements-embeddings.txt или запустите publish с машины разработчика."
        ) from e

    g = gender.strip().lower()
    draft = get_draft_batch(db, gender=g)
    if not draft:
        raise ValueError("Нет черновика пакета для этого пола — сначала загрузите фото через ingest")

    photos = list(
        db.execute(
            select(Photo).where(
                Photo.release_batch_id == draft.id,
                Photo.feed_visible.is_(False),
                Photo.is_active.is_(True),
            )
        ).scalars().all()
    )
    if not photos:
        raise ValueError("В черновике нет фото — дождитесь обработки Fashn")

    failed: list[dict] = []
    for photo in photos:
        existing = db.get(PhotoEmbedding, photo.id)
        if existing is not None:
            photo.vector_embed_error = None
            continue
        try:
            vec = embed_photo_url(photo.url)
            upsert_photo_embedding(db, photo_id=photo.id, embedding=vec)
            photo.vector_embed_error = None
        except Exception as e:
            msg = f"{type(e).__name__}: {e}"[:2000]
            photo.vector_embed_error = msg
            failed.append({"photo_id": str(photo.id), "error": msg})
            log.warning("embed failed photo_id=%s: %s", photo.id, msg)

    if failed:
        draft.last_embed_error = f"Не удалось векторизовать {len(failed)} из {len(photos)}"
        db.commit()
        return {
            "ok": False,
            "published": False,
            "failed": failed,
            "message": draft.last_embed_error,
        }

    for photo in photos:
        photo.feed_visible = True
    draft.status = "published"
    draft.published_at = datetime.now(timezone.utc)
    draft.last_embed_error = None
    db.execute(
        delete(AiIngestJob).where(
            AiIngestJob.release_batch_id == draft.id,
            AiIngestJob.status == "completed",
        )
    )
    db.commit()

    log.info(
        "feed_release_batch published batch_id=%s gender=%s photos=%s",
        draft.id,
        g,
        len(photos),
    )
    return {
        "ok": True,
        "published": True,
        "batch_id": str(draft.id),
        "photo_count": len(photos),
        "message": "Пакет выпущен в ленту",
    }


def count_pending_fashn_for_draft(db: Session, batch_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(AiIngestJob)
            .where(
                AiIngestJob.release_batch_id == batch_id,
                AiIngestJob.status.in_(("pending", "processing")),
            )
        )
        or 0
    )


def count_failed_fashn_for_draft(db: Session, batch_id: uuid.UUID) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(AiIngestJob)
            .where(
                AiIngestJob.release_batch_id == batch_id,
                AiIngestJob.status == "failed",
            )
        )
        or 0
    )
