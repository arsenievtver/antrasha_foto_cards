"""Спрос от продавцов: свой дневной чат в work PWA и общий журнал для суперпользователя."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import AdminPrincipal, get_admin_principal, require_superuser
from app.models.staff_feedback import StaffFeedback
from app.schemas.staff_feedback import (
    StaffFeedbackListOut,
    StaffFeedbackOut,
    StaffFeedbackStatsOut,
    StaffFeedbackTextIn,
)
from app.services.staff_feedback import (
    author_identity,
    feedback_dict,
    feedback_stats,
    is_own,
    list_feedback,
    own_filter,
    today_start,
)

router = APIRouter(prefix="/admin/staff-feedback", tags=["admin-staff-feedback"])


@router.get("/mine", response_model=list[StaffFeedbackOut])
def list_my_feedback(
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(get_admin_principal),
) -> list[dict]:
    rows = db.scalars(
        select(StaffFeedback)
        .where(own_filter(principal), StaffFeedback.created_at >= today_start())
        .order_by(StaffFeedback.created_at)
    ).all()
    return [feedback_dict(r) for r in rows]


@router.post("/mine", response_model=StaffFeedbackOut, status_code=201)
def create_my_feedback(
    body: StaffFeedbackTextIn,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(get_admin_principal),
) -> dict:
    user_id, label = author_identity(principal)
    row = StaffFeedback(author_user_id=user_id, author_label=label, text=body.text)
    db.add(row)
    db.commit()
    db.refresh(row)
    return feedback_dict(row)


@router.patch("/mine/{feedback_id}", response_model=StaffFeedbackOut)
def update_my_feedback(
    feedback_id: uuid.UUID,
    body: StaffFeedbackTextIn,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(get_admin_principal),
) -> dict:
    row = db.get(StaffFeedback, feedback_id)
    if row is None or not is_own(row, principal) or row.created_at < today_start():
        raise HTTPException(status_code=404, detail="Сообщение не найдено")
    row.text = body.text
    row.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(row)
    return feedback_dict(row)


@router.get("", response_model=StaffFeedbackListOut)
def list_all_feedback(
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(require_superuser),
    author_user_id: uuid.UUID | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    rows, total = list_feedback(
        db,
        author_user_id=author_user_id,
        date_from=date_from,
        date_to=date_to,
        skip=skip,
        limit=limit,
    )
    return {
        "items": [feedback_dict(r) for r in rows],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/stats", response_model=StaffFeedbackStatsOut)
def staff_feedback_stats(
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(require_superuser),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
) -> dict:
    return {"items": feedback_stats(db, date_from=date_from, date_to=date_to)}
