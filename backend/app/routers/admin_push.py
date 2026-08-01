"""Админка: ручная рассылка Web Push."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import AdminPrincipal, require_permission
from app.schemas.push import (
    AdminPushBroadcastRequest,
    AdminPushBroadcastResponse,
    AdminPushStatsResponse,
)
from app.services.web_push import (
    broadcast_admin_push,
    push_subscription_stats,
    web_push_configured,
)

log = logging.getLogger("app.api.admin_push")

router = APIRouter(prefix="/admin/push", tags=["admin-push"])


@router.get("/stats", response_model=AdminPushStatsResponse)
def push_stats(
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("ads")),
) -> AdminPushStatsResponse:
    _ = _su
    configured = web_push_configured(settings)
    if not configured:
        return AdminPushStatsResponse(configured=False)
    stats = push_subscription_stats(db)
    return AdminPushStatsResponse(configured=True, **stats)


@router.post("/broadcast", response_model=AdminPushBroadcastResponse)
def push_broadcast(
    body: AdminPushBroadcastRequest,
    db: Session = Depends(get_db),
    _su: AdminPrincipal = Depends(require_permission("ads")),
) -> AdminPushBroadcastResponse:
    _ = _su
    if not web_push_configured(settings):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Web Push не настроен (VAPID)",
        )
    result = broadcast_admin_push(
        db,
        settings=settings,
        title=body.title,
        body=body.body,
        url=body.url,
        audience=body.audience,
        respect_cooldown=body.respect_cooldown,
    )
    log.info(
        "admin push broadcast role=%s user=%s audience=%s sent=%s",
        _su.role,
        _su.user.id if _su.user else "superuser",
        body.audience,
        result["sent"],
    )
    return AdminPushBroadcastResponse(**result)
