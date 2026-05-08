import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.deps import get_optional_user, get_session_or_404, parse_session_id
from app.models import PHOTO_SOURCE_YC_OBJECT_STORAGE, Interaction, Photo, PhotoTag, Tag
from app.schemas.interaction import InteractionCreate, InteractionResponse
from app.services.k_factor import k_factor
from app.services.weights import apply_swipe_to_weights, touch_session

router = APIRouter(prefix="/interactions", tags=["interactions"])


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
