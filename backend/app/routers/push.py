import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_optional_user, get_session_or_404, parse_session_id, require_user
from app.models import User
from app.schemas.push import (
    PushAccountStatusResponse,
    PushSubscribeRequest,
    PushSubscribeResponse,
    PushUnsubscribeRequest,
    PushVapidPublicKeyResponse,
)
from app.services.web_push import (
    deactivate_all_push_subscriptions_for_user,
    deactivate_push_subscription,
    push_account_status_for_user,
    upsert_push_subscription,
    web_push_configured,
)

log = logging.getLogger("app.api.push")
router = APIRouter(prefix="/push", tags=["push"])


@router.get("/vapid-public-key", response_model=PushVapidPublicKeyResponse)
def get_vapid_public_key() -> PushVapidPublicKeyResponse:
    if not web_push_configured(settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Web Push is not configured",
        )
    return PushVapidPublicKeyResponse(
        public_key=settings.vapid_public_key.strip(),
    )


@router.post("/subscribe", response_model=PushSubscribeResponse)
def subscribe_push(
    body: PushSubscribeRequest,
    db: Session = Depends(get_db),
    session_id: uuid.UUID = Depends(parse_session_id),
    user: User | None = Depends(get_optional_user),
) -> PushSubscribeResponse:
    if not web_push_configured(settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Web Push is not configured",
        )
    get_session_or_404(db, session_id)
    uid = user.id if user else None
    upsert_push_subscription(
        db,
        endpoint=body.endpoint.strip(),
        p256dh=body.keys.p256dh.strip(),
        auth=body.keys.auth.strip(),
        session_id=session_id,
        user_id=uid,
        gender_scope=body.gender_scope,
    )
    db.commit()
    log.info(
        "POST /push/subscribe session=%s user=%s gender_scope=%s",
        session_id,
        uid,
        body.gender_scope,
    )
    return PushSubscribeResponse()


@router.get("/account-status", response_model=PushAccountStatusResponse)
def push_account_status(
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> PushAccountStatusResponse:
    active, scope = push_account_status_for_user(db, user.id)
    return PushAccountStatusResponse(active=active, gender_scope=scope)


@router.post("/unsubscribe", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe_push(
    body: PushUnsubscribeRequest,
    db: Session = Depends(get_db),
    session_id: uuid.UUID = Depends(parse_session_id),
) -> None:
    get_session_or_404(db, session_id)
    deactivate_push_subscription(db, body.endpoint.strip())
    db.commit()
    log.info("POST /push/unsubscribe session=%s", session_id)


@router.post("/unsubscribe-all", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe_all_push_for_user(
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> None:
    n = deactivate_all_push_subscriptions_for_user(db, user.id)
    db.commit()
    log.info("POST /push/unsubscribe-all user=%s count=%s", user.id, n)
