import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, select, update
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import get_optional_user, get_session_or_404, parse_session_id
from app.models import PHOTO_SOURCE_YC_OBJECT_STORAGE, Interaction, Photo, PhotoTag, Tag
from app.schemas.interaction import InteractionCreate, InteractionResponse
from app.services.k_factor import k_factor
from app.services.weights import apply_swipe_to_weights, touch_session

router = APIRouter(prefix="/interactions", tags=["interactions"])


def _identity_filter(user_id: uuid.UUID | None, session_id: uuid.UUID):
    """Идентичность реакции на фото: либо user_id, либо session_id (для анонимов).

    После регистрации сессии сливаются (см. services.weights.merge_session_into_user),
    поэтому пара (user_id, session_id) корректно описывает «одного и того же» зрителя.
    """
    if user_id is not None:
        return Interaction.user_id == user_id
    return and_(Interaction.user_id.is_(None), Interaction.session_id == session_id)


def _previous_reaction(
    db: Session,
    *,
    photo_id: uuid.UUID,
    user_id: uuid.UUID | None,
    session_id: uuid.UUID,
) -> str | None:
    """Последний like/dislike той же идентичности на это фото (или None)."""
    row = db.execute(
        select(Interaction.action)
        .where(
            Interaction.photo_id == photo_id,
            Interaction.action.in_(("like", "dislike")),
            _identity_filter(user_id, session_id),
        )
        .order_by(Interaction.created_at.desc())
        .limit(1),
    ).first()
    return row[0] if row else None


def _counter_deltas(prev: str | None, new: str) -> tuple[int, int]:
    """Дельты для (likes_count, dislikes_count) при переходе prev → new.

    Семантика: каждая идентичность держит максимум один голос. Повторный свайп
    в ту же сторону — 0; переключение — снимает голос с одной стороны и ставит
    на другую.
    """
    if new not in ("like", "dislike"):
        return 0, 0
    if prev == new:
        return 0, 0
    if prev is None:
        return (1, 0) if new == "like" else (0, 1)
    # prev — противоположное действие
    return (1, -1) if new == "like" else (-1, 1)


@router.post("", response_model=InteractionResponse)
def create_interaction(
    body: InteractionCreate,
    db: Session = Depends(get_db),
    session_id: uuid.UUID = Depends(parse_session_id),
    user=Depends(get_optional_user),
) -> InteractionResponse:
    get_session_or_404(db, session_id)
    touch_session(db, session_id)

    photo = db.execute(
        select(Photo)
        .where(Photo.id == body.photo_id)
        .options(
            selectinload(Photo.photo_tags).selectinload(PhotoTag.tag).selectinload(Tag.group),
        )
    ).scalar_one_or_none()
    if (
        not photo
        or not photo.is_active
        or photo.source_type != PHOTO_SOURCE_YC_OBJECT_STORAGE
    ):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")

    uid = user.id if user else None
    k = k_factor(body.view_time_ms)

    # Денормализованные счётчики обновляем ДО записи новой интеракции, чтобы
    # «предыдущий вердикт» определялся по уже сохранённой истории.
    if body.action in ("like", "dislike"):
        prev = _previous_reaction(
            db, photo_id=photo.id, user_id=uid, session_id=session_id,
        )
        d_likes, d_dislikes = _counter_deltas(prev, body.action)
        if d_likes != 0 or d_dislikes != 0:
            db.execute(
                update(Photo)
                .where(Photo.id == photo.id)
                .values(
                    likes_count=Photo.likes_count + d_likes,
                    dislikes_count=Photo.dislikes_count + d_dislikes,
                ),
            )

    inter = Interaction(
        user_id=uid,
        session_id=session_id,
        photo_id=photo.id,
        action=body.action,
        view_time_ms=body.view_time_ms,
    )
    db.add(inter)

    if body.action in ("like", "dislike"):
        apply_swipe_to_weights(
            db,
            photo,
            action=body.action,
            k=k,
            user_id=uid,
            session_id=session_id if uid is None else None,
        )

    db.commit()
    db.refresh(inter)
    return InteractionResponse(id=inter.id)
