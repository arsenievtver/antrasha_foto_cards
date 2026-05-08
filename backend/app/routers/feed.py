import logging
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_optional_user, get_session_or_404, parse_session_id
from app.schemas.feed import FeedPhoto, FeedResponse, TagOut
from app.services.feed import fetch_feed_photos
from app.services.weights import touch_session

log = logging.getLogger("app.api.feed")
router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("", response_model=FeedResponse)
def get_feed(
    db: Session = Depends(get_db),
    gender: str = Query(..., min_length=1, max_length=10),
    limit: int = Query(20, ge=1, le=50),
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
    photos, meta = fetch_feed_photos(
        db,
        gender=gender,
        limit=limit,
        user_id=uid,
        session_id=session_id,
    )
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
                tags=tags,
            )
        )
    return FeedResponse(photos=out, meta=meta)
