"""Запуск недельного отчёта: по кнопке из админки или по расписанию в понедельник утром."""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.database import SessionLocal
from app.models.staff_feedback import StaffFeedback
from app.models.weekly_insight_report import WeeklyInsightReport
from app.services.warehouse_analytics.ms_client import MoySkladAnalyticsClient
from app.services.weekly_insight.compute import Periods, build_report
from app.services.weekly_insight.fetch import load_dataset
from app.services.weekly_insight.summary import generate_summary

log = logging.getLogger("app.weekly_insight.runner")

TZ = ZoneInfo("Europe/Moscow")
STALE_AFTER = timedelta(hours=2)
SCHEDULE_MAX_ERRORS = 3
FEEDBACK_TEXTS_MAX = 40

_run_lock = threading.Lock()


class WeeklyInsightBusy(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def report_dict(row: WeeklyInsightReport, *, full: bool = False, with_watchlist: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": str(row.id),
        "week_start": row.week_start.isoformat(),
        "status": row.status,
        "trigger": row.trigger,
        "started_by": row.started_by,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "summary_model": row.summary_model,
        "ms_requests": row.ms_requests,
        "error": row.error,
        "watchlist_size": len(row.watchlist or []),
    }
    if full:
        out["summary_md"] = row.summary_md
        out["metrics"] = row.metrics
    if with_watchlist:
        out["watchlist"] = row.watchlist or []
    return out


def mark_stale(db: Session) -> None:
    stale = db.scalars(
        select(WeeklyInsightReport).where(
            WeeklyInsightReport.status == "running",
            WeeklyInsightReport.started_at < _now() - STALE_AFTER,
        )
    ).all()
    for r in stale:
        r.status = "error"
        r.error = "Прерван: сервер перезапускался или прогон завис"
        r.finished_at = _now()
    if stale:
        db.commit()


def create_report(db: Session, *, trigger: str, started_by: str | None = None) -> WeeklyInsightReport:
    mark_stale(db)
    if db.scalar(select(WeeklyInsightReport.id).where(WeeklyInsightReport.status == "running")):
        raise WeeklyInsightBusy("Отчёт уже формируется")
    today = datetime.now(TZ).date()
    row = WeeklyInsightReport(
        week_start=Periods.for_run(today).week_start,
        status="running",
        trigger=trigger,
        started_by=started_by,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _staff_feedback(db: Session, p: Periods) -> dict:
    start = datetime.combine(p.week_start, time.min, TZ)
    end = datetime.combine(p.week_end + timedelta(days=1), time.min, TZ)
    rows = db.scalars(
        select(StaffFeedback)
        .where(StaffFeedback.created_at >= start, StaffFeedback.created_at < end)
        .order_by(StaffFeedback.created_at)
    ).all()
    return {
        "messages_week": len(rows),
        "authors_week": len({r.author_label for r in rows}),
        "texts": [
            {"day": r.created_at.astimezone(TZ).date().isoformat(), "author": r.author_label, "text": r.text[:300]}
            for r in rows[:FEEDBACK_TEXTS_MAX]
        ],
    }


def _prev_watchlist_ids(db: Session, week_start) -> set[str]:
    prev = db.scalars(
        select(WeeklyInsightReport)
        .where(WeeklyInsightReport.status == "done", WeeklyInsightReport.week_start < week_start)
        .order_by(WeeklyInsightReport.week_start.desc(), WeeklyInsightReport.finished_at.desc())
        .limit(1)
    ).first()
    return {w["id"] for w in (prev.watchlist or []) if isinstance(w, dict) and w.get("id")} if prev else set()


def execute_report(settings: Settings, report_id: uuid.UUID) -> None:
    """Долгий прогон (несколько минут): выгрузка МойСклад, расчёт, текст. Своя сессия БД."""
    if not _run_lock.acquire(blocking=False):
        log.warning("weekly_insight: прогон %s пропущен — уже идёт другой", report_id)
        return
    db = SessionLocal()
    client: MoySkladAnalyticsClient | None = None
    try:
        row = db.get(WeeklyInsightReport, report_id)
        if row is None:
            return
        try:
            if not settings.moysklad_configured:
                raise RuntimeError("Не задан MOYSKLAD_TOKEN")
            today = datetime.now(TZ).date()
            p = Periods.for_run(today)
            client = MoySkladAnalyticsClient(str(settings.moysklad_token).strip())
            ds, requests_count = load_dataset(
                client,
                today=today,
                history_from=p.history_from,
                windows={"cur": (p.cur_from, p.week_end), "prev": (p.prev_from, p.cur_from - timedelta(days=1))},
                stock_dates=[p.week_end - timedelta(days=28), p.week_end - timedelta(days=364)],
            )
            metrics, watchlist = build_report(
                ds,
                today,
                prev_watchlist_ids=_prev_watchlist_ids(db, p.week_start),
                staff_feedback=_staff_feedback(db, p),
            )
            summary, model, usage = generate_summary(settings, metrics)
            metrics["summary_usage"] = usage
            row.metrics = metrics
            row.watchlist = watchlist
            row.summary_md = summary
            row.summary_model = model
            row.ms_requests = requests_count
            row.status = "done"
            log.info("weekly_insight: отчёт %s готов, запросов МойСклад %s", report_id, requests_count)
        except Exception as e:  # noqa: BLE001
            log.exception("weekly_insight: отчёт %s упал", report_id)
            db.rollback()
            row = db.get(WeeklyInsightReport, report_id)
            if row is None:
                return
            row.status = "error"
            row.error = str(e)[:2000]
        row.finished_at = _now()
        db.commit()
    finally:
        if client is not None:
            client.close()
        db.close()
        _run_lock.release()


def scheduled_due(db: Session, settings: Settings, now: datetime | None = None) -> bool:
    """Пора ли запускать: с понедельника WEEKLY_INSIGHT_HOUR и до конца недели, если отчёта ещё нет."""
    if not (settings.weekly_insight_enabled and settings.moysklad_configured):
        return False
    now = (now or datetime.now(TZ)).astimezone(TZ)
    if now.weekday() == 0 and now.hour < settings.weekly_insight_hour:
        return False
    week_start = Periods.for_run(now.date()).week_start
    rows = db.scalars(select(WeeklyInsightReport).where(WeeklyInsightReport.week_start == week_start)).all()
    if any(r.status in ("done", "running") for r in rows):
        return False
    return sum(1 for r in rows if r.trigger == "schedule" and r.status == "error") < SCHEDULE_MAX_ERRORS


def run_scheduled_if_due(settings: Settings) -> None:
    db = SessionLocal()
    try:
        mark_stale(db)
        if not scheduled_due(db, settings):
            return
        row = create_report(db, trigger="schedule")
        report_id = row.id
    except WeeklyInsightBusy:
        return
    finally:
        db.close()
    execute_report(settings, report_id)
