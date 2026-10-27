"""Недельный отчёт по МойСклад для суперпользователя: история, детали, запуск по кнопке."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import AdminPrincipal, require_superuser
from app.models.weekly_insight_report import WeeklyInsightReport
from app.services.staff_feedback import author_identity
from app.services.weekly_insight.runner import (
    WeeklyInsightBusy,
    create_report,
    execute_report,
    mark_stale,
    report_dict,
)
from app.services.weekly_insight.summary import ai_configured

router = APIRouter(prefix="/admin/weekly-insight", tags=["admin-weekly-insight"])


@router.get("")
def list_reports(
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(require_superuser),
    limit: int = Query(20, ge=1, le=100),
) -> dict:
    mark_stale(db)
    rows = db.scalars(
        select(WeeklyInsightReport).order_by(WeeklyInsightReport.started_at.desc()).limit(limit)
    ).all()
    return {
        "items": [report_dict(r) for r in rows],
        "moysklad_configured": settings.moysklad_configured,
        "ai_configured": ai_configured(settings),
        "schedule_enabled": settings.weekly_insight_enabled and settings.moysklad_configured,
        "schedule_hour": settings.weekly_insight_hour,
    }


@router.get("/latest")
def latest_report(
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(require_superuser),
) -> dict:
    row = db.scalars(
        select(WeeklyInsightReport)
        .where(WeeklyInsightReport.status == "done")
        .order_by(WeeklyInsightReport.started_at.desc())
        .limit(1)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Готовых отчётов пока нет")
    return report_dict(row, full=True, with_watchlist=True)


@router.get("/{report_id}")
def get_report(
    report_id: uuid.UUID,
    db: Session = Depends(get_db),
    _p: AdminPrincipal = Depends(require_superuser),
) -> dict:
    row = db.get(WeeklyInsightReport, report_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Отчёт не найден")
    return report_dict(row, full=True, with_watchlist=True)


@router.post("/run", status_code=202)
def run_report_now(
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    principal: AdminPrincipal = Depends(require_superuser),
) -> dict:
    if not settings.moysklad_configured:
        raise HTTPException(status_code=400, detail="На сервере не задан MOYSKLAD_TOKEN")
    try:
        row = create_report(db, trigger="manual", started_by=author_identity(principal)[1])
    except WeeklyInsightBusy as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    background.add_task(execute_report, settings, row.id)
    return report_dict(row)
