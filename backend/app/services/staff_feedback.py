"""Спрос от продавцов: общая выборка для админки и MCP."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Date, cast, func, select
from sqlalchemy.orm import Session

from app.deps import AdminPrincipal
from app.models.staff_feedback import StaffFeedback

TZ = ZoneInfo("Europe/Moscow")
SUPERUSER_LABEL = "Суперпользователь"


def author_identity(principal: AdminPrincipal) -> tuple[uuid.UUID | None, str]:
    if principal.role == "superuser" or principal.user is None:
        return None, SUPERUSER_LABEL
    user = principal.user
    label = (user.display_name or "").strip() or user.phone
    return user.id, label


def is_own(row: StaffFeedback, principal: AdminPrincipal) -> bool:
    user_id, label = author_identity(principal)
    if user_id is not None:
        return row.author_user_id == user_id
    return row.author_user_id is None and row.author_label == label


def own_filter(principal: AdminPrincipal):
    user_id, label = author_identity(principal)
    if user_id is not None:
        return StaffFeedback.author_user_id == user_id
    return (StaffFeedback.author_user_id.is_(None)) & (StaffFeedback.author_label == label)


def today_start() -> datetime:
    """Полночь по Москве: сотрудник видит и правит только сообщения после неё."""
    return datetime.combine(datetime.now(TZ).date(), time.min, TZ)


def _period_filters(date_from: date | None, date_to: date | None) -> list:
    out = []
    if date_from is not None:
        out.append(StaffFeedback.created_at >= datetime.combine(date_from, time.min, TZ))
    if date_to is not None:
        out.append(
            StaffFeedback.created_at
            < datetime.combine(date_to + timedelta(days=1), time.min, TZ)
        )
    return out


def feedback_dict(row: StaffFeedback) -> dict:
    return {
        "id": str(row.id),
        "author_user_id": str(row.author_user_id) if row.author_user_id else None,
        "author_label": row.author_label,
        "text": row.text,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def list_feedback(
    db: Session,
    *,
    author_user_id: uuid.UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    skip: int = 0,
    limit: int = 100,
) -> tuple[list[StaffFeedback], int]:
    filters = _period_filters(date_from, date_to)
    if author_user_id is not None:
        filters.append(StaffFeedback.author_user_id == author_user_id)
    total = db.scalar(select(func.count()).select_from(StaffFeedback).where(*filters)) or 0
    rows = db.scalars(
        select(StaffFeedback)
        .where(*filters)
        .order_by(StaffFeedback.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    return list(rows), int(total)


def feedback_stats(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[dict]:
    local_day = cast(func.timezone(TZ.key, StaffFeedback.created_at), Date)
    rows = db.execute(
        select(
            StaffFeedback.author_user_id,
            StaffFeedback.author_label,
            func.count().label("messages"),
            func.count(func.distinct(local_day)).label("active_days"),
            func.sum(func.length(StaffFeedback.text)).label("total_chars"),
            func.min(StaffFeedback.created_at).label("first_at"),
            func.max(StaffFeedback.created_at).label("last_at"),
        )
        .where(*_period_filters(date_from, date_to))
        .group_by(StaffFeedback.author_user_id, StaffFeedback.author_label)
        .order_by(func.count().desc())
    ).all()
    return [
        {
            "author_user_id": str(r.author_user_id) if r.author_user_id else None,
            "author_label": r.author_label,
            "messages": int(r.messages),
            "active_days": int(r.active_days),
            "total_chars": int(r.total_chars or 0),
            "first_at": r.first_at.isoformat() if r.first_at else None,
            "last_at": r.last_at.isoformat() if r.last_at else None,
        }
        for r in rows
    ]
