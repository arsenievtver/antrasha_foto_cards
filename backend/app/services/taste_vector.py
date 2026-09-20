from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.embedding_constants import EMBEDDING_MODEL_VERSION, TASTE_EMA_ALPHA_BASE
from app.models import PhotoEmbedding, User, UserTasteVector
from app.services.taste_vector_math import ema_step


def load_taste_embedding(
    db: Session,
    *,
    user_id: uuid.UUID | None,
    session_id: uuid.UUID,
) -> list[float] | None:
    if user_id is not None:
        q = select(UserTasteVector).where(
            UserTasteVector.user_id == user_id,
            UserTasteVector.session_id.is_(None),
            UserTasteVector.model_version == EMBEDDING_MODEL_VERSION,
        )
    else:
        q = select(UserTasteVector).where(
            UserTasteVector.session_id == session_id,
            UserTasteVector.user_id.is_(None),
            UserTasteVector.model_version == EMBEDDING_MODEL_VERSION,
        )
    row = db.execute(q).scalar_one_or_none()
    if not row or row.embedding is None:
        return None
    return [float(x) for x in row.embedding]


def _get_or_create_row(
    db: Session,
    *,
    user_id: uuid.UUID | None,
    session_id: uuid.UUID | None,
) -> UserTasteVector:
    if user_id is not None:
        q = select(UserTasteVector).where(
            UserTasteVector.user_id == user_id,
            UserTasteVector.session_id.is_(None),
        )
    else:
        q = select(UserTasteVector).where(
            UserTasteVector.session_id == session_id,
            UserTasteVector.user_id.is_(None),
        )
    row = db.execute(q).scalar_one_or_none()
    if row:
        return row
    row = UserTasteVector(
        user_id=user_id,
        session_id=session_id,
        model_version=EMBEDDING_MODEL_VERSION,
        embedding=None,
        swipe_updates=0,
    )
    db.add(row)
    db.flush()
    return row


def apply_swipe_to_taste_vector(
    db: Session,
    photo_id: uuid.UUID,
    *,
    action: str,
    k: float,
    user_id: uuid.UUID | None,
    session_id: uuid.UUID | None,
) -> None:
    if action not in ("like", "dislike"):
        return
    pe = db.get(PhotoEmbedding, photo_id)
    if not pe or pe.model_version != EMBEDDING_MODEL_VERSION:
        return
    photo_emb = [float(x) for x in pe.embedding]
    sign = 1.0 if action == "like" else -1.0
    alpha = min(1.0, TASTE_EMA_ALPHA_BASE * max(k, 0.05))
    owner_session = session_id if user_id is None else None

    row = _get_or_create_row(db, user_id=user_id, session_id=owner_session)
    if row.model_version != EMBEDDING_MODEL_VERSION:
        row.model_version = EMBEDDING_MODEL_VERSION
        row.embedding = None
        row.swipe_updates = 0

    current = None if row.embedding is None else [float(x) for x in row.embedding]
    row.embedding = ema_step(current, photo_emb, alpha=alpha, sign=sign)
    row.swipe_updates = int(row.swipe_updates) + 1


def merge_session_taste_into_user(
    db: Session,
    *,
    session_id: uuid.UUID,
    user: User,
) -> None:
    user_id = user.id
    session_row = db.execute(
        select(UserTasteVector).where(
            UserTasteVector.session_id == session_id,
            UserTasteVector.user_id.is_(None),
        )
    ).scalar_one_or_none()
    if not session_row or session_row.embedding is None:
        if session_row:
            db.delete(session_row)
        return

    user_row = db.execute(
        select(UserTasteVector).where(
            UserTasteVector.user_id == user_id,
            UserTasteVector.session_id.is_(None),
        )
    ).scalar_one_or_none()

    session_emb = [float(x) for x in session_row.embedding]
    if user_row is None:
        db.add(
            UserTasteVector(
                user_id=user_id,
                session_id=None,
                model_version=EMBEDDING_MODEL_VERSION,
                embedding=session_emb,
                swipe_updates=int(session_row.swipe_updates),
            )
        )
    elif user_row.embedding is None:
        user_row.embedding = session_emb
        user_row.swipe_updates = int(session_row.swipe_updates)
    else:
        user_emb = [float(x) for x in user_row.embedding]
        w_s = max(1, int(session_row.swipe_updates))
        w_u = max(1, int(user_row.swipe_updates))
        merged = [
            (w_u * u + w_s * s) / (w_u + w_s) for u, s in zip(user_emb, session_emb, strict=True)
        ]
        from app.services.taste_vector_math import l2_normalize

        user_row.embedding = l2_normalize(merged)
        user_row.swipe_updates = w_u + w_s

    db.delete(session_row)
