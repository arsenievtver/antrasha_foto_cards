import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import FittingRequest
from app.schemas.auth import (
    FittingRequestCreateResponse,
    GuestFittingRequestCreateRequest,
)
from app.services.max_notify import send_fitting_request_notification
from app.utils.phone import normalize_ru_phone

log = logging.getLogger("app.api.guest")

router = APIRouter(tags=["guest"])


@router.post("/guest/fitting-request", response_model=FittingRequestCreateResponse)
def create_guest_fitting_request(
    body: GuestFittingRequestCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> FittingRequestCreateResponse:
    normalized = normalize_ru_phone(body.phone)
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Укажите корректный номер телефона (РФ, 10 или 11 цифр)",
        )
    note_parts: list[str] = []
    if body.note and body.note.strip():
        note_parts.append(body.note.strip())
    note_parts.append("Источник: гость, без регистрации")
    note = " | ".join(note_parts)

    fr = FittingRequest(
        user_id=None,
        display_name=None,
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
    log.info("POST /guest/fitting-request request_id=%s phone=%s", fr.id, normalized)
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
    )
    return FittingRequestCreateResponse(request_id=fr.id, status=fr.status)
