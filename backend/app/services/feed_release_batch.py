from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import AiIngestJob, FeedReleaseBatch, Photo, PhotoEmbedding

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


def _draft_photos_query(draft_id: uuid.UUID):
    return select(Photo).where(
        Photo.release_batch_id == draft_id,
        Photo.feed_visible.is_(False),
        Photo.is_active.is_(True),
    )


def draft_batch_summary(db: Session, *, gender: str) -> dict:
    draft = get_draft_batch(db, gender=gender)
    if not draft:
        return {
            "batch_id": None,
            "photo_count": 0,
            "embedded_count": 0,
            "embed_error_count": 0,
            "last_embed_error": None,
        }
    photos = db.execute(_draft_photos_query(draft.id)).scalars().all()
    ids = [p.id for p in photos]
    embedded = 0
    if ids:
        embedded = int(
            db.scalar(
                select(func.count())
                .select_from(PhotoEmbedding)
                .where(PhotoEmbedding.photo_id.in_(ids))
            )
            or 0
        )
    err_n = sum(1 for p in photos if p.vector_embed_error)
    return {
        "batch_id": draft.id,
        "photo_count": len(photos),
        "embedded_count": embedded,
        "embed_error_count": err_n,
        "last_embed_error": draft.last_embed_error,
    }


def pick_draft_photo_needing_embedding(db: Session) -> Photo | None:
    """Фото черновиков без вектора. Фото с ошибкой — в конце очереди, чтобы не крутиться на одном."""
    return db.execute(
        select(Photo)
        .join(FeedReleaseBatch, FeedReleaseBatch.id == Photo.release_batch_id)
        .outerjoin(PhotoEmbedding, PhotoEmbedding.photo_id == Photo.id)
        .where(
            FeedReleaseBatch.status == "draft",
            Photo.feed_visible.is_(False),
            Photo.is_active.is_(True),
            PhotoEmbedding.photo_id.is_(None),
        )
        .order_by(Photo.vector_embed_error.is_not(None), Photo.created_at.asc())
        .limit(1)
    ).scalar_one_or_none()


def publish_draft_batch(db: Session, *, gender: str) -> dict:
    """
    Выпустить черновик в ленту. Векторы заранее считает ai-ingest-worker —
    здесь только проверка, что они есть у всех фото: запрос админки не ждёт модель.
    """
    g = gender.strip().lower()
    draft = get_draft_batch(db, gender=g)
    if not draft:
        raise ValueError("Нет черновика пакета для этого пола — сначала загрузите фото через ingest")

    photos = list(db.execute(_draft_photos_query(draft.id)).scalars().all())
    if not photos:
        raise ValueError("В черновике нет фото — дождитесь обработки Fashn")

    ids = [p.id for p in photos]
    embedded_ids = set(
        db.execute(select(PhotoEmbedding.photo_id).where(PhotoEmbedding.photo_id.in_(ids))).scalars().all()
    )
    missing = [p for p in photos if p.id not in embedded_ids]
    if missing:
        failed = [
            {"photo_id": str(p.id), "error": p.vector_embed_error}
            for p in missing
            if p.vector_embed_error
        ]
        msg = f"Векторы готовы для {len(photos) - len(missing)} из {len(photos)} — воркер ещё считает"
        if failed:
            msg = f"{msg}; с ошибкой: {len(failed)}"
        return {
            "ok": False,
            "published": False,
            "failed": failed,
            "message": msg,
        }

    for photo in photos:
        photo.feed_visible = True
        photo.vector_embed_error = None
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
