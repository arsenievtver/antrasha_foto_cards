from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.embedding_constants import EMBEDDING_MODEL_VERSION
from app.models import PHOTO_SOURCE_YC_OBJECT_STORAGE, Photo, PhotoEmbedding, UserTasteVector
from app.services.feed_policy import taste_vectors_separate_by_gender
from app.services.taste_vector import COLLECTION_GENDERS, normalize_collection_gender
from app.services.taste_vector_math import cosine_similarity


def user_taste_meta(
    db: Session,
    user_id: uuid.UUID,
    *,
    collection_gender: str,
) -> tuple[list[float] | None, int]:
    separate = taste_vectors_separate_by_gender(db)
    g_key = normalize_collection_gender(collection_gender) if separate else None
    q = select(UserTasteVector).where(
        UserTasteVector.user_id == user_id,
        UserTasteVector.session_id.is_(None),
        UserTasteVector.model_version == EMBEDDING_MODEL_VERSION,
    )
    if g_key is None:
        q = q.where(UserTasteVector.collection_gender.is_(None))
    else:
        q = q.where(UserTasteVector.collection_gender == g_key)
    row = db.execute(q).scalar_one_or_none()
    if not row or row.embedding is None:
        return None, 0
    return [float(x) for x in row.embedding], int(row.swipe_updates)


def nearest_feed_photos_to_taste(
    db: Session,
    taste: list[float],
    *,
    k: int = 4,
    catalog_gender: str,
) -> list[tuple[Photo, float]]:
    g_norm = normalize_collection_gender(catalog_gender)
    rows = db.execute(
        select(Photo, PhotoEmbedding)
        .join(PhotoEmbedding, PhotoEmbedding.photo_id == Photo.id)
        .where(
            Photo.is_active.is_(True),
            Photo.feed_visible.is_(True),
            Photo.source_type == PHOTO_SOURCE_YC_OBJECT_STORAGE,
            PhotoEmbedding.model_version == EMBEDDING_MODEL_VERSION,
            func.lower(Photo.gender) == g_norm,
        )
    ).all()
    scored: list[tuple[Photo, float]] = []
    for photo, pe in rows:
        vec = [float(x) for x in pe.embedding]
        scored.append((photo, cosine_similarity(taste, vec)))
    scored.sort(key=lambda x: -x[1])
    return scored[: max(1, k)]


def taste_previews_for_user(
    db: Session,
    user_id: uuid.UUID,
    *,
    k: int = 4,
) -> list[tuple[str, list[float] | None, int, list[tuple[Photo, float]]]]:
    """Секции male/female: свой вектор или один общий (см. feed_settings)."""
    _ = taste_vectors_separate_by_gender(db)
    out: list[tuple[str, list[float] | None, int, list[tuple[Photo, float]]]] = []
    for catalog_g in COLLECTION_GENDERS:
        taste_emb, updates = user_taste_meta(db, user_id, collection_gender=catalog_g)
        nearest: list[tuple[Photo, float]] = []
        if taste_emb:
            nearest = nearest_feed_photos_to_taste(
                db,
                taste_emb,
                k=k,
                catalog_gender=catalog_g,
            )
        out.append((catalog_g, taste_emb, updates, nearest))
    return out
