"""Действующие клиенты А: сравнение понедельничных срезов.

«Действующие» — категория А не на контроле (в ритме или одна покупка).
Новый и выбывший считаются относительно прошлого среза. Динамика в процентах —
последние 12 месяцев к предыдущим 12 у самого клиента.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.weekly_insight_report import WeeklyInsightReport

FLAT_BAND = 5.0


def _trend(cur: float | None, prev: float | None) -> float | None:
    if not prev:
        return None
    return round(((cur or 0) / prev - 1) * 100, 1)


def _pace(pct: float | None) -> str:
    if pct is None:
        return "нет базы"
    if pct > FLAT_BAND:
        return "растёт"
    if pct < -FLAT_BAND:
        return "падает"
    return "ровно"


def compare_active(
    current: list | None,
    previous: list | None,
    watchlist: list | None,
) -> dict:
    """Собрать таблицу и сводку. previous=None — первой недели сравнения ещё нет."""
    prev_rows = [row for row in (previous or []) if isinstance(row, dict) and row.get("id")]
    prev_by = {row["id"]: row for row in prev_rows}
    watch_by = {
        row["id"]: row
        for row in (watchlist or [])
        if isinstance(row, dict) and row.get("id")
    }
    items = []
    cur_ids: set[str] = set()
    for raw in current or []:
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        cur_ids.add(raw["id"])
        old = prev_by.get(raw["id"])
        trend = _trend(raw.get("rev_cur12"), raw.get("rev_prev12"))
        if previous is None:
            cohort = None
        elif old is None:
            cohort = "новый"
        else:
            cohort = "был"
        items.append(
            {
                **raw,
                "cohort": cohort,
                "trend_pct": trend,
                "pace": _pace(trend),
                "week_pct": _trend(raw.get("rev_cur12"), old.get("rev_cur12")) if old else None,
            }
        )
    left = []
    if previous is not None:
        for cid, old in prev_by.items():
            if cid in cur_ids:
                continue
            watch = watch_by.get(cid)
            left.append(
                {
                    "id": cid,
                    "name": old.get("name"),
                    "phone": old.get("phone"),
                    "rev_cur12": old.get("rev_cur12"),
                    "rev_prev12": old.get("rev_prev12"),
                    "where": watch.get("status") if watch else "вышел из категории А",
                }
            )
    total_prev = sum(row.get("rev_prev12") or 0 for row in items)
    total_cur = sum(row.get("rev_cur12") or 0 for row in items)
    gaps = [row["median_gap"] for row in items if row.get("median_gap")]
    checks = [row["avg_check"] for row in items if row.get("avg_check")]
    return {
        "summary": {
            "clients": len(items),
            "new": sum(1 for row in items if row["cohort"] == "новый"),
            "stayed": sum(1 for row in items if row["cohort"] == "был"),
            "left": len(left),
            "growing": sum(1 for row in items if row["pace"] == "растёт"),
            "falling": sum(1 for row in items if row["pace"] == "падает"),
            "flat": sum(1 for row in items if row["pace"] == "ровно"),
            "no_base": sum(1 for row in items if row["pace"] == "нет базы"),
            "rev_prev12": round(total_prev),
            "rev_cur12": round(total_cur),
            "trend_pct": _trend(total_cur, total_prev),
            "avg_check": round(sum(checks) / len(checks)) if checks else None,
            "avg_gap": round(sum(gaps) / len(gaps), 1) if gaps else None,
            "has_previous": previous is not None,
        },
        "items": items,
        "left": left,
    }


def load_active_board(db: Session) -> dict:
    """Последний готовый срез и предыдущая неделя. Пусто, пока колонка ещё не заполнялась."""
    rows = list(
        db.scalars(
            select(WeeklyInsightReport)
            .where(
                WeeklyInsightReport.status == "done",
                WeeklyInsightReport.active_clients.is_not(None),
            )
            .order_by(WeeklyInsightReport.week_start.desc(), WeeklyInsightReport.finished_at.desc())
        ).all()
    )
    by_week: dict = {}
    for row in rows:
        by_week.setdefault(row.week_start, row)
    weeks = sorted(by_week, reverse=True)
    if not weeks:
        return {
            "ready": False,
            "week_start": None,
            "prev_week_start": None,
            "summary": None,
            "items": [],
            "left": [],
        }
    current = by_week[weeks[0]]
    prev = by_week[weeks[1]] if len(weeks) > 1 else None
    board = compare_active(
        current.active_clients,
        prev.active_clients if prev is not None else None,
        current.watchlist,
    )
    board["ready"] = True
    board["week_start"] = current.week_start.isoformat()
    board["prev_week_start"] = prev.week_start.isoformat() if prev is not None else None
    return board
