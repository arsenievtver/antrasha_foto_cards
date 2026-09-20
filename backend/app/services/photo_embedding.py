from __future__ import annotations

import logging
import tempfile
import uuid
from pathlib import Path

import requests
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.embedding_constants import (
    EMBEDDING_DIM,
    EMBEDDING_MODEL_VERSION,
    FASTEMBED_IMAGE_MODEL,
)
from app.models import PHOTO_SOURCE_YC_OBJECT_STORAGE, Photo, PhotoEmbedding

log = logging.getLogger("app.photo_embedding")

_IMAGE_MODEL = None


def _get_image_model():
    global _IMAGE_MODEL
    if _IMAGE_MODEL is not None:
        return _IMAGE_MODEL
    try:
        from fastembed import ImageEmbedding
    except ImportError as e:
        raise RuntimeError(
            "fastembed не установлен — worker эмбеддингов недоступен "
            "(pip install -r requirements-embeddings.txt)"
        ) from e
    _IMAGE_MODEL = ImageEmbedding(model_name=FASTEMBED_IMAGE_MODEL)
    return _IMAGE_MODEL


def embed_image_file(path: Path) -> list[float]:
    model = _get_image_model()
    vectors = list(model.embed([str(path)]))
    if not vectors:
        raise RuntimeError("fastembed вернул пустой результат")
    vec = [float(x) for x in vectors[0]]
    if len(vec) != EMBEDDING_DIM:
        raise RuntimeError(f"ожидали dim={EMBEDDING_DIM}, получили {len(vec)}")
    return vec


def download_photo_bytes(url: str, *, timeout: float = 45.0) -> bytes:
    r = requests.get(url, timeout=timeout)
    r.raise_for_status()
    return r.content


def embed_photo_url(url: str) -> list[float]:
    data = download_photo_bytes(url)
    suffix = ".jpg"
    if ".png" in url.lower():
        suffix = ".png"
    elif ".webp" in url.lower():
        suffix = ".webp"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        return embed_image_file(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def upsert_photo_embedding(
    db: Session,
    *,
    photo_id: uuid.UUID,
    embedding: list[float],
) -> None:
    row = db.get(PhotoEmbedding, photo_id)
    if row:
        row.model_version = EMBEDDING_MODEL_VERSION
        row.embedding = embedding
    else:
        db.add(
            PhotoEmbedding(
                photo_id=photo_id,
                model_version=EMBEDDING_MODEL_VERSION,
                embedding=embedding,
            )
        )


def load_embeddings_for_photo_ids(
    db: Session,
    photo_ids: list[uuid.UUID],
) -> dict[uuid.UUID, list[float]]:
    if not photo_ids:
        return {}
    rows = db.execute(
        select(PhotoEmbedding).where(
            PhotoEmbedding.photo_id.in_(photo_ids),
            PhotoEmbedding.model_version == EMBEDDING_MODEL_VERSION,
        )
    ).scalars().all()
    out: dict[uuid.UUID, list[float]] = {}
    for r in rows:
        out[r.photo_id] = [float(x) for x in r.embedding]
    return out


def pick_photo_needing_embedding(db: Session) -> Photo | None:
    q = (
        select(Photo)
        .outerjoin(PhotoEmbedding, PhotoEmbedding.photo_id == Photo.id)
        .where(
            Photo.is_active.is_(True),
            PhotoEmbedding.photo_id.is_(None),
        )
        .order_by(Photo.created_at.desc())
        .limit(1)
    )
    return db.execute(q).scalar_one_or_none()


def _catalog_embed_conditions(*, gender: str | None) -> list:
    cond = [
        Photo.is_active.is_(True),
        Photo.feed_visible.is_(True),
        Photo.source_type == PHOTO_SOURCE_YC_OBJECT_STORAGE,
        PhotoEmbedding.photo_id.is_(None),
    ]
    if gender:
        cond.append(Photo.gender == gender.strip().lower())
    return cond


def count_catalog_photos_needing_embedding(db: Session, *, gender: str | None = None) -> int:
    cond = _catalog_embed_conditions(gender=gender)
    return int(
        db.scalar(
            select(func.count())
            .select_from(Photo)
            .outerjoin(PhotoEmbedding, PhotoEmbedding.photo_id == Photo.id)
            .where(*cond)
        )
        or 0
    )


def embed_catalog_backfill_batch(
    db: Session,
    *,
    gender: str | None = None,
    limit: int = 12,
) -> dict:
    """Векторизация уже видимых в ленте фото без embedding (первый прогон после миграции)."""
    _get_image_model()

    lim = max(1, min(30, int(limit)))
    cond = _catalog_embed_conditions(gender=gender)
    photos = list(
        db.execute(
            select(Photo)
            .outerjoin(PhotoEmbedding, PhotoEmbedding.photo_id == Photo.id)
            .where(*cond)
            .order_by(Photo.created_at.asc())
            .limit(lim)
        )
        .scalars()
        .all()
    )

    succeeded = 0
    failed: list[dict] = []
    for photo in photos:
        try:
            vec = embed_photo_url(photo.url)
            upsert_photo_embedding(db, photo_id=photo.id, embedding=vec)
            photo.vector_embed_error = None
            db.commit()
            succeeded += 1
        except Exception as e:
            db.rollback()
            msg = f"{type(e).__name__}: {e}"[:2000]
            row = db.get(Photo, photo.id)
            if row:
                row.vector_embed_error = msg
                db.commit()
            failed.append({"photo_id": str(photo.id), "error": msg})
            log.warning("catalog embed failed photo_id=%s: %s", photo.id, msg)

    remaining = count_catalog_photos_needing_embedding(db, gender=gender)
    return {
        "processed": len(photos),
        "succeeded": succeeded,
        "failed": failed,
        "remaining": remaining,
        "done": remaining == 0,
    }


def try_embed_one_photo(db: Session) -> bool:
    photo = pick_photo_needing_embedding(db)
    if not photo:
        return False
    try:
        vec = embed_photo_url(photo.url)
    except Exception:
        log.exception("embed failed photo_id=%s url=%s", photo.id, photo.url)
        db.rollback()
        return True
    upsert_photo_embedding(db, photo_id=photo.id, embedding=vec)
    db.commit()
    log.info("embedded photo_id=%s", photo.id)
    return True
