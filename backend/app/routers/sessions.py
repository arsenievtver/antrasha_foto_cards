import logging
import uuid

from fastapi import APIRouter, Body, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import MarketingCampaign, UserSession
from app.models.marketing_campaign import normalize_campaign_slug
from app.schemas.session import SessionCreateRequest, SessionCreateResponse

log = logging.getLogger("app.api.sessions")
router = APIRouter(prefix="/sessions", tags=["sessions"])


def _resolve_campaign_id(db: Session, ref: str | None) -> uuid.UUID | None:
    if not ref or not str(ref).strip():
        return None
    try:
        slug = normalize_campaign_slug(ref)
    except ValueError:
        log.info("POST /sessions unknown ref slug rejected: %s", ref[:32])
        return None
    row = db.execute(
        select(MarketingCampaign.id).where(
            MarketingCampaign.slug == slug,
            MarketingCampaign.is_active.is_(True),
        ),
    ).first()
    return row[0] if row else None


@router.post("", response_model=SessionCreateResponse)
def create_session(
    db: Session = Depends(get_db),
    body: SessionCreateRequest = Body(default_factory=SessionCreateRequest),
) -> SessionCreateResponse:
    campaign_id = _resolve_campaign_id(db, body.ref)
    s = UserSession(campaign_id=campaign_id)
    db.add(s)
    db.commit()
    db.refresh(s)
    log.info(
        "POST /sessions new session_id=%s campaign_id=%s ref=%s",
        s.id,
        s.campaign_id,
        body.ref,
    )
    return SessionCreateResponse(session_id=s.id)
