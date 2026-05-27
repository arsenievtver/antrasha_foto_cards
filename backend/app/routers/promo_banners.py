import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_optional_user, get_session_or_404, parse_session_id
from app.models.promo_banner import PromoBanner
from app.schemas.promo_banner import PromoBannerActiveResponse, PromoBannerPublicOut
from app.services.promo_banner import pick_active_banner, record_banner_seen
from app.services.weights import touch_session

log = logging.getLogger("app.api.promo_banners")
router = APIRouter(prefix="/promo-banners", tags=["promo-banners"])


@router.get("/active", response_model=PromoBannerActiveResponse)
def get_active_promo_banner(
    db: Session = Depends(get_db),
    session_id: uuid.UUID = Depends(parse_session_id),
    user=Depends(get_optional_user),
) -> PromoBannerActiveResponse:
    get_session_or_404(db, session_id)
    touch_session(db, session_id)
    db.commit()

    uid = user.id if user else None
    banner = pick_active_banner(db, session_id, uid)
    if not banner:
        return PromoBannerActiveResponse(banner=None)
    return PromoBannerActiveResponse(
        banner=PromoBannerPublicOut.model_validate(banner),
    )


@router.post("/{banner_id}/seen", status_code=status.HTTP_204_NO_CONTENT)
def mark_promo_banner_seen(
    banner_id: uuid.UUID,
    db: Session = Depends(get_db),
    session_id: uuid.UUID = Depends(parse_session_id),
    user=Depends(get_optional_user),
) -> None:
    get_session_or_404(db, session_id)
    banner = db.get(PromoBanner, banner_id)
    if not banner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Banner not found")
    uid = user.id if user else None
    record_banner_seen(db, banner, session_id, uid)
    touch_session(db, session_id)
    db.commit()
    log.info("POST /promo-banners/%s/seen session=%s user=%s", banner_id, session_id, uid)
