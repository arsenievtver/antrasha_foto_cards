import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import FittingRequest, MarketingCampaign, XfashionLandingVisit
from app.models.marketing_campaign import normalize_campaign_slug
from app.schemas.xfashion import (
    XfashionLeadCreateRequest,
    XfashionLeadCreateResponse,
    XfashionVisitRequest,
    XfashionVisitResponse,
)
from app.services.max_notify import send_fitting_request_notification
from app.utils.phone import normalize_ru_phone

log = logging.getLogger("app.api.xfashion")

router = APIRouter(prefix="/public/xfashion", tags=["xfashion-public"])

_XFASHION_HEADING = "Заявка Xfashion (лендинг)"


def _resolve_xfashion_campaign_id(db: Session, ref: str | None) -> uuid.UUID | None:
    if not ref or not str(ref).strip():
        return None
    try:
        slug = normalize_campaign_slug(ref)
    except ValueError:
        return None
    row = db.execute(
        select(MarketingCampaign.id).where(
            MarketingCampaign.slug == slug,
            MarketingCampaign.is_active.is_(True),
            MarketingCampaign.product == "xfashion",
        ),
    ).first()
    return row[0] if row else None


@router.post("/visit", response_model=XfashionVisitResponse)
def record_landing_visit(
    body: XfashionVisitRequest,
    db: Session = Depends(get_db),
) -> XfashionVisitResponse:
    campaign_id = _resolve_xfashion_campaign_id(db, body.ref)
    if campaign_id is None:
        return XfashionVisitResponse(recorded=False)
    db.add(XfashionLandingVisit(campaign_id=campaign_id))
    db.commit()
    log.info("POST /public/xfashion/visit campaign_id=%s ref=%s", campaign_id, body.ref[:32])
    return XfashionVisitResponse(recorded=True)


@router.post("/lead", response_model=XfashionLeadCreateResponse)
def create_xfashion_lead(
    body: XfashionLeadCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> XfashionLeadCreateResponse:
    normalized = normalize_ru_phone(body.phone)
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Укажите корректный номер телефона (РФ, 10 или 11 цифр)",
        )
    note_parts = ["[Xfashion]"]
    if body.name and body.name.strip():
        note_parts.append(f"Имя: {body.name.strip()}")
    if body.contact_channel and body.contact_channel.strip():
        note_parts.append(f"Связь: {body.contact_channel.strip()}")
    if body.ref and body.ref.strip():
        note_parts.append(f"ref={body.ref.strip()}")
    if body.message and body.message.strip():
        note_parts.append(body.message.strip())
    note_parts.append("Источник: лендинг xfashion.pro")
    note = " | ".join(note_parts)

    fr = FittingRequest(
        user_id=None,
        display_name=body.name.strip() if body.name and body.name.strip() else None,
        phone=normalized,
        likes=0,
        total=0,
        match_rate=0.0,
        note=note,
        status="new",
    )
    db.add(fr)
    db.commit()
    db.refresh(fr)
    log.info("POST /public/xfashion/lead request_id=%s phone=%s", fr.id, normalized)
    background_tasks.add_task(
        send_fitting_request_notification,
        request_id=fr.id,
        display_name=fr.display_name,
        phone=fr.phone,
        likes=fr.likes,
        total=fr.total,
        match_rate=fr.match_rate,
        note=fr.note,
        is_guest=True,
        liked_photo_urls=[],
        created_at=fr.created_at,
        heading=_XFASHION_HEADING,
    )
    return XfashionLeadCreateResponse(request_id=str(fr.id), status=fr.status)
