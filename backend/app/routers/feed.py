import logging
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_optional_user, get_session_or_404, parse_session_id
from app.schemas.feed import FeedPhoto, FeedPublicSettingsOut, FeedResponse, TagOut
from app.services.feed import fetch_feed_photos
from app.services.feed_policy import feed_card_badge_label, feed_swipe_chunk_size
from app.services.weights import touch_session

log = logging.getLogger("app.api.feed")
router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("/public-settings", response_model=FeedPublicSettingsOut)
def get_feed_public_settings(db: Session = Depends(get_db)) -> FeedPublicSettingsOut:
    return FeedPublicSettingsOut(swipe_chunk_size=feed_swipe_chunk_size(db))


@router.get("", response_model=FeedResponse)
def get_feed(
    db: Session = Depends(get_db),
    gender: str = Query(..., min_length=1, max_length=10),
    limit: int = Query(20, ge=1, le=50),
    include_seen: bool = Query(
        False,
        description="Показать уже просмотренные (пересмотр каталога без новых релизов)",
    ),
    exclude_photo_id: list[uuid.UUID] = Query(
        default=[],
        description="Не показывать эти фото (пагинация при include_seen / пересмотре)",
    ),
    session_id: uuid.UUID = Depends(parse_session_id),
    user=Depends(get_optional_user),
) -> FeedResponse:
    get_session_or_404(db, session_id)
    touch_session(db, session_id)
    db.commit()

    uid = user.id if user else None
    log.info(
        "GET /feed gender=%s limit=%s session_id=%s user=%s",
        gender,
        limit,
        session_id,
        uid,
    )
    exclude_ids = set(exclude_photo_id) if exclude_photo_id else None
    photos, meta = fetch_feed_photos(
        db,
        gender=gender,
        limit=limit,
        user_id=uid,
        session_id=session_id,
        include_seen=include_seen,
        exclude_photo_ids=exclude_ids,
    )
    badge_text = feed_card_badge_label(db)
    out: list[FeedPhoto] = []
    for p in photos:
        tags = [
            TagOut(
                id=pt.tag.id,
                name=pt.tag.name,
                type=pt.tag.type,
                weight=float(pt.weight),
            )
            for pt in p.photo_tags
        ]
        out.append(
            FeedPhoto(
                id=p.id,
                url=p.url,
                gender=p.gender,
                source_type=p.source_type,
                brand=p.brand,
                badge_label=badge_text if p.show_badge and badge_text else None,
                tags=tags,
            )
        )
    return FeedResponse(photos=out, meta=meta)
