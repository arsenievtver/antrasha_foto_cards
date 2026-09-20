from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embedding_constants import EMBEDDING_MODEL_VERSION
from app.models import PHOTO_SOURCE_YC_OBJECT_STORAGE, Photo, PhotoEmbedding, UserTasteVector
from app.services.taste_vector_math import cosine_similarity


def user_taste_meta(db: Session, user_id: uuid.UUID) -> tuple[list[float] | None, int]:
    row = db.execute(
        select(UserTasteVector).where(
            UserTasteVector.user_id == user_id,
            UserTasteVector.session_id.is_(None),
            UserTasteVector.model_version == EMBEDDING_MODEL_VERSION,
        )
    ).scalar_one_or_none()
    if not row or row.embedding is None:
        return None, 0
    return [float(x) for x in row.embedding], int(row.swipe_updates)


def nearest_feed_photos_to_taste(
    db: Session,
    taste: list[float],
    *,
    k: int = 4,
) -> list[tuple[Photo, float]]:
    rows = db.execute(
        select(Photo, PhotoEmbedding)
        .join(PhotoEmbedding, PhotoEmbedding.photo_id == Photo.id)
        .where(
            Photo.is_active.is_(True),
            Photo.feed_visible.is_(True),
            Photo.source_type == PHOTO_SOURCE_YC_OBJECT_STORAGE,
            PhotoEmbedding.model_version == EMBEDDING_MODEL_VERSION,
        )
    ).all()
    scored: list[tuple[Photo, float]] = []
    for photo, pe in rows:
        vec = [float(x) for x in pe.embedding]
        scored.append((photo, cosine_similarity(taste, vec)))
    scored.sort(key=lambda x: -x[1])
    return scored[: max(1, k)]
